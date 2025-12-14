# src/crashsense/core/k8s_monitor.py
"""
Kubernetes cluster monitoring for pod crashes, resource exhaustion, and network failures.
"""
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from rich.console import Console
import time
import os

console = Console()


class KubernetesMonitor:
    """Monitor Kubernetes cluster for common issues requiring remediation."""
    
    def __init__(self, kubeconfig_path: Optional[str] = None, namespaces: Optional[List[str]] = None):
        """
        Initialize Kubernetes monitor.
        
        Args:
            kubeconfig_path: Path to kubeconfig file (None for in-cluster config)
            namespaces: List of namespaces to monitor (None for all namespaces)
        """
        self.kubeconfig_path = kubeconfig_path
        self.namespaces = namespaces or []
        self.v1 = None
        self.apps_v1 = None
        self._load_config()
    
    def _load_config(self):
        """Load Kubernetes configuration."""
        try:
            if self.kubeconfig_path:
                config.load_kube_config(config_file=self.kubeconfig_path)
            elif os.getenv('KUBERNETES_SERVICE_HOST'):
                # Running inside a pod
                config.load_incluster_config()
            else:
                # Use default kubeconfig
                config.load_kube_config()
            
            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            console.print("[green]✓ Connected to Kubernetes cluster[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to connect to Kubernetes: {e}[/red]")
            raise
    
    def get_cluster_info(self) -> Dict:
        """Get basic cluster information."""
        try:
            version_info = client.VersionApi().get_code()
            nodes = self.v1.list_node()
            
            return {
                "version": f"{version_info.major}.{version_info.minor}",
                "node_count": len(nodes.items),
                "nodes": [
                    {
                        "name": node.metadata.name,
                        "status": next((c.status for c in node.status.conditions if c.type == "Ready"), "Unknown"),
                        "cpu_capacity": node.status.capacity.get("cpu", "N/A"),
                        "memory_capacity": node.status.capacity.get("memory", "N/A"),
                    }
                    for node in nodes.items
                ],
            }
        except ApiException as e:
            console.print(f"[red]Error getting cluster info: {e}[/red]")
            return {}
    
    def detect_pod_crashes(self, time_window_minutes: int = 15) -> List[Dict]:
        """
        Detect pods with crash issues (CrashLoopBackOff, Error, OOMKilled).
        
        Args:
            time_window_minutes: Look for crashes within this time window
            
        Returns:
            List of problematic pods with details
        """
        problematic_pods = []
        namespaces = self.namespaces if self.namespaces else [ns.metadata.name for ns in self.v1.list_namespace().items]
        
        for namespace in namespaces:
            try:
                pods = self.v1.list_namespaced_pod(namespace)
                
                for pod in pods.items:
                    pod_info = self._analyze_pod_status(pod, namespace)
                    if pod_info and pod_info.get("needs_remediation"):
                        problematic_pods.append(pod_info)
                        
            except ApiException as e:
                console.print(f"[yellow]Warning: Could not access namespace {namespace}: {e}[/yellow]")
        
        return problematic_pods
    
    def _analyze_pod_status(self, pod, namespace: str) -> Optional[Dict]:
        """Analyze individual pod for issues."""
        pod_name = pod.metadata.name
        pod_phase = pod.status.phase
        
        issues = []
        needs_remediation = False
        restart_count = 0
        container_statuses = []
        
        # Analyze container statuses
        if pod.status.container_statuses:
            for container in pod.status.container_statuses:
                restart_count += container.restart_count
                container_info = {
                    "name": container.name,
                    "ready": container.ready,
                    "restart_count": container.restart_count,
                    "state": {},
                }
                
                # Check waiting state
                if container.state.waiting:
                    reason = container.state.waiting.reason
                    message = container.state.waiting.message or ""
                    container_info["state"] = {"waiting": {"reason": reason, "message": message}}
                    
                    if reason in ["CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerError"]:
                        issues.append(f"Container {container.name}: {reason}")
                        needs_remediation = True
                
                # Check terminated state
                elif container.state.terminated:
                    reason = container.state.terminated.reason
                    exit_code = container.state.terminated.exit_code
                    container_info["state"] = {"terminated": {"reason": reason, "exit_code": exit_code}}
                    
                    if reason in ["OOMKilled", "Error"] or exit_code != 0:
                        issues.append(f"Container {container.name}: {reason} (exit code: {exit_code})")
                        needs_remediation = True
                
                # High restart count
                if container.restart_count > 5:
                    issues.append(f"Container {container.name}: High restart count ({container.restart_count})")
                    needs_remediation = True
                
                container_statuses.append(container_info)
        
        # Check pod conditions
        if pod.status.conditions:
            for condition in pod.status.conditions:
                if condition.type == "Ready" and condition.status != "True":
                    issues.append(f"Pod not ready: {condition.reason or 'Unknown'}")
                if condition.type == "PodScheduled" and condition.status != "True":
                    issues.append(f"Pod not scheduled: {condition.reason or 'Unknown'}")
                    needs_remediation = True
        
        if not needs_remediation and pod_phase not in ["Running", "Succeeded"]:
            if pod_phase in ["Failed", "Unknown", "Pending"]:
                needs_remediation = True
                issues.append(f"Pod in {pod_phase} state")
        
        if issues:
            return {
                "name": pod_name,
                "namespace": namespace,
                "phase": pod_phase,
                "restart_count": restart_count,
                "issues": issues,
                "needs_remediation": needs_remediation,
                "containers": container_statuses,
                "labels": pod.metadata.labels or {},
                "node": pod.spec.node_name,
                "created": pod.metadata.creation_timestamp,
            }
        
        return None
    
    def detect_resource_exhaustion(self, threshold_percent: int = 85) -> List[Dict]:
        """
        Detect pods/nodes with resource exhaustion (CPU, memory).
        
        Args:
            threshold_percent: Alert when usage exceeds this percentage
            
        Returns:
            List of resources with high utilization
        """
        exhausted_resources = []
        
        try:
            # Get pod metrics (requires metrics-server)
            try:
                from kubernetes import client as k8s_client
                custom_api = k8s_client.CustomObjectsApi()
                
                namespaces = self.namespaces if self.namespaces else [ns.metadata.name for ns in self.v1.list_namespace().items]
                
                for namespace in namespaces:
                    try:
                        metrics = custom_api.list_namespaced_custom_object(
                            group="metrics.k8s.io",
                            version="v1beta1",
                            namespace=namespace,
                            plural="pods"
                        )
                        
                        for pod_metrics in metrics.get("items", []):
                            pod_name = pod_metrics["metadata"]["name"]
                            
                            # Get pod spec for limits
                            try:
                                pod = self.v1.read_namespaced_pod(pod_name, namespace)
                                
                                for container_metrics in pod_metrics.get("containers", []):
                                    container_name = container_metrics["name"]
                                    usage_cpu = container_metrics["usage"].get("cpu", "0")
                                    usage_memory = container_metrics["usage"].get("memory", "0")
                                    
                                    # Find matching container spec
                                    for container in pod.spec.containers:
                                        if container.name == container_name:
                                            limits = container.resources.limits or {}
                                            
                                            # Check memory exhaustion
                                            if limits.get("memory"):
                                                memory_limit_bytes = self._parse_resource(limits["memory"])
                                                memory_usage_bytes = self._parse_resource(usage_memory)
                                                
                                                if memory_limit_bytes > 0:
                                                    memory_percent = (memory_usage_bytes / memory_limit_bytes) * 100
                                                    
                                                    if memory_percent > threshold_percent:
                                                        exhausted_resources.append({
                                                            "type": "pod_memory",
                                                            "pod": pod_name,
                                                            "namespace": namespace,
                                                            "container": container_name,
                                                            "usage_percent": round(memory_percent, 2),
                                                            "usage": usage_memory,
                                                            "limit": limits["memory"],
                                                            "remediation": "increase_memory_limit"
                                                        })
                            except ApiException:
                                pass
                                
                    except ApiException:
                        # Metrics server might not be available
                        pass
                        
            except ImportError:
                console.print("[yellow]Metrics API not available - install metrics-server for resource monitoring[/yellow]")
                
        except Exception as e:
            console.print(f"[yellow]Resource exhaustion detection error: {e}[/yellow]")
        
        return exhausted_resources
    
    def _parse_resource(self, resource_str: str) -> int:
        """Parse Kubernetes resource string (e.g., '100Mi', '2Gi') to bytes."""
        if not resource_str:
            return 0
        
        resource_str = resource_str.strip()
        
        # Handle CPU (millicores)
        if resource_str.endswith('m'):
            return int(resource_str[:-1])
        
        # Handle memory
        units = {
            'Ki': 1024,
            'Mi': 1024**2,
            'Gi': 1024**3,
            'Ti': 1024**4,
            'K': 1000,
            'M': 1000**2,
            'G': 1000**3,
            'T': 1000**4,
        }
        
        for suffix, multiplier in units.items():
            if resource_str.endswith(suffix):
                try:
                    return int(float(resource_str[:-len(suffix)]) * multiplier)
                except ValueError:
                    return 0
        
        # Plain number
        try:
            return int(resource_str)
        except ValueError:
            return 0
    
    def detect_network_failures(self) -> List[Dict]:
        """
        Detect network-related issues (service failures, endpoint issues).
        
        Returns:
            List of network issues
        """
        network_issues = []
        namespaces = self.namespaces if self.namespaces else [ns.metadata.name for ns in self.v1.list_namespace().items]
        
        for namespace in namespaces:
            try:
                # Check services and endpoints
                services = self.v1.list_namespaced_service(namespace)
                
                for service in services.items:
                    service_name = service.metadata.name
                    
                    # Check if service has endpoints
                    try:
                        endpoints = self.v1.read_namespaced_endpoints(service_name, namespace)
                        
                        if not endpoints.subsets or not any(subset.addresses for subset in endpoints.subsets):
                            network_issues.append({
                                "type": "service_no_endpoints",
                                "service": service_name,
                                "namespace": namespace,
                                "issue": "Service has no available endpoints",
                                "remediation": "check_pod_selectors"
                            })
                    except ApiException:
                        pass
                
            except ApiException as e:
                console.print(f"[yellow]Warning: Could not check network in namespace {namespace}: {e}[/yellow]")
        
        return network_issues
    
    def watch_pod_events(self, callback, namespaces: Optional[List[str]] = None, timeout_seconds: int = 300):
        """
        Watch for pod events in real-time.
        
        Args:
            callback: Function to call with event data
            namespaces: Namespaces to watch (None for all)
            timeout_seconds: How long to watch
        """
        w = watch.Watch()
        namespaces = namespaces or self.namespaces or ["default"]
        
        console.print(f"[cyan]Watching pod events in namespaces: {', '.join(namespaces)}[/cyan]")
        
        for namespace in namespaces:
            try:
                for event in w.stream(
                    self.v1.list_namespaced_pod,
                    namespace=namespace,
                    timeout_seconds=timeout_seconds
                ):
                    event_type = event['type']  # ADDED, MODIFIED, DELETED
                    pod = event['object']
                    
                    event_data = {
                        "type": event_type,
                        "pod": pod.metadata.name,
                        "namespace": namespace,
                        "phase": pod.status.phase,
                        "timestamp": datetime.now(),
                    }
                    
                    # Analyze if pod needs attention
                    pod_analysis = self._analyze_pod_status(pod, namespace)
                    if pod_analysis:
                        event_data["analysis"] = pod_analysis
                    
                    callback(event_data)
                    
            except ApiException as e:
                console.print(f"[red]Error watching namespace {namespace}: {e}[/red]")
    
    def get_pod_logs(self, pod_name: str, namespace: str, container: Optional[str] = None, 
                     tail_lines: int = 100, previous: bool = False) -> str:
        """
        Get logs from a pod.
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace
            container: Container name (optional)
            tail_lines: Number of lines to retrieve
            previous: Get logs from previous terminated container
            
        Returns:
            Pod logs as string
        """
        try:
            logs = self.v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                previous=previous
            )
            return logs
        except ApiException as e:
            return f"Error retrieving logs: {e}"
    
    def health_check(self) -> Dict:
        """
        Perform comprehensive cluster health check.
        
        Returns:
            Health status dictionary
        """
        health = {
            "timestamp": datetime.now().isoformat(),
            "healthy": True,
            "issues": [],
            "summary": {},
        }
        
        try:
            # Check pod crashes
            crashes = self.detect_pod_crashes()
            health["summary"]["pod_crashes"] = len(crashes)
            if crashes:
                health["healthy"] = False
                health["issues"].extend([f"Pod crash: {c['name']} in {c['namespace']}" for c in crashes[:5]])
            
            # Check resource exhaustion
            exhaustion = self.detect_resource_exhaustion()
            health["summary"]["resource_exhaustion"] = len(exhaustion)
            if exhaustion:
                health["issues"].extend([f"Resource exhaustion: {r['pod']}" for r in exhaustion[:5]])
            
            # Check network issues
            network = self.detect_network_failures()
            health["summary"]["network_issues"] = len(network)
            if network:
                health["issues"].extend([f"Network issue: {n['service']}" for n in network[:5]])
            
        except Exception as e:
            health["healthy"] = False
            health["issues"].append(f"Health check error: {str(e)}")
        
        return health
