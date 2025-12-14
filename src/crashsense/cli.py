# src/crashsense/cli.py
import click
import subprocess
import os
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from .config import load_config, save_config
from .core.analyzer import BackTrackEngine
from .core.memory import MemoryStore
from .core.llm_adapter import LLMAdapter
from .utils import (
    detect_last_log,
    create_fake_log,  # Added import
    create_error_log,
    read_terminal_history,
    read_file,
    short_print,
    write_last_log,
    check_ollama_running,  # Moved to utils.py
    pull_ollama_model,  # Moved to utils.py
    detect_compute_device,
    run_command_safe,
)
# run_tui will be imported lazily inside the tui() command

console = Console()


def try_install_ollama():
    """
    Best-effort automated installer. Running this will execute the official
    Ollama install script. It requires network access and user permission.
    WARNING: Running remote install scripts has security implications.
    We only do this if the user confirms.
    """
    console.print(
        "[yellow]Attempting to install Ollama via the official installer...[/yellow]"
    )
    # Avoid shell pipelines; try to fetch installer first, then run sh on file.
    try:
        import tempfile
        import urllib.request

        with tempfile.TemporaryDirectory() as td:
            installer = Path(td) / "install.sh"
            urllib.request.urlretrieve("https://ollama.com/install.sh", installer)
            cp = subprocess.run(["sh", str(installer)], timeout=600)
            return cp.returncode == 0
    except Exception:
        # Fallback: inform user to install manually for safety.
        console.print(
            "[yellow]Automatic install failed. Please install manually from https://ollama.com[/yellow]"
        )
        return False


def test_openai_key(key: str) -> bool:
    adapter = LLMAdapter(provider="openai")
    adapter.openai_key = key
    return adapter.validate_openai_key()


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """CrashSense - AI-powered crash analysis"""
    if ctx.invoked_subcommand is None:
        # No args: emulate `analyze` with no logfile
        return ctx.invoke(analyze, logfile=None, includes=(), excludes=())


@main.group()
def rag():
    """Manage Retrieval-Augmented Generation (RAG) docs and indexing."""
    pass


@rag.command("add")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
def rag_add(paths):
    """Add one or more files/dirs to RAG docs."""
    if not paths:
        console.print("[yellow]No paths provided.[/yellow]")
        return
    cfg = load_config()
    rag_cfg = cfg.setdefault("rag", {})
    docs = set(rag_cfg.get("docs") or [])
    added = []
    for p in paths:
        p_str = str(Path(p).resolve())
        if p_str not in docs:
            docs.add(p_str)
            added.append(p_str)
    rag_cfg["docs"] = sorted(docs)
    save_config(cfg)
    if added:
        console.print(Panel.fit("\n".join(added), title="Added to RAG docs", border_style="green"))
    else:
        console.print("[dim]No new docs added.[/dim]")


@rag.command("clear")
def rag_clear():
    """Clear all configured RAG docs (keeps bundled ./kb)."""
    cfg = load_config()
    rag_cfg = cfg.setdefault("rag", {})
    # Keep default kb if present in defaults
    default_kb = str(Path.cwd() / "kb")
    rag_cfg["docs"] = [d for d in rag_cfg.get("docs", []) if d == default_kb]
    save_config(cfg)
    console.print("[green]RAG docs cleared (bundled kb retained if present).[/green]")


@rag.command("build")
@click.option("--dry-run", is_flag=True, help="Only report chunk stats without saving anything.")
def rag_build(dry_run):
    """Chunk configured docs and report stats (retrieval uses these on demand)."""
    cfg = load_config()
    rag_cfg = cfg.get("rag", {})
    paths = rag_cfg.get("docs") or []
    size = int(rag_cfg.get("chunk_chars", 800))
    overlap = int(rag_cfg.get("chunk_overlap", 120))
    total_chunks = 0
    files = 0
    from pathlib import Path as _P
    exts = {".md", ".txt", ".log", ".py", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".conf", ".cfg", ".csv"}
    for p in paths:
        try:
            path = _P(p)
            if path.is_file():
                try:
                    txt = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                chunks = _chunk_text_cli(txt, size, overlap)
                total_chunks += len(chunks)
                files += 1
            elif path.is_dir():
                for child in path.rglob("*"):
                    if not child.is_file():
                        continue
                    if child.suffix.lower() not in exts:
                        continue
                    try:
                        txt = child.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    chunks = _chunk_text_cli(txt, size, overlap)
                    total_chunks += len(chunks)
                    files += 1
        except Exception:
            continue
    console.print(Panel.fit(f"Files processed: {files}\nChunks (~{size} chars, overlap {overlap}): {total_chunks}", title="RAG Build", border_style="cyan"))
    if not dry_run:
        console.print("[dim]No persistent index is created; retrieval embeds on demand.[/dim]")


def _chunk_text_cli(text: str, size: int, overlap: int):
    if size <= 0:
        return [text]
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        chunks.append(text[start:end])
        if end == n:
            break
        start = max(end - overlap, start + 1)
    return chunks


@main.group()
def k8s():
    """Kubernetes cluster monitoring and self-healing commands."""
    pass


@k8s.command("status")
@click.option("--kubeconfig", type=click.Path(exists=True), help="Path to kubeconfig file")
@click.option("--namespace", "-n", multiple=True, help="Namespaces to check (can be repeated)")
def k8s_status(kubeconfig, namespace):
    """Check Kubernetes cluster health status."""
    from .core.k8s_monitor import KubernetesMonitor
    from rich.table import Table
    
    cfg = load_config()
    k8s_cfg = cfg.get("kubernetes", {})
    
    kubeconfig = kubeconfig or k8s_cfg.get("kubeconfig")
    namespaces = list(namespace) if namespace else k8s_cfg.get("namespaces", [])
    
    try:
        monitor = KubernetesMonitor(kubeconfig_path=kubeconfig, namespaces=namespaces)
        
        # Get cluster info
        cluster_info = monitor.get_cluster_info()
        console.print(Panel.fit(
            f"[bold]Kubernetes Cluster[/bold]\n"
            f"Version: {cluster_info.get('version', 'N/A')}\n"
            f"Nodes: {cluster_info.get('node_count', 0)}",
            title="Cluster Info",
            border_style="cyan"
        ))
        
        # Show nodes
        if cluster_info.get('nodes'):
            table = Table(title="Nodes")
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("CPU", style="yellow")
            table.add_column("Memory", style="yellow")
            
            for node in cluster_info['nodes']:
                table.add_row(
                    node['name'],
                    node['status'],
                    node['cpu_capacity'],
                    node['memory_capacity']
                )
            console.print(table)
        
        # Health check
        health = monitor.health_check()
        
        status_color = "green" if health['healthy'] else "red"
        status_text = "✓ Healthy" if health['healthy'] else "✗ Issues Detected"
        
        console.print(Panel.fit(
            f"[bold {status_color}]{status_text}[/bold {status_color}]\n\n"
            f"Pod Crashes: {health['summary'].get('pod_crashes', 0)}\n"
            f"Resource Exhaustion: {health['summary'].get('resource_exhaustion', 0)}\n"
            f"Network Issues: {health['summary'].get('network_issues', 0)}",
            title="Health Status",
            border_style=status_color
        ))
        
        if health.get('issues'):
            console.print("\n[bold red]Issues:[/bold red]")
            for issue in health['issues'][:10]:
                console.print(f"  • {issue}")
                
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@k8s.command("monitor")
@click.option("--kubeconfig", type=click.Path(exists=True), help="Path to kubeconfig file")
@click.option("--namespace", "-n", multiple=True, help="Namespaces to monitor")
@click.option("--interval", "-i", default=60, help="Monitoring interval in seconds")
@click.option("--auto-heal", is_flag=True, help="Automatically remediate detected issues")
def k8s_monitor(kubeconfig, namespace, interval, auto_heal):
    """Continuously monitor Kubernetes cluster for issues."""
    from .core.k8s_monitor import KubernetesMonitor
    from .core.remediation import RemediationEngine
    import time
    
    cfg = load_config()
    k8s_cfg = cfg.get("kubernetes", {})
    
    kubeconfig = kubeconfig or k8s_cfg.get("kubeconfig")
    namespaces = list(namespace) if namespace else k8s_cfg.get("namespaces", [])
    interval = interval or k8s_cfg.get("monitor_interval_seconds", 60)
    
    if auto_heal and not Confirm.ask(
        "[yellow]Auto-heal mode will automatically apply remediations. Continue?[/yellow]",
        default=False
    ):
        console.print("[yellow]Monitoring without auto-heal.[/yellow]")
        auto_heal = False
    
    try:
        monitor = KubernetesMonitor(kubeconfig_path=kubeconfig, namespaces=namespaces)
        remediation_engine = None
        
        if auto_heal:
            remediation_engine = RemediationEngine(
                monitor,
                dry_run=k8s_cfg.get("dry_run", True)
            )
        
        console.print(f"[bold cyan]🔍 Monitoring cluster every {interval}s[/bold cyan]")
        console.print(f"   Auto-heal: {'[green]Enabled[/green]' if auto_heal else '[yellow]Disabled[/yellow]'}")
        console.print(f"   Namespaces: {', '.join(namespaces) if namespaces else 'All'}\n")
        
        iteration = 0
        while True:
            iteration += 1
            console.print(f"\n[dim]--- Iteration {iteration} at {time.strftime('%H:%M:%S')} ---[/dim]")
            
            # Detect issues
            crashes = monitor.detect_pod_crashes()
            exhaustion = monitor.detect_resource_exhaustion()
            network = monitor.detect_network_failures()
            
            all_issues = crashes + exhaustion + network
            
            if all_issues:
                console.print(f"[yellow]⚠ Found {len(all_issues)} issues[/yellow]")
                
                for issue in all_issues[:5]:
                    console.print(f"  • {issue.get('name') or issue.get('pod')}: {', '.join(issue.get('issues', [issue.get('type', 'unknown')]))}")
                
                if auto_heal and remediation_engine:
                    console.print(f"\n[bold]🏥 Applying auto-heal...[/bold]")
                    results = remediation_engine.auto_heal(
                        all_issues,
                        max_actions=k8s_cfg.get("max_remediation_actions", 10)
                    )
                    
                    successful = sum(1 for r in results if r.get("success"))
                    console.print(f"[green]✓ {successful}/{len(results)} remediations successful[/green]")
            else:
                console.print("[green]✓ No issues detected[/green]")
            
            # Wait for next iteration
            console.print(f"[dim]Sleeping for {interval}s...[/dim]")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@k8s.command("heal")
@click.option("--kubeconfig", type=click.Path(exists=True), help="Path to kubeconfig file")
@click.option("--namespace", "-n", multiple=True, help="Namespaces to check")
@click.option("--dry-run", is_flag=True, help="Simulate remediation without applying changes")
def k8s_heal(kubeconfig, namespace, dry_run):
    """Detect and remediate Kubernetes issues (one-time scan)."""
    from .core.k8s_monitor import KubernetesMonitor
    from .core.remediation import RemediationEngine
    from rich.table import Table
    
    cfg = load_config()
    k8s_cfg = cfg.get("kubernetes", {})
    
    kubeconfig = kubeconfig or k8s_cfg.get("kubeconfig")
    namespaces = list(namespace) if namespace else k8s_cfg.get("namespaces", [])
    
    try:
        monitor = KubernetesMonitor(kubeconfig_path=kubeconfig, namespaces=namespaces)
        
        console.print("[bold]🔍 Scanning for issues...[/bold]")
        
        crashes = monitor.detect_pod_crashes()
        exhaustion = monitor.detect_resource_exhaustion()
        network = monitor.detect_network_failures()
        
        all_issues = crashes + exhaustion + network
        
        if not all_issues:
            console.print("[green]✓ No issues found - cluster is healthy![/green]")
            return
        
        console.print(f"\n[yellow]Found {len(all_issues)} issues:[/yellow]\n")
        
        # Display issues
        table = Table(title="Detected Issues")
        table.add_column("Pod/Service", style="cyan")
        table.add_column("Namespace", style="magenta")
        table.add_column("Issue Type", style="yellow")
        table.add_column("Details", style="white")
        
        for issue in all_issues:
            table.add_row(
                issue.get("name") or issue.get("pod") or issue.get("service", "N/A"),
                issue.get("namespace", "N/A"),
                issue.get("type", "Unknown"),
                ", ".join(issue.get("issues", [])[:2])
            )
        
        console.print(table)
        
        # Ask for remediation
        if not Confirm.ask(
            f"\n[bold]Apply remediation for {len(all_issues)} issues?[/bold]",
            default=False
        ):
            console.print("[yellow]Remediation cancelled.[/yellow]")
            return
        
        remediation_engine = RemediationEngine(monitor, dry_run=dry_run)
        
        console.print(f"\n[bold cyan]🏥 Starting remediation...[/bold cyan]")
        results = remediation_engine.auto_heal(
            all_issues,
            max_actions=k8s_cfg.get("max_remediation_actions", 10)
        )
        
        # Summary
        successful = sum(1 for r in results if r.get("success"))
        console.print(f"\n[bold]Remediation Summary:[/bold]")
        console.print(f"  Total issues: {len(all_issues)}")
        console.print(f"  Remediated: {len(results)}")
        console.print(f"  Successful: [green]{successful}[/green]")
        console.print(f"  Failed: [red]{len(results) - successful}[/red]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@k8s.command("logs")
@click.argument("pod")
@click.option("--namespace", "-n", default="default", help="Kubernetes namespace")
@click.option("--container", "-c", help="Container name (if pod has multiple containers)")
@click.option("--tail", "-t", default=100, help="Number of lines to show")
@click.option("--previous", "-p", is_flag=True, help="Show logs from previous terminated container")
@click.option("--analyze", is_flag=True, help="Analyze logs with AI")
def k8s_logs(pod, namespace, container, tail, previous, analyze):
    """Get logs from a Kubernetes pod."""
    from .core.k8s_monitor import KubernetesMonitor
    
    cfg = load_config()
    k8s_cfg = cfg.get("kubernetes", {})
    
    try:
        monitor = KubernetesMonitor(kubeconfig_path=k8s_cfg.get("kubeconfig"))
        
        console.print(f"[cyan]Fetching logs for pod {pod} in namespace {namespace}...[/cyan]")
        logs = monitor.get_pod_logs(pod, namespace, container=container, tail_lines=tail, previous=previous)
        
        if logs.startswith("Error"):
            console.print(f"[red]{logs}[/red]")
            return
        
        console.print(Panel(logs, title=f"Logs: {pod}", border_style="cyan"))
        
        if analyze:
            console.print("\n[bold]🧠 Analyzing logs with AI...[/bold]")
            
            provider = cfg.get("provider", "auto")
            local_model = cfg.get("local", {}).get("model")
            engine = BackTrackEngine(provider=provider, local_model=local_model)
            
            result = engine.analyze(logs)
            analysis = result["analysis"]
            
            console.print(Panel.fit(
                f"[bold]Analysis:[/bold]\n{analysis.get('explanation', 'No analysis available')}\n\n"
                f"[bold]Suggested Fix:[/bold]\n{analysis.get('patch', 'No fix suggested')}",
                title="AI Analysis",
                border_style="green"
            ))
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@main.command()
def init():
    """Interactive initial setup (LLM provider, local model download, API test)"""
    cfg = load_config()
    console.print("[bold]CrashSense initial setup[/bold]")
    provider = Prompt.ask(
        "LLM provider",
        choices=["openai", "ollama", "none", "auto"],
        default=cfg.get("provider", "auto"),
    )
    cfg["provider"] = provider

    if provider == "openai":
        console.print("OpenAI selected. We will validate your API key.")
        env_key = os.environ.get("CRASHSENSE_OPENAI_KEY")
        if env_key and Confirm.ask(
            "Use the API key from environment variable CRASHSENSE_OPENAI_KEY?",
            default=True,
        ):
            key = env_key
        else:
            key = Prompt.ask(
                "Enter OpenAI API key",
                password=True,
                show_default=False,
            )
        if key:
            console.print("Testing OpenAI key...")
            ok = test_openai_key(key)
            if ok:
                console.print("[green]OpenAI key validated successfully.[/green]")
                os.environ["CRASHSENSE_OPENAI_KEY"] = key
            else:
                console.print(
                    "[red]OpenAI key validation failed. Keep it in env var CRASHSENSE_OPENAI_KEY or try again later.[/red]"
                )
        else:
            console.print(
                "[yellow]No key provided. You can set CRASHSENSE_OPENAI_KEY later.[/yellow]"
            )

    elif provider == "ollama":
        console.print("Local Ollama selected.")
        # check ollama binary
        if not check_ollama_running():
            console.print("[yellow]Ollama not found on your PATH.[/yellow]")
            if Confirm.ask(
                "Would you like CrashSense to attempt to install Ollama for you now? (requires network & root privileges)",
                default=False,
            ):
                if try_install_ollama():
                    console.print(
                        "[green]Ollama installer finished. Re-checking...[/green]"
                    )
                else:
                    console.print(
                        "[red]Ollama installer failed or was cancelled. Please install Ollama manually: https://ollama.com[/red]"
                    )
            else:
                console.print(
                    "[cyan]Skipping automatic install — please install Ollama manually and re-run init when ready.[/cyan]"
                )
        else:
            console.print("[green]Ollama binary found on PATH.[/green]")

        # model choice
        console.print(
            "Choose a model tier (these are suggestions — adapt model names to your Ollama repo):"
        )
        model_map = {
            "low": ["llama3.2:1b", "phi3:mini", "codegen-lite"],
            "medium": ["llama3.1:8b", "mistral:7b"],
            "high": ["llama3.1:70b", "codellama:34b"],
        }
        tier = Prompt.ask("Tier", choices=["low", "medium", "high"], default="medium")
        candidates = model_map[tier]
        choice = Prompt.ask(
            "Model to pull", choices=candidates + ["custom"], default=candidates[0]
        )
        if choice == "custom":
            choice = Prompt.ask("Model name (as seen by Ollama, e.g. llama3.1:8b)")
        console.print(f"Selected model: {choice}")
        # attempt to pull model if ollama present
        if check_ollama_running():
            if Confirm.ask(
                f"Pull/download model '{choice}' now using ollama CLI?", default=True
            ):
                ok = pull_ollama_model(choice)
                if ok:
                    console.print("[green]Model pull succeeded.[/green]")
                    cfg.setdefault("local", {})["model"] = choice
                else:
                    console.print(
                        "[red]Model pull failed. You can try again later.[/red]"
                    )
        else:
            console.print(
                "[yellow]Ollama not installed — cannot pull model now.[/yellow]"
            )

    # save config
    save_config(cfg)
    console.print("[green]Configuration saved to ~/.crashsense/config.toml[/green]")


@main.command()
@click.argument("logfile", type=click.Path(exists=True), required=False)
@click.option(
    "--include",
    "includes",
    multiple=True,
    help="Directories to scan for logs (can be repeated)",
)
@click.option(
    "--exclude",
    "excludes",
    multiple=True,
    help="Case-insensitive substrings to exclude from auto-detection",
)
def analyze(logfile, includes, excludes):
    """
    Analyze a crash log file. Automatically detects the latest log file if none is provided.
    """
    cfg = load_config()
    # Device info
    try:
        device = detect_compute_device()
        console.print(f"[dim]Compute device: {device}[/dim]")
    except Exception:
        pass

    # Only show a friendly message for log detection
    if not logfile:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}")
        ) as progress:
            progress.add_task(
                description="Looking for the latest crash log...", total=None
            )
            directories = list(includes) if includes else None
            exclude_patterns = list(excludes) if excludes else None
            logfile = detect_last_log(directories=directories, exclude_patterns=exclude_patterns)
        if logfile:
            console.print(
                Panel.fit(
                    f"[bold green]Found latest log file:[/bold green]\n{logfile}",
                    title="CrashSense",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[red]No log files found in common directories.[/red]",
                    title="CrashSense",
                )
            )
            logfile = Prompt.ask("Path to crash log (file)")

    # Hide technical errors, show only a friendly message
    content = ""
    try:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}")
        ) as progress:
            progress.add_task(description="Reading log file...", total=None)
            content = read_file(logfile)
    except Exception:
        console.print(
            Panel.fit(
                "[red]Sorry, failed to read the log file. Please select another file.[/red]",
                title="CrashSense",
            )
        )
        raise click.Abort()

    # Show a friendly spinner while analyzing
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress:
        progress.add_task(
            description="CrashSense is analyzing your crash log...", total=None
        )
        # Include terminal history
        terminal_history = read_terminal_history(limit=50)
        if terminal_history:
            content += "\n\n# Terminal History:\n" + terminal_history

        # Write last log for convenience
        last_log_path = cfg.get("last", {}).get(
            "last_log", str(Path.home() / ".crashsense" / "last.log")
        )
        write_last_log(last_log_path, content)

        # Analyze
        provider = cfg.get("provider", "auto")
        local_model = cfg.get("local", {}).get("model")
        engine = BackTrackEngine(provider=provider, local_model=local_model)
        res = engine.analyze(content)
        parsed = res["parsed"]
        analysis = res["analysis"]

    # Show results in a nice panel
    console.rule("[bold blue]CrashSense Analysis Complete[/bold blue]")
    console.print(
        Panel.fit(
            f"[bold]Parsed Info:[/bold]\n{parsed}\n\n"
            f"[bold]Explanation:[/bold]\n{analysis.get('explanation', '')}\n\n"
            f"[bold]Suggested Patch:[/bold]\n{analysis.get('patch', 'No patch suggested.')}",
            title="CrashSense Results",
        )
    )

    # Add summary table for analyzed logs (single or batch)
    if isinstance(parsed, dict) and parsed.get('log_type'):
        from rich.table import Table
        table = Table(title="Log Analysis Summary")
        table.add_column("Log Type", style="cyan")
        table.add_column("Exception", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Patch", style="yellow")
        exc = parsed.get('exception', {})
        exc_type = exc.get('type') if exc else "-"
        status = "Success" if exc_type else "No Exception"
        patch = analysis.get('patch', 'No patch')
        table.add_row(parsed['log_type'], exc_type or "-", status, patch[:40])
        console.print(table)

    # If LLM included commands in output, attempt to parse them (hardened heuristic)
    commands = []  # Initialize command list
    expl = analysis.get("explanation", "")
    # simple parse: look for lines starting with 'commands:' or '```bash' blocks
    for line in expl.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("$ "):
            s = s[2:].strip()
        if s.startswith(("sudo ", "pip ", "crashsense ")):
            commands.append(s)
    # try to find fenced blocks
    if "```bash" in expl or "```sh" in expl:
        import re

        blocks = re.findall(r"```(?:bash|sh)\n(.*?)```", expl, re.S)
        for b in blocks:
            for line in b.splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if s.startswith("$ "):
                    s = s[2:].strip()
                if s:
                    commands.append(s)

    # Deduplicate commands while preserving order
    if commands:
        seen = set()
        unique = []
        for c in commands:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        commands = unique

    # Basic safety/validity preflight for sensitive commands
    valid_commands = []
    skipped_info = []
    if commands:
        import shlex
        from pathlib import Path as _Path

        try:
            import pwd as _pwd
            import grp as _grp
        except Exception:
            _pwd = None
            _grp = None

        dangerous = {"rm", "mkfs", "dd", "shutdown", "reboot", "init", ":"}
        allowed_subcommands = {
            "init",
            "analyze",
            "tui",
            "memory",
            "create_fake_log_cmd",
            "create_error_log_cmd",
        }
        for c in commands:
            try:
                parts = shlex.split(c)
            except Exception:
                skipped_info.append((c, "cannot parse"))
                continue
            if not parts:
                continue
            if parts[0] == "sudo":
                parts = parts[1:]
            if not parts:
                continue
            cmd = parts[0]

            # Skip obviously dangerous commands by default
            if cmd in dangerous:
                skipped_info.append((c, f"dangerous command '{cmd}' skipped"))
                continue

            if cmd == "chown":
                # Form: chown [-R] user[:group] path
                # Find user:group and path tokens
                usergrp = None
                path = None
                # skip flags
                rest = [p for p in parts[1:] if not p.startswith("-")]
                for p in rest:
                    if usergrp is None and ":" in p:
                        usergrp = p
                        continue
                # path is last non-flag
                if rest:
                    path = rest[-1]
                if not usergrp or not path:
                    skipped_info.append((c, "missing user/group or path"))
                    continue
                # validate
                u, g = usergrp.split(":", 1)
                if _pwd:
                    try:
                        _pwd.getpwnam(u)
                    except KeyError:
                        skipped_info.append((c, f"user '{u}' not found"))
                        continue
                if _grp:
                    try:
                        _grp.getgrnam(g)
                    except KeyError:
                        skipped_info.append((c, f"group '{g}' not found"))
                        continue
                if not _Path(path).exists():
                    skipped_info.append((c, f"path '{path}' not found"))
                    continue
                valid_commands.append(c)
                continue

            if cmd == "chmod":
                # Form: chmod [-R] MODE path
                rest = [p for p in parts[1:] if not p.startswith("-")]
                if len(rest) < 2:
                    skipped_info.append((c, "missing mode or path"))
                    continue
                path = rest[-1]
                if not _Path(path).exists():
                    skipped_info.append((c, f"path '{path}' not found"))
                    continue
                valid_commands.append(c)
                continue

            # ln -s validation: allow only if src exists and dest parent exists, and path isn't suspicious
            if cmd == "ln":
                # Expect a form like: ln -s SRC DST
                rest = parts[1:]
                if not rest or "-s" not in rest or len([p for p in rest if not p.startswith("-")]) < 2:
                    skipped_info.append((c, "unsupported ln form; only 'ln -s SRC DST' allowed"))
                    continue
                nonflags = [p for p in rest if not p.startswith("-")]
                src, dst = nonflags[-2], nonflags[-1]
                # Skip clearly wrong prefixed paths like './home/...'
                if dst.startswith("./home/"):
                    skipped_info.append((c, "suspicious destination path './home/...'") )
                    continue
                src_p = _Path(src)
                dst_p = _Path(dst)
                if not src_p.exists():
                    skipped_info.append((c, f"source '{src}' not found"))
                    continue
                if not dst_p.parent.exists():
                    skipped_info.append((c, f"destination parent '{dst_p.parent}' not found"))
                    continue
                valid_commands.append(c)
                continue

            # Skip shell builtins or env exports not reliable without a shell
            if cmd in {"export", "source"}:
                skipped_info.append((c, f"'{cmd}' requires a shell/persistent session"))
                continue

            # Validate crashsense subcommands and basic args
            if cmd == "crashsense":
                if len(parts) == 1:
                    skipped_info.append((c, "missing subcommand"))
                    continue
                sub = parts[1]
                if sub not in allowed_subcommands:
                    skipped_info.append((c, f"unknown subcommand '{sub}'"))
                    continue
                # analyze: allow optional logfile path only; skip unsupported flags
                if sub == "analyze":
                    flags = [p for p in parts[2:] if p.startswith("-")]
                    if flags:
                        skipped_info.append((c, f"unsupported flags {flags}"))
                        continue
                    paths = [p for p in parts[2:] if not p.startswith("-")]
                    if paths:
                        target = _Path(paths[0])
                        if not target.exists():
                            skipped_info.append((c, f"path '{target}' not found"))
                            continue
                valid_commands.append(c)
                continue

            # Default: allow non-sensitive commands
            # Skip pip installs suggested by LLM by default
            if cmd == "pip":
                skipped_info.append((c, "pip operations not auto-run"))
                continue
            # Skip placeholder paths like /path/to/*
            if any("/path/to/" in p for p in parts[1:]):
                skipped_info.append((c, "placeholder path detected"))
                continue
            # Skip if executable is missing
            from shutil import which as _which

            if _which(cmd) is None:
                skipped_info.append((c, f"executable '{cmd}' not found"))
                continue
            valid_commands.append(c)

    # store memory
    mem = MemoryStore(cfg["memory"]["path"])
    mem.upsert(content, analysis.get("explanation", ""), analysis.get("patch", ""))

    # offer to run suggested commands
    if valid_commands:
        console.print("\n[bold]Detected suggested shell commands:[/bold]")
        for i, c in enumerate(valid_commands, 1):
            console.print(f"{i}. {c}")
        if Confirm.ask(
            "Allow CrashSense to run these commands now? (safe mode, no shell)",
            default=False,
        ):
            for c in valid_commands:
                console.print(f"[cyan]Running (safe):[/cyan] {c}")
                code, out, err = run_command_safe(c, timeout=600)
                if code == 0:
                    console.print(f"[green]Command succeeded: {c}[/green]")
                else:
                    msg = err.strip() or out.strip()
                    # Improved error message for missing files/paths
                    if "No such file or directory" in msg:
                        console.print(f"[red]Command failed (code {code}): {c}\nFile or path not found. Details: {msg[:400]}[/red]")
                    elif "executable" in msg or "not found" in msg:
                        console.print(f"[red]Command failed (code {code}): {c}\nExecutable missing or not found. Details: {msg[:400]}[/red]")
                    else:
                        console.print(f"[red]Command failed (code {code}): {c}\n{msg[:400]}[/red]")
        else:
            console.print("[yellow]Skipped running detected commands.[/yellow]")
    else:
        if commands and skipped_info:
            for c, reason in skipped_info:
                console.print(f"[yellow]Skipped: {c} ({reason})[/yellow]")
        else:
            console.print("[cyan]No automated commands detected in analysis output.[/cyan]")


@main.command()
def tui():
    """Launch interactive TUI (keeps previous simple menu)"""
    from .tui import run_tui

    run_tui()


@main.command()
def memory():
    cfg = load_config()
    mem = MemoryStore(cfg["memory"]["path"])
    items = mem.list(50)
    if not items:
        console.print("No memories yet.")
        return  # This return is valid as it is inside a function
    for i, m in enumerate(items, 1):
        console.print(
            f"[{i}] {m.id} • {m.last_accessed} • {m.frequency}\n  {short_print(m.summary, 140)}\n"
        )


@main.command()
@click.argument(
    "directory",
    type=click.Path(file_okay=False, writable=True),
    required=False,
    default=str(Path.home()),
)
def create_fake_log_cmd(directory):
    """
    Create a fake log file for testing purposes.
    """
    create_fake_log(directory)


@main.command()
@click.argument(
    "directory",
    type=click.Path(file_okay=False, writable=True),
    required=False,
    default=str(Path.cwd() / "test-logs"),
)
def create_error_log_cmd(directory):
    """
    Create a realistic error log file for testing.
    """
    path = create_error_log(directory)
    if path:
        console.print(f"You can now run: crashsense analyze '{path}'")


if __name__ == "__main__":
    main()
