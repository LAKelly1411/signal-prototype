"""Gambling must behave exactly as it did before sectors existed. The
baseline was recorded from the pre-sector code (tests/fixtures/
make_gambling_baseline.py); every assertion compares against it."""

import copy
import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from src import categories, cluster, score
from src.entities import build_alias_map
from src.sectors import load_sector

BASE = json.loads(Path("tests/fixtures/gambling_baseline.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(BASE["now"])


def test_prompts_are_identical():
    assert score.SYSTEM_PROMPT == BASE["prompts"]["system"]
    assert score.CLUSTER_SYSTEM_PROMPT == BASE["prompts"]["cluster"]
    assert score.THEME_SYSTEM_PROMPT == BASE["prompts"]["theme"]


def test_summary_versions_are_identical():
    assert score.CLUSTER_SUMMARY_VERSION == BASE["versions"]["cluster"]
    assert score.THEME_SUMMARY_VERSION == BASE["versions"]["theme"]


def test_taxonomy_is_identical():
    gambling = load_sector("gambling")
    assert categories.taxonomy() == BASE["taxonomy"]
    assert categories.taxonomy(gambling) == BASE["taxonomy"]


def test_categories_are_identical():
    gambling = load_sector("gambling")
    assert [categories.canonical_category(*i) for i in BASE["category_inputs"]] == BASE["categories"]
    assert [categories.canonical_category(*i, sector=gambling) for i in BASE["category_inputs"]] == BASE["categories"]


def test_exclusions_are_identical():
    assert [cluster.is_excluded(e) for e in BASE["entities"]] == BASE["excluded"]


def test_clusters_and_themes_are_identical():
    working = copy.deepcopy(BASE["signals"])
    alias_map = build_alias_map(BASE["alias_operators"])
    cluster.assign_clusters(working, now=NOW, alias_map=alias_map)
    cluster.assign_themes(working, now=NOW, alias_map=alias_map)
    assert {s["id"]: s.get("cluster_id") for s in working} == BASE["cluster_ids"]
    assert {s["id"]: s.get("theme_id") for s in working} == BASE["theme_ids"]


def test_collectors_are_identical(monkeypatch):
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "baseline-test-key")
    from src.pipeline import build_collectors, load_sources
    from tests.fixtures.make_gambling_baseline import collector_snapshot

    got = [collector_snapshot(c) for c in build_collectors(load_sources())]
    assert got == BASE["collectors"]
