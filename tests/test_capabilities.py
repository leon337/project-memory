from pathlib import Path

import pytest

from context_anchor.capabilities import (
    CapabilityNotAvailable,
    CapabilityResolver,
)


def fake_path(*available: str):
    installed = set(available)
    return lambda name: f"/mock/bin/{name}" if name in installed else None


def test_text_edit_resolves_only_an_editor_present_on_path() -> None:
    resolver = CapabilityResolver(
        which=fake_path("gedit"),
        desktop_dirs=(),
    )

    result = resolver.resolve("text.edit")

    assert result.app_id == "gedit"
    assert result.command == ("/mock/bin/gedit",)
    assert result.source == "path"


def test_xed_provider_requests_a_fresh_editing_window() -> None:
    resolver = CapabilityResolver(which=fake_path("xed"), desktop_dirs=())

    result = resolver.resolve("text.edit")

    assert result.open_app_target == "/mock/bin/xed --new-window"


def test_calculate_falls_back_to_the_available_tool() -> None:
    resolver = CapabilityResolver(
        which=fake_path("mate-calc"),
        desktop_dirs=(),
    )

    result = resolver.resolve("calculate")

    assert result.app_id == "mate-calc"
    assert result.open_app_target == "/mock/bin/mate-calc"


def test_vs_code_aliases_converge_on_the_same_installed_application() -> None:
    resolver = CapabilityResolver(
        which=fake_path("code", "codium"),
        desktop_dirs=(),
    )

    short_name = resolver.resolve("code.edit", hint="VS Code")
    full_name = resolver.resolve("code.edit", hint="Visual Studio Code")

    assert short_name == full_name
    assert short_name.app_id == "code"


@pytest.mark.parametrize("capability", ["web.search", "web.read", "browser.navigate"])
def test_web_capabilities_share_real_browser_discovery(capability: str) -> None:
    resolver = CapabilityResolver(
        which=fake_path("brave-browser"),
        desktop_dirs=(),
    )

    result = resolver.resolve(capability, hint="Brave")

    assert result.capability == capability
    assert result.app_id == "brave-browser"


def test_desktop_category_can_discover_an_unknown_calculator(tmp_path: Path) -> None:
    desktop_file = tmp_path / "org.example.Abacus.desktop"
    desktop_file.write_text(
        """\
[Desktop Entry]
Type=Application
Name=Abacus
Categories=Utility;Calculator;
Exec=abacus --new-window %U
StartupWMClass=org.example.Abacus
""",
        encoding="utf-8",
    )
    resolver = CapabilityResolver(
        which=fake_path("abacus"),
        desktop_dirs=(tmp_path,),
    )

    result = resolver.resolve("calculate")

    assert result.app_id == "org.example.Abacus"
    assert result.command == ("/mock/bin/abacus", "--new-window")
    assert result.source == "desktop"
    assert result.desktop_entry == str(desktop_file)
    assert result.startup_wm_class == "org.example.Abacus"


def test_alias_does_not_make_an_uninstalled_application_available() -> None:
    resolver = CapabilityResolver(which=fake_path(), desktop_dirs=())

    with pytest.raises(CapabilityNotAvailable):
        resolver.resolve("code.edit", hint="Visual Studio Code")


def test_malformed_desktop_entry_does_not_hide_valid_path_provider(tmp_path: Path) -> None:
    (tmp_path / "broken.desktop").write_text(
        """[Desktop Entry]\nType=Application\nName=Broken\nCategories=Calculator;\nExec=broken\nHidden=perhaps\n""",
        encoding="utf-8",
    )
    resolver = CapabilityResolver(
        which=fake_path("gnome-calculator", "broken"),
        desktop_dirs=(tmp_path,),
    )

    assert resolver.resolve("calculate").app_id == "gnome-calculator"


def test_terminal_desktop_entry_is_not_selected_as_graphical_surface(tmp_path: Path) -> None:
    (tmp_path / "terminal-editor.desktop").write_text(
        """[Desktop Entry]\nType=Application\nName=Terminal Editor\nCategories=TextEditor;\nExec=vim\nTerminal=true\n""",
        encoding="utf-8",
    )
    resolver = CapabilityResolver(
        which=fake_path("gedit", "vim"),
        desktop_dirs=(tmp_path,),
    )

    assert resolver.resolve("text.edit").app_id == "gedit"
