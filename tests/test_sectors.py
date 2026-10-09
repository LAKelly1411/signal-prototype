from pathlib import Path

import pytest
import yaml

from src import sectors
from src.sectors import SectorConfigError, list_sector_slugs, load_sector

MINIMAL = {
    "slug": "fintech",
    "name": "Fintech",
    "brief": "UK fintech and payments.",
    "prompt": {f: f"{f} text" for f in sectors.PROMPT_FIELDS},
    "sources": {"gazette": {}},
}


def write(dir_: Path, name: str, data) -> None:
    (dir_ / name).write_text(yaml.safe_dump(data), encoding="utf-8")


class TestGambling:
    def test_loads(self):
        s = load_sector("gambling")
        assert s.slug == "gambling"
        assert s.name == "Gambling & gaming"
        assert [c["name"] for c in s.companies][:2] == [
            "bet365 Group Limited", "Entain Holdings (UK) Limited"]
        assert s.tickers["RNK"] == "Rank Group"
        assert list(s.sources) == [
            "gambling_commission", "companies_house", "gazette", "dcms",
            "parliament", "asa", "bgc", "insolvency_service", "lse_rns"]

    def test_paths(self):
        s = load_sector("gambling")
        assert s.signals_path == Path("data/gambling/signals.json")
        assert s.run_status_path == Path("data/gambling/run_status.json")
        assert s.archive_ids_path == Path("data/gambling/archive/ids.json")


class TestValidation:
    def test_minimal_config_loads(self, tmp_path):
        write(tmp_path, "fintech.yaml", MINIMAL)
        s = load_sector("fintech", config_dir=tmp_path)
        assert s.keywords == [] and s.companies == [] and s.categories == []

    @pytest.mark.parametrize("field", ["slug", "name", "brief", "prompt", "sources"])
    def test_required_fields(self, tmp_path, field):
        write(tmp_path, "fintech.yaml", {k: v for k, v in MINIMAL.items() if k != field})
        with pytest.raises(SectorConfigError, match=field):
            load_sector("fintech", config_dir=tmp_path)

    def test_slug_must_match_filename(self, tmp_path):
        write(tmp_path, "fintech.yaml", {**MINIMAL, "slug": "payments"})
        with pytest.raises(SectorConfigError, match="slug"):
            load_sector("fintech", config_dir=tmp_path)

    def test_prompt_needs_every_field(self, tmp_path):
        prompt = dict(MINIMAL["prompt"]); prompt.pop("newsroom")
        write(tmp_path, "fintech.yaml", {**MINIMAL, "prompt": prompt})
        with pytest.raises(SectorConfigError, match="newsroom"):
            load_sector("fintech", config_dir=tmp_path)

    def test_unknown_source_rejected(self, tmp_path):
        write(tmp_path, "fintech.yaml", {**MINIMAL, "sources": {"fca_scraper": {}}})
        with pytest.raises(SectorConfigError, match="fca_scraper"):
            load_sector("fintech", config_dir=tmp_path)

    def test_bad_category_regex_rejected(self, tmp_path):
        cats = [{"name": "Crypto", "pattern": "crypto(", "before": "Enforcement action"}]
        write(tmp_path, "fintech.yaml", {**MINIMAL, "categories": cats})
        with pytest.raises(SectorConfigError, match="categories"):
            load_sector("fintech", config_dir=tmp_path)

    def test_category_before_must_be_core(self, tmp_path):
        cats = [{"name": "Crypto", "pattern": "crypto", "before": "Nonsense"}]
        write(tmp_path, "fintech.yaml", {**MINIMAL, "categories": cats})
        with pytest.raises(SectorConfigError, match="before"):
            load_sector("fintech", config_dir=tmp_path)

    def test_unquoted_company_number_rejected(self, tmp_path):
        # YAML reads 04241161 as the int 4241161, losing the leading zero.
        (tmp_path / "fintech.yaml").write_text(
            yaml.safe_dump({**MINIMAL}) + "companies:\n  - name: X Ltd\n    company_number: 04241161\n",
            encoding="utf-8")
        with pytest.raises(SectorConfigError, match="company_number"):
            load_sector("fintech", config_dir=tmp_path)

    def test_error_names_the_file(self, tmp_path):
        write(tmp_path, "fintech.yaml", {k: v for k, v in MINIMAL.items() if k != "name"})
        with pytest.raises(SectorConfigError, match="fintech.yaml"):
            load_sector("fintech", config_dir=tmp_path)

    def test_missing_file(self, tmp_path):
        with pytest.raises(SectorConfigError, match="not found"):
            load_sector("nope", config_dir=tmp_path)


class TestUserAdditions:
    def test_companies_key_is_merged(self, tmp_path):
        write(tmp_path, "fintech.yaml", MINIMAL)
        write(tmp_path, "fintech.user.yaml", {"companies": [{"name": "Monzo Bank Ltd"}]})
        assert [c["name"] for c in load_sector("fintech", config_dir=tmp_path).companies] == ["Monzo Bank Ltd"]

    def test_dashboard_operators_key_is_merged(self, tmp_path):
        # The dashboard's watchlist form writes {"operators": [...]}.
        write(tmp_path, "fintech.yaml", {**MINIMAL, "companies": [{"name": "A Ltd"}]})
        write(tmp_path, "fintech.user.yaml", {"operators": [{"name": "B Ltd", "company_number": None}]})
        names = [c["name"] for c in load_sector("fintech", config_dir=tmp_path).companies]
        assert names == ["A Ltd", "B Ltd"]


class TestListing:
    def test_lists_slugs_without_user_files(self, tmp_path):
        write(tmp_path, "fintech.yaml", MINIMAL)
        write(tmp_path, "fintech.user.yaml", {"companies": []})
        write(tmp_path, "gambling.yaml", {**MINIMAL, "slug": "gambling"})
        assert list_sector_slugs(config_dir=tmp_path) == ["fintech", "gambling"]

    def test_skips_stems_that_are_not_valid_slugs(self, tmp_path):
        # The slug becomes a path under data/, so `..yaml` must never list.
        write(tmp_path, "fintech.yaml", MINIMAL)
        for name in ("..yaml", "Bad_Name.yaml", "-x.yaml"):
            write(tmp_path, name, MINIMAL)
        assert list_sector_slugs(config_dir=tmp_path) == ["fintech"]


class TestIndex:
    def test_update_index_merges_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
        sectors.update_index("gambling", name="Gambling & gaming", status="ready", signal_count=3)
        sectors.update_index("gambling", status="error", error="boom")
        index = sectors.read_index()
        assert index["gambling"] == {"slug": "gambling", "name": "Gambling & gaming",
                                     "status": "error", "signal_count": 3, "error": "boom"}

    def test_refresh_index_marks_new_sectors_setting_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
        monkeypatch.setattr(sectors, "CONFIG_DIR", tmp_path)
        write(tmp_path, "fintech.yaml", MINIMAL)
        sectors.refresh_index(["fintech"])
        entry = sectors.read_index()["fintech"]
        assert entry["status"] == "setting_up" and entry["name"] == "Fintech"

    def test_refresh_index_records_any_load_failure_and_continues(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
        monkeypatch.setattr(sectors, "CONFIG_DIR", tmp_path)
        (tmp_path / "broken.yaml").write_bytes(b"slug: broken\nname: \xff\xfe\n")
        write(tmp_path, "fintech.yaml", MINIMAL)
        sectors.refresh_index(["broken", "fintech"])
        index = sectors.read_index()
        assert index["broken"]["status"] == "error" and index["broken"]["error"]
        assert index["fintech"]["status"] == "setting_up"

    def test_corrupt_index_is_treated_as_empty(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
        monkeypatch.setattr(sectors, "CONFIG_DIR", tmp_path)
        (tmp_path / "sectors.json").write_text('[{"slug": "gambl', encoding="utf-8")
        with caplog.at_level("WARNING"):
            assert sectors.read_index() == {}
        assert "unreadable sector index" in caplog.text
        write(tmp_path, "fintech.yaml", MINIMAL)
        sectors.refresh_index(["fintech"])
        assert set(sectors.read_index()) == {"fintech"}

    def test_refresh_index_drops_sectors_whose_config_is_gone(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sectors, "INDEX_PATH", tmp_path / "sectors.json")
        monkeypatch.setattr(sectors, "CONFIG_DIR", tmp_path)
        write(tmp_path, "fintech.yaml", MINIMAL)
        sectors.update_index("retired", status="ready", signal_count=4)
        sectors.update_index("fintech", status="ready", signal_count=2)
        sectors.refresh_index(["fintech"])
        index = sectors.read_index()
        assert set(index) == {"fintech"}
        assert index["fintech"]["signal_count"] == 2  # kept as it was


def test_known_sources_match_the_registry():
    from src.pipeline import COLLECTORS
    assert tuple(COLLECTORS) == sectors.KNOWN_SOURCES


class TestParseSector:
    def test_valid_dict(self):
        s = sectors.parse_sector(dict(MINIMAL), "fintech")
        assert s.slug == "fintech" and s.companies == []

    def test_slug_mismatch(self):
        with pytest.raises(SectorConfigError, match="slug"):
            sectors.parse_sector({**MINIMAL, "slug": "other"}, "fintech")

    def test_same_errors_as_load_sector(self):
        bad = {**MINIMAL, "sources": {"fca_scraper": {}}}
        with pytest.raises(SectorConfigError, match="fca_scraper"):
            sectors.parse_sector(bad, "fintech")

    def test_unquoted_number_rejected(self):
        bad = {**MINIMAL, "companies": [{"name": "X Ltd", "company_number": 4241161}]}
        with pytest.raises(SectorConfigError, match="company_number"):
            sectors.parse_sector(bad, "fintech")

    def test_error_names_the_virtual_file(self):
        with pytest.raises(SectorConfigError, match="fintech.yaml"):
            sectors.parse_sector({k: v for k, v in MINIMAL.items() if k != "brief"}, "fintech")

    @pytest.mark.parametrize("slug", ["a/b", "../x", "B", "b\n"])
    def test_rejects_invalid_slug_argument(self, slug):
        with pytest.raises(SectorConfigError, match="slug"):
            sectors.parse_sector({**MINIMAL, "slug": slug}, slug)


def test_build_rejects_trailing_newline_slug():
    # Same slug on both sides, so only the regex can reject it.
    path = Path("config/sectors/b\n.yaml")
    with pytest.raises(SectorConfigError, match="slug"):
        sectors._build(path, {**MINIMAL, "slug": "b\n"}, {}, path)


def test_list_skips_trailing_newline_filename(tmp_path):
    write(tmp_path, "fintech.yaml", MINIMAL)
    (tmp_path / "b\n.yaml").write_text(yaml.safe_dump({**MINIMAL, "slug": "b\n"}), encoding="utf-8")
    assert list_sector_slugs(config_dir=tmp_path) == ["fintech"]
