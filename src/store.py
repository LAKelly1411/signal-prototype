import json
from pathlib import Path

DEFAULT_PATH = Path("data/signals.json")


def load(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(signals: list[dict], path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(signals, f, indent=2, ensure_ascii=False)


def merge_new(existing: list[dict], new_signals: list[dict]) -> tuple[list[dict], list[dict]]:
    """Append signals whose id isn't already present. Never overwrites history."""
    existing_ids = {s["id"] for s in existing}
    added = [s for s in new_signals if s["id"] not in existing_ids]
    return existing + added, added
