# Kubernetes Remediation Playbook

## Common Kubernetes Issues and Automated Fixes

### Pod Crash Issues

#### CrashLoopBackOff
**Symptoms:**
- Pod repeatedly crashes and restarts
- `kubectl get pods` shows CrashLoopBackOff status
- Restart count continuously increasing

**Common Causes:**
1. Application startup failure (missing dependencies, configuration errors)
2. Resource constraints (OOMKilled)
3. Liveness probe failures
4. Invalid container command or entrypoint

**Automated Remediation:**
```bash
# 1. Check pod logs for error details
kubectl logs <pod-name> --previous

# 2. If high restart count (>10), delete pod to force fresh start
kubectl delete pod <pod-name>

# 3. Check and fix deployment configuration
kubectl describe deployment <deployment-name>

# 4. Scale deployment to recreate all pods
kubectl rollout restart deployment <deployment-name>
```

**CrashSense Actions:**
- Analyze pod logs (current and previous)
- Delete pod if restart count > 10
- Identify configuration issues
- Notify about deployment health

---

#### ImagePullBackOff / ErrImagePull
**Symptoms:**
- Pod stuck in ImagePullBackOff or ErrImagePull state
- Cannot pull container image from registry

**Common Causes:**
1. Image doesn't exist or wrong tag
2. Missing or invalid image pull secrets
3. Registry authentication failure
4. Private registry not accessible

**Automated Remediation:**
```bash
# 1. Verify image exists
docker pull <image-name>

# 2. Check image pull secrets
kubectl get secrets -n <namespace>

# 3. Create image pull secret if missing
kubectl create secret docker-registry regcred \
  --docker-server=<registry> \
  --docker-username=<username> \
  --docker-password=<password>

# 4. Add secret to service account
kubectl patch serviceaccount default -p '{"imagePullSecrets": [{"name": "regcred"}]}'
```

**CrashSense Actions:**
- Check if image uses 'latest' tag (bad practice)
- Verify image pull secrets are configured
- Detect localhost/invalid registry URLs
- Provide manual intervention steps

---

#### OOMKilled (Out of Memory)
**Symptoms:**
- Container terminated with OOMKilled reason
- Exit code 137
- Repeated restarts due to memory exhaustion

**Common Causes:**
1. Memory limit too low for application needs
2. Memory leak in application
3. Unexpected load spike

**Automated Remediation:**
```bash
# 1. Check current memory limits
kubectl describe pod <pod-name> | grep -A 5 "Limits"

# 2. Increase memory limit (50% increase recommended)
kubectl set resources deployment <deployment> \
  --limits=memory=768Mi \
  --requests=memory=512Mi

# 3. Monitor memory usage
kubectl top pod <pod-name>

# 4. Enable horizontal pod autoscaling
kubectl autoscale deployment <deployment> \
  --cpu-percent=70 \
  --min=2 \
  --max=10
```

**CrashSense Actions:**
- Parse current memory limits
- Calculate 50% increase
- Patch deployment with new limits
- Recommend HPA if not already configured

---

### Resource Exhaustion

#### High CPU/Memory Usage
**Symptoms:**
- Pod using >85% of allocated resources
- Performance degradation
- Potential for throttling or OOMKill

**Automated Remediation:**
```bash
# 1. Check resource usage
kubectl top pods -n <namespace>

# 2. Scale horizontally
kubectl scale deployment <deployment> --replicas=<new-count>

# 3. Increase resource limits
kubectl set resources deployment <deployment> \
  --limits=cpu=2000m,memory=2Gi \
  --requests=cpu=1000m,memory=1Gi

# 4. Enable HPA for automatic scaling
kubectl autoscale deployment <deployment> \
  --cpu-percent=70 \
  --min=3 \
  --max=15
```

**CrashSense Actions:**
- Monitor resource usage via Prometheus
- Scale up deployment replicas
- Increase resource limits
- Alert when threshold exceeded

---

### Network Issues

#### Service Has No Endpoints
**Symptoms:**
- Service exists but has no endpoints
- Requests to service fail or timeout
- `kubectl get endpoints` shows no addresses

**Common Causes:**
1. No pods match service selector
2. Pods exist but not in Ready state
3. Label mismatch between service and pods

**Automated Remediation:**
```bash
# 1. Check service selector
kubectl describe service <service-name> | grep Selector

# 2. Find matching pods
kubectl get pods -l <selector-labels>

# 3. If no pods, check deployment
kubectl get deployment <deployment-name>

# 4. Fix label mismatch
kubectl label pods <pod-name> <correct-label>=<value>

# 5. Restart pods if not ready
kubectl rollout restart deployment <deployment>
```

**CrashSense Actions:**
- Extract service selector
- Find pods matching selector
- Check pod readiness status
- Report label mismatches

---

### Configuration Issues

#### Pending Pods
**Symptoms:**
- Pod stuck in Pending state
- Not scheduled to any node

**Common Causes:**
1. Insufficient cluster resources
2. Node selector constraints not satisfied
3. Taints/tolerations mismatch
4. Volume provisioning issues

**Automated Remediation:**
```bash
# 1. Check pod events
kubectl describe pod <pod-name>

# 2. Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# 3. Remove restrictive node selectors
kubectl patch deployment <deployment> \
  --type=json -p='[{"op": "remove", "path": "/spec/template/spec/nodeSelector"}]'

# 4. Check PVC status if volume issues
kubectl get pvc -n <namespace>
```

**CrashSense Actions:**
- Analyze pod scheduling events
- Check node resource availability
- Identify constraint issues
- Recommend constraint removal or cluster scaling

---

## Prometheus Alert Integration

### High Pod Restart Rate
**Alert Rule:**
```yaml
alert: HighPodRestartRate
expr: rate(kube_pod_container_status_restarts_total[15m]) > 0.1
for: 5m
labels:
  severity: warning
annotations:
  description: "Pod {{ $labels.pod }} in namespace {{ $labels.namespace }} is restarting frequently"
```

**CrashSense Actions:**
- Detect via Prometheus query
- Analyze pod logs
- Apply CrashLoopBackOff remediation
- Silence alert after remediation

---

### Pod OOM
**Alert Rule:**
```yaml
alert: PodOOM
expr: kube_pod_container_status_terminated_reason{reason="OOMKilled"} > 0
for: 1m
labels:
  severity: critical
annotations:
  description: "Container in pod {{ $labels.pod }} was OOMKilled"
```

**CrashSense Actions:**
- Increase memory limits
- Check for memory leaks
- Enable memory profiling
- Recommend application optimization

---

### Service Down
**Alert Rule:**
```yaml
alert: ServiceDown
expr: kube_endpoint_address_available == 0
for: 5m
labels:
  severity: critical
annotations:
  description: "Service {{ $labels.service }} has no available endpoints"
```

**CrashSense Actions:**
- Check service selector
- Verify pod labels and status
- Restart pods if needed
- Fix label mismatches

---

## Best Practices for Self-Healing

### 1. Resource Limits
Always set resource requests and limits:
```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### 2. Liveness and Readiness Probes
Configure probes to enable automatic recovery:
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

### 3. PodDisruptionBudgets
Ensure availability during updates:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: myapp-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: myapp
```

### 4. Horizontal Pod Autoscaling
Enable automatic scaling:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 5. Health Check Endpoints
Implement proper health checks:
```python
# Flask example
@app.route('/healthz')
def healthz():
    # Check database connection, external services, etc.
    if all_systems_ok():
        return 'OK', 200
    return 'Service Unavailable', 503

@app.route('/ready')
def ready():
    # Check if ready to receive traffic
    if app.is_initialized and database.is_connected():
        return 'Ready', 200
    return 'Not Ready', 503
```

---

## CrashSense Configuration for Kubernetes

### Enable Kubernetes Monitoring
```toml
[kubernetes]
enabled = true
kubeconfig = "~/.kube/config"  # or null for in-cluster config
namespaces = ["production", "staging"]  # or [] for all
auto_heal = true
dry_run = false  # Set to true for safe testing
max_remediation_actions = 10
monitor_interval_seconds = 60
crash_time_window_minutes = 15
resource_threshold_percent = 85

[prometheus]
enabled = true
url = "http://prometheus.monitoring.svc:9090"
alertmanager_url = "http://alertmanager.monitoring.svc:9093"
metrics_port = 8000
```

### Usage Examples
```bash
# Check cluster health
crashsense k8s status

# One-time scan and remediation
crashsense k8s heal

# Continuous monitoring (with auto-heal)
crashsense k8s monitor --auto-heal

# Get and analyze pod logs
crashsense k8s logs my-pod --analyze

# Monitor specific namespaces
crashsense k8s monitor -n production -n staging
```

---

## Remediation Safety

CrashSense implements safety measures:

1. **Dry Run Mode**: Test remediation without applying changes
2. **Action Limits**: Maximum actions per cycle to prevent runaway automation
3. **Confirmation Prompts**: Interactive mode requires user confirmation
4. **Audit Trail**: All actions logged with timestamps
5. **Metrics**: Prometheus metrics for monitoring remediation effectiveness
6. **Rollback Support**: Some actions can be reverted if issues persist

### Safe Remediation Workflow
1. Monitor detects issue
2. Analyze root cause with AI
3. Determine remediation action
4. Apply fix (or simulate in dry-run)
5. Verify fix effectiveness
6. Record metrics and logs
7. Alert if remediation fails

---

## Integration with CI/CD

### Pre-deployment Health Check
```bash
# In CI/CD pipeline before deployment
crashsense k8s status || exit 1
```

### Post-deployment Monitoring
```bash
# After deployment, monitor for 5 minutes
timeout 300 crashsense k8s monitor --namespace production
```

### Alertmanager Webhook
Configure Alertmanager to send webhooks to CrashSense for automated remediation:
```yaml
receivers:
  - name: crashsense
    webhook_configs:
      - url: 'http://crashsense.default.svc:9094/webhook'
        send_resolved: true
```

---

## Troubleshooting CrashSense

### Cannot Connect to Kubernetes
```bash
# Check kubeconfig
kubectl cluster-info

# Verify permissions
kubectl auth can-i get pods --all-namespaces

# Test with explicit kubeconfig
crashsense k8s status --kubeconfig ~/.kube/config
```

### Prometheus Metrics Not Available
```bash
# Check if metrics-server is installed
kubectl get deployment metrics-server -n kube-system

# Install metrics-server if missing
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Remediation Not Working
```bash
# Test in dry-run mode
crashsense k8s heal --dry-run

# Check logs
kubectl logs -n default <crashsense-pod>

# Verify RBAC permissions
kubectl auth can-i delete pods --all-namespaces
kubectl auth can-i patch deployments --all-namespaces
```
