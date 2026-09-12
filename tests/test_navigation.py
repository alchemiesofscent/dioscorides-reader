from pathlib import Path
import shutil
import subprocess

import pytest


def test_async_navigation_does_not_mix_versions():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the asynchronous UI regression suite")
    result = subprocess.run([node, "--test", str(Path(__file__).with_name("navigation_races.cjs"))],
                            text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
