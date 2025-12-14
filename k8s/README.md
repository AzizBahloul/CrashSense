# Kubernetes Deployment for CrashSense

This directory contains Kubernetes manifests for deploying CrashSense as a self-healing platform in your cluster.

## Quick Start

```bash
# Create namespace
kubectl create namespace crashsense

# Apply RBAC permissions
kubectl apply -f rbac.yaml

# Deploy CrashSense
kubectl apply -f deployment.yaml

# Expose metrics for Prometheus
kubectl apply -f service.yaml
```

## Files

- `rbac.yaml` - ServiceAccount, ClusterRole, and ClusterRoleBinding for CrashSense
- `deployment.yaml` - Main CrashSense deployment with auto-heal enabled
- `service.yaml` - Service to expose Prometheus metrics
- `configmap.yaml` - Configuration for CrashSense
- `alertmanager-config.yaml` - Alertmanager webhook configuration

## Configuration

### Environment Variables

Set these in your deployment:

```yaml
env:
  - name: CRASHSENSE_OPENAI_KEY
    valueFrom:
      secretKeyRef:
        name: crashsense-secrets
        key: openai-api-key
  - name: CRASHSENSE_PROVIDER
    value: "openai"  # or "ollama" for local
```

### Monitoring Namespaces

Edit `configmap.yaml` to specify which namespaces to monitor:

```yaml
kubernetes:
  namespaces: ["production", "staging"]
```

## Prometheus Integration

Add this job to your Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'crashsense'
    static_configs:
      - targets: ['crashsense.crashsense.svc:8000']
```

## Alertmanager Integration

Configure Alertmanager to send webhooks to CrashSense:

```yaml
receivers:
  - name: 'crashsense'
    webhook_configs:
      - url: 'http://crashsense.crashsense.svc:9094/webhook'
        send_resolved: true
```

## Security Notes

1. **Secrets**: Store OpenAI API key in Kubernetes secrets
2. **RBAC**: CrashSense requires cluster-wide read/write permissions
3. **Network Policies**: Consider restricting network access
4. **Dry Run**: Enable dry-run mode initially to test remediation

## Monitoring CrashSense

View logs:
```bash
kubectl logs -n crashsense deployment/crashsense -f
```

Check metrics:
```bash
kubectl port-forward -n crashsense svc/crashsense 8000:8000
curl http://localhost:8000/metrics
```

## Scaling

CrashSense can run as a single instance or be scaled for high availability:

```bash
kubectl scale -n crashsense deployment/crashsense --replicas=2
```

Note: Use leader election if running multiple replicas to avoid duplicate remediation actions.
