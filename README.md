# 🚀 CrashSense - Self-Healing Kubernetes Platform

<div align="center">

**Production-Ready Kubernetes Self-Healing Platform with AI-Powered Analysis**

[![PyPI version](https://img.shields.io/pypi/v/crashsense?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/crashsense/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.28%2B-326CE5?logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![Tests](https://img.shields.io/badge/tests-49%20passing-success)](tests/)

*Automatically detect, analyze, and remediate Kubernetes failures with intelligent automation*

[**Installation**](#installation) • [**Quick Start**](#quick-start) • [**Documentation**](#documentation) • [**Contributing**](#contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Kubernetes Operations](#kubernetes-operations)
  - [Log Analysis](#log-analysis)
  - [Configuration](#configuration)
- [Remediation Capabilities](#remediation-capabilities)
- [Architecture](#architecture)
- [Prometheus Integration](#prometheus-integration)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

**CrashSense** is an enterprise-grade self-healing platform for Kubernetes environments that combines intelligent monitoring, automated remediation, and AI-powered log analysis. It reduces MTTR (Mean Time To Recovery) by automatically detecting and resolving common Kubernetes issues without human intervention.

### Why CrashSense?

- **🔄 Autonomous Healing**: Automatically remediate CrashLoopBackOff, OOMKilled, and ImagePullBackOff issues
- **📊 Production-Ready**: Battle-tested with comprehensive test coverage (49 tests)
- **🧠 AI-Powered**: Leverage GPT or Ollama for intelligent root cause analysis
- **📈 Observable**: Full Prometheus metrics and Alertmanager integration
- **🛡️ Safe**: Built-in dry-run mode, action limits, and audit trails
- **⚡ Fast**: Real-time monitoring with sub-second detection
- **🔧 Extensible**: Plugin architecture for custom remediation policies

### Use Cases

| Scenario | Solution |
|----------|----------|
| **Pod Crash Loops** | Automatic log analysis, pod deletion, and deployment fixes |
| **Memory Issues** | Dynamic memory limit scaling and OOMKilled prevention |
| **Image Problems** | Pull secret verification and registry health checks |
| **Network Failures** | Service endpoint remediation and connectivity testing |
| **Resource Exhaustion** | Auto-scaling and quota management |
| **SRE Automation** | Reduce on-call burden with intelligent auto-remediation |

---

## ✨ Key Features

### Kubernetes Self-Healing

<table>
<tr>
<td width="50%" valign="top">

**🔍 Intelligent Monitoring**
- Real-time pod crash detection
- CrashLoopBackOff identification
- OOMKilled tracking
- ImagePullBackOff detection
- Network failure analysis
- Resource exhaustion monitoring
- Multi-namespace support
- Cluster health scoring

</td>
<td width="50%" valign="top">

**🏥 Automated Remediation**
- Pod restart/deletion
- Memory limit auto-adjustment (+50%)
- Service endpoint healing
- Image pull secret verification
- Deployment rollout management
- Resource quota optimization
- Configurable action limits
- Dry-run simulation mode

</td>
</tr>
</table>

### Observability & Integration

- **📊 Prometheus Metrics**: Expose crash rates, remediation counts, cluster health
- **🔔 Alertmanager**: Webhook receiver for alert-driven remediation
- **📝 Audit Logging**: Complete action history with timestamps
- **🎯 Custom Metrics**: Define and track your own SLIs/SLOs
- **🔗 API Integration**: RESTful endpoints for external tools

### AI-Powered Analysis

- **🤖 LLM Integration**: GPT-4, GPT-3.5, or local Ollama models
- **📚 RAG Support**: Leverage documentation for contextual analysis
- **🎯 Root Cause Detection**: Identify failure patterns automatically
- **💡 Smart Recommendations**: Actionable remediation suggestions
- **📖 Knowledge Base**: Built-in playbooks for common issues

---

## 📦 Installation

### From PyPI (Recommended)

```bash
pip install crashsense
```

### From Source

```bash
git clone https://github.com/AzizBahloul/CrashSense.git
cd CrashSense
pip install -e ".[dev]"  # Install with development dependencies
```

### Docker

```bash
docker pull azizbahloul/crashsense:2.0.0
```

### Kubernetes Deployment

```bash
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### Verification

```bash
crashsense --help
python3 -c "import crashsense; print(crashsense.__version__)"
```

---

## 🚀 Quick Start

### 1. Initial Setup

```bash
# Interactive configuration wizard
crashsense init
```

Select your LLM provider:
- **OpenAI** (GPT-4, GPT-3.5-turbo) - Best accuracy
- **Ollama** (llama3.2, mistral) - Privacy-focused, no API costs

### 2. Configure Kubernetes Monitoring

Edit `~/.crashsense/config.toml`:

```toml
[kubernetes]
enabled = true
kubeconfig = null  # Uses default ~/.kube/config
namespaces = []  # Empty = all namespaces
auto_heal = true
dry_run = false  # Set true for testing
max_remediation_actions = 10

[prometheus]
enabled = true
url = "http://localhost:9090"
alertmanager_url = "http://localhost:9093"
metrics_port = 8000
```

### 3. Start Monitoring

```bash
# Check cluster status
crashsense k8s status

# One-time scan and heal
crashsense k8s heal

# Continuous monitoring with auto-heal
crashsense k8s monitor --auto-heal --interval 60
```

---

## 💻 Usage

### Kubernetes Operations

#### Cluster Health Check

```bash
# Overall cluster status
crashsense k8s status

# Specific namespaces
crashsense k8s status -n production -n staging

# JSON output for automation
crashsense k8s status --format json
```

#### Manual Remediation

```bash
# Scan and remediate (with confirmation prompts)
crashsense k8s heal

# Dry-run mode (preview actions without applying)
crashsense k8s heal --dry-run

# Specific namespace
crashsense k8s heal -n production
```

#### Continuous Monitoring

```bash
# Monitor every 60 seconds
crashsense k8s monitor

# Enable automatic remediation
crashsense k8s monitor --auto-heal

# Custom monitoring interval
crashsense k8s monitor --auto-heal --interval 30

# Multiple namespaces
crashsense k8s monitor -n prod -n staging --auto-heal
```

#### Pod Log Analysis

```bash
# View pod logs
crashsense k8s logs my-app-pod -n production

# Analyze with AI
crashsense k8s logs my-app-pod --analyze

# Previous container (for crashed pods)
crashsense k8s logs my-app-pod --previous --analyze

# Follow logs in real-time
crashsense k8s logs my-app-pod --follow
```

### Log Analysis

#### Traditional Crash Analysis

```bash
# Analyze log file
crashsense analyze /var/log/app/error.log

# Auto-detect latest crash
crashsense

# Interactive TUI mode
crashsense tui

# Pipe from stdin
tail -f /var/log/syslog | crashsense analyze
```

#### RAG Document Management

```bash
# Add custom documentation
crashsense rag add /path/to/kubernetes-docs

# Add multiple directories
crashsense rag add ./playbooks ./runbooks

# Build RAG index
crashsense rag build

# Clear and rebuild
crashsense rag clear
crashsense rag add ./updated-docs
crashsense rag build
```

#### Memory Management

```bash
# View crash analysis history
crashsense memory

# List recent analyses
crashsense memory --limit 20

# Export history
crashsense memory --export history.json
```

### Configuration

#### Configuration File Location

```bash
~/.crashsense/config.toml  # User configuration
~/.crashsense/memories.db  # SQLite database for history
```

#### Environment Variables

```bash
# OpenAI API Key
export OPENAI_API_KEY="sk-..."

# Ollama endpoint
export OLLAMA_HOST="http://localhost:11434"

# Kubernetes config
export KUBECONFIG="~/.kube/config"
```

#### Full Configuration Example

```toml
[provider]
selected = "openai"  # or "ollama"

[openai]
api_key = "sk-..."
model = "gpt-4"
temperature = 0.7

[ollama]
endpoint = "http://localhost:11434"
model = "llama3.2:1b"

[local]
model = "gpt-3.5-turbo"
temperature = 0.5

[memory]
enabled = true
db_path = "~/.crashsense/memories.db"
max_entries = 1000
auto_prune = true

[kubernetes]
enabled = true
kubeconfig = null
namespaces = ["production", "staging"]
auto_heal = true
dry_run = false
max_remediation_actions = 10

[prometheus]
enabled = true
url = "http://prometheus:9090"
alertmanager_url = "http://alertmanager:9093"
metrics_port = 8000

[rag]
enabled = true
chunk_size = 1000
chunk_overlap = 200
vector_store_path = "~/.crashsense/vectorstore"
```

---

## 🔧 Remediation Capabilities

CrashSense automatically handles these common Kubernetes issues:

### Pod Lifecycle Issues

| Issue | Detection | Remediation |
|-------|-----------|-------------|
| **CrashLoopBackOff** | Restart count > threshold | Analyze logs → Delete pod → Monitor recovery |
| **ImagePullBackOff** | Image pull failures | Verify secrets → Check registry → Suggest fixes |
| **OOMKilled** | Memory limit exceeded | Increase memory limit by 50% → Update deployment |
| **CreateContainerError** | Container creation fails | Parse error → Suggest configuration fixes |
| **Pending** | Pod not scheduled | Analyze constraints → Check node resources |

### Resource Management

| Issue | Detection | Remediation |
|-------|-----------|-------------|
| **High Memory Usage** | Memory > 90% | Scale memory limits → Enable HPA |
| **High CPU Usage** | CPU > 90% | Scale replicas → Optimize resources |
| **Disk Pressure** | Disk > 85% | Clean ephemeral storage → Expand PVs |
| **Quota Exceeded** | ResourceQuota hit | Recommend quota increase |

### Network Issues

| Issue | Detection | Remediation |
|-------|-----------|-------------|
| **No Endpoints** | Service has 0 endpoints | Verify selectors → Fix pod labels |
| **DNS Failures** | DNS resolution errors | Check CoreDNS → Verify service |
| **Connection Refused** | TCP connection fails | Check pod readiness → Restart if needed |

### Safety Features

- ✅ **Dry-Run Mode**: Preview all actions before applying
- ✅ **Action Limits**: Maximum remediation actions per cycle (default: 10)
- ✅ **Confirmation Prompts**: Interactive approval required
- ✅ **Audit Trail**: All actions logged with timestamps and results
- ✅ **Rollback Support**: Failed remediations can be reverted
- ✅ **RBAC Respect**: Honors Kubernetes permissions

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CrashSense Platform                       │
│                        (v2.0.0)                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │  KubernetesMonitor│◄─────►│ PrometheusCollector│         │
│  │   - Pod Watcher  │         │  - Metrics Export │          │
│  │   - Health Check │         │  - Alert Receiver │          │
│  │   - Log Fetcher  │         │  - Custom Metrics │          │
│  └────────┬─────────┘         └──────────────────┘          │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │  BackTrackEngine │◄─────►│   LLMAdapter     │          │
│  │   - Language ID  │         │  - OpenAI GPT    │          │
│  │   - Exception    │         │  - Ollama Local  │          │
│  │   - Stack Parse  │         │  - RAG Search    │          │
│  │   - RAG Enhance  │         │  - Context Build │          │
│  └────────┬─────────┘         └──────────────────┘          │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │ RemediationEngine│◄─────►│  MemoryStore     │          │
│  │   - Policy Match │         │  - SQLite DB     │          │
│  │   - Action Exec  │         │  - History Track │          │
│  │   - Dry-Run Test │         │  - Frequency Log │          │
│  │   - Audit Log    │         │  - Auto Prune    │          │
│  └─────────────────┘         └──────────────────┘          │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│            CLI / TUI / API / Webhook Interface               │
└─────────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
   Kubernetes API      Prometheus/             Alertmanager
    (CoreV1/AppsV1)    Metrics Server           Webhooks
```

### Components

- **KubernetesMonitor**: Watches cluster state, detects anomalies
- **PrometheusCollector**: Exposes metrics, receives alerts
- **BackTrackEngine**: Analyzes logs, identifies root causes
- **LLMAdapter**: Interfaces with AI models for analysis
- **RemediationEngine**: Executes healing actions safely
- **MemoryStore**: Persists analysis history and patterns

---

## 📊 Prometheus Integration

### Exposed Metrics

CrashSense exposes metrics on port 8000 by default:

```bash
curl http://localhost:8000/metrics
```

#### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `crashsense_pod_crashes_total` | Counter | Total pod crashes detected by namespace/pod |
| `crashsense_remediations_total` | Counter | Total remediation actions by type/status |
| `crashsense_pod_health` | Gauge | Pod health status (0=unhealthy, 1=healthy) |
| `crashsense_cluster_health_score` | Gauge | Overall cluster health (0-100) |
| `crashsense_remediation_duration_seconds` | Histogram | Time to complete remediation |
| `crashsense_active_issues` | Gauge | Current number of detected issues |

### Alertmanager Integration

Configure Alertmanager to trigger CrashSense remediation:

```yaml
# alertmanager.yml
receivers:
  - name: 'crashsense'
    webhook_configs:
      - url: 'http://crashsense-service:9094/webhook'
        send_resolved: true
        http_config:
          basic_auth:
            username: 'crashsense'
            password: 'secure-password'

route:
  group_by: ['alertname', 'namespace']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'crashsense'
  routes:
    - match:
        severity: critical
      receiver: 'crashsense'
```

### Grafana Dashboard

Import the provided dashboard for visualization:

```bash
# Coming soon: grafana-dashboard.json
```

---

## 🚢 Deployment

### Kubernetes Deployment

Deploy CrashSense in your cluster for production use:

```bash
# Apply RBAC (required permissions)
kubectl apply -f k8s/rbac.yaml

# Deploy CrashSense
kubectl apply -f k8s/deployment.yaml

# Expose metrics service
kubectl apply -f k8s/service.yaml

# Configure via ConfigMap
kubectl apply -f k8s/configmap.yaml
```

#### Required RBAC Permissions
#### Required RBAC Permissions

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: crashsense
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "services", "endpoints"]
    verbs: ["get", "list", "watch", "delete"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "patch"]
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["pods", "nodes"]
    verbs: ["get", "list"]
```

### Local Development

```bash
# Clone repository
git clone https://github.com/AzizBahloul/CrashSense.git
cd CrashSense

# Install in development mode with test dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=crashsense --cov-report=html

# Format code
black src/ tests/

# Type checking
mypy src/
```

### CI/CD Integration

#### GitHub Actions Example

```yaml
name: K8s Health Check
on: [push]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install CrashSense
        run: pip install crashsense
      
      - name: Check Cluster Health
        run: |
          crashsense k8s status
          crashsense k8s heal --dry-run
        env:
          KUBECONFIG: ${{ secrets.KUBECONFIG }}
```

#### GitLab CI Example

```yaml
k8s-health-check:
  stage: post-deploy
  image: python:3.11
  script:
    - pip install crashsense
    - crashsense k8s status || exit 1
    - crashsense k8s heal --dry-run
  only:
    - main
```

---

## 📚 Documentation

### Knowledge Base

CrashSense includes comprehensive built-in documentation:

- **[Kubernetes Remediation Playbook](src/data/kubernetes_remediation_playbook.md)** - Complete guide to K8s issue resolution
- **[Python Exceptions Guide](src/data/python_exceptions_playbook.md)** - Python error analysis and fixes
- **[Web Server Patterns](src/data/web_server_error_patterns.md)** - Apache, Nginx, HTTP error handling
- **[Linux Permissions](src/data/linux_permission_paths.md)** - File system and permission issues

### API Reference

#### Python API

```python
from crashsense.core.k8s_monitor import KubernetesMonitor
from crashsense.core.remediation import RemediationEngine
from crashsense.core.analyzer import BackTrackEngine

# Initialize Kubernetes monitoring
monitor = KubernetesMonitor(namespaces=['production'])
info = monitor.get_cluster_info()
crashes = monitor.detect_pod_crashes()

# Initialize remediation engine
engine = RemediationEngine(monitor, dry_run=False)
results = []

for crash in crashes:
    result = engine.remediate_issue(crash)
    results.append(result)
    print(f"Remediated {crash['name']}: {result['success']}")

# Analyze logs with AI
analyzer = BackTrackEngine(provider="openai")
analysis = analyzer.analyze("Error log content...")
print(f"Root cause: {analysis['summary']}")
```

#### REST API (Coming Soon)

```bash
# Health check
GET /health

# Cluster status
GET /api/v1/k8s/status

# Trigger remediation
POST /api/v1/k8s/heal

# Metrics
GET /metrics
```

### Configuration Reference

See the [complete configuration guide](.github/SETUP_GUIDE.md) for all options.

---

## 🔬 Advanced Usage

### Custom Remediation Policies

Extend CrashSense with custom remediation logic:

```python
from crashsense.core.remediation import RemediationEngine

class CustomRemediationEngine(RemediationEngine):
    def remediate_issue(self, issue):
        # Custom logic here
        if issue['type'] == 'CustomError':
            # Your remediation
            return {'success': True, 'actions_taken': ['custom_fix']}
        return super().remediate_issue(issue)

# Use custom engine
engine = CustomRemediationEngine(monitor)
engine.auto_heal(issues)
```

### Prometheus Query Examples

```promql
# Crash rate by namespace (last hour)
rate(crashsense_pod_crashes_total[1h])

# Remediation success rate
sum(rate(crashsense_remediations_total{status="success"}[5m])) 
/ 
sum(rate(crashsense_remediations_total[5m]))

# Cluster health trend
avg_over_time(crashsense_cluster_health_score[1h])

# Alert on high crash rate
ALERT HighCrashRate
  IF rate(crashsense_pod_crashes_total[5m]) > 0.5
  FOR 5m
  LABELS { severity="critical" }
```

### Webhook Integration

Create custom webhook handlers:

```python
from flask import Flask, request
from crashsense.core.remediation import RemediationEngine

app = Flask(__name__)
engine = RemediationEngine(monitor)

@app.route('/webhook', methods=['POST'])
def alertmanager_webhook():
    """Handle Alertmanager webhooks"""
    alert = request.json
    
    # Extract alert details
    for alert_item in alert.get('alerts', []):
        labels = alert_item.get('labels', {})
        
        # Create issue from alert
        issue = {
            'type': labels.get('alertname'),
            'name': labels.get('pod'),
            'namespace': labels.get('namespace'),
            'severity': labels.get('severity')
        }
        
        # Trigger remediation
        result = engine.remediate_issue(issue)
        
    return {'status': 'processed'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9094)
```

---

## 🧪 Testing

CrashSense includes comprehensive test coverage:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_k8s_monitor.py -v

# Run with coverage
pytest tests/ --cov=crashsense --cov-report=html
open htmlcov/index.html

# Run only K8s tests
pytest tests/test_k8s_monitor.py tests/test_remediation.py -v

# Run with markers
pytest -m "not slow" tests/
```

### Test Statistics

- **Total Tests**: 49
- **Coverage**: 85%+
- **Test Categories**:
  - Kubernetes monitoring (7 tests)
  - Remediation engine (8 tests)
  - Log analyzer (11 tests)
  - Configuration (7 tests)
  - CLI commands (8 tests)
  - Integration (8 tests)

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/CrashSense.git
cd CrashSense

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"

# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
pytest tests/ -v
black src/ tests/
mypy src/

# Commit and push
git commit -m "feat: add your feature"
git push origin feature/your-feature
```

### Contribution Areas

- 🐛 Bug fixes and issue resolution
- ✨ New remediation policies
- 📝 Documentation improvements
- 🧪 Test coverage expansion
- 🎨 UI/UX enhancements
- 🌍 Translations

---

## 📊 Project Status

### Roadmap

- [x] Core Kubernetes monitoring
- [x] Automated remediation
- [x] Prometheus integration
- [x] AI-powered log analysis
- [x] Comprehensive testing
- [x] PyPI publication
- [ ] REST API endpoints
- [ ] Grafana dashboards
- [ ] Multi-cluster support
- [ ] Cost optimization features
- [ ] Slack/Teams notifications
- [ ] Advanced ML-based predictions

### Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

**Latest Release: v2.0.0**
- ✨ Complete Kubernetes self-healing platform
- ✨ Prometheus metrics and Alertmanager integration
- ✨ AI-powered crash analysis with RAG
- ✨ 49 comprehensive tests (100% passing)
- ✨ Published to PyPI
- ✨ Docker and Kubernetes deployment support

---

## 🐛 Troubleshooting

### Common Issues

#### Ollama Connection Failed

```bash
# Check Ollama is running
ollama serve

# Pull model if not available
ollama pull llama3.2:1b

# Verify endpoint
curl http://localhost:11434/api/tags
```

#### Kubernetes Authentication

```bash
# Verify kubeconfig
kubectl cluster-info

# Check permissions
kubectl auth can-i get pods --all-namespaces

# Test connection
kubectl get nodes
```

#### Prometheus Not Scraping

```yaml
# Add to prometheus.yml
scrape_configs:
  - job_name: 'crashsense'
    static_configs:
      - targets: ['crashsense-service:8000']
```

### Debug Mode

```bash
# Enable verbose logging
export CRASHSENSE_LOG_LEVEL=DEBUG
crashsense k8s status

# Check configuration
cat ~/.crashsense/config.toml

# View logs
tail -f ~/.crashsense/crashsense.log
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

- [Kubernetes Python Client](https://github.com/kubernetes-client/python) - Apache 2.0
- [Prometheus Client](https://github.com/prometheus/client_python) - Apache 2.0
- [Rich](https://github.com/Textualize/rich) - MIT
- [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) - MIT
- [Click](https://github.com/pallets/click) - BSD-3-Clause

---

## 🙏 Acknowledgments

CrashSense is built with these excellent open-source projects:

- **Kubernetes Python Client** - Kubernetes API interactions
- **Prometheus Client** - Metrics collection and export
- **Rich** - Beautiful terminal output and TUI
- **SQLAlchemy** - Database ORM for history storage
- **Click** - CLI framework
- **Flask** - Webhook receiver
- **OpenAI** - GPT models for analysis
- **Ollama** - Local LLM support

Special thanks to all contributors and the open-source community!

---

## 💝 Support

If CrashSense helps improve your operations, consider supporting development:

<div align="center">

[![Star on GitHub](https://img.shields.io/github/stars/AzizBahloul/CrashSense?style=social)](https://github.com/AzizBahloul/CrashSense)

</div>

### Contact & Support

- 📧 **Email**: azizbahloul3@gmail.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/AzizBahloul/CrashSense/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/AzizBahloul/CrashSense/discussions)
- 📖 **Documentation**: [Setup Guide](.github/SETUP_GUIDE.md)

---

<div align="center">

**Made with ❤️ by [Mohamed Aziz Bahloul](https://github.com/AzizBahloul)**

[![GitHub](https://img.shields.io/badge/GitHub-AzizBahloul-181717?logo=github)](https://github.com/AzizBahloul)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?logo=linkedin)](https://linkedin.com/in/azizbahloul)

⭐ **Star this repository if you find it useful!** ⭐

[Report Bug](https://github.com/AzizBahloul/CrashSense/issues) • [Request Feature](https://github.com/AzizBahloul/CrashSense/issues) • [Contribute](CONTRIBUTING.md)

</div>
