import pytest

from context_anchor.desktop import DesktopFailsafeTriggered, PyAutoGuiDesktopBackend


class FakeGui:
    def __init__(self, position=(500, 400), size=(1000, 800)) -> None:
        self._position = position
        self._size = size
        self.moves: list[tuple[int, int, float]] = []
        self.clicks: list[str] = []
        self.writes: list[str] = []
        self.presses: list[str] = []

    def position(self):
        return self._position

    def size(self):
        return self._size

    def moveTo(self, x: int, y: int, duration: float = 0.0) -> None:
        self.moves.append((x, y, duration))
        self._position = (x, y)

    def click(self, button: str) -> None:
        self.clicks.append(button)

    def write(self, text: str, interval: float = 0.0) -> None:
        self.writes.append(text)

    def press(self, key: str) -> None:
        self.presses.append(key)


@pytest.mark.parametrize(
    "position",
    [
        (0, 0),
        (999, 0),
        (0, 799),
        (999, 799),
        (10, 10),
        (989, 10),
        (10, 789),
        (989, 789),
    ],
)
def test_failsafe_blocks_mouse_move_from_any_safety_corner(position) -> None:
    backend = PyAutoGuiDesktopBackend(failsafe_margin_pixels=20)
    gui = FakeGui(position=position)
    backend._gui = gui

    with pytest.raises(DesktopFailsafeTriggered, match="zona de segurança"):
        backend.move_mouse(200, 200)

    assert gui.moves == []


@pytest.mark.parametrize("operation", ["click", "type", "press"])
def test_failsafe_blocks_other_physical_input_before_execution(operation) -> None:
    backend = PyAutoGuiDesktopBackend(failsafe_margin_pixels=20)
    gui = FakeGui(position=(0, 0))
    backend._gui = gui

    with pytest.raises(DesktopFailsafeTriggered):
        if operation == "click":
            backend.click_mouse("left")
        elif operation == "type":
            backend.type_text("nao deve ser digitado")
        else:
            backend.press_key("enter")

    assert gui.clicks == []
    assert gui.writes == []
    assert gui.presses == []


def test_failsafe_allows_mouse_move_outside_corner_zone() -> None:
    backend = PyAutoGuiDesktopBackend(failsafe_margin_pixels=20)
    gui = FakeGui(position=(500, 400))
    backend._gui = gui

    result = backend.move_mouse(200, 200)

    assert gui.moves == [(200, 200, 0.15)]
    assert result["verified"] is True
    assert result["x"] == 200
    assert result["y"] == 200


def test_failsafe_margin_must_be_positive() -> None:
    with pytest.raises(ValueError, match="pelo menos 1"):
        PyAutoGuiDesktopBackend(failsafe_margin_pixels=0)
