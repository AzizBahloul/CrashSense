# 🚀 CrashSense - Self-Healing Kubernetes Platform

<div align="center">

**AI-Powered Kubernetes Monitoring with Automated Crash Detection & Remediation**

[![PyPI](https://img.shields.io/pypi/v/crashsense?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/crashsense/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.28%2B-326CE5?logo=kubernetes&logoColor=white)](https://kubernetes.io)

*Automatically detect and remediate Kubernetes pod crashes, resource exhaustion, and network failures*

[**🚀 Install from PyPI**](https://pypi.org/project/crashsense/) • [**📖 Documentation**](#quickstart) • [**💬 Support**](#support--donations)

</div>

---

## ✨ What is CrashSense?

CrashSense is a comprehensive **self-healing Kubernetes platform** that combines AI-powered log analysis with automated remediation for containerized workloads. Originally designed for crash log analysis, it now provides enterprise-grade Kubernetes cluster monitoring, intelligent issue detection, and autonomous healing capabilities.

### 🎯 Key Use Cases

| Use Case | Description |
|----------|-------------|
| 🔄 **Self-Healing K8s** | Automatically detect and fix pod crashes, OOMKilled containers, and CrashLoopBackOff |
| 📊 **Resource Management** | Monitor and remediate resource exhaustion (CPU/memory limits) |
| 🌐 **Network Reliability** | Detect service endpoint failures and network issues |
| 📈 **Prometheus Integration** | Collect metrics and integrate with Alertmanager for comprehensive monitoring |
| 🧠 **AI-Powered Analysis** | Leverage LLMs to analyze crash logs and suggest intelligent fixes |
| 🖥️ **Traditional Monitoring** | Support for web servers, system logs, and CI/CD pipelines |

---

## 🌟 Features & Highlights

<table>
<tr>
<td width="50%">

### 🔍 **Kubernetes Monitoring**
- Pod crash detection (CrashLoopBackOff, OOMKilled)
- Resource exhaustion monitoring
- Network failure detection
- Real-time cluster health checks
- Multi-namespace support

### 🏥 **Self-Healing**
- Automated pod restart/deletion
- Memory limit auto-scaling
- Service endpoint remediation
- Deployment rollout management
- Configurable dry-run mode

</td>
<td width="50%">

### 📊 **Observability**
- Prometheus metrics exposure
- Alertmanager integration
- Custom metric collection
- Webhook receivers for alerts
- Historical trend analysis

### 🧠 **AI-Powered**
- GPT/Ollama integration for log analysis
- Root cause identification
- Intelligent remediation suggestions
- RAG over documentation
- Context-aware fixes

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI with Kubernetes support
pip install crashsense

# Or install from source (development)
git clone https://github.com/AzizBahloul/CrashSense.git
cd CrashSense
pip install -e .
```

### Initial Setup

```bash
# Initialize and configure LLM provider
crashsense init
```

Choose your preferred provider:
- **OpenAI GPT** (recommended for accuracy)
- **Local Ollama** (privacy-focused, no API costs)

### Kubernetes Setup

Enable Kubernetes monitoring in `~/.crashsense/config.toml`:

```toml
[kubernetes]
enabled = true
kubeconfig = null  # Uses default ~/.kube/config
namespaces = []  # Monitor all namespaces, or specify: ["production", "staging"]
auto_heal = true
dry_run = false  # Set to true for safe testing
max_remediation_actions = 10

[prometheus]
enabled = true
url = "http://localhost:9090"
alertmanager_url = "http://localhost:9093"
metrics_port = 8000
```

---

## 💻 Usage Examples

### Kubernetes Monitoring

#### Check Cluster Health
```bash
# View cluster status and health metrics
crashsense k8s status

# Check specific namespaces
crashsense k8s status -n production -n staging
```

#### One-Time Scan and Heal
```bash
# Detect and fix issues (with confirmation)
crashsense k8s heal

# Dry-run mode (simulate without applying changes)
crashsense k8s heal --dry-run
```

#### Continuous Monitoring
```bash
# Monitor cluster every 60 seconds
crashsense k8s monitor

# Enable auto-heal mode
crashsense k8s monitor --auto-heal

# Custom interval
crashsense k8s monitor --interval 30 --auto-heal
```

#### Pod Log Analysis
```bash
# Get pod logs
crashsense k8s logs my-pod -n production

# Analyze logs with AI
crashsense k8s logs my-pod --analyze

# Previous container logs (for crashed pods)
crashsense k8s logs my-pod --previous --analyze
```

### Traditional Log Analysis

```bash
# Auto-detect and analyze latest crash log
crashsense

# Analyze specific log file
crashsense analyze /var/log/myapp/error.log

# Interactive TUI mode
crashsense tui
```

---

## 🔧 Kubernetes Remediation Capabilities

CrashSense automatically handles common Kubernetes issues:

### Pod Crash Issues
- **CrashLoopBackOff**: Analyzes logs, deletes pods with high restart counts
- **ImagePullBackOff**: Checks image pull secrets and registry configuration
- **OOMKilled**: Increases memory limits automatically (50% increase)
- **CreateContainerError**: Identifies configuration issues

### Resource Exhaustion
- **High Memory**: Auto-scales memory limits and enables HPA
- **High CPU**: Scales deployment replicas
- **Quota Exceeded**: Recommends quota adjustments

### Network Issues
- **No Service Endpoints**: Verifies pod selectors and labels
- **Service Unavailable**: Checks pod readiness and restarts if needed

### Configuration Issues
- **Pending Pods**: Analyzes scheduling constraints and node resources
- **Failed Mounts**: Identifies PVC and volume issues

---

## 📊 Prometheus & Alertmanager Integration

### Expose Metrics

CrashSense exposes Prometheus metrics:

```bash
# Metrics available at http://localhost:8000/metrics
```

**Available Metrics:**
- `crashsense_pod_crashes_total` - Total pod crashes detected
- `crashsense_remediations_total` - Total remediation actions taken
- `crashsense_pod_health` - Pod health status (0/1)
- `crashsense_cluster_health_score` - Overall cluster health (0-100)
- `crashsense_remediation_duration_seconds` - Remediation action duration

### Alertmanager Webhook

Configure Alertmanager to trigger CrashSense remediation:

```yaml
receivers:
  - name: crashsense
    webhook_configs:
      - url: 'http://crashsense:9094/webhook'
        send_resolved: true
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│           CrashSense Platform                    │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐      ┌──────────────┐        │
│  │ K8s Monitor  │◄────►│  Prometheus  │        │
│  │              │      │  Collector   │        │
│  └──────┬───────┘      └──────────────┘        │
│         │                                        │
│         ▼                                        │
│  ┌──────────────┐      ┌──────────────┐        │
│  │   Analyzer   │◄────►│  LLM Adapter │        │
│  │  (AI-Powered)│      │ (GPT/Ollama) │        │
│  └──────┬───────┘      └──────────────┘        │
│         │                                        │
│         ▼                                        │
│  ┌──────────────┐      ┌──────────────┐        │
│  │ Remediation  │◄────►│   Memory     │        │
│  │   Engine     │      │    Store     │        │
│  └──────────────┘      └──────────────┘        │
│                                                  │
├─────────────────────────────────────────────────┤
│         CLI / TUI / API Interface                │
└─────────────────────────────────────────────────┘
         ▲                       ▲
         │                       │
    Kubernetes API         Alertmanager
```

---

## 🛡️ Safety Features

CrashSense implements multiple safety layers:

1. **Dry-Run Mode**: Test remediation without applying changes
2. **Action Limits**: Maximum actions per cycle (default: 10)
3. **Confirmation Prompts**: Interactive mode requires user approval
4. **Audit Trail**: All actions logged with timestamps and results
5. **Rollback Support**: Failed actions can be reverted
6. **RBAC Integration**: Respects Kubernetes permissions

---

## 📋 Requirements

### System Requirements
- Python 3.8+
- Kubernetes cluster (1.28+) with kubectl access
- Optional: Prometheus & Alertmanager for metrics

### Kubernetes Permissions
CrashSense requires these RBAC permissions:

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

---

## 🎓 Advanced Usage

### Custom Remediation Policies

Create custom remediation logic:

```python
from crashsense.core.k8s_monitor import KubernetesMonitor
from crashsense.core.remediation import RemediationEngine

# Initialize
monitor = KubernetesMonitor()
engine = RemediationEngine(monitor, dry_run=False)

# Detect issues
crashes = monitor.detect_pod_crashes()

# Apply remediation
for crash in crashes:
    result = engine.remediate_issue(crash)
    print(f"Remediation: {result}")
```

### RAG Document Management

Add Kubernetes documentation for better analysis:

```bash
# Add custom documentation
crashsense rag add /path/to/k8s-docs

# Build RAG index
crashsense rag build

# Clear and rebuild
crashsense rag clear
crashsense rag add ./kubernetes-playbooks
```

### Memory Management

View and manage crash analysis history:

```bash
# List recent crash analyses
crashsense memory

# Stored in SQLite: ~/.crashsense/memories.db
```

---

## 🔌 Integration Examples

### CI/CD Pipeline

```yaml
# GitLab CI example
k8s-health-check:
  stage: post-deploy
  script:
    - pip install crashsense
    - crashsense k8s status || exit 1
    - crashsense k8s heal --dry-run
```

### Monitoring Dashboard

```python
# Flask webhook receiver
from flask import Flask, request
from crashsense.core.remediation import RemediationEngine

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def alertmanager_webhook():
    alert = request.json
    # Trigger remediation based on alert
    engine.remediate_issue(alert)
    return {'status': 'ok'}
```

---

## 📚 Documentation

- [Kubernetes Remediation Playbook](src/data/kubernetes_remediation_playbook.md)
- [Python Exceptions Guide](src/data/python_exceptions_playbook.md)
- [Web Server Patterns](src/data/web_server_error_patterns.md)

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with:
- [Kubernetes Python Client](https://github.com/kubernetes-client/python)
- [Prometheus Client](https://github.com/prometheus/client_python)
- [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- OpenAI GPT & Ollama for AI-powered analysis

---

<div align="center">

**Made with ❤️ by Mohamed Aziz Bahloul**

⭐ Star this repo if you find it useful!

</div> 

# Analyze specific file
crashsense analyze /var/log/apache2/error.log

# Pipe from STDIN
tail -f /var/log/syslog | crashsense analyze

# Launch interactive TUI
crashsense tui
```

---

## 📸 Screenshots & Workflow

### 🔄 Startup & Device Detection
*CrashSense initializing and detecting compute resources*

![Startup & Device Detection](image1.png)

### 🔍 Crash Log Analysis & Explanation
*AI-powered analysis showing parsed information and remediation steps*

![Crash Log Analysis & Explanation](image2.png)

### 📊 Summary Table & Command Suggestions
*Actionable summary with safe shell command recommendations*

![Summary Table & Command Suggestions](image3.png)

---

## 📚 RAG Documentation (Optional)

CrashSense can leverage your existing documentation for more contextual analysis:

### 📁 **Default Knowledge Base**
```
kb/                              # Your custom docs
src/data/
├── crashsense_best_practices.md
├── python_exceptions_playbook.md
├── web_server_error_patterns.md
└── linux_permission_paths.md
```

### 🛠️ **Manage Documentation**

```bash
# Add custom documentation
crashsense rag add /path/to/docs/

# Clear knowledge base
crashsense rag clear

# Rebuild with dry-run preview
crashsense rag build --dry-run
```

---

## ⚙️ Configuration & Security

### 📝 Configuration File
```toml
# ~/.crashsense/config.toml
[llm]
provider = "openai"  # or "ollama"
model = "gpt-4"

[security]
safe_mode = true
confirm_commands = true
```

### 🔐 Environment Variables
```bash
export CRASHSENSE_OPENAI_KEY="your-api-key-here"
```

### 🛡️ Security Features
- ✅ Command execution requires explicit confirmation
- ✅ Built-in safety checks and validation
- ✅ Configurable security policies
- ✅ Audit trail for executed commands

---

## 🔧 Troubleshooting

### Ollama Setup Issues
```bash
# Manual model pull
ollama pull llama3.2:1b

# Check daemon status
ollama serve

# Verify installation
ollama list
```

For more help, visit the [Ollama Documentation](https://ollama.com/docs)

---

## 💝 Support & Donations

If CrashSense has helped streamline your debugging workflow, consider supporting continued development:

<div align="center">

| Platform | ID |
|----------|-----|
| 💳 **RedotPay** | `1951109247` |
| 🟡 **Binance** | `1104913076` |

*Your support helps keep CrashSense free and continuously improving!*

</div>

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

⭐ **Star this repo** yar7am book!

</div>
