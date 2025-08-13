# Python exceptions and tracebacks cheatsheet

## ModuleNotFoundError
- Symptom: ModuleNotFoundError: No module named 'X'
- Root cause: Package X not installed in current environment or wrong interpreter.
- Fix: pip install X (or poetry/pipenv equivalent). Ensure correct venv is active. Check PYTHONPATH for local modules.

## ImportError: cannot import name 'X' from 'Y'
- Cause: Version mismatch or symbol moved/renamed. Sometimes circular import.
- Fix: Pin compatible versions, import from correct submodule, refactor circular imports.

## AttributeError: 'Obj' has no attribute 'X'
- Cause: API change, wrong object type, monkeypatch missed.
- Fix: Inspect type(obj), print(dir(obj)), consult library docs for new attribute name.

## TypeError: missing required positional argument
- Cause: Function signature mismatch after upgrade.
- Fix: Check function signature, add/rename arguments; pin lib version if needed.

## ValueError: could not convert string to float
- Cause: Bad input data; locale/decimal separator issues.
- Fix: Validate/clean input, handle None/""; use Decimal when needed.

## UnicodeDecodeError / EncodeError
- Cause: Wrong file encoding assumptions.
- Fix: Open files with encoding="utf-8" and errors="ignore" or correct codec; normalize inputs.
