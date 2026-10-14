"""Convenient Python-only launcher: python run.py."""

from pathlib import Path
import subprocess
import sys


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    candidates = [root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python"]
    interpreter = next((str(path) for path in candidates if path.exists()), sys.executable)
    raise SystemExit(subprocess.call([interpreter, "-m", "streamlit", "run", str(root / "app.py")], cwd=root))
