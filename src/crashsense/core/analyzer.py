from typing import Dict, Optional
import re
from .llm_adapter import LLMAdapter


class BackTrackEngine:
    def __init__(self, provider="auto", local_model: Optional[str] = None):
        chosen = provider
        if provider == "auto":
            # Prefer OpenAI if key present; else Ollama if reachable; else none
            import os
            from ..utils import is_executable_on_path

            if os.environ.get("CRASHSENSE_OPENAI_KEY"):
                chosen = "openai"
            elif is_executable_on_path("ollama"):
                chosen = "ollama"
            else:
                chosen = "none"
        self.llm = LLMAdapter(provider=chosen, local_model=local_model)

    def parse_log(self, text: str) -> Dict:
        language = self.detect_language(text)
        exception = self.detect_exception(text)
        frames = self.extract_frames(text)
        return {"language": language, "exception": exception, "frames": frames}

    def detect_language(self, text: str) -> str:
        if "Traceback (most recent call last)" in text:
            return "python"
        if "Exception in thread" in text or ".java:" in text:
            return "java"
        return "unknown"

    def detect_exception(self, text: str):
        m = re.search(
            r"([A-Za-z_][A-Za-z0-9_.]+(?:Exception|Error))(?::\s*(.*))?", text
        )
        if m:
            return {"type": m.group(1), "message": m.group(2) or ""}
        return None

    def extract_frames(self, text: str):
        frames = []
        for m in re.finditer(
            r'  File "([^"]+)", line (\d+), in ([^\n]+)\n\s+(.*)', text
        ):
            frames.append(
                {
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "func": m.group(3),
                    "code": m.group(4),
                }
            )
        return frames

    def analyze(self, text: str) -> Dict:
        parsed = self.parse_log(text)
        import os
        try:
            max_chars = int(os.environ.get("CRASHSENSE_PREVIEW_CHARS", "4000"))
        except ValueError:
            max_chars = 4000
        preview = text[:max_chars]
        prompt = (
            f"Crash log:\n{preview}\n\n"
            f"Parsed info: {parsed}\n\n"
            "Explain root cause and suggest a concrete code patch or remediation. Keep answers actionable and short. "
            "If you can provide shell commands that could help automatically apply fixes, list them in a 'commands:' section."
        )
        llm_ans = self.llm.analyze(prompt)
        return {"parsed": parsed, "analysis": llm_ans}
