"""Historical: gambling_baseline.json was recorded from the pre-sector code at
commit 4e8ea12, so the sector refactor could prove it changed nothing. Running
the recorder against today's code would record the refactor against itself, so
main() refuses. To regenerate, check out 4e8ea12 and run it there:

    .venv/bin/python -m tests.fixtures.make_gambling_baseline

Only collector_snapshot is still used, by tests/test_gambling_equivalence.py.
"""

import json


def collector_snapshot(collector) -> dict:
    attrs = {k: v for k, v in vars(collector).items() if k != "api_key"}
    return {
        "class": type(collector).__name__,
        "attrs": json.loads(json.dumps(attrs, default=str, sort_keys=True)),
    }


def main() -> None:
    raise SystemExit(
        "Refusing to run: tests/fixtures/gambling_baseline.json was recorded from "
        "the pre-sector code at commit 4e8ea12. Regenerate it only by checking "
        "that commit out and running this script there."
    )


if __name__ == "__main__":
    main()
