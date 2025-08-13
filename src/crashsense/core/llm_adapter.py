# src/crashsense/core/llm_adapter.py
import os
import time
import math
import requests
import subprocess
import re  # Add this import for sanitization
from typing import Optional
from rich.console import Console  # Import Console from rich

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"
# Initialize the console for rich output
console = Console()


class LLMAdapter:
    def __init__(self, provider: str = "openai", local_model: Optional[str] = None):
        self.provider = provider
        self.openai_key = os.environ.get("CRASHSENSE_OPENAI_KEY")
        self.local_model = local_model
        self._cache = {}
        # Simple rate limit: minimum seconds between API calls
        try:
            self._min_call_interval = float(
                os.environ.get("CRASHSENSE_MIN_CALL_INTERVAL_SEC", "1.0")
            )
        except ValueError:
            self._min_call_interval = 1.0
        self._last_call_ts = 0.0
        # Embedding model selection for RAG
        self._embed_model = os.environ.get(
            "CRASHSENSE_OPENAI_EMBED_MODEL", "text-embedding-3-small"
        )

    def _rate_limit_sleep(self):
        now = time.time()
        elapsed = now - self._last_call_ts
        if elapsed < self._min_call_interval:
            time.sleep(self._min_call_interval - elapsed)
        self._last_call_ts = time.time()

    def _post_with_retries(
        self, url: str, *, headers=None, json=None, timeout=60, max_retries=3
    ):
        """POST with basic retry/backoff on 429/5xx/timeouts."""
        backoff = 1.0
        for attempt in range(max_retries):
            self._rate_limit_sleep()
            try:
                resp = requests.post(url, headers=headers, json=json, timeout=timeout)
                # Retry on 429/5xx
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                return resp
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise
        # Fallback shouldn't be reached; return last response or raise
        return requests.post(url, headers=headers, json=json, timeout=timeout)

    # --- RAG helpers -----------------------------------------------------
    def _embed_openai(self, texts):
        """Get embeddings from OpenAI for a list of strings."""
        if not self.openai_key:
            raise RuntimeError("OpenAI key not set for embeddings")
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        body = {"model": self._embed_model, "input": texts}
        resp = self._post_with_retries(OPENAI_EMBED_URL, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return [d["embedding"] for d in data.get("data", [])]

    def _cosine(self, a, b):
        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(y * y for y in b))
        if da == 0 or db == 0:
            return 0.0
        return num / (da * db)

    def retrieve(self, query: str, docs: list[str], top_k: int = 3) -> list[tuple[str, float]]:
        """Simple retriever: try OpenAI embeddings; fallback to keyword overlap.

        Returns list of (doc, score) sorted by score desc.
        """
        # Filter bad docs
        docs = [d for d in docs if isinstance(d, str) and d.strip()]
        if not docs:
            return []
        # Dense path
        if self.openai_key:
            try:
                emb = self._embed_openai([query] + docs)
                if not emb or len(emb) < 1:
                    raise RuntimeError("No embedding returned")
                qv, dv = emb[0], emb[1:]
                scored = [(doc, self._cosine(qv, v)) for doc, v in zip(docs, dv)]
                return sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]
            except Exception:
                # Fall back to keyword below
                pass
        # Keyword fallback
        qk = set(w for w in re.findall(r"\b\w+\b", query.lower()) if len(w) > 2)
        scored = []
        for doc in docs:
            tk = set(w for w in re.findall(r"\b\w+\b", doc.lower()) if len(w) > 2)
            inter = len(qk & tk)
            scored.append((doc, float(inter)))
        return sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]

    def analyze(self, prompt: str, system: str = "You are CrashSense assistant."):
        key = (self.provider, self.local_model, system, prompt[:4096])
        if key in self._cache:
            return self._cache[key]
        if self.provider == "openai" and self.openai_key:
            ans = self._call_openai(prompt, system)
        elif self.provider == "ollama":
            ans = self._call_ollama(prompt)
        else:
            ans = self._heuristic_answer(prompt)
        self._cache[key] = ans
        return ans

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
        try:
            resp = self._post_with_retries(
                OPENAI_API_URL, headers=headers, json=body, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            # return full LLM response as both explanation and patch so code examples are visible
            return {
                "explanation": text,
                "root_cause": "See explanation",
                "patch": text,
            }
        except requests.exceptions.Timeout:
            return {
                "explanation": "OpenAI request timed out. Try again or reduce max tokens.",
                "root_cause": "timeout",
                "patch": "",
            }
        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status == 401:
                rc = "unauthorized"
                exp = "OpenAI API rejected the request (401). Check CRASHSENSE_OPENAI_KEY."
            elif status == 429:
                rc = "rate_limited"
                exp = (
                    "Rate limited by OpenAI (429). Slow down requests or upgrade plan."
                )
            else:
                rc = "http_error"
                exp = f"OpenAI HTTP error: {status}"
            return {"explanation": exp, "root_cause": rc, "patch": ""}
        except Exception:
            return {
                "explanation": "Failed to call OpenAI API due to an unexpected error.",
                "root_cause": "exception",
                "patch": "",
            }

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
            self._rate_limit_sleep()
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
            resp = self._post_with_retries(
                f"{host}/api/generate",
                headers=None,
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=(5, timeout_s),
                max_retries=3,
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
