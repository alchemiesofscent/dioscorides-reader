from __future__ import annotations

import re
import tomllib
from pathlib import Path

from dioscorides_reader import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_the_same_everywhere():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == __version__
    html = (ROOT / "web/reader.html").read_text(encoding="utf-8")
    assets = re.findall(r'(?:href|src)="([^"]+\.(?:css|js))(?:\?v=([^"]*))?"', html)
    local = [(path, version) for path, version in assets if not path.startswith("vendor/")]
    assert local and all(version == __version__ for _, version in local), local
    assert f"## {__version__} " in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
