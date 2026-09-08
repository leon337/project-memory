from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_pointer_binds_project_root_and_preserves_gate_order():
    pointer = ROOT / "AGENTS.md"
    assert pointer.is_file(), "AGENTS.md bootstrap pointer must exist"
    text = pointer.read_text(encoding="utf-8")
    required = (
        "TARGET_REPOSITORY_ROOT",
        "docs/CONTINUITY.md",
        ".mcf/project-capsule.yaml",
        "docs/NEXT.md",
        "first unfinished numbered priority",
        "perform discovery only and do not modify files",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"bootstrap pointer missing required tokens: {missing}"
