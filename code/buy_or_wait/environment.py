"""Load only supported local credential variables; never log their values."""
import os
from pathlib import Path


def load_credentials(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        name, value = name.strip(), value.strip()
        if name not in {'GEMINI_API_KEY', 'GOOGLE_API_KEY'}:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if value and value != 'YOUR_GEMINI_API_KEY_HERE':
            os.environ.setdefault(name, value)
