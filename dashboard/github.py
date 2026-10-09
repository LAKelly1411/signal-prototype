"""The dashboard's writes to the repo, over the GitHub API: watchlist
additions, new sector configs, the sector index, and starting a pipeline run.
No Streamlit here; dashboard/app.py builds a GitHub from its secrets."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass

import requests
import yaml

from src.sectors import SLUG_RE

OWNER = "LAKelly1411"
REPO = "signal-prototype"
BRANCH = "main"
WORKFLOW = "pipeline.yml"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

logger = logging.getLogger(__name__)

MSG_NOT_SAVED = "We couldn't save the sector. Please try again."
MSG_NOT_INDEXED = "Saved. It will appear in the menu after the next update."
MSG_NOT_DISPATCHED = "Saved. Its first update will run with the next scheduled one."


class GitHubError(Exception):
    pass


class FileExists(GitHubError):
    pass


class GitHub:
    def __init__(self, token: str, http=requests):
        self.http = http
        self.headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    def get_file(self, path: str) -> tuple[str, str] | None:
        resp = self.http.get(f"{API}/contents/{path}", headers=self.headers,
                             params={"ref": BRANCH}, timeout=20)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise GitHubError(f"GET {path}: {resp.status_code}")
        payload = resp.json()
        return base64.b64decode(payload["content"]).decode("utf-8"), payload["sha"]

    def put_file(self, path: str, text: str, message: str, sha: str | None = None,
                 create_only: bool = False) -> None:
        if create_only and self.get_file(path) is not None:
            raise FileExists(path)
        body = {"message": message, "branch": BRANCH,
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii")}
        if sha:
            body["sha"] = sha
        resp = self.http.put(f"{API}/contents/{path}", headers=self.headers, json=body, timeout=20)
        if create_only and resp.status_code == 422:
            # Created by someone else between the check and the PUT.
            raise FileExists(path)
        if resp.status_code >= 400:
            raise GitHubError(f"PUT {path}: {resp.status_code}")

    def dispatch_workflow(self, inputs: dict) -> None:
        resp = self.http.post(f"{API}/actions/workflows/{WORKFLOW}/dispatches", headers=self.headers,
                              json={"ref": BRANCH, "inputs": inputs}, timeout=20)
        if resp.status_code >= 400:
            raise GitHubError(f"dispatch: {resp.status_code}")


@dataclass
class SaveResult:
    saved: bool
    indexed: bool
    dispatched: bool
    message: str
    exists: bool = False  # step 1 failed because the config file already exists


def sector_yaml(config: dict, today: str) -> str:
    header = f"# Drafted with Claude from the dashboard on {today}; reviewed by a user.\n"
    return header + yaml.safe_dump(config, sort_keys=False, allow_unicode=True)


def save_sector(gh: GitHub, config: dict, index_entry: dict, today: str) -> SaveResult:
    """Config first, then the index entry, then an all-sectors run. A later
    step only runs if the earlier one worked; nothing is left half-saved.

    The run covers every sector, not just the new one: GitHub keeps one pending
    run per concurrency group, so a single-sector dispatch could replace a
    queued scheduled run and gambling would miss an update."""
    slug = config.get("slug")
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        return SaveResult(False, False, False, MSG_NOT_SAVED)
    try:
        gh.put_file(f"config/sectors/{slug}.yaml", sector_yaml(config, today),
                    f"Add the {config['name']} sector via dashboard", create_only=True)
    except FileExists:
        logger.warning("sector config %s already exists", slug)
        return SaveResult(False, False, False, MSG_NOT_SAVED, exists=True)
    except Exception:
        logger.exception("saving the %s sector config failed", slug)
        return SaveResult(False, False, False, MSG_NOT_SAVED)

    indexed = False
    index_absent = False
    try:
        current = gh.get_file("data/sectors.json")
        if current is None:
            index_absent = True
        else:
            text, sha = current
            entries = json.loads(text)
            if not isinstance(entries, list):
                raise GitHubError("data/sectors.json is not a list")
            index = [e for e in entries if isinstance(e, dict) and e.get("slug") != slug]
            index.append(index_entry)
            index.sort(key=lambda e: e.get("slug", ""))
            gh.put_file("data/sectors.json", json.dumps(index, indent=2, ensure_ascii=False),
                        f"List the {config['name']} sector", sha=sha)
            indexed = True
    except Exception:
        logger.exception("adding %s to the sector index failed", slug)
        indexed = False

    try:
        gh.dispatch_workflow({"sector": ""})
        dispatched = True
    except Exception:
        logger.exception("starting the pipeline run for %s failed", slug)
        dispatched = False

    if not dispatched:
        message = MSG_NOT_DISPATCHED
    elif not indexed and not index_absent:
        message = MSG_NOT_INDEXED
    else:
        message = ""
    return SaveResult(True, indexed, dispatched, message)
