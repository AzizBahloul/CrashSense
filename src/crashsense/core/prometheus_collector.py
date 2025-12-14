# src/crashsense/core/prometheus_collector.py
"""
Prometheus metrics collection and Alertmanager integration for self-healing.
"""
from prometheus_client import Counter, Gauge, Histogram, start_http_server, CollectorRegistry
from prometheus_api_client import PrometheusConnect
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from rich.console import Console
import requests
import time
import json

console = Console()


class PrometheusCollector:
    """Collect metrics and integrate with Prometheus/Alertmanager."""
    
    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        alertmanager_url: str = "http://localhost:9093",
        metrics_port: int = 8000,
    ):
        """
        Initialize Prometheus collector.
        
        Args:
            prometheus_url: URL of Prometheus server
            alertmanager_url: URL of Alertmanager
            metrics_port: Port to expose CrashSense metrics
        """
        self.prometheus_url = prometheus_url
        self.alertmanager_url = alertmanager_url
        self.metrics_port = metrics_port
        
        # Prometheus client
        try:
            self.prom = PrometheusConnect(url=prometheus_url, disable_ssl=True)
            console.print(f"[green]✓ Connected to Prometheus at {prometheus_url}[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Could not connect to Prometheus: {e}[/yellow]")
            self.prom = None
        
        # Custom metrics registry
        self.registry = CollectorRegistry()
        
        # Define CrashSense metrics
        self.pod_crash_total = Counter(
            'crashsense_pod_crashes_total',
            'Total number of pod crashes detected',
            ['namespace', 'pod', 'reason'],
            registry=self.registry
        )
        
        self.remediation_total = Counter(
            'crashsense_remediations_total',
            'Total number of remediation actions taken',
            ['namespace', 'pod', 'action', 'status'],
            registry=self.registry
        )
        
        self.pod_health = Gauge(
            'crashsense_pod_health',
            'Pod health status (1=healthy, 0=unhealthy)',
            ['namespace', 'pod'],
            registry=self.registry
        )
        
        self.cluster_health = Gauge(
            'crashsense_cluster_health_score',
            'Overall cluster health score (0-100)',
            registry=self.registry
        )
        
        self.remediation_duration = Histogram(
            'crashsense_remediation_duration_seconds',
            'Time taken for remediation actions',
            ['action'],
            registry=self.registry
        )
        
        self.resource_exhaustion = Gauge(
            'crashsense_resource_exhaustion',
            'Resource exhaustion detected (1=yes, 0=no)',
            ['namespace', 'pod', 'resource_type'],
            registry=self.registry
        )
    
    def start_metrics_server(self):
        """Start HTTP server to expose metrics to Prometheus."""
        try:
            start_http_server(self.metrics_port, registry=self.registry)
            console.print(f"[green]✓ Metrics server started on port {self.metrics_port}[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to start metrics server: {e}[/red]")
    
    def record_pod_crash(self, namespace: str, pod: str, reason: str):
        """Record a pod crash event."""
        self.pod_crash_total.labels(namespace=namespace, pod=pod, reason=reason).inc()
        self.pod_health.labels(namespace=namespace, pod=pod).set(0)
    
    def record_remediation(self, namespace: str, pod: str, action: str, status: str, duration: float = 0):
        """Record a remediation action."""
        self.remediation_total.labels(namespace=namespace, pod=pod, action=action, status=status).inc()
        if duration > 0:
            self.remediation_duration.labels(action=action).observe(duration)
    
    def record_resource_exhaustion(self, namespace: str, pod: str, resource_type: str, is_exhausted: bool):
        """Record resource exhaustion."""
        self.resource_exhaustion.labels(
            namespace=namespace,
            pod=pod,
            resource_type=resource_type
        ).set(1 if is_exhausted else 0)
    
    def update_cluster_health(self, score: float):
        """Update overall cluster health score (0-100)."""
        self.cluster_health.set(max(0, min(100, score)))
    
    def query_metric(self, query: str, time_range: Optional[str] = None) -> List[Dict]:
        """
        Query Prometheus metrics.
        
        Args:
            query: PromQL query
            time_range: Optional time range (e.g., '5m', '1h')
            
        Returns:
            List of metric results
        """
        if not self.prom:
            return []
        
        try:
            if time_range:
                end_time = datetime.now()
                # Parse time_range
                if time_range.endswith('m'):
                    minutes = int(time_range[:-1])
                    start_time = end_time - timedelta(minutes=minutes)
                elif time_range.endswith('h'):
                    hours = int(time_range[:-1])
                    start_time = end_time - timedelta(hours=hours)
                elif time_range.endswith('d'):
                    days = int(time_range[:-1])
                    start_time = end_time - timedelta(days=days)
                else:
                    start_time = end_time - timedelta(minutes=5)
                
                result = self.prom.custom_query_range(
                    query=query,
                    start_time=start_time,
                    end_time=end_time,
                    step='15s'
                )
            else:
                result = self.prom.custom_query(query=query)
            
            return result
        except Exception as e:
            console.print(f"[yellow]Query error: {e}[/yellow]")
            return []
    
    def get_pod_cpu_usage(self, namespace: str, pod: str) -> Optional[float]:
        """Get current CPU usage for a pod."""
        query = f'rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod="{pod}"}}[5m])'
        result = self.query_metric(query)
        
        if result:
            try:
                return float(result[0]['value'][1])
            except (KeyError, IndexError, ValueError):
                pass
        return None
    
    def get_pod_memory_usage(self, namespace: str, pod: str) -> Optional[float]:
        """Get current memory usage for a pod (in bytes)."""
        query = f'container_memory_usage_bytes{{namespace="{namespace}", pod="{pod}"}}'
        result = self.query_metric(query)
        
        if result:
            try:
                return float(result[0]['value'][1])
            except (KeyError, IndexError, ValueError):
                pass
        return None
    
    def get_pod_restart_count(self, namespace: str, pod: str) -> Optional[int]:
        """Get restart count for a pod."""
        query = f'kube_pod_container_status_restarts_total{{namespace="{namespace}", pod="{pod}"}}'
        result = self.query_metric(query)
        
        if result:
            try:
                return int(float(result[0]['value'][1]))
            except (KeyError, IndexError, ValueError):
                pass
        return None
    
    def check_alertmanager_alerts(self) -> List[Dict]:
        """
        Retrieve active alerts from Alertmanager.
        
        Returns:
            List of active alerts
        """
        try:
            response = requests.get(
                f"{self.alertmanager_url}/api/v2/alerts",
                timeout=10
            )
            response.raise_for_status()
            
            alerts = response.json()
            return [
                {
                    "name": alert.get("labels", {}).get("alertname", "Unknown"),
                    "severity": alert.get("labels", {}).get("severity", "unknown"),
                    "namespace": alert.get("labels", {}).get("namespace", "unknown"),
                    "pod": alert.get("labels", {}).get("pod", "unknown"),
                    "description": alert.get("annotations", {}).get("description", ""),
                    "state": alert.get("status", {}).get("state", "unknown"),
                    "starts_at": alert.get("startsAt", ""),
                }
                for alert in alerts
                if alert.get("status", {}).get("state") == "active"
            ]
        except Exception as e:
            console.print(f"[yellow]Could not retrieve Alertmanager alerts: {e}[/yellow]")
            return []
    
    def send_alert_to_alertmanager(
        self,
        alert_name: str,
        severity: str,
        namespace: str,
        pod: str,
        description: str,
        labels: Optional[Dict] = None
    ):
        """
        Send a custom alert to Alertmanager.
        
        Args:
            alert_name: Name of the alert
            severity: Severity level (critical, warning, info)
            namespace: Kubernetes namespace
            pod: Pod name
            description: Alert description
            labels: Additional labels
        """
        try:
            alert_labels = {
                "alertname": alert_name,
                "severity": severity,
                "namespace": namespace,
                "pod": pod,
                "source": "crashsense",
            }
            
            if labels:
                alert_labels.update(labels)
            
            alert_data = [{
                "labels": alert_labels,
                "annotations": {
                    "description": description,
                    "summary": f"{alert_name} for pod {pod} in {namespace}"
                },
                "startsAt": datetime.now().isoformat(),
            }]
            
            response = requests.post(
                f"{self.alertmanager_url}/api/v2/alerts",
                json=alert_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            console.print(f"[green]✓ Alert sent to Alertmanager: {alert_name}[/green]")
            
        except Exception as e:
            console.print(f"[yellow]Could not send alert to Alertmanager: {e}[/yellow]")
    
    def silence_alert(self, alert_id: str, duration_hours: int = 1, comment: str = "Silenced by CrashSense"):
        """
        Silence an alert in Alertmanager.
        
        Args:
            alert_id: Alert identifier
            duration_hours: How long to silence
            comment: Reason for silencing
        """
        try:
            silence_data = {
                "matchers": [{"name": "alertname", "value": alert_id, "isRegex": False}],
                "startsAt": datetime.now().isoformat(),
                "endsAt": (datetime.now() + timedelta(hours=duration_hours)).isoformat(),
                "comment": comment,
                "createdBy": "crashsense",
            }
            
            response = requests.post(
                f"{self.alertmanager_url}/api/v2/silences",
                json=silence_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            console.print(f"[green]✓ Alert {alert_id} silenced for {duration_hours}h[/green]")
            
        except Exception as e:
            console.print(f"[yellow]Could not silence alert: {e}[/yellow]")
    
    def setup_webhook_receiver(self, callback: Callable[[Dict], None], port: int = 9094):
        """
        Setup a webhook receiver for Alertmanager alerts.
        
        Args:
            callback: Function to call when alert is received
            port: Port to listen on
        """
        from flask import Flask, request
        
        app = Flask(__name__)
        
        @app.route('/webhook', methods=['POST'])
        def webhook():
            try:
                data = request.get_json()
                
                for alert in data.get('alerts', []):
                    callback({
                        "name": alert.get("labels", {}).get("alertname"),
                        "status": alert.get("status"),
                        "labels": alert.get("labels", {}),
                        "annotations": alert.get("annotations", {}),
                    })
                
                return {"status": "success"}, 200
            except Exception as e:
                console.print(f"[red]Webhook error: {e}[/red]")
                return {"status": "error", "message": str(e)}, 500
        
        console.print(f"[cyan]Starting webhook receiver on port {port}[/cyan]")
        app.run(host='0.0.0.0', port=port)
    
    def get_cluster_metrics_summary(self) -> Dict:
        """Get a summary of important cluster metrics."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }
        
        if not self.prom:
            return summary
        
        # Common queries
        queries = {
            "total_pods": 'count(kube_pod_info)',
            "running_pods": 'count(kube_pod_status_phase{phase="Running"})',
            "failed_pods": 'count(kube_pod_status_phase{phase="Failed"})',
            "pending_pods": 'count(kube_pod_status_phase{phase="Pending"})',
            "node_count": 'count(kube_node_info)',
            "avg_cpu_usage": 'avg(rate(container_cpu_usage_seconds_total[5m]))',
            "avg_memory_usage_gb": 'avg(container_memory_usage_bytes) / 1024 / 1024 / 1024',
        }
        
        for metric_name, query in queries.items():
            result = self.query_metric(query)
            if result:
                try:
                    summary["metrics"][metric_name] = float(result[0]['value'][1])
                except (KeyError, IndexError, ValueError):
                    summary["metrics"][metric_name] = None
        
        return summary
