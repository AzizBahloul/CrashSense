# CrashSense

AI-powered crash log analyzer with safe command suggestions, memory, and optional RAG from your docs.

## Highlights

- Auto-detects the latest crash-like log file (Python, Apache, Nginx, system hints)
- Concise root-cause + actionable patch suggestions
- Includes recent terminal history to improve context
- Optional RAG over `kb/` and curated docs in `src/data` (configurable)
- Safe-mode shell command runner with preflight checks (denylist, path checks)

## Quickstart

Install from source (editable):

```bash
pip install -e .
```

Initialize and pick an LLM provider (OpenAI or local Ollama):

```bash
crashsense init
```

Analyze a log (auto-detect if none provided):

```bash
crashsense analyze
```

Pipe from STDIN:

```bash
cat error.log | crashsense analyze
```

Launch the TUI:

```bash
crashsense tui
```

## Screenshots

Below are example terminal screenshots; replace with your own as needed.

![Analyze output 1](image1.png)

![Analyze output 2](image2.png)

![Analyze output 3](image3.png)

## RAG docs (optional)

- Defaults index `kb/` and curated files in `src/data`:
   - `crashsense_best_practices.md`
   - `python_exceptions_playbook.md`
   - `web_server_error_patterns.md`
   - `linux_permission_paths.md`
- Manage docs at runtime:

```bash
crashsense rag add /path/to/extra/doc_or_folder
crashsense rag clear
crashsense rag build --dry-run
```

## Config & Security

- Config: `~/.crashsense/config.toml`
- OpenAI key: `CRASHSENSE_OPENAI_KEY`
- Command execution requires confirmation and passes safety checks

## Troubleshooting (Ollama)

If automatic pull fails:

```bash
ollama pull llama3.2:1b
```

Check daemon and network; see docs: https://ollama.com/docs
