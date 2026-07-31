from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RADAR_TESTS = sorted((ROOT / "xhs-topic-radar" / "test").glob("*.test.mjs"))


def test_xhs_topic_radar_node_suite() -> None:
    try:
        version = subprocess.run(
            ["node", "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise AssertionError("xhs-topic-radar requires Node.js >=22.5.0") from error
    assert version.returncode == 0, "xhs-topic-radar requires Node.js >=22.5.0"
    major, minor, *_ = version.stdout.strip().lstrip("v").split(".")
    assert (int(major), int(minor)) >= (22, 5), (
        "xhs-topic-radar requires Node.js >=22.5.0; "
        f"found {version.stdout.strip()}"
    )

    result = subprocess.run(
        ["node", "--test", *(str(path) for path in RADAR_TESTS)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
