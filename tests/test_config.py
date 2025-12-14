# tests/test_config.py
"""
Tests for configuration management.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile


class TestConfiguration:
    """Test suite for configuration management."""
    
    def test_default_config_structure(self):
        """Test default configuration has all required keys."""
        from crashsense.config import DEFAULT_CONFIG
        
        assert 'provider' in DEFAULT_CONFIG
        assert 'kubernetes' in DEFAULT_CONFIG
        assert 'prometheus' in DEFAULT_CONFIG
        assert 'memory' in DEFAULT_CONFIG
        assert 'rag' in DEFAULT_CONFIG
        
        # Check kubernetes config
        k8s_cfg = DEFAULT_CONFIG['kubernetes']
        assert 'enabled' in k8s_cfg
        assert 'kubeconfig' in k8s_cfg
        assert 'namespaces' in k8s_cfg
        assert 'auto_heal' in k8s_cfg
        assert 'dry_run' in k8s_cfg
        
        # Check prometheus config
        prom_cfg = DEFAULT_CONFIG['prometheus']
        assert 'enabled' in prom_cfg
        assert 'url' in prom_cfg
        assert 'alertmanager_url' in prom_cfg
    
    @patch('crashsense.config.CONFIG_PATH')
    def test_load_config_creates_default(self, mock_config_path):
        """Test loading config creates default if not exists."""
        from crashsense.config import load_config
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            temp_path.unlink()  # Remove it to test creation
            mock_config_path.return_value = temp_path
            mock_config_path.parent.mkdir = Mock()
            mock_config_path.exists.return_value = False
            
            config = load_config()
            
            assert config is not None
            assert 'provider' in config
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        from crashsense.config import save_config, load_config
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('crashsense.config.CONFIG_PATH', Path(tmpdir) / 'config.toml'):
                test_config = {
                    'provider': 'openai',
                    'kubernetes': {'enabled': True}
                }
                
                save_config(test_config)
                loaded = load_config()
                
                assert loaded['provider'] == 'openai'


class TestMemoryStore:
    """Test suite for memory storage."""
    
    def test_memory_store_creation(self):
        """Test memory store database creation."""
        from crashsense.core.memory import MemoryStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            store = MemoryStore(str(db_path))
            
            assert db_path.exists()
    
    def test_memory_upsert(self):
        """Test upserting memories."""
        from crashsense.core.memory import MemoryStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            store = MemoryStore(str(db_path))
            
            store.upsert("test problem", "test summary", "test solution")
            
            memories = store.list(10)
            assert len(memories) == 1
            assert memories[0].summary == "test summary"
    
    def test_memory_frequency_tracking(self):
        """Test frequency tracking for repeated issues."""
        from crashsense.core.memory import MemoryStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            store = MemoryStore(str(db_path))
            
            # Insert same problem twice
            store.upsert("same problem", "summary 1", "solution 1")
            store.upsert("same problem", "summary 2", "solution 2")
            
            memories = store.list(10)
            assert len(memories) == 1
            assert memories[0].frequency == 2
    
    def test_memory_pruning(self):
        """Test memory pruning."""
        from crashsense.core.memory import MemoryStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            store = MemoryStore(str(db_path))
            
            # Add many entries
            for i in range(20):
                store.upsert(f"problem {i}", f"summary {i}", f"solution {i}")
            
            # Prune to max 10
            store.prune(max_entries=10, retention_days=365)
            
            memories = store.list(100)
            assert len(memories) <= 10
