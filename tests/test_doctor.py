from context_anchor.doctor import collect_diagnostics


def test_doctor_collects_environment_without_agent_credentials() -> None:
    diagnostics = collect_diagnostics()

    assert diagnostics["python"]["supported"] is True
    assert "desktop" in diagnostics
    assert "applications" in diagnostics
    assert diagnostics["desktop"]["pyautogui_installed"] in {True, False}
    assert "firefox" in diagnostics["applications"]
