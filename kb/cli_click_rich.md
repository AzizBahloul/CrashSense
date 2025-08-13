# Click and Rich quick reference for CLI/TUI

## Click
- Group commands with @click.group and @click.command.
- Validate file args with click.Path(exists=True, dir_okay=False).
- Use safe defaults; avoid shell=True in any subprocess.

## Rich
- Console().print for styled text.
- Tracebacks: from rich.traceback import install; install(show_locals=False).
- Tables, Panels for structured output; keep width bounded for logs.
