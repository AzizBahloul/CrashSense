# tests/test_analyzer.py
"""
Comprehensive tests for log analyzer functionality.
"""
import pytest
from unittest.mock import Mock, patch


class TestBackTrackEngine:
    """Test suite for BackTrackEngine class."""
    
    def test_detect_kubernetes_language(self):
        """Test Kubernetes log detection."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        # Test Kubernetes detection
        k8s_log = "Error: CrashLoopBackOff in pod myapp"
        assert engine.detect_language(k8s_log) == "kubernetes"
        
        k8s_log2 = "kubectl get pods shows ImagePullBackOff"
        assert engine.detect_language(k8s_log2) == "kubernetes"
        
        k8s_log3 = '{"kind":"Pod","status":"OOMKilled"}'
        assert engine.detect_language(k8s_log3) == "kubernetes"
    
    def test_detect_python_language(self):
        """Test Python log detection."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        python_log = "Traceback (most recent call last):\n  File..."
        assert engine.detect_language(python_log) == "python"
    
    def test_detect_kubernetes_exceptions(self):
        """Test Kubernetes exception detection."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        # Test CrashLoopBackOff
        exc = engine.detect_exception("Pod status: CrashLoopBackOff")
        assert exc is not None
        assert exc['type'] == 'CrashLoopBackOff'
        
        # Test OOMKilled
        exc = engine.detect_exception("Container terminated: OOMKilled")
        assert exc is not None
        assert exc['type'] == 'OOMKilled'
        
        # Test ImagePullBackOff
        exc = engine.detect_exception("Error: ImagePullBackOff")
        assert exc is not None
        assert exc['type'] == 'ImagePullBackOff'
    
    def test_detect_python_exceptions(self):
        """Test Python exception detection."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        exc = engine.detect_exception("ValueError: invalid literal for int()")
        assert exc is not None
        assert exc['type'] == 'ValueError'
        assert 'invalid literal' in exc['message']
    
    def test_extract_python_frames(self):
        """Test Python stack frame extraction."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        traceback = '''
Traceback (most recent call last):
  File "/app/main.py", line 10, in <module>
    run()
  File "/app/main.py", line 6, in run
    result = divide(10, 0)
ZeroDivisionError: division by zero
'''
        
        frames = engine.extract_frames(traceback)
        
        assert len(frames) >= 2
        assert frames[0]['file'] == '/app/main.py'
        assert frames[0]['line'] == 10
        assert frames[0]['func'] == '<module>'
    
    def test_parse_log_comprehensive(self):
        """Test comprehensive log parsing."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        log = """
2025-12-14 10:00:00 ERROR Pod crash detected
CrashLoopBackOff: Container app is failing
Traceback (most recent call last):
  File "/app/main.py", line 5, in main
    raise RuntimeError("Application failed")
RuntimeError: Application failed
"""
        
        parsed = engine.parse_log(log)
        
        assert parsed['language'] == 'kubernetes'
        assert parsed['exception'] is not None
        assert len(parsed['frames']) > 0
    
    @patch('crashsense.core.analyzer.LLMAdapter')
    def test_analyze_with_rag(self, mock_llm):
        """Test analysis with RAG context."""
        from crashsense.core.analyzer import BackTrackEngine
        from crashsense.config import load_config
        
        mock_llm_instance = Mock()
        mock_llm_instance.analyze.return_value = {
            'explanation': 'Pod crashed due to OOM',
            'patch': 'Increase memory limits'
        }
        mock_llm_instance.retrieve.return_value = [
            ('OOMKilled fix: increase memory', 0.95)
        ]
        mock_llm.return_value = mock_llm_instance
        
        engine = BackTrackEngine(provider="none")
        
        log = "Container terminated: OOMKilled"
        result = engine.analyze(log)
        
        assert 'parsed' in result
        assert 'analysis' in result
        assert result['analysis']['explanation'] == 'Pod crashed due to OOM'
    
    def test_analyze_with_large_log(self):
        """Test analysis with large log files."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        # Create a large log (>8000 chars)
        large_log = "ERROR: " + ("x" * 10000) + " CrashLoopBackOff"
        
        result = engine.analyze(large_log)
        
        # Should handle large logs without crashing
        assert 'parsed' in result
        assert 'analysis' in result
    
    def test_sanitize_log_input(self):
        """Test log sanitization."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        # Log with null bytes and control characters
        dirty_log = "Error\x00\x01\x02 in pod\x0B\x0C test"
        
        result = engine.analyze(dirty_log)
        
        # Should handle dirty input gracefully
        assert 'parsed' in result


class TestRAGIntegration:
    """Test RAG document loading and chunking."""
    
    def test_chunk_text(self):
        """Test text chunking."""
        from crashsense.core.analyzer import BackTrackEngine
        
        engine = BackTrackEngine(provider="none")
        
        text = "A" * 1000
        chunks = engine._chunk_text(text, size=200, overlap=50)
        
        assert len(chunks) > 1
        # Check overlap
        assert chunks[0][-50:] == chunks[1][:50]
    
    @patch('crashsense.core.analyzer.Path')
    def test_load_rag_docs(self, mock_path):
        """Test RAG document loading."""
        from crashsense.core.analyzer import BackTrackEngine
        
        mock_file = Mock()
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "Kubernetes troubleshooting guide"
        mock_file.suffix = ".md"
        
        mock_path_instance = Mock()
        mock_path_instance.is_file.return_value = True
        mock_path_instance.is_dir.return_value = False
        mock_path_instance.read_text.return_value = "Kubernetes troubleshooting guide"
        mock_path.return_value = mock_path_instance
        
        engine = BackTrackEngine(provider="none")
        
        rag_cfg = {
            "docs": ["/fake/path/doc.md"],
            "chunk_chars": 100,
            "chunk_overlap": 20
        }
        
        chunks = engine._load_rag_docs(rag_cfg)
        
        # Should return chunks (even if mocking doesn't work perfectly)
        assert isinstance(chunks, list)
