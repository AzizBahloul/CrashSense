"""
Basic integration tests for CrashSense.
"""
import pytest
from pathlib import Path


def test_crashsense_imports():
    """Test that all main modules can be imported."""
    from crashsense import __version__
    from crashsense.config import load_config, save_config
    from crashsense.core.analyzer import BackTrackEngine
    from crashsense.core.memory import MemoryStore
    from crashsense.core.llm_adapter import LLMAdapter
    
    assert __version__ == "2.0.0"


def test_kubernetes_imports():
    """Test that Kubernetes modules can be imported."""
    try:
        from crashsense.core.k8s_monitor import KubernetesMonitor
        from crashsense.core.remediation import RemediationEngine
        from crashsense.core.prometheus_collector import PrometheusCollector
        assert True
    except ImportError as e:
        pytest.skip(f"Kubernetes dependencies not installed: {e}")


def test_cli_imports():
    """Test that CLI module can be imported."""
    from crashsense.cli import main
    assert main is not None


def test_config_structure():
    """Test configuration structure."""
    from crashsense.config import DEFAULT_CONFIG
    
    required_keys = ['provider', 'local', 'memory', 'kubernetes', 'prometheus', 'rag']
    for key in required_keys:
        assert key in DEFAULT_CONFIG, f"Missing config key: {key}"


def test_analyzer_basic_functionality():
    """Test basic analyzer functionality."""
    from crashsense.core.analyzer import BackTrackEngine
    
    engine = BackTrackEngine(provider="none")
    
    # Test language detection
    assert engine.detect_language("Traceback (most recent call last)") == "python"
    assert engine.detect_language("CrashLoopBackOff") == "kubernetes"
    
    # Test exception detection
    exc = engine.detect_exception("ValueError: test error")
    assert exc is not None
    assert exc['type'] == 'ValueError'


def test_memory_store_basic():
    """Test basic memory store functionality."""
    from crashsense.core.memory import MemoryStore
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        store = MemoryStore(str(db_path))
        
        # Test upsert
        store.upsert("test problem", "test summary", "test solution")
        
        # Test list
        memories = store.list(10)
        assert len(memories) == 1
        assert memories[0].summary == "test summary"


def test_llm_adapter_initialization():
    """Test LLM adapter can be initialized."""
    from crashsense.core.llm_adapter import LLMAdapter
    
    adapter = LLMAdapter(provider="none")
    assert adapter.provider == "none"


def test_utils_functions():
    """Test utility functions."""
    from crashsense.utils import safe_filename, short_print
    
    assert safe_filename("test-file.log") == "test-file.log"
    assert safe_filename("bad/file\\name") == "badfilename"
    
    assert short_print("short", max_len=100) == "short"
    assert len(short_print("x" * 500, max_len=200)) <= 201  # 200 + ellipsis
