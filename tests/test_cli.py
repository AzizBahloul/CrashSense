# tests/test_cli.py
"""
Tests for CLI commands.
"""
import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch


class TestCLICommands:
    """Test suite for CLI functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()
    
    def test_main_help(self):
        """Test main command help."""
        from crashsense.cli import main
        
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'CrashSense' in result.output
    
    @patch('crashsense.cli.load_config')
    def test_init_command(self, mock_load_config):
        """Test init command."""
        from crashsense.cli import init
        
        mock_load_config.return_value = {'provider': 'auto'}
        
        result = self.runner.invoke(init, input='none\n')
        assert result.exit_code == 0
    
    @patch('crashsense.cli.load_config')
    @patch('crashsense.core.k8s_monitor.KubernetesMonitor')
    def test_k8s_status_command(self, mock_monitor, mock_load_config):
        """Test k8s status command."""
        from crashsense.cli import main
        
        mock_load_config.return_value = {
            'kubernetes': {'kubeconfig': None, 'namespaces': []},
            'provider': 'none'
        }
        
        mock_monitor_instance = Mock()
        mock_monitor_instance.get_cluster_info.return_value = {
            'version': '1.28',
            'node_count': 1,
            'nodes': []
        }
        mock_monitor_instance.health_check.return_value = {
            'healthy': True,
            'summary': {'pod_crashes': 0, 'resource_exhaustion': 0, 'network_issues': 0},
            'issues': []
        }
        mock_monitor.return_value = mock_monitor_instance
        
        result = self.runner.invoke(main, ['k8s', 'status'])
        assert result.exit_code == 0
    
    @patch('crashsense.cli.load_config')
    @patch('crashsense.core.k8s_monitor.KubernetesMonitor')
    @patch('crashsense.core.remediation.RemediationEngine')
    def test_k8s_heal_command(self, mock_engine, mock_monitor, mock_load_config):
        """Test k8s heal command."""
        from crashsense.cli import main
        
        mock_load_config.return_value = {
            'kubernetes': {
                'kubeconfig': None,
                'namespaces': [],
                'dry_run': True,
                'max_remediation_actions': 10
            },
            'provider': 'none'
        }
        
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_pod_crashes.return_value = []
        mock_monitor_instance.detect_resource_exhaustion.return_value = []
        mock_monitor_instance.detect_network_failures.return_value = []
        mock_monitor.return_value = mock_monitor_instance
        
        result = self.runner.invoke(main, ['k8s', 'heal'])
        assert result.exit_code == 0
        assert 'healthy' in result.output.lower() or 'no issues' in result.output.lower()
    
    @patch('crashsense.cli.load_config')
    def test_rag_add_command(self, mock_load_config):
        """Test RAG add command."""
        from crashsense.cli import main
        import tempfile
        
        mock_load_config.return_value = {'rag': {'docs': []}}
        
        with tempfile.NamedTemporaryFile(suffix='.md') as f:
            result = self.runner.invoke(main, ['rag', 'add', f.name])
            assert result.exit_code == 0
    
    @patch('crashsense.cli.load_config')
    def test_rag_clear_command(self, mock_load_config):
        """Test RAG clear command."""
        from crashsense.cli import main
        
        mock_load_config.return_value = {'rag': {'docs': ['/some/path']}}
        
        result = self.runner.invoke(main, ['rag', 'clear'])
        assert result.exit_code == 0
    
    @patch('crashsense.cli.load_config')
    @patch('crashsense.cli.MemoryStore')
    def test_memory_command(self, mock_memory, mock_load_config):
        """Test memory list command."""
        from crashsense.cli import main
        
        mock_load_config.return_value = {'memory': {'path': '/tmp/test.db'}}
        
        mock_store = Mock()
        mock_store.list.return_value = []
        mock_memory.return_value = mock_store
        
        result = self.runner.invoke(main, ['memory'])
        assert result.exit_code == 0


class TestCLIIntegration:
    """Integration tests for CLI."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()
    
    @patch('crashsense.cli.BackTrackEngine')
    @patch('crashsense.cli.MemoryStore')
    @patch('crashsense.cli.load_config')
    @patch('crashsense.cli.read_file')
    def test_analyze_command_with_file(self, mock_read, mock_config, mock_memory, mock_engine):
        """Test analyze command with log file."""
        from crashsense.cli import main
        import tempfile
        
        mock_config.return_value = {
            'provider': 'none',
            'local': {'model': 'test'},
            'last': {'last_log': '/tmp/last.log'},
            'memory': {'path': '/tmp/mem.db'}
        }
        
        mock_read.return_value = "Test log content"
        
        mock_engine_instance = Mock()
        mock_engine_instance.analyze.return_value = {
            'parsed': {'language': 'python', 'exception': None, 'frames': [], 'log_type': 'python'},
            'analysis': {'explanation': 'Test explanation', 'patch': 'Test patch'}
        }
        mock_engine.return_value = mock_engine_instance
        
        mock_store = Mock()
        mock_memory.return_value = mock_store
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log') as f:
            f.write("Test log")
            f.flush()
            
            result = self.runner.invoke(main, ['analyze', f.name])
            assert result.exit_code == 0
            assert 'Analysis' in result.output or 'explanation' in result.output.lower()
