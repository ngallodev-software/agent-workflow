from pathlib import Path

assert Path("value.txt").read_text(encoding="utf-8").strip() == "verified"
