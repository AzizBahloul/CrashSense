# src/crashsense/tui.py
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from .config import load_config
from .core.memory import MemoryStore
from .core.analyzer import BackTrackEngine
from .utils import read_file, write_last_log

console = Console()


def run_tui():
    cfg = load_config()
    mem = MemoryStore(cfg["memory"]["path"])
    engine = BackTrackEngine(
        provider=cfg.get("provider", "auto"),
        local_model=cfg.get("local", {}).get("model"),
    )
    console.clear()
    console.print(
        Panel(
            "CrashSense interactive (MVP)\n1) Analyze file\n2) List memories\n3) Prune memory\n4) Init/Configure\n5) Quit",
            title="CrashSense",
        )
    )
    while True:
        choice = Prompt.ask("Choose", choices=["1", "2", "3", "4", "5"], default="5")
        if choice == "1":
            path = Prompt.ask("Path to crash log (file)")
            try:
                txt = read_file(path)
                write_last_log(cfg["last"]["last_log"], txt)
                console.print("[bold]Analyzing...[/bold]")
                res = engine.analyze(txt)
                console.print(res["analysis"].get("explanation", ""))
                console.print(
                    "[bold]Patch:[/bold]\n" + res["analysis"].get("patch", "")
                )
                mem.upsert(
                    txt,
                    res["analysis"].get("explanation", ""),
                    res["analysis"].get("patch", ""),
                )
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
        elif choice == "2":
            items = mem.list(30)
            for i, m in enumerate(items, 1):
                console.print(f"{i}. {m.summary[:120]} ... (freq={m.frequency})")
        elif choice == "3":
            mem.prune(
                max_entries=cfg["memory"]["max_entries"],
                retention_days=cfg["memory"]["retention_days"],
            )
            console.print("[green]Pruned memory.[/green]")
        elif choice == "4":
            # delegate to CLI init
            from .cli import init

            init.callback()
            cfg = load_config()
            engine = BackTrackEngine(
                provider=cfg.get("provider", "auto"),
                local_model=cfg.get("local", {}).get("model"),
            )
        else:
            console.print("Bye 👋")
            break
            break
