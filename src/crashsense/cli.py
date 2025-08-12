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
    cmd = "curl -fsSL https://ollama.com/install.sh | sh"
    # For safety, run via shell only if user confirmed earlier.
    return subprocess.run(cmd, shell=True).returncode == 0


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
        analyze.callback(None)


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
        key = Prompt.ask(
            "Enter OpenAI API key (or set CRASHSENSE_OPENAI_KEY env var)",
            default=os.environ.get("CRASHSENSE_OPENAI_KEY", ""),
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
def analyze(logfile):
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
            logfile = detect_last_log()
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

    # If LLM included commands in output, attempt to parse them (very simple heuristic)
    commands = []
    expl = analysis.get("explanation", "")
    # simple parse: look for lines starting with 'commands:' or '```bash' blocks
    for line in expl.splitlines():
        if (
            line.strip().startswith("$ ")
            or line.strip().startswith("sudo ")
            or line.strip().startswith("pip ")
        ):
            commands.append(line.strip())
    # try to find fenced blocks
    if "```bash" in expl or "```sh" in expl:
        import re

        blocks = re.findall(r"```(?:bash|sh)\n(.*?)```", expl, re.S)
        for b in blocks:
            for line in b.splitlines():
                if line.strip():
                    commands.append(line.strip())

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

            # Default: allow non-sensitive commands
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
            "Allow CrashSense to run these commands now? (runs sequentially in shell)",
            default=False,
        ):
            for c in valid_commands:
                console.print(f"[cyan]Running:[/cyan] {c}")
                try:
                    cp = subprocess.run(c, shell=True)
                    if cp.returncode == 0:
                        console.print(f"[green]Command succeeded: {c}[/green]")
                    else:
                        console.print(
                            f"[red]Command failed (code {cp.returncode}): {c}[/red]"
                        )
                except Exception as e:
                    console.print(f"[red]Failed to run command {c}: {e}[/red]")
        else:
            console.print("[yellow]Skipped running detected commands.[/yellow]")
    else:
        if commands and skipped_info:
            console.print(
                "[yellow]All suggested commands were skipped after preflight (e.g., missing users/groups or paths).[/yellow]"
            )
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
