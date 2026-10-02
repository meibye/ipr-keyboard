"""The early-boot OLED screen — scripts/headless/ipr_oled_boot.py.

The script runs as root before the application exists, so it is loaded here
the same way it loads the SSD1306 driver: by path, with no package import.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "headless" / "ipr_oled_boot.py"


@pytest.fixture(scope="module")
def boot():
    spec = importlib.util.spec_from_file_location("ipr_oled_boot", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reads_the_defaults_file(boot, tmp_path):
    path = tmp_path / "ipr-oled"
    path.write_text(
        "# managed by install_oled_support.sh\n"
        "OLED_BUS=1\n"
        'OLED_ADDR="0x3c"\n'
        "OLED_ROTATE=180\n"
        "REPO_DIR=/home/pi/ipr-keyboard\n"
        "\n",
        encoding="utf-8",
    )
    cfg = boot.read_defaults(str(path))
    assert cfg == {
        "OLED_BUS": "1",
        "OLED_ADDR": "0x3c",
        "OLED_ROTATE": "180",
        "REPO_DIR": "/home/pi/ipr-keyboard",
    }
    assert int(cfg["OLED_ADDR"], 0) == 0x3C


def test_missing_defaults_file_is_not_an_error(boot, tmp_path):
    assert boot.read_defaults(str(tmp_path / "absent")) == {}


def test_unit_states_are_paired_with_their_units(boot, monkeypatch):
    class Result:
        stdout = "active\ninactive\nactivating\n"

    units = ("a.service", "b.service", "c.service")
    monkeypatch.setattr(boot.subprocess, "run", lambda *a, **k: Result())
    assert boot.units_active(units) == {
        "a.service": True,
        "b.service": False,
        "c.service": False,
    }


def test_a_short_systemctl_answer_marks_everything_pending(boot, monkeypatch):
    """Never claim a milestone is done on an answer we cannot line up."""

    class Result:
        stdout = "active\n"

    monkeypatch.setattr(boot.subprocess, "run", lambda *a, **k: Result())
    assert boot.units_active(("a.service", "b.service")) == {
        "a.service": False,
        "b.service": False,
    }


def test_systemctl_failure_marks_everything_pending(boot, monkeypatch):
    def boom(*_a, **_k):
        raise OSError("systemctl is not there yet")

    monkeypatch.setattr(boot.subprocess, "run", boom)
    assert boot.units_active(("a.service",)) == {"a.service": False}


def test_the_application_is_the_last_milestone(boot):
    labels = [label for label, _unit in boot.MILESTONES]
    assert labels[0] == "System" and labels[-1] == "Application"
    assert boot.MILESTONES[-1][1] == boot.APP_UNIT
    assert len(boot.MILESTONES) == len(boot.LINE_Y)


def test_the_driver_loads_from_a_repository_checkout(boot):
    driver = boot.load_driver(str(REPO_ROOT))
    assert (driver.WIDTH, driver.HEIGHT) == (boot.WIDTH, boot.HEIGHT)
    assert driver.device_path(1) == "/dev/i2c-1"


def test_a_missing_driver_raises_so_main_can_bail_out(boot, tmp_path):
    with pytest.raises((ImportError, OSError)):
        boot.load_driver(str(tmp_path))


def test_render_draws_the_header_lines_and_the_mode_badge(boot):
    pytest.importorskip("PIL")
    fonts = (
        boot.load_font("DejaVuSans-Bold.ttf", 12),
        boot.load_font("DejaVuSans.ttf", 9),
        boot.load_font("DejaVuSans-Bold.ttf", 8),
    )

    def lit(img, box):
        return img.crop(box).convert("L").histogram()[255]

    img = boot.render(fonts, {"System": True}, "PROD")
    assert img.size == (boot.WIDTH, boot.HEIGHT) and img.mode == "1"
    assert lit(img, (0, 0, 128, 16)) > 0  # header band
    assert lit(img, (95, 0, 128, 14)) > 40  # inverted badge
    for y in boot.LINE_Y:
        assert lit(img, (0, y, 128, y + 11)) > 0  # one line per milestone

    done = boot.render(fonts, {label: True for label, _ in boot.MILESTONES}, "DEV")
    assert done.tobytes() != img.tobytes(), "ticked milestones change the frame"
