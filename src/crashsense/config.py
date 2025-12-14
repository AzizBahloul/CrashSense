from pathlib import Path
import toml

DEFAULT_CONFIG = {
    "provider": "auto",  # auto, openai, ollama
    "local": {"ollama_path": None, "model": "llama3.2:1b"},
    "memory": {
        "path": str(Path.home() / ".crashsense" / "memories.db"),
        "max_entries": 1000,
        "retention_days": 365,
    },
    "security": {"use_keyring": True},
    "last": {"last_log": str(Path.home() / ".crashsense" / "last.log")},
    "rag": {
        "enabled": True,
        "docs": [
            str(Path.cwd() / "kb"),
            str(Path.cwd() / "src" / "data" / "crashsense_best_practices.md"),
            str(Path.cwd() / "src" / "data" / "python_exceptions_playbook.md"),
            str(Path.cwd() / "src" / "data" / "web_server_error_patterns.md"),
            str(Path.cwd() / "src" / "data" / "linux_permission_paths.md"),
            str(Path.cwd() / "src" / "data" / "kubernetes_remediation_playbook.md"),
        ],
        "chunk_chars": 800,
        "chunk_overlap": 120,
        "top_k": 3,
    },
    "kubernetes": {
        "enabled": False,
        "kubeconfig": None,  # None for default ~/.kube/config
        "namespaces": [],  # Empty list means all namespaces
        "auto_heal": False,
        "dry_run": True,
        "max_remediation_actions": 10,
        "monitor_interval_seconds": 60,
        "crash_time_window_minutes": 15,
        "resource_threshold_percent": 85,
    },
    "prometheus": {
        "enabled": False,
        "url": "http://localhost:9090",
        "alertmanager_url": "http://localhost:9093",
        "metrics_port": 8000,
        "scrape_interval_seconds": 15,
    },
}

CONFIG_PATH = Path.home() / ".crashsense" / "config.toml"


def ensure_config_dir():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_config_dir()
    if CONFIG_PATH.exists():
        try:
            data = toml.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg = DEFAULT_CONFIG.copy()
            # deep-ish merge for keys we care about
            for k, v in data.items():
                if isinstance(v, dict) and k in cfg:
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            return cfg
        except Exception:
            return DEFAULT_CONFIG
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG


def save_config(cfg: dict):
    ensure_config_dir()
    CONFIG_PATH.write_text(toml.dumps(cfg), encoding="utf-8")
