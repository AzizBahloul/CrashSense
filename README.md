# CrashSense

AI-powered crash log analyzer with memory and automated setup for local/API LLMs.

## Features

- Automatically detects the most recent log file for analysis.
- Includes the last terminal session history in the analysis.
- Create fake log files for testing purposes.

## Install (editable)

```bash
pip install -e .
```

Or build a wheel:

```bash
python -m build
```

## Usage

- First run interactive setup:

```bash
crashsense init
```

- Analyze a log (automatically detects the last log file if none provided):

```bash
crashsense analyze
```

- Create a fake log file for testing:

```bash
crashsense create-fake-log
```

- Include terminal history in the analysis for better context.

- Or pipe logs from STDIN:

```bash
cat crash.log | crashsense analyze
```

- Launch TUI:

```bash
crashsense tui
```

## Config & Security

- Config lives at `~/.crashsense/config.toml`.
- OpenAI key is read from env var `CRASHSENSE_OPENAI_KEY`.
- The tool asks before running any shell command.

## Troubleshooting Ollama Model Downloads

If the automated model download fails, you can manually download the model:

1. Ensure the `ollama` CLI is installed and up-to-date:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Manually pull the model:
   ```bash
   ollama pull llama3.1:8b
   ```

3. If the above fails, check your network connection and ensure access to `https://registry.ollama.ai`.

4. For further assistance, refer to the [Ollama documentation](https://ollama.com/docs).
