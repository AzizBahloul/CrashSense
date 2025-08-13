# Python Exceptions Quick Fix Playbook

Common errors with actionable fixes.

- ModuleNotFoundError: Install missing package (pip install <pkg>) or fix PYTHONPATH; ensure virtualenv is active.
- ImportError: Check circular imports; move import inside function; correct module name and version.
- FileNotFoundError: Verify path exists; use os.path.exists; create parent dirs with os.makedirs(..., exist_ok=True).
- PermissionError: Use a writable path (e.g., ~/.local/share/app) or adjust chmod/chown on target files/directories; avoid writing to /var without sudo.
- UnicodeDecodeError: Open files with correct encoding (encoding="utf-8", errors="replace"); normalize inputs.
- TypeError: Validate function signatures; add typing; guard None inputs.
- ValueError: Validate user inputs; add try/except with clear messages.
- ZeroDivisionError: Add guards for zero; handle empty denominators gracefully.

Diagnostics:
- Print sys.path; run python -V; show which python; check env vars.
- Reproduce with minimal script; write unit tests for the failing case.

Secure remediation:
- Avoid running arbitrary shell; prefer explicit subprocess with lists and timeouts.
- Never pipe sudo | sh from the internet; verify sources.
