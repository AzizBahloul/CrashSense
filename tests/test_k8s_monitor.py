# tests/test_k8s_monitor.py
"""
Comprehensive tests for Kubernetes monitoring functionality.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestKubernetesMonitor:
    """Test suite for KubernetesMonitor class."""
    
    @patch('crashsense.core.k8s_monitor.config')
    @patch('crashsense.core.k8s_monitor.client')
    def test_initialization(self, mock_client, mock_config):
        """Test KubernetesMonitor initialization."""
        from crashsense.core.k8s_monitor import KubernetesMonitor
        
        mock_config.load_kube_config = Mock()
        mock_client.CoreV1Api = Mock()
        mock_client.AppsV1Api = Mock()
        
        monitor = KubernetesMonitor(namespaces=['default', 'production'])
        
        assert monitor.namespaces == ['default', 'production']
        assert monitor.v1 is not None
        assert monitor.apps_v1 is not None
        mock_config.load_kube_config.assert_called_once()
    
    @patch('crashsense.core.k8s_monitor.config')
    @patch('crashsense.core.k8s_monitor.client')
    def test_get_cluster_info(self, mock_client, mock_config):
        """Test cluster information retrieval."""
        from crashsense.core.k8s_monitor import KubernetesMonitor
        
        # Mock version info
        mock_version = Mock()
        mock_version.major = "1"
        mock_version.minor = "28"
        mock_client.VersionApi.return_value.get_code.return_value = mock_version
        
        # Mock nodes
        mock_node = Mock()
        mock_node.metadata.name = "node-1"
        mock_node.status.conditions = [Mock(type="Ready", status="True")]
        mock_node.status.capacity = {"cpu": "4", "memory": "16Gi"}
        
        mock_v1 = Mock()
        mock_v1.list_node.return_value.items = [mock_node]
        
        mock_config.load_kube_config = Mock()
        mock_client.CoreV1Api.return_value = mock_v1
        
        monitor = KubernetesMonitor()
        cluster_info = monitor.get_cluster_info()
        
        assert cluster_info['version'] == "1.28"
        assert cluster_info['node_count'] == 1
        assert len(cluster_info['nodes']) == 1
        assert cluster_info['nodes'][0]['name'] == "node-1"
    
    @patch('crashsense.core.k8s_monitor.config')
    @patch('crashsense.core.k8s_monitor.client')
    def test_detect_crashloop_backoff(self, mock_client, mock_config):
        """Test detection of CrashLoopBackOff pods."""
        from crashsense.core.k8s_monitor import KubernetesMonitor
        
        # Create mock pod with CrashLoopBackOff
        mock_container_status = Mock()
        mock_container_status.name = "app"
        mock_container_status.ready = False
        mock_container_status.restart_count = 10
        mock_container_status.state.waiting = Mock(reason="CrashLoopBackOff", message="Back-off restarting")
        mock_container_status.state.terminated = None
        
        mock_pod = Mock()
        mock_pod.metadata.name = "crashy-pod"
        mock_pod.metadata.creation_timestamp = datetime.now()
        mock_pod.metadata.labels = {"app": "myapp"}
        mock_pod.status.phase = "Running"
        mock_pod.status.container_statuses = [mock_container_status]
        mock_pod.status.conditions = []
        mock_pod.spec.node_name = "node-1"
        
        # Mock namespace list
        mock_ns = Mock()
        mock_ns.metadata.name = "default"
        
        mock_v1 = Mock()
        mock_v1.list_namespace.return_value.items = [mock_ns]
        mock_v1.list_namespaced_pod.return_value.items = [mock_pod]
        
        mock_config.load_kube_config = Mock()
        mock_client.CoreV1Api.return_value = mock_v1
        
        monitor = KubernetesMonitor()
        crashes = monitor.detect_pod_crashes()
        
        assert len(crashes) == 1
        assert crashes[0]['name'] == 'crashy-pod'
        assert crashes[0]['needs_remediation'] is True
        assert any('CrashLoopBackOff' in issue for issue in crashes[0]['issues'])
    
    @patch('crashsense.core.k8s_monitor.config')
    @patch('crashsense.core.k8s_monitor.client')
    def test_detect_oomkilled(self, mock_client, mock_config):
        """Test detection of OOMKilled containers."""
        from crashsense.core.k8s_monitor import KubernetesMonitor
        
        # Create mock pod with OOMKilled container
        mock_container_status = Mock()
        mock_container_status.name = "app"
        mock_container_status.ready = False
        mock_container_status.restart_count = 5
        mock_container_status.state.waiting = None
        mock_container_status.state.terminated = Mock(reason="OOMKilled", exit_code=137)
        
        mock_pod = Mock()
        mock_pod.metadata.name = "oom-pod"
        mock_pod.metadata.creation_timestamp = datetime.now()
        mock_pod.metadata.labels = {"app": "memory-hog"}
        mock_pod.status.phase = "Running"
        mock_pod.status.container_statuses = [mock_container_status]
        mock_pod.status.conditions = []
        mock_pod.spec.node_name = "node-1"
        
        mock_ns = Mock()
        mock_ns.metadata.name = "default"
        
        mock_v1 = Mock()
        mock_v1.list_namespace.return_value.items = [mock_ns]
        mock_v1.list_namespaced_pod.return_value.items = [mock_pod]
        
        mock_config.load_kube_config = Mock()
        mock_client.CoreV1Api.return_value = mock_v1
        
        monitor = KubernetesMonitor()
        crashes = monitor.detect_pod_crashes()
        
        assert len(crashes) == 1
        assert crashes[0]['name'] == 'oom-pod'
        assert any('OOMKilled' in issue for issue in crashes[0]['issues'])
    
    @patch('crashsense.core.k8s_monitor.config')
    @patch('crashsense.core.k8s_monitor.client')
    def test_parse_resource_string(self, mock_client, mock_config):
        """Test resource string parsing."""
        from crashsense.core.k8s_monitor import KubernetesMonitor
        
        mock_config.load_kube_config = Mock()
        mock_client.CoreV1Api = Mock()
        
        monitor = KubernetesMonitor()
        
        # Test memory parsing
        assert monitor._parse_resource("100Mi") == 100 * 1024 * 1024
        assert monitor._parse_resource("1Gi") == 1 * 1024 * 1024 * 1024
        assert monitor._parse_resource("512Ki") == 512 * 1024
        
        # Test CPU parsing
        assert monitor._parse_resource("100m") == 100
        
        # Test plain numbers
        assert monitor._parse_resource("1024") == 1024
    
    @patch('crashsense.core.k8s_monitor.config')
    @patch('crashsense.core.k8s_monitor.client')
    def test_detect_network_failures(self, mock_client, mock_config):
        """Test network failure detection."""
        from crashsense.core.k8s_monitor import KubernetesMonitor
        
        # Mock service with no endpoints
        mock_service = Mock()
        mock_service.metadata.name = "my-service"
        
        mock_endpoints = Mock()
        mock_endpoints.subsets = []  # No endpoints
        
        mock_ns = Mock()
        mock_ns.metadata.name = "default"
        
        mock_v1 = Mock()
        mock_v1.list_namespace.return_value.items = [mock_ns]
        mock_v1.list_namespaced_service.return_value.items = [mock_service]
        mock_v1.read_namespaced_endpoints.return_value = mock_endpoints
        
        mock_config.load_kube_config = Mock()
        mock_client.CoreV1Api.return_value = mock_v1
        
        monitor = KubernetesMonitor()
        network_issues = monitor.detect_network_failures()
        
        assert len(network_issues) == 1
        assert network_issues[0]['service'] == 'my-service'
        assert network_issues[0]['type'] == 'service_no_endpoints'
    
    @patch('crashsense.core.k8s_monitor.config')
    @patch('crashsense.core.k8s_monitor.client')
    def test_health_check(self, mock_client, mock_config):
        """Test comprehensive health check."""
        from crashsense.core.k8s_monitor import KubernetesMonitor
        
        # Mock healthy cluster
        mock_ns = Mock()
        mock_ns.metadata.name = "default"
        
        mock_v1 = Mock()
        mock_v1.list_namespace.return_value.items = [mock_ns]
        mock_v1.list_namespaced_pod.return_value.items = []
        mock_v1.list_namespaced_service.return_value.items = []
        
        mock_config.load_kube_config = Mock()
        mock_client.CoreV1Api.return_value = mock_v1
        
        monitor = KubernetesMonitor()
        health = monitor.health_check()
        
        assert 'timestamp' in health
        assert health['healthy'] is True
        assert health['summary']['pod_crashes'] == 0
        assert len(health['issues']) == 0
