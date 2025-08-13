# src/crashsense/utils.py
from pathlib import Path
import shutil
import subprocess
import shlex
from typing import Tuple
from rich.console import Console

console = Console()


def read_file(path: str) -> str:
    """
    Reads the content of a file, trying multiple encodings if necessary.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    encodings = ["utf-8", "iso-8859-1", "latin-1"]
    for encoding in encodings:
        try:
            return p.read_text(encoding=encoding)
        except UnicodeDecodeError:
            # Do not print to user, just try next encoding
            pass
    raise UnicodeDecodeError(
        "all",
        b"",
        0,
        0,
        f"Unable to decode file {path} with supported encodings: {encodings}",
    )


def short_print(text: str, max_len=200):
    return text if len(text) <= max_len else text[:max_len] + "…"


def safe_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_", ".")).rstrip()


def is_executable_on_path(name: str) -> bool:
    return shutil.which(name) is not None


def write_last_log(path: str, content: str):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def get_ollama_version() -> str:
    """
    Returns the version of the installed Ollama CLI, or None if not found.
    """
    try:
        result = subprocess.run(
            ["ollama", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        return None
    except Exception:
        return None
    return None


def detect_last_log(
    directories=None,
    extensions=(".log", ".txt"),
    exclude_patterns=None,
) -> str:
    """
    Detect the most recently modified log file in the given directories.
    Searches recursively for files with the specified extensions.
    """
    if directories is None:
        directories = [
            str(Path.home()),
            "/var/log",
        ]  # Limit search to common log directories
    if exclude_patterns is None:
        exclude_patterns = [
            "google-chrome",
            "extension state",
            ".cache/",
        ]
    try:
        files = []
        for directory in directories:
            dir_path = Path(directory)
            if dir_path.exists() and dir_path.is_dir():
                for f in dir_path.rglob("*"):
                    try:
                        if f.suffix.lower() in extensions:
                            path_lower = str(f).lower()
                            if any(pat in path_lower for pat in exclude_patterns):
                                continue
                            files.append(f)
                    except Exception:
                        continue
        if not files:
            return None
        # Consider only recent candidates to limit IO
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        candidates = files[:200]

        def score_file(p: Path) -> float:
            s = 0.0
            name = p.name.lower()
            path_str = str(p).lower()
            # Filename hints
            for kw, w in (("error", 3), ("crash", 3), ("exception", 3), ("trace", 2), ("fail", 2)):
                if kw in name:
                    s += w
            # Penalize noisy app data (e.g., Chrome extension state)
            if any(bad in path_str for bad in [
                "google-chrome/",
                "extension state",
                "chrome",
                "/.cache/",
            ]):
                s -= 5
            # Recency
            try:
                mtime = p.stat().st_mtime
                s += (mtime / 1e9)  # monotonic-ish scaling without heavy math
            except Exception:
                pass
            # Content sample
            try:
                head = p.read_bytes()[:4096]
                text = head.decode("utf-8", errors="ignore").lower()
                # Python
                if "traceback (most recent call last)" in text:
                    s += 5
                if "error" in text or "exception" in text or "fatal" in text or "stack trace" in text:
                    s += 2
                # Apache
                if "[error] [client" in text or "mod_wsgi" in text or "apache2" in text:
                    s += 3
                # Nginx
                if "nginx" in text and "[error]" in text:
                    s += 3
                # System
                if "/var/log/" in text or "kernel:" in text or "systemd" in text:
                    s += 2
                # Skip files with no crash/error pattern
                if s == 0:
                    return -1
            except Exception:
                return -1
            return s

        best = max(candidates, key=score_file)
        # Ensure not obviously irrelevant
        if score_file(best) <= 0:
            return None
        return str(best)
    except Exception as e:
        console.print(f"[red]Error detecting last log: {e}[/red]")
        return None


def read_terminal_history(limit=50) -> str:
    """
    Read the last `limit` commands from the terminal history.
    """
    try:
        # Prefer reading bash history files directly to avoid invoking a shell.
        candidates = [
            Path.home() / ".bash_history",
            Path.home() / ".zsh_history",
            Path.home() / ".history",
        ]
        for f in candidates:
            if f.exists() and f.is_file():
                try:
                    # Large files: read only the tail efficiently
                    with f.open("r", encoding="utf-8", errors="ignore") as fh:
                        lines = fh.read().splitlines()
                        return "\n".join(lines[-limit:])
                except Exception:
                    continue
        return ""
    except Exception:
        return ""


def check_ollama_running() -> bool:
    """
    Check if the Ollama binary is available on the system PATH.
    """
    return is_executable_on_path("ollama")


def pull_ollama_model(model_name: str) -> bool:
    """
    Pull/download a model using the Ollama CLI.
    """
    try_cmds = [
        ["ollama", "pull", model_name],
        ["ollama", "install", model_name],
        ["ollama", "fetch", model_name],
        ["ollama", "run", model_name, "--pull"],
    ]
    for cmd in try_cmds:
        try:
            console.print(f"[cyan]Trying: {' '.join(cmd)}[/cyan]")
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if cp.returncode == 0:
                console.print("[green]Model pulled successfully.[/green]")
                return True
            else:
                console.print(
                    f"[yellow]Command returned non-zero: {cp.returncode} — {cp.stderr[:200]}[/yellow]"
                )
        except FileNotFoundError:
            console.print(
                "[red]`ollama` binary not found on PATH while pulling model.[/red]"
            )
            return False
        except subprocess.TimeoutExpired:
            console.print(
                f"[red]Command '{' '.join(cmd)}' timed out after 600 seconds.[/red]"
            )
        except Exception as e:
            console.print(f"[red]Error while pulling model: {e}[/red]")
    console.print(
        "[red]All attempts to pull the model failed. Please try again later or manually download the model.[/red]"
    )
    return False


def has_shell_metacharacters(cmd: str) -> bool:
    """
    Detect common shell metacharacters that indicate complex shell expressions
    (pipes, redirects, command substitution, backgrounding, etc.).
    If present, we should not attempt to run with shell=False.
    """
    # Minimal, conservative set
    forbidden = ["|", "&", ";", ">", "<", "`", "$(", ")", "(", "\n"]
    return any(ch in cmd for ch in forbidden)


def run_command_safe(cmd: str, timeout: int = 600) -> Tuple[int, str, str]:
    """
    Run a simple command safely without invoking a shell.
    Rejects commands containing shell metacharacters.
    Returns (returncode, stdout, stderr).
    """
    if has_shell_metacharacters(cmd):
        return (127, "", "Unsafe shell metacharacters detected; refusing to run.")
    try:
        parts = shlex.split(cmd)
    except Exception as e:
        return (127, "", f"Failed to parse command: {e}")
    if not parts:
        return (0, "", "")
    try:
        cp = subprocess.run(parts, capture_output=True, text=True, timeout=timeout)
        return (cp.returncode, cp.stdout, cp.stderr)
    except FileNotFoundError as e:
        return (127, "", str(e))
    except subprocess.TimeoutExpired:
        return (124, "", "Command timed out")
    except Exception as e:
        return (1, "", str(e))


def create_fake_log(directory: str, filename: str = "fake_log.log") -> str:
    """
    Create a fake log file for testing purposes.
    """
    try:
        log_path = Path(directory) / filename
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "This is a fake log file for testing purposes.\n", encoding="utf-8"
        )
        console.print(f"[green]Fake log file created at: {log_path}[/green]")
        return str(log_path)
    except Exception as e:
        console.print(f"[red]Error creating fake log file: {e}[/red]")
        return None


def create_error_log(directory: str, filename: str = "error_sample.log") -> str:
    """
    Create a realistic error log file (Python traceback) for testing analysis.
    Returns the file path or None on error.
    """
    content = (
        "2025-08-12 10:15:43,120 [INFO] Starting job worker\n"
        "2025-08-12 10:15:43,321 [DEBUG] loading config from /etc/myapp/config.yml\n\n"
        "Traceback (most recent call last):\n"
        '  File "/app/main.py", line 10, in <module>\n'
        "    run()\n"
        '  File "/app/main.py", line 6, in run\n'
        "    result = divide(10, 0)\n"
        '  File "/app/utils.py", line 2, in divide\n'
        "    return a / b\n"
        "ZeroDivisionError: division by zero\n\n"
        "During handling of the above exception, another exception occurred:\n\n"
        "Traceback (most recent call last):\n"
        '  File "/app/worker.py", line 42, in process\n'
        "    open('/var/log/myapp/output.log').write('done')\n"
        "PermissionError: [Errno 13] Permission denied: '/var/log/myapp/output.log'\n\n"
        "2025-08-12 10:15:43,999 [ERROR] worker crashed\n"
    )
    try:
        log_path = Path(directory) / filename
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(content, encoding="utf-8")
        console.print(f"[green]Error log file created at: {log_path}[/green]")
        return str(log_path)
    except Exception as e:
        console.print(f"[red]Error creating error log file: {e}[/red]")
        return None


def detect_compute_device() -> str:
    """
    Best-effort detection of compute device.
    Returns a short label like:
    - "GPU (NVIDIA <name>)"
    - "GPU (AMD)"
    - "CPU"
    """
    # NVIDIA
    try:
        cp = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if cp.returncode == 0:
            name = (cp.stdout or "").splitlines()
            if name:
                return f"GPU (NVIDIA {name[0].strip()})"
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # AMD ROCm
    try:
        cp = subprocess.run(["rocm-smi"], capture_output=True, text=True, timeout=2)
        if cp.returncode == 0 and (cp.stdout or ""):
            return "GPU (AMD)"
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return "CPU"
