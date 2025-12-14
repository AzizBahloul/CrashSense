# src/crashsense/core/remediation.py
"""
Self-healing remediation engine for Kubernetes issues.
"""
from kubernetes import client
from kubernetes.client.rest import ApiException
from typing import Dict, List, Optional, Callable
from datetime import datetime
from rich.console import Console
import time
import yaml

console = Console()


class RemediationEngine:
    """Automated remediation for common Kubernetes issues."""
    
    def __init__(self, k8s_monitor, prometheus_collector=None, dry_run: bool = False):
        """
        Initialize remediation engine.
        
        Args:
            k8s_monitor: KubernetesMonitor instance
            prometheus_collector: PrometheusCollector instance (optional)
            dry_run: If True, only simulate actions without applying them
        """
        self.monitor = k8s_monitor
        self.prometheus = prometheus_collector
        self.dry_run = dry_run
        self.v1 = k8s_monitor.v1
        self.apps_v1 = k8s_monitor.apps_v1
        
        # Remediation policies
        self.policies = {
            "CrashLoopBackOff": self._remediate_crashloop,
            "ImagePullBackOff": self._remediate_image_pull,
            "OOMKilled": self._remediate_oom,
            "Error": self._remediate_error,
            "service_no_endpoints": self._remediate_no_endpoints,
            "resource_exhaustion": self._remediate_resource_exhaustion,
        }
    
    def remediate_issue(self, issue: Dict) -> Dict:
        """
        Apply remediation for a detected issue.
        
        Args:
            issue: Issue dictionary from monitoring
            
        Returns:
            Remediation result
        """
        start_time = time.time()
        
        issue_type = issue.get("type") or self._infer_issue_type(issue)
        namespace = issue.get("namespace")
        pod_name = issue.get("pod") or issue.get("name")
        
        console.print(f"\n[bold cyan]🔧 Remediating: {issue_type}[/bold cyan]")
        console.print(f"   Pod: {pod_name} (namespace: {namespace})")
        
        if self.dry_run:
            console.print(f"   [yellow]DRY RUN MODE - No actual changes will be made[/yellow]")
        
        result = {
            "issue_type": issue_type,
            "namespace": namespace,
            "pod": pod_name,
            "timestamp": datetime.now().isoformat(),
            "actions_taken": [],
            "success": False,
            "message": "",
        }
        
        # Find and execute remediation policy
        remediation_func = self.policies.get(issue_type)
        
        if remediation_func:
            try:
                remediation_result = remediation_func(issue)
                result.update(remediation_result)
                result["success"] = remediation_result.get("success", False)
                
                if result["success"]:
                    console.print(f"   [green]✓ Remediation successful[/green]")
                else:
                    console.print(f"   [yellow]⚠ Remediation partially successful[/yellow]")
                    
            except Exception as e:
                result["success"] = False
                result["message"] = f"Remediation failed: {str(e)}"
                console.print(f"   [red]✗ Remediation failed: {e}[/red]")
        else:
            result["message"] = f"No remediation policy for issue type: {issue_type}"
            console.print(f"   [yellow]⚠ {result['message']}[/yellow]")
        
        # Record metrics
        duration = time.time() - start_time
        if self.prometheus:
            status = "success" if result["success"] else "failed"
            action = result.get("actions_taken", ["unknown"])[0] if result.get("actions_taken") else "unknown"
            self.prometheus.record_remediation(
                namespace=namespace,
                pod=pod_name,
                action=action,
                status=status,
                duration=duration
            )
        
        result["duration_seconds"] = round(duration, 2)
        return result
    
    def _infer_issue_type(self, issue: Dict) -> str:
        """Infer issue type from issue dictionary."""
        issues = issue.get("issues", [])
        
        for issue_str in issues:
            if "CrashLoopBackOff" in issue_str:
                return "CrashLoopBackOff"
            elif "ImagePullBackOff" in issue_str or "ErrImagePull" in issue_str:
                return "ImagePullBackOff"
            elif "OOMKilled" in issue_str:
                return "OOMKilled"
            elif "Error" in issue_str:
                return "Error"
        
        return issue.get("type", "Unknown")
    
    def _remediate_crashloop(self, issue: Dict) -> Dict:
        """Remediate CrashLoopBackOff by analyzing logs and attempting fixes."""
        namespace = issue["namespace"]
        pod_name = issue.get("pod") or issue.get("name")
        actions = []
        
        # Step 1: Analyze pod logs for root cause
        console.print(f"   → Analyzing pod logs...")
        logs = self.monitor.get_pod_logs(pod_name, namespace, tail_lines=200, previous=True)
        
        # Step 2: Check for common issues
        restart_count = issue.get("restart_count", 0)
        
        if restart_count > 10:
            # High restart count - might need deployment recreation
            console.print(f"   → High restart count ({restart_count}), considering pod deletion...")
            
            if not self.dry_run:
                try:
                    self.v1.delete_namespaced_pod(pod_name, namespace)
                    actions.append("deleted_pod")
                    console.print(f"   → Deleted pod {pod_name} (will be recreated by controller)")
                except ApiException as e:
                    return {"success": False, "message": f"Failed to delete pod: {e}", "actions_taken": actions}
            else:
                actions.append("would_delete_pod")
                console.print(f"   → Would delete pod {pod_name}")
        
        # Step 3: Check if it's a configuration issue
        if "environment" in logs.lower() or "config" in logs.lower():
            console.print(f"   → Possible configuration issue detected")
            actions.append("identified_config_issue")
        
        # Step 4: Check deployment health
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)
            owner_refs = pod.metadata.owner_references
            
            if owner_refs:
                for owner in owner_refs:
                    if owner.kind == "ReplicaSet":
                        # Get deployment
                        rs = self.apps_v1.read_namespaced_replica_set(owner.name, namespace)
                        if rs.metadata.owner_references:
                            for deploy_owner in rs.metadata.owner_references:
                                if deploy_owner.kind == "Deployment":
                                    console.print(f"   → Found parent deployment: {deploy_owner.name}")
                                    actions.append(f"identified_deployment_{deploy_owner.name}")
        except ApiException:
            pass
        
        return {
            "success": len(actions) > 0,
            "actions_taken": actions,
            "message": f"CrashLoopBackOff remediation attempted with {len(actions)} actions",
            "logs_snippet": logs[:500] if logs else "",
        }
    
    def _remediate_image_pull(self, issue: Dict) -> Dict:
        """Remediate ImagePullBackOff issues."""
        namespace = issue["namespace"]
        pod_name = issue.get("pod") or issue.get("name")
        actions = []
        
        console.print(f"   → Checking image pull issues...")
        
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)
            
            # Check image pull secrets
            if not pod.spec.image_pull_secrets:
                console.print(f"   → No image pull secrets configured")
                actions.append("missing_image_pull_secrets")
            
            # Get container images
            for container in pod.spec.containers:
                image = container.image
                console.print(f"   → Image: {image}")
                
                # Check if image uses 'latest' tag (bad practice)
                if image.endswith(":latest") or ":" not in image:
                    console.print(f"   → Warning: Using 'latest' tag or no tag specified")
                    actions.append("using_latest_tag")
                
                # Check registry accessibility (basic check)
                if image.startswith("localhost") or "127.0.0.1" in image:
                    console.print(f"   → Warning: Using localhost registry")
                    actions.append("localhost_registry")
            
            return {
                "success": True,
                "actions_taken": actions,
                "message": "ImagePullBackOff analysis complete - manual intervention may be required",
                "recommendation": "Check image registry credentials and image availability",
            }
            
        except ApiException as e:
            return {"success": False, "message": f"Failed to analyze image pull issue: {e}", "actions_taken": actions}
    
    def _remediate_oom(self, issue: Dict) -> Dict:
        """Remediate OOMKilled by increasing memory limits."""
        namespace = issue["namespace"]
        pod_name = issue.get("pod") or issue.get("name")
        actions = []
        
        console.print(f"   → Handling OOMKilled - increasing memory limits...")
        
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)
            owner_refs = pod.metadata.owner_references
            
            if not owner_refs:
                return {"success": False, "message": "Pod has no owner - cannot update memory limits", "actions_taken": actions}
            
            # Find deployment or statefulset
            for owner in owner_refs:
                if owner.kind == "ReplicaSet":
                    rs = self.apps_v1.read_namespaced_replica_set(owner.name, namespace)
                    if rs.metadata.owner_references:
                        for deploy_owner in rs.metadata.owner_references:
                            if deploy_owner.kind == "Deployment":
                                deployment_name = deploy_owner.name
                                
                                if not self.dry_run:
                                    # Patch deployment to increase memory
                                    deployment = self.apps_v1.read_namespaced_deployment(deployment_name, namespace)
                                    
                                    for i, container in enumerate(deployment.spec.template.spec.containers):
                                        current_limit = container.resources.limits.get("memory", "128Mi") if container.resources.limits else "128Mi"
                                        
                                        # Parse and increase memory limit by 50%
                                        new_limit = self._increase_memory_limit(current_limit, factor=1.5)
                                        
                                        console.print(f"   → Increasing memory limit: {current_limit} → {new_limit}")
                                        
                                        # Patch
                                        patch = {
                                            "spec": {
                                                "template": {
                                                    "spec": {
                                                        "containers": [{
                                                            "name": container.name,
                                                            "resources": {
                                                                "limits": {"memory": new_limit},
                                                                "requests": {"memory": new_limit}
                                                            }
                                                        }]
                                                    }
                                                }
                                            }
                                        }
                                        
                                        try:
                                            self.apps_v1.patch_namespaced_deployment(
                                                deployment_name,
                                                namespace,
                                                patch
                                            )
                                            actions.append(f"increased_memory_{current_limit}_to_{new_limit}")
                                            console.print(f"   → Deployment {deployment_name} updated")
                                        except ApiException as e:
                                            console.print(f"   → Failed to patch deployment: {e}")
                                else:
                                    actions.append("would_increase_memory")
                                    console.print(f"   → Would increase memory limits for deployment {deployment_name}")
            
            return {
                "success": len(actions) > 0,
                "actions_taken": actions,
                "message": "OOMKilled remediation completed",
            }
            
        except ApiException as e:
            return {"success": False, "message": f"Failed to remediate OOMKilled: {e}", "actions_taken": actions}
    
    def _increase_memory_limit(self, current_limit: str, factor: float = 1.5) -> str:
        """Increase memory limit by a factor."""
        # Parse memory string
        if current_limit.endswith("Mi"):
            value = int(current_limit[:-2])
            new_value = int(value * factor)
            return f"{new_value}Mi"
        elif current_limit.endswith("Gi"):
            value = int(current_limit[:-2])
            new_value = value * factor
            if new_value < 1:
                return f"{int(new_value * 1024)}Mi"
            return f"{int(new_value)}Gi"
        else:
            # Default increase
            return "256Mi"
    
    def _remediate_error(self, issue: Dict) -> Dict:
        """Generic error remediation - restart pod."""
        namespace = issue["namespace"]
        pod_name = issue.get("pod") or issue.get("name")
        actions = []
        
        console.print(f"   → Restarting pod due to error state...")
        
        if not self.dry_run:
            try:
                self.v1.delete_namespaced_pod(pod_name, namespace)
                actions.append("deleted_pod")
                console.print(f"   → Pod {pod_name} deleted (will be recreated)")
            except ApiException as e:
                return {"success": False, "message": f"Failed to delete pod: {e}", "actions_taken": actions}
        else:
            actions.append("would_delete_pod")
            console.print(f"   → Would delete pod {pod_name}")
        
        return {
            "success": True,
            "actions_taken": actions,
            "message": "Pod restart initiated",
        }
    
    def _remediate_no_endpoints(self, issue: Dict) -> Dict:
        """Remediate service with no endpoints."""
        namespace = issue["namespace"]
        service_name = issue.get("service")
        actions = []
        
        console.print(f"   → Analyzing service {service_name} with no endpoints...")
        
        try:
            service = self.v1.read_namespaced_service(service_name, namespace)
            selector = service.spec.selector
            
            if not selector:
                return {
                    "success": False,
                    "message": "Service has no selector - cannot find matching pods",
                    "actions_taken": actions
                }
            
            # Find pods matching selector
            console.print(f"   → Service selector: {selector}")
            label_selector = ",".join([f"{k}={v}" for k, v in selector.items()])
            
            pods = self.v1.list_namespaced_pod(namespace, label_selector=label_selector)
            
            if not pods.items:
                console.print(f"   → No pods match service selector")
                actions.append("no_matching_pods")
            else:
                console.print(f"   → Found {len(pods.items)} matching pods")
                for pod in pods.items:
                    console.print(f"      - {pod.metadata.name} ({pod.status.phase})")
                actions.append(f"found_{len(pods.items)}_matching_pods")
            
            return {
                "success": True,
                "actions_taken": actions,
                "message": f"Service analysis complete - {len(pods.items)} matching pods found",
                "recommendation": "Ensure pod labels match service selector and pods are running",
            }
            
        except ApiException as e:
            return {"success": False, "message": f"Failed to analyze service: {e}", "actions_taken": actions}
    
    def _remediate_resource_exhaustion(self, issue: Dict) -> Dict:
        """Remediate resource exhaustion by scaling or increasing limits."""
        namespace = issue["namespace"]
        pod_name = issue.get("pod")
        resource_type = issue.get("resource_type", "unknown")
        actions = []
        
        console.print(f"   → Handling resource exhaustion: {resource_type}...")
        
        if resource_type == "pod_memory":
            # Delegate to OOM remediation
            return self._remediate_oom(issue)
        
        # Generic scaling approach
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)
            owner_refs = pod.metadata.owner_references
            
            if owner_refs:
                for owner in owner_refs:
                    if owner.kind == "ReplicaSet":
                        rs = self.apps_v1.read_namespaced_replica_set(owner.name, namespace)
                        if rs.metadata.owner_references:
                            for deploy_owner in rs.metadata.owner_references:
                                if deploy_owner.kind == "Deployment":
                                    deployment_name = deploy_owner.name
                                    deployment = self.apps_v1.read_namespaced_deployment(deployment_name, namespace)
                                    current_replicas = deployment.spec.replicas or 1
                                    
                                    # Scale up
                                    new_replicas = current_replicas + 1
                                    console.print(f"   → Scaling deployment {deployment_name}: {current_replicas} → {new_replicas}")
                                    
                                    if not self.dry_run:
                                        deployment.spec.replicas = new_replicas
                                        self.apps_v1.patch_namespaced_deployment(deployment_name, namespace, deployment)
                                        actions.append(f"scaled_deployment_{current_replicas}_to_{new_replicas}")
                                    else:
                                        actions.append(f"would_scale_to_{new_replicas}")
            
            return {
                "success": len(actions) > 0,
                "actions_taken": actions,
                "message": "Resource exhaustion remediation attempted",
            }
            
        except ApiException as e:
            return {"success": False, "message": f"Failed to remediate resource exhaustion: {e}", "actions_taken": actions}
    
    def auto_heal(self, issues: List[Dict], max_actions: int = 10) -> List[Dict]:
        """
        Automatically remediate a list of issues.
        
        Args:
            issues: List of detected issues
            max_actions: Maximum number of remediation actions to take
            
        Returns:
            List of remediation results
        """
        console.print(f"\n[bold]🏥 Auto-Heal Mode: Processing {len(issues)} issues[/bold]")
        
        results = []
        actions_taken = 0
        
        for i, issue in enumerate(issues):
            if actions_taken >= max_actions:
                console.print(f"\n[yellow]⚠ Reached maximum actions limit ({max_actions})[/yellow]")
                break
            
            console.print(f"\n[dim]Issue {i+1}/{len(issues)}[/dim]")
            result = self.remediate_issue(issue)
            results.append(result)
            
            if result.get("success"):
                actions_taken += len(result.get("actions_taken", []))
            
            # Small delay between actions
            time.sleep(2)
        
        console.print(f"\n[bold green]✓ Auto-heal complete: {actions_taken} actions taken[/bold green]")
        return results
