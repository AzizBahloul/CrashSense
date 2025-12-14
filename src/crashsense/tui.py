# src/crashsense/tui.py
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from .config import load_config, save_config
from .core.memory import MemoryStore
from .core.analyzer import BackTrackEngine
from .utils import read_file, write_last_log
import time

console = Console()


def run_tui():
    cfg = load_config()
    mem = MemoryStore(cfg["memory"]["path"])
    engine = BackTrackEngine(
        provider=cfg.get("provider", "auto"),
        local_model=cfg.get("local", {}).get("model"),
    )
    
    # Check if Kubernetes is enabled
    k8s_enabled = cfg.get("kubernetes", {}).get("enabled", False)
    
    console.clear()
    
    menu_items = [
        "1) Analyze crash log file",
        "2) List crash memories",
        "3) Prune memory",
        "4) Init/Configure",
    ]
    
    if k8s_enabled:
        menu_items.extend([
            "5) Kubernetes cluster status",
            "6) Kubernetes auto-heal",
            "7) Kubernetes live monitor",
            "8) Quit"
        ])
        choices = ["1", "2", "3", "4", "5", "6", "7", "8"]
        default = "8"
    else:
        menu_items.append("5) Quit")
        choices = ["1", "2", "3", "4", "5"]
        default = "5"
    
    console.print(
        Panel(
            "CrashSense Interactive TUI\n\n" + "\n".join(menu_items),
            title="🚀 CrashSense",
            border_style="cyan"
        )
    )
    
    while True:
        choice = Prompt.ask("Choose", choices=choices, default=default)
        
        if choice == "1":
            _analyze_log(cfg, engine, mem)
        elif choice == "2":
            _list_memories(mem)
        elif choice == "3":
            _prune_memory(cfg, mem)
        elif choice == "4":
            _configure(cfg, engine)
        elif k8s_enabled and choice == "5":
            _k8s_status(cfg)
        elif k8s_enabled and choice == "6":
            _k8s_heal(cfg)
        elif k8s_enabled and choice == "7":
            _k8s_live_monitor(cfg)
        else:
            console.print("👋 Goodbye!")
            break


def _analyze_log(cfg, engine, mem):
    """Analyze a crash log file."""
    path = Prompt.ask("Path to crash log file")
    try:
        txt = read_file(path)
        write_last_log(cfg["last"]["last_log"], txt)
        
        console.print("[bold cyan]Analyzing...[/bold cyan]")
        res = engine.analyze(txt)
        
        explanation = res["analysis"].get("explanation", "")
        patch = res["analysis"].get("patch", "")
        
        console.print(Panel(
            f"[bold]Explanation:[/bold]\n{explanation}\n\n[bold]Patch:[/bold]\n{patch}",
            title="Analysis Results",
            border_style="green"
        ))
        
        mem.upsert(txt, explanation, patch)
        console.print("[dim]✓ Saved to memory[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def _list_memories(mem):
    """List crash analysis memories."""
    items = mem.list(30)
    if not items:
        console.print("[yellow]No memories found.[/yellow]")
        return
    
    table = Table(title="Crash Memories")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Summary", style="white")
    table.add_column("Frequency", style="yellow", width=10)
    table.add_column("Last Accessed", style="dim", width=20)
    
    for i, m in enumerate(items, 1):
        table.add_row(
            str(i),
            m.summary[:100] + "..." if len(m.summary) > 100 else m.summary,
            str(m.frequency),
            str(m.last_accessed)
        )
    
    console.print(table)


def _prune_memory(cfg, mem):
    """Prune old crash memories."""
    mem.prune(
        max_entries=cfg["memory"]["max_entries"],
        retention_days=cfg["memory"]["retention_days"],
    )
    console.print("[green]✓ Memory pruned successfully.[/green]")


def _configure(cfg, engine):
    """Configure CrashSense settings."""
    from .cli import init
    init.callback()
    cfg = load_config()
    engine = BackTrackEngine(
        provider=cfg.get("provider", "auto"),
        local_model=cfg.get("local", {}).get("model"),
    )
    console.print("[green]✓ Configuration updated.[/green]")


def _k8s_status(cfg):
    """Show Kubernetes cluster status."""
    try:
        from .core.k8s_monitor import KubernetesMonitor
        
        k8s_cfg = cfg.get("kubernetes", {})
        monitor = KubernetesMonitor(
            kubeconfig_path=k8s_cfg.get("kubeconfig"),
            namespaces=k8s_cfg.get("namespaces", [])
        )
        
        console.print("[bold cyan]🔍 Checking cluster health...[/bold cyan]\n")
        
        # Cluster info
        cluster_info = monitor.get_cluster_info()
        console.print(Panel(
            f"[bold]Kubernetes Cluster[/bold]\n"
            f"Version: {cluster_info.get('version', 'N/A')}\n"
            f"Nodes: {cluster_info.get('node_count', 0)}",
            title="Cluster Info",
            border_style="cyan"
        ))
        
        # Health check
        health = monitor.health_check()
        
        status_color = "green" if health['healthy'] else "red"
        status_text = "✓ Healthy" if health['healthy'] else "✗ Issues Detected"
        
        console.print(Panel(
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
        
        Prompt.ask("\nPress Enter to continue", default="")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        Prompt.ask("Press Enter to continue", default="")


def _k8s_heal(cfg):
    """Detect and heal Kubernetes issues."""
    try:
        from .core.k8s_monitor import KubernetesMonitor
        from .core.remediation import RemediationEngine
        
        k8s_cfg = cfg.get("kubernetes", {})
        monitor = KubernetesMonitor(
            kubeconfig_path=k8s_cfg.get("kubeconfig"),
            namespaces=k8s_cfg.get("namespaces", [])
        )
        
        console.print("[bold cyan]🔍 Scanning for issues...[/bold cyan]\n")
        
        crashes = monitor.detect_pod_crashes()
        exhaustion = monitor.detect_resource_exhaustion()
        network = monitor.detect_network_failures()
        
        all_issues = crashes + exhaustion + network
        
        if not all_issues:
            console.print("[green]✓ No issues found - cluster is healthy![/green]")
            Prompt.ask("\nPress Enter to continue", default="")
            return
        
        console.print(f"[yellow]Found {len(all_issues)} issues:[/yellow]\n")
        
        # Display issues
        table = Table(title="Detected Issues")
        table.add_column("Pod/Service", style="cyan")
        table.add_column("Namespace", style="magenta")
        table.add_column("Issue Type", style="yellow")
        
        for issue in all_issues[:10]:
            table.add_row(
                issue.get("name") or issue.get("pod") or issue.get("service", "N/A"),
                issue.get("namespace", "N/A"),
                issue.get("type", "Unknown")
            )
        
        console.print(table)
        
        if not Confirm.ask(f"\n[bold]Apply remediation for {len(all_issues)} issues?[/bold]", default=False):
            console.print("[yellow]Remediation cancelled.[/yellow]")
            Prompt.ask("\nPress Enter to continue", default="")
            return
        
        remediation_engine = RemediationEngine(
            monitor,
            dry_run=k8s_cfg.get("dry_run", True)
        )
        
        console.print(f"\n[bold cyan]🏥 Starting remediation...[/bold cyan]")
        results = remediation_engine.auto_heal(
            all_issues,
            max_actions=k8s_cfg.get("max_remediation_actions", 10)
        )
        
        successful = sum(1 for r in results if r.get("success"))
        console.print(f"\n[bold green]✓ Remediation complete: {successful}/{len(results)} successful[/bold green]")
        
        Prompt.ask("\nPress Enter to continue", default="")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        Prompt.ask("Press Enter to continue", default="")


def _k8s_live_monitor(cfg):
    """Live monitoring dashboard for Kubernetes."""
    try:
        from .core.k8s_monitor import KubernetesMonitor
        
        k8s_cfg = cfg.get("kubernetes", {})
        monitor = KubernetesMonitor(
            kubeconfig_path=k8s_cfg.get("kubeconfig"),
            namespaces=k8s_cfg.get("namespaces", [])
        )
        
        console.print("[bold cyan]🔴 Live Monitoring - Press Ctrl+C to stop[/bold cyan]\n")
        
        iteration = 0
        try:
            while True:
                iteration += 1
                
                # Create dashboard
                layout = Layout()
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="body"),
                )
                
                # Header
                layout["header"].update(Panel(
                    f"[bold]CrashSense Live Monitor[/bold] - Iteration #{iteration}",
                    style="cyan"
                ))
                
                # Get health status
                health = monitor.health_check()
                
                status_color = "green" if health['healthy'] else "red"
                status_text = "✓ Healthy" if health['healthy'] else "✗ Issues Detected"
                
                # Body content
                body_content = f"""
[bold {status_color}]{status_text}[/bold {status_color}]

[bold]Summary:[/bold]
  Pod Crashes: {health['summary'].get('pod_crashes', 0)}
  Resource Exhaustion: {health['summary'].get('resource_exhaustion', 0)}
  Network Issues: {health['summary'].get('network_issues', 0)}
"""
                
                if health.get('issues'):
                    body_content += f"\n[bold red]Recent Issues:[/bold red]\n"
                    for issue in health['issues'][:5]:
                        body_content += f"  • {issue}\n"
                
                layout["body"].update(Panel(body_content, border_style=status_color))
                
                console.print(layout)
                console.print(f"[dim]Next refresh in {k8s_cfg.get('monitor_interval_seconds', 60)}s...[/dim]\n")
                
                time.sleep(k8s_cfg.get("monitor_interval_seconds", 60))
                console.clear()
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped.[/yellow]")
            Prompt.ask("Press Enter to continue", default="")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        Prompt.ask("Press Enter to continue", default="")
