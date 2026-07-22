from pathlib import Path

assert Path("allowed.txt").read_text(encoding="utf-8").strip() == "approved"
assert Path("protected.txt").read_text(encoding="utf-8").strip() == "preserve"
