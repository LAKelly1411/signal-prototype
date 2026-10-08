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
