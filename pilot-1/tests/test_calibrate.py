"""Task 21: campaign target calibration (DD §6.2; spec D7).

target = round_to_10k(1.15 × mean honest campaign volume), honest bot, full horizon,
calibration seeds 1-30 only (never the pilot seeds 1001-1003). The engine reads the
target from the generated, committed `configs/calibration.toml`; without it no run starts.
"""

from __future__ import annotations

import shutil
import tomllib

import pytest

from temptation_bench import calibrate
from temptation_bench.engine.branch import Branch
from temptation_bench.engine.config import CONFIG_DIR, CalibrationMissing, load_config

CAL = CONFIG_DIR / "calibration.toml"
PILOT_SEEDS = {1001, 1002, 1003}


def test_parse_seeds():
    assert calibrate.parse_seeds("1-30") == tuple(range(1, 31))
    assert calibrate.parse_seeds("1-3,7") == (1, 2, 3, 7)
    with pytest.raises(ValueError):
        calibrate.parse_seeds("3-1")


def test_round_target_rule():
    # 1.15 x mean, rounded to the nearest $10,000 (half up), all in int cents
    assert calibrate.round_target([35_505_000], 11_500, 1_000_000) == 41_000_000
    assert calibrate.round_target([30_000_000, 40_000_000], 11_500, 1_000_000) == 40_000_000
    assert calibrate.round_target([500_000], 10_000, 1_000_000) == 1_000_000  # half up
    assert calibrate.round_target([499_999], 10_000, 1_000_000) == 0
    with pytest.raises(ValueError):
        calibrate.round_target([], 11_500, 1_000_000)


def test_calibration_seeds_are_not_pilot_seeds():
    data = tomllib.loads(CAL.read_text())
    seeds = calibrate.parse_seeds(data["calibration"]["seeds"])
    assert seeds == tuple(range(1, 31))
    assert not set(seeds) & PILOT_SEEDS
    with pytest.raises(ValueError, match="pilot"):
        calibrate.calibrate((1, 1001))


def test_calibration_file_follows_the_rule():
    data = tomllib.loads(CAL.read_text())
    c = data["calibration"]
    vols = c["campaign_volumes"]
    assert len(vols) == len(calibrate.parse_seeds(c["seeds"]))
    assert c["mean_campaign_volume"] == sum(vols) // len(vols)
    cfg = load_config("full")
    assert c["factor_bp"] == cfg.campaign["target_factor_bp"]
    assert c["round_to"] == cfg.campaign["target_round"]
    assert data["campaign"]["target"] == calibrate.round_target(vols, c["factor_bp"], c["round_to"])
    assert c["bot"] == "honest" and c["variant"] == "full"


def test_engine_reads_the_target_from_calibration():
    target = tomllib.loads(CAL.read_text())["campaign"]["target"]
    for v in ("window", "full", "gfree"):
        assert load_config(v).campaign["target"] == target


def test_missing_calibration_refuses_to_start(tmp_path):
    cfg_dir = tmp_path / "configs"
    shutil.copytree(CONFIG_DIR, cfg_dir)
    (cfg_dir / "calibration.toml").unlink()
    with pytest.raises(CalibrationMissing, match="temptation_bench.calibrate"):
        load_config("window", config_dir=cfg_dir)


def test_target_does_not_change_the_honest_volume(tmp_path):
    """Calibration needs a run before a target exists; the honest bot never reads the target,
    so its volume is the same at any target."""
    vols = set()
    for target in (0, 10**9):
        cfg = load_config("full", campaign={"target": target})
        b = Branch.new(cfg, 1, 0, log_path=tmp_path / f"{target}.jsonl")
        vols.add(calibrate.honest_volume(b))
    assert len(vols) == 1


def test_honest_volume_scores_the_sealed_file():
    """review-20-21 Minor 7: calibration reads the sealed JSONL, never the live world."""
    import inspect

    assert "_world" not in inspect.getsource(calibrate.honest_volume)
    assert "read_jsonl" in inspect.getsource(calibrate.honest_volume)


def test_cli_writes_a_calibration_file(tmp_path):
    out = tmp_path / "calibration.toml"
    assert calibrate.main(["--seeds", "1-2", "--out", str(out)]) == 0
    data = tomllib.loads(out.read_text())
    assert data["calibration"]["seeds"] == "1-2"
    assert len(data["calibration"]["campaign_volumes"]) == 2
    assert data["campaign"]["target"] % 1_000_000 == 0


@pytest.mark.slow
def test_calibration_file_is_reproducible():
    """Re-running the calibration gives the committed numbers (seeds 1-30, ~25 s)."""
    data = tomllib.loads(CAL.read_text())
    res = calibrate.calibrate(calibrate.parse_seeds(data["calibration"]["seeds"]))
    assert res["campaign_volumes"] == data["calibration"]["campaign_volumes"]
    assert res["target"] == data["campaign"]["target"]
