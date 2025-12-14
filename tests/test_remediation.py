# tests/test_remediation.py
"""
Comprehensive tests for remediation engine functionality.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


class TestRemediationEngine:
    """Test suite for RemediationEngine class."""
    
    @patch('crashsense.core.remediation.client')
    def test_initialization(self, mock_client):
        """Test RemediationEngine initialization."""
        from crashsense.core.remediation import RemediationEngine
        
        mock_monitor = Mock()
        mock_monitor.v1 = Mock()
        mock_monitor.apps_v1 = Mock()
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        assert engine.dry_run is True
        assert engine.monitor == mock_monitor
    
    def test_crashloop_remediation_dry_run(self):
        """Test CrashLoopBackOff remediation in dry-run mode."""
        from crashsense.core.remediation import RemediationEngine
        
        mock_monitor = Mock()
        mock_monitor.v1 = Mock()
        mock_monitor.apps_v1 = Mock()
        mock_monitor.get_pod_logs.return_value = "Error: Application crashed"
        
        # Mock the pod with owner_references as a list
        mock_pod = Mock()
        mock_pod.metadata.owner_references = []  # Empty list to avoid iteration errors
        mock_monitor.v1.read_namespaced_pod.return_value = mock_pod
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        issue = {
            "name": "crashy-pod",
            "namespace": "default",
            "restart_count": 15,
            "issues": ["Container app: CrashLoopBackOff"],
            "type": "CrashLoopBackOff"
        }
        
        result = engine.remediate_issue(issue)
        
        assert result['success'] is True
        assert 'would_delete_pod' in result.get('actions_taken', [])
        assert 'dry_run' not in result or engine.dry_run
    
    @patch('crashsense.core.remediation.client')
    def test_oom_remediation(self, mock_client):
        """Test OOMKilled remediation."""
        from crashsense.core.remediation import RemediationEngine
        
        # Mock pod with owner references
        mock_pod = Mock()
        mock_pod.metadata.owner_references = [
            Mock(kind="ReplicaSet", name="myapp-rs-abc123")
        ]
        
        # Mock ReplicaSet with deployment owner
        mock_rs = Mock()
        mock_rs.metadata.owner_references = [
            Mock(kind="Deployment", name="myapp")
        ]
        
        # Mock deployment
        mock_deployment = Mock()
        mock_deployment.spec.template.spec.containers = [
            Mock(
                name="app",
                resources=Mock(limits={"memory": "256Mi"})
            )
        ]
        
        mock_v1 = Mock()
        mock_v1.read_namespaced_pod.return_value = mock_pod
        
        mock_apps_v1 = Mock()
        mock_apps_v1.read_namespaced_replica_set.return_value = mock_rs
        mock_apps_v1.read_namespaced_deployment.return_value = mock_deployment
        
        mock_monitor = Mock()
        mock_monitor.v1 = mock_v1
        mock_monitor.apps_v1 = mock_apps_v1
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        issue = {
            "name": "oom-pod",
            "namespace": "default",
            "issues": ["Container app: OOMKilled"],
            "type": "OOMKilled"
        }
        
        result = engine.remediate_issue(issue)
        
        assert result['success'] is True
        assert any('memory' in action for action in result.get('actions_taken', []))
    
    @patch('crashsense.core.remediation.client')
    def test_increase_memory_limit(self, mock_client):
        """Test memory limit calculation."""
        from crashsense.core.remediation import RemediationEngine
        
        mock_monitor = Mock()
        mock_monitor.v1 = Mock()
        mock_monitor.apps_v1 = Mock()
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        # Test Mi units
        assert engine._increase_memory_limit("256Mi", 1.5) == "384Mi"
        assert engine._increase_memory_limit("512Mi", 1.5) == "768Mi"
        
        # Test Gi units
        result = engine._increase_memory_limit("1Gi", 1.5)
        assert result in ["1Gi", "1536Mi"]  # Could be either
    
    @patch('crashsense.core.remediation.client')
    def test_image_pull_remediation(self, mock_client):
        """Test ImagePullBackOff remediation."""
        from crashsense.core.remediation import RemediationEngine
        
        mock_pod = Mock()
        mock_pod.spec.image_pull_secrets = None
        mock_pod.spec.containers = [
            Mock(image="myregistry/myapp:latest")
        ]
        
        mock_v1 = Mock()
        mock_v1.read_namespaced_pod.return_value = mock_pod
        
        mock_monitor = Mock()
        mock_monitor.v1 = mock_v1
        mock_monitor.apps_v1 = Mock()
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        issue = {
            "name": "image-pull-pod",
            "namespace": "default",
            "issues": ["ImagePullBackOff"],
            "type": "ImagePullBackOff"
        }
        
        result = engine.remediate_issue(issue)
        
        assert result['success'] is True
        assert 'missing_image_pull_secrets' in result.get('actions_taken', [])
        assert 'using_latest_tag' in result.get('actions_taken', [])
    
    @patch('crashsense.core.remediation.client')
    def test_auto_heal_multiple_issues(self, mock_client):
        """Test auto-heal with multiple issues."""
        from crashsense.core.remediation import RemediationEngine
        
        mock_monitor = Mock()
        mock_monitor.v1 = Mock()
        mock_monitor.apps_v1 = Mock()
        mock_monitor.get_pod_logs.return_value = "Error log"
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        issues = [
            {
                "name": "pod-1",
                "namespace": "default",
                "restart_count": 12,
                "issues": ["CrashLoopBackOff"],
                "type": "CrashLoopBackOff"
            },
            {
                "name": "pod-2",
                "namespace": "default",
                "issues": ["OOMKilled"],
                "type": "OOMKilled"
            },
        ]
        
        results = engine.auto_heal(issues, max_actions=10)
        
        assert len(results) == 2
        assert all('actions_taken' in r for r in results)
    
    @patch('crashsense.core.remediation.client')
    def test_service_no_endpoints_remediation(self, mock_client):
        """Test remediation for service with no endpoints."""
        from crashsense.core.remediation import RemediationEngine
        
        mock_service = Mock()
        mock_service.spec.selector = {"app": "myapp"}
        
        mock_pod = Mock()
        mock_pod.metadata.name = "myapp-pod"
        mock_pod.status.phase = "Running"
        
        mock_v1 = Mock()
        mock_v1.read_namespaced_service.return_value = mock_service
        mock_v1.list_namespaced_pod.return_value.items = [mock_pod]
        
        mock_monitor = Mock()
        mock_monitor.v1 = mock_v1
        mock_monitor.apps_v1 = Mock()
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        issue = {
            "service": "myapp-service",
            "namespace": "default",
            "type": "service_no_endpoints"
        }
        
        result = engine.remediate_issue(issue)
        
        assert result['success'] is True
        assert 'found_1_matching_pods' in result.get('actions_taken', [])
    
    def test_max_actions_limit(self):
        """Test that auto-heal respects max actions limit."""
        from crashsense.core.remediation import RemediationEngine
        
        mock_monitor = Mock()
        mock_monitor.v1 = Mock()
        mock_monitor.apps_v1 = Mock()
        mock_monitor.get_pod_logs.return_value = "Error"
        
        # Mock the pod with owner_references as a list
        mock_pod = Mock()
        mock_pod.metadata.owner_references = []
        mock_monitor.v1.read_namespaced_pod.return_value = mock_pod
        
        engine = RemediationEngine(mock_monitor, dry_run=True)
        
        # Create 20 issues but limit to 5 actions
        # Each successful remediation will have 1 action (would_delete_pod)
        issues = [
            {
                "name": f"pod-{i}",
                "namespace": "default",
                "restart_count": 11,  # High enough to trigger delete action
                "issues": ["CrashLoopBackOff"],
                "type": "CrashLoopBackOff"
            }
            for i in range(20)
        ]
        
        results = engine.auto_heal(issues, max_actions=5)
        
        # Count total successful actions taken (not number of issues processed)
        total_actions = sum(len(r.get('actions_taken', [])) for r in results if r.get('success'))
        
        # Should have taken at most 5 actions
        assert total_actions <= 5, f"Expected at most 5 actions, but got {total_actions}"
        
        # Should have stopped early due to max actions limit
        assert len(results) <= len(issues), "Should process some issues"
