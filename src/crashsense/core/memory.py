# src/crashsense/core/memory.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta
import hashlib
import os

Base = declarative_base()


class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True)
    problem_hash = Column(String(64), index=True, unique=True)
    summary = Column(Text)
    solution = Column(Text)
    frequency = Column(Integer, default=1)
    last_accessed = Column(DateTime, default=datetime.utcnow)


class MemoryStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def upsert(self, problem_text: str, summary: str, solution: str):
        h = self._hash(problem_text)
        s = self.Session()
        try:
            mem = s.query(Memory).filter_by(problem_hash=h).one_or_none()
            if mem:
                mem.frequency += 1
                mem.last_accessed = datetime.utcnow()
                mem.summary = summary
                mem.solution = solution
            else:
                mem = Memory(
                    problem_hash=h,
                    summary=summary,
                    solution=solution,
                    last_accessed=datetime.utcnow(),
                )
                s.add(mem)
            s.commit()
        finally:
            s.close()

    def query_similar(self, problem_text: str, limit=5):
        s = self.Session()
        try:
            q = s.query(Memory).order_by(Memory.last_accessed.desc()).limit(limit)
            return q.all()
        finally:
            s.close()

    def list(self, limit=50):
        s = self.Session()
        try:
            return (
                s.query(Memory).order_by(Memory.last_accessed.desc()).limit(limit).all()
            )
        finally:
            s.close()

    def prune(self, max_entries=1000, retention_days=365):
        s = self.Session()
        try:
            total = s.query(func.count(Memory.id)).scalar()
            if total <= max_entries:
                return
            cutoff = datetime.utcnow() - timedelta(days=retention_days)
            s.query(Memory).filter(Memory.last_accessed < cutoff).delete()
            total = s.query(func.count(Memory.id)).scalar()
            if total > max_entries:
                to_delete = total - max_entries
                oldest = (
                    s.query(Memory)
                    .order_by(Memory.last_accessed)
                    .limit(to_delete)
                    .all()
                )
                for o in oldest:
                    s.delete(o)
            s.commit()
        finally:
            s.close()
