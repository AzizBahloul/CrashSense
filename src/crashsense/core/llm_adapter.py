"""
LLM Adapter supporting:
- OpenAI (via HTTP API) — test the key by a small call
- Local Ollama via CLI (subprocess) — pull/run models via ollama CLI

Notes:
- Ollama CLI behavior can vary across versions; this adapter uses the `ollama` binary when provider == "ollama".
- All network or subprocess calls are executed only with user consent in the CLI flow.
"""

import os
import requests
import subprocess
import re  # Add this import for sanitization
from typing import Optional
from rich.console import Console  # Import Console from rich

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
# Initialize the console for rich output
console = Console()


class LLMAdapter:
    def __init__(self, provider="openai", local_model: Optional[str] = None):
        self.provider = provider
        self.openai_key = os.environ.get("CRASHSENSE_OPENAI_KEY")
        self.local_model = local_model

    def analyze(self, prompt: str, system: str = "You are CrashSense assistant."):
        if self.provider == "openai" and self.openai_key:
            return self._call_openai(prompt, system)
        elif self.provider == "ollama":
            return self._call_ollama(prompt)
        else:
            return self._heuristic_answer(prompt)

    def validate_openai_key(self) -> bool:
        if not self.openai_key:
            return False
        try:
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "Validation ping"},
                    {"role": "user", "content": "Say 'ok'"},
                ],
                "max_tokens": 5,
                "temperature": 0,
            }
            resp = requests.post(OPENAI_API_URL, headers=headers, json=body, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def _call_openai(self, prompt: str, system: str):
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 700,
            "temperature": 0.2,
        }
        resp = requests.post(OPENAI_API_URL, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        # return full LLM response as both explanation and patch so code examples are visible
        return {"explanation": text, "root_cause": "See explanation", "patch": text}

    def _sanitize_string(self, value: str) -> str:
        """
        Remove null bytes and other invalid characters from a string.
        """
        return re.sub(r"[\x00-\x1F\x7F]", "", value)

    def _call_ollama(self, prompt: str):
        """
        Prefer Ollama HTTP API; fall back to CLI. Increase timeouts and return
        clearer guidance when a model isn't present or the daemon isn't running.

        Env overrides:
        - OLLAMA_HOST (default: http://localhost:11434)
        - CRASHSENSE_OLLAMA_TIMEOUT (seconds, default: 180)
        """
        model = self.local_model or "llama3.2:1b"
        # Sanitize the model and prompt
        model = self._sanitize_string(model)
        prompt = self._sanitize_string(prompt)

        # Timeouts: (connect, read)
        try:
            timeout_s = int(os.environ.get("CRASHSENSE_OLLAMA_TIMEOUT", "180"))
        except ValueError:
            timeout_s = 180

        # 1) Try HTTP API first (more reliable than CLI REPL)
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        try:
            # Fast ping to tags to check daemon and model presence
            tags_resp = requests.get(f"{host}/api/tags", timeout=5)
            available_models = set()
            try:
                tags_json = tags_resp.json() if tags_resp.ok else {}
                for m in tags_json.get("models", []) or []:
                    name = m.get("name") or m.get("model")
                    if name:
                        available_models.add(str(name))
            except Exception:
                pass
            if available_models and model not in available_models:
                return {
                    "explanation": f"Ollama model '{model}' is not available locally. Pull it with: ollama pull {model} — or pick a smaller model via 'crashsense init'. Available: {sorted(available_models)}",
                    "root_cause": "ollama_model_missing",
                    "patch": "",
                }
            resp = requests.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=(5, timeout_s),
            )
            if resp.status_code == 200:
                data = resp.json()
                text = (data.get("response") or "").strip()
                if not text:
                    text = "Ollama returned no output."
                return {
                    "explanation": text,
                    "root_cause": "See explanation",
                    "patch": "See explanation",
                }
            else:
                # Common error body: { "error": "model 'xxx' not found" }
                try:
                    err = resp.json().get("error", resp.text)
                except Exception:
                    err = resp.text
                # Fall through to CLI but surface a helpful message if it's clearly a model issue
                if "not found" in (err or "").lower():
                    return {
                        "explanation": f"Ollama error: {err}. Try pulling the model: ollama pull {model}",
                        "root_cause": "ollama_model_missing",
                        "patch": "",
                    }
        except requests.exceptions.ConnectTimeout:
            # Daemon likely not running; fall back to CLI
            pass
        except requests.exceptions.ConnectionError:
            # Daemon not reachable; fall back to CLI
            pass
        except requests.exceptions.ReadTimeout:
            # Try CLI fallback instead of bailing immediately
            pass

        # 2) CLI fallback: use non-interactive forms only
        cli_cmds = [
            ["ollama", "run", model, "-p", prompt],
            ["ollama", "generate", "-m", model, "-p", prompt],
        ]
        for cmd in cli_cmds:
            try:
                completed = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=timeout_s
                )
                if completed.returncode == 0:
                    text = completed.stdout.strip() or completed.stderr.strip()
                    if not text:
                        text = "Ollama returned no output."
                    return {
                        "explanation": text,
                        "root_cause": "See explanation",
                        "patch": "See explanation",
                    }
                # If model missing, stderr often hints it
                stderr = (completed.stderr or "").lower()
                if "not found" in stderr or "no such model" in stderr:
                    return {
                        "explanation": f"Ollama reports the model '{model}' is missing. Pull it with: ollama pull {model}",
                        "root_cause": "ollama_model_missing",
                        "patch": "",
                    }
            except FileNotFoundError:
                return {
                    "explanation": "Ollama CLI not found on PATH.",
                    "root_cause": "ollama_not_installed",
                    "patch": "",
                }
            except subprocess.TimeoutExpired:
                return {
                    "explanation": "Ollama timed out via HTTP and CLI. Increase CRASHSENSE_OLLAMA_TIMEOUT (e.g. 300), ensure the daemon is running and the model is pulled, or switch to a smaller model (e.g. llama3.2:1b).",
                    "root_cause": "timeout",
                    "patch": "",
                }
            except ValueError as e:
                return {
                    "explanation": f"Invalid input: {e}",
                    "root_cause": "invalid_input",
                    "patch": "",
                }

        # none of the commands worked
        tried = [" ".join(c) for c in cli_cmds]
        return {
            "explanation": f"Ollama generation failed for: {tried}. Ensure the daemon is running (e.g. 'ollama serve') and the model is available.",
            "root_cause": "ollama_failed",
            "patch": "",
        }

    def _heuristic_answer(self, prompt: str):
        # Basic heuristics for stack traces and python exceptions
        lines = prompt.splitlines()
        exc = None
        for line in reversed(lines[-60:]):
            if ":" in line and line.strip().endswith(("Error", "Exception")):
                exc = line.strip()
                break
        explanation = (
            f"Heuristic analysis: found exception hint: {exc}"
            if exc
            else "Heuristic analysis: unable to parse exception type."
        )
        patch = "Check stack trace, ensure proper null checks and resource lifecycles.\nConsider adding try/except around the failing area."
        return {
            "explanation": explanation,
            "root_cause": exc or "unknown",
            "patch": patch,
        }
