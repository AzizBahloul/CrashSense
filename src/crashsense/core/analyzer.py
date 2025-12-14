# src/crashsense/core/analyzer.py
from typing import Dict, Optional, List
import re
from .llm_adapter import LLMAdapter
from ..config import load_config
from pathlib import Path


class BackTrackEngine:
    def __init__(self, provider="auto", local_model: Optional[str] = None):
        chosen = provider
        if provider == "auto":
            # Prefer OpenAI if key present; else Ollama if reachable; else none
            import os
            from ..utils import is_executable_on_path

            if os.environ.get("CRASHSENSE_OPENAI_KEY"):
                chosen = "openai"
            elif is_executable_on_path("ollama"):
                chosen = "ollama"
            else:
                chosen = "none"
        self.llm = LLMAdapter(provider=chosen, local_model=local_model)

    def parse_log(self, text: str) -> Dict:
        language = self.detect_language(text)
        exception = self.detect_exception(text)
        frames = self.extract_frames(text)
        return {"language": language, "exception": exception, "frames": frames}

    def detect_language(self, text: str) -> str:
        # Kubernetes
        if "CrashLoopBackOff" in text or "ImagePullBackOff" in text or "OOMKilled" in text:
            return "kubernetes"
        if "kubectl" in text or "kube-apiserver" in text or "kubelet" in text:
            return "kubernetes"
        if '"kind":"Pod"' in text or '"kind":"Deployment"' in text:
            return "kubernetes"
        # Python
        if "Traceback (most recent call last)" in text:
            return "python"
        if "Exception in thread" in text or ".java:" in text:
            return "java"
        # Apache
        if "[error] [client" in text or "mod_wsgi" in text or "apache2" in text:
            return "apache"
        # Nginx
        if "nginx" in text or ("[error]" in text and "nginx" in text):
            return "nginx"
        # System
        if "/var/log/" in text or "kernel:" in text or "systemd" in text:
            return "system"
        return "unknown"

    def detect_exception(self, text: str):
        # Kubernetes-specific errors
        k8s_patterns = [
            r"(CrashLoopBackOff|ImagePullBackOff|ErrImagePull|OOMKilled|Evicted|CreateContainerError|InvalidImageName)",
            r"(PodInitializing|ContainerCreating|Pending|Failed|Unknown)",
            r"failed to pull image \"([^\"]+)\"",
            r"back-off \d+ restarting failed container",
        ]
        
        for pattern in k8s_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return {"type": m.group(1) if m.lastindex >= 1 else "KubernetesError", "message": m.group(0) or ""}
        
        # Python exceptions
        m = re.search(
            r"([A-Za-z_][A-Za-z0-9_.]+(?:Exception|Error))(?::\s*(.*))?", text
        )
        if m:
            return {"type": m.group(1), "message": m.group(2) or ""}
        return None

    def extract_frames(self, text: str):
        frames = []
        
        # Python stack traces
        for m in re.finditer(
            r'  File "([^"]+)", line (\d+), in ([^\n]+)\n\s+(.*)', text
        ):
            frames.append(
                {
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "func": m.group(3),
                    "code": m.group(4),
                }
            )
        
        # Kubernetes events
        k8s_event_pattern = r"(?:Event|Warning|Error).*?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).*?(Pod|Container|Node|Service).*?([A-Za-z]+)\s+(.*?)(?:\n|$)"
        for m in re.finditer(k8s_event_pattern, text):
            frames.append({
                "timestamp": m.group(1),
                "resource_type": m.group(2),
                "reason": m.group(3),
                "message": m.group(4),
                "type": "kubernetes_event"
            })
        
        return frames

    def analyze(self, text: str) -> Dict:
        # Input validation and preview capping for very large logs
        if not isinstance(text, str):
            text = str(text)
        # Drop NULs/control chars
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
        parsed = self.parse_log(text)
        import os

        try:
            max_chars = int(os.environ.get("CRASHSENSE_PREVIEW_CHARS", "4000"))
        except ValueError:
            max_chars = 4000
        # Keep both head and tail for context if file is huge
        if len(text) > max_chars * 2:
            head = text[:max_chars]
            tail = text[-max_chars:]
            preview = head + "\n... <snip middle> ...\n" + tail
        else:
            preview = text[:max_chars]
        # Optional RAG context
        cfg = load_config()
        rag_ctx = ""
        if cfg.get("rag", {}).get("enabled"):
            docs = self._load_rag_docs(cfg.get("rag", {}))
            if docs:
                top_k = int(cfg["rag"].get("top_k", 3))
                retrieved = self.llm.retrieve(preview, docs, top_k=top_k)
                if retrieved:
                    parts = []
                    for i, (chunk, score) in enumerate(retrieved, 1):
                        parts.append(f"[ctx#{i} score={score:.3f}]\n{chunk}")
                    rag_ctx = "\n\nContext:\n" + "\n\n".join(parts)

        prompt = (
            f"Crash log:\n{preview}\n\n"
            f"Parsed info: {parsed}{rag_ctx}\n\n"
            "Using any provided Context, explain root cause and suggest a concrete code patch or remediation. Keep answers actionable and short. "
            "If you can provide shell commands that could help automatically apply fixes, list them in a 'commands:' section."
        )
        llm_ans = self.llm.analyze(prompt)
        # Add log type to parsed
        parsed['log_type'] = self.detect_language(text)
        return {"parsed": parsed, "analysis": llm_ans}

    # --- RAG helpers -----------------------------------------------------
    def _chunk_text(self, text: str, size: int, overlap: int) -> List[str]:
        if size <= 0:
            return [text]
        chunks = []
        start = 0
        n = len(text)
        while start < n:
            end = min(n, start + size)
            chunks.append(text[start:end])
            if end == n:
                break
            start = max(end - overlap, start + 1)
        return chunks

    def _load_rag_docs(self, rag_cfg: dict) -> List[str]:
        paths = rag_cfg.get("docs") or []
        size = int(rag_cfg.get("chunk_chars", 800))
        overlap = int(rag_cfg.get("chunk_overlap", 120))
        chunks: List[str] = []
        exts = {".md", ".txt", ".log", ".py", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".conf", ".cfg", ".csv"}
        for p in paths:
            try:
                path = Path(p)
                if path.is_file():
                    txt = path.read_text(encoding="utf-8", errors="ignore")
                    chunks.extend(self._chunk_text(txt, size, overlap))
                elif path.is_dir():
                    # Recursive scan for common text-like formats
                    for child in path.rglob("*"):
                        if not child.is_file():
                            continue
                        if child.suffix.lower() not in exts:
                            continue
                        try:
                            txt = child.read_text(encoding="utf-8", errors="ignore")
                            chunks.extend(self._chunk_text(txt, size, overlap))
                            if len(chunks) >= 200:
                                break
                        except Exception:
                            continue
            except Exception:
                continue
        # Cap total chunks to a reasonable number to avoid prompt bloat
        return chunks[:200]
