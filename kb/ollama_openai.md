# OpenAI and Ollama operational notes

## OpenAI
- Env: CRASHSENSE_OPENAI_KEY required for API use; set model names conservatively.
- Timeouts: keep connect<=5s, read<=60s; retry on 429/5xx with backoff.
- Embeddings: text-embedding-3-small is cheap and strong; large model optional.

## Ollama
- Daemon: OLLAMA_HOST defaults to http://localhost:11434; ensure `ollama serve`.
- Models: pull before use (e.g., `ollama pull llama3.2:1b`).
- Errors: "model not found" -> advise pull; timeouts -> reduce prompt or use smaller model.
