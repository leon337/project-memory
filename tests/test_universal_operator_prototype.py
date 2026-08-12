from __future__ import annotations

import re
from pathlib import Path


PROTOTYPE_ROOT = Path(__file__).resolve().parents[1] / "prototypes" / "pm-universal-operator-ui"


def test_prototype_uses_relative_responsive_units_as_primary_scale() -> None:
    css = (PROTOTYPE_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "rem" in css
    assert "clamp(" in css
    assert "minmax(" in css
    assert "fr" in css
    assert "dvh" in css

    pixel_values = [float(value) for value in re.findall(r"(?<![\w.-])(\d+(?:\.\d+)?)px\b", css)]
    assert pixel_values
    assert all(value == 1 for value in pixel_values)


def test_prototype_separates_current_step_from_proven_progress() -> None:
    html = (PROTOTYPE_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (PROTOTYPE_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="progressPercent">40%</strong>' in html
    assert 'id="progressLabel">2 de 5 comprovadas</span>' in html
    assert 'id="currentPositionLabel">Etapa atual: 3 de 5</small>' in html
    assert "progress: 60" not in javascript
    assert javascript.count("progress: 40") == 4
    assert "progress: 100" in javascript


def test_home_keeps_technical_execution_fields_in_secondary_drawer() -> None:
    html = (PROTOTYPE_ROOT / "index.html").read_text(encoding="utf-8")

    drawer_start = html.index('id="technicalDrawer"')
    main_start = html.index('id="mainContent"')
    main_end = html.index('id="drawerBackdrop"')
    main_html = html[main_start:main_end]
    drawer_html = html[drawer_start:]

    assert "summaryCapability" not in main_html
    assert "summaryRoute" not in main_html
    assert "connection-list" not in main_html
    assert 'id="drawerCapability"' in drawer_html
    assert 'id="drawerRoute"' in drawer_html
    assert 'id="drawerJournal"' in drawer_html
    assert 'id="drawerRecovery"' in drawer_html
