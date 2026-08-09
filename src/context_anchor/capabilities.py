from __future__ import annotations

import configparser
import os
import re
import shlex
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


ExecutableLookup = Callable[[str], str | None]


class CapabilityNotAvailable(LookupError):
    """Raised when no installed application can satisfy a capability."""


@dataclass(frozen=True, slots=True)
class ResolvedCapability:
    """An installed application selected to satisfy a semantic capability.

    ``executable`` is resolved before this object is returned.  Aliases and
    desktop metadata influence ranking, but never make an unavailable command
    appear available.
    """

    capability: str
    app_id: str
    display_name: str
    executable: str
    argv: tuple[str, ...] = ()
    source: str = "path"
    desktop_entry: str | None = None
    startup_wm_class: str | None = None

    @property
    def command(self) -> tuple[str, ...]:
        return (self.executable, *self.argv)

    @property
    def open_app_target(self) -> str:
        """Return a shell-free target understood by ``open_application``."""

        return shlex.join(self.command)


@dataclass(frozen=True, slots=True)
class _ApplicationHint:
    executable: str
    display_name: str
    aliases: tuple[str, ...] = ()
    argv: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _CapabilityProfile:
    applications: tuple[_ApplicationHint, ...]
    desktop_categories: frozenset[str]


_TEXT_EDIT = _CapabilityProfile(
    applications=(
        _ApplicationHint(
            "xed",
            "Xed",
            ("editor", "editor de texto"),
            ("--new-window",),
        ),
        _ApplicationHint("gnome-text-editor", "GNOME Text Editor"),
        _ApplicationHint("gedit", "gedit"),
        _ApplicationHint("mousepad", "Mousepad"),
        _ApplicationHint("kate", "Kate"),
        _ApplicationHint("pluma", "Pluma"),
        _ApplicationHint("leafpad", "Leafpad"),
    ),
    desktop_categories=frozenset({"texteditor"}),
)

_CALCULATE = _CapabilityProfile(
    applications=(
        _ApplicationHint(
            "gnome-calculator",
            "GNOME Calculator",
            ("calculator", "calculadora"),
        ),
        _ApplicationHint("mate-calc", "MATE Calculator"),
        _ApplicationHint("qalculate-gtk", "Qalculate!"),
        _ApplicationHint("kcalc", "KCalc"),
        _ApplicationHint("galculator", "Galculator"),
    ),
    desktop_categories=frozenset({"calculator"}),
)

_WEB = _CapabilityProfile(
    applications=(
        _ApplicationHint("firefox", "Firefox", ("browser", "navegador")),
        _ApplicationHint("chromium", "Chromium"),
        _ApplicationHint("chromium-browser", "Chromium"),
        _ApplicationHint("google-chrome", "Google Chrome", ("chrome",)),
        _ApplicationHint(
            "brave-browser",
            "Brave",
            ("brave", "brave browser", "navegador brave"),
        ),
    ),
    desktop_categories=frozenset({"webbrowser"}),
)

_CODE_EDIT = _CapabilityProfile(
    applications=(
        _ApplicationHint(
            "code",
            "Visual Studio Code",
            ("vs code", "vscode", "visual studio code"),
            ("--new-window",),
        ),
        _ApplicationHint("codium", "VSCodium", ("vscodium",)),
        _ApplicationHint("code-insiders", "Visual Studio Code - Insiders"),
        _ApplicationHint("subl", "Sublime Text", ("sublime", "sublime text")),
        _ApplicationHint("geany", "Geany"),
    ),
    desktop_categories=frozenset({"ide"}),
)


_PROFILES: dict[str, _CapabilityProfile] = {
    "text.edit": _TEXT_EDIT,
    "calculate": _CALCULATE,
    "web.search": _WEB,
    "web.read": _WEB,
    "browser.navigate": _WEB,
    "code.edit": _CODE_EDIT,
}

_CAPABILITY_ALIASES = {
    "web.navigate": "browser.navigate",
    "browser.search": "web.search",
}

_DESKTOP_FIELD_CODE = re.compile(r"%[fFuUdDnNickvm]")


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def _canonical_capability(value: str) -> str:
    normalized = _normalize(value).replace(" ", ".")
    return _CAPABILITY_ALIASES.get(normalized, normalized)


def _default_desktop_dirs() -> tuple[Path, ...]:
    data_home = os.environ.get("XDG_DATA_HOME")
    home_root = Path(data_home).expanduser() if data_home else Path.home() / ".local/share"
    data_roots = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    roots = (home_root, *(Path(item) for item in data_roots.split(":") if item))
    return tuple(root / "applications" for root in roots)


class CapabilityResolver:
    """Discover an installed application for a small semantic capability set.

    PATH candidates are checked with ``which`` and XDG ``.desktop`` entries are
    inspected for both their executable and standard application categories.
    The built-in names are preference hints rather than an allowlist: a desktop
    entry with a matching category can provide an application unknown to this
    module.
    """

    def __init__(
        self,
        *,
        which: ExecutableLookup | None = None,
        desktop_dirs: Iterable[Path | str] | None = None,
    ) -> None:
        self._which = which or shutil.which
        self._desktop_dirs = (
            tuple(Path(item) for item in desktop_dirs)
            if desktop_dirs is not None
            else _default_desktop_dirs()
        )

    @property
    def supported_capabilities(self) -> frozenset[str]:
        return frozenset(_PROFILES)

    def resolve(
        self,
        capability: str,
        hint: str | None = None,
        *,
        strict_hint: bool = False,
    ) -> ResolvedCapability:
        canonical = _canonical_capability(capability)
        profile = _PROFILES.get(canonical)
        if profile is None:
            supported = ", ".join(sorted(_PROFILES))
            raise ValueError(
                f"Capability '{capability}' is not supported. Supported capabilities: {supported}."
            )

        candidates = self._discover(canonical, profile)
        if not candidates:
            qualifier = f" (requested application: {hint})" if hint else ""
            raise CapabilityNotAvailable(
                f"No installed application was found for capability '{canonical}'{qualifier}."
            )

        if strict_hint and hint:
            canonical_hint = self._canonical_hint(profile, hint)
            candidates = [
                candidate
                for candidate in candidates
                if canonical_hint
                in {
                    _normalize(candidate.app_id),
                    _normalize(candidate.display_name),
                    _normalize(Path(candidate.executable).name),
                }
            ]
            if not candidates:
                raise CapabilityNotAvailable(
                    f"Requested application {hint!r} is not installed for "
                    f"capability {canonical!r}."
                )

        return max(
            candidates,
            key=lambda candidate: self._rank(candidate, profile, hint),
        )

    def available(self, capability: str) -> tuple[ResolvedCapability, ...]:
        """Return all discovered providers, ordered by the default preference."""

        canonical = _canonical_capability(capability)
        profile = _PROFILES.get(canonical)
        if profile is None:
            raise ValueError(f"Capability '{capability}' is not supported.")
        return tuple(
            sorted(
                self._discover(canonical, profile),
                key=lambda candidate: self._rank(candidate, profile, None),
                reverse=True,
            )
        )

    def _discover(
        self,
        capability: str,
        profile: _CapabilityProfile,
    ) -> list[ResolvedCapability]:
        candidates: list[ResolvedCapability] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()

        for application in profile.applications:
            executable = self._resolve_executable(application.executable)
            if executable is None:
                continue
            candidate = ResolvedCapability(
                capability=capability,
                app_id=application.executable,
                display_name=application.display_name,
                executable=executable,
                argv=application.argv,
            )
            self._append_unique(candidates, seen, candidate)

        for desktop_dir in self._desktop_dirs:
            if not desktop_dir.is_dir():
                continue
            for path in sorted(desktop_dir.glob("*.desktop")):
                candidate = self._read_desktop_entry(path, capability, profile)
                if candidate is not None:
                    self._append_unique(candidates, seen, candidate)

        return candidates

    @staticmethod
    def _append_unique(
        candidates: list[ResolvedCapability],
        seen: set[tuple[str, tuple[str, ...]]],
        candidate: ResolvedCapability,
    ) -> None:
        identity = (candidate.executable, candidate.argv)
        if identity not in seen:
            seen.add(identity)
            candidates.append(candidate)

    def _read_desktop_entry(
        self,
        path: Path,
        capability: str,
        profile: _CapabilityProfile,
    ) -> ResolvedCapability | None:
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read(path, encoding="utf-8")
            entry = parser["Desktop Entry"]
        except (OSError, UnicodeError, configparser.Error, KeyError):
            return None

        if entry.get("Type", "Application").casefold() != "application":
            return None
        try:
            if entry.getboolean("Hidden", fallback=False):
                return None
            # Terminal applications cannot provide the desktop surface expected
            # by open_app/readback without an explicit terminal adapter.
            if entry.getboolean("Terminal", fallback=False):
                return None
        except ValueError:
            # One malformed desktop file must not make an otherwise available
            # capability disappear.
            return None

        raw_exec = entry.get("Exec", "").strip()
        command = self._desktop_command(raw_exec)
        if not command:
            return None

        executable = self._resolve_executable(command[0])
        if executable is None:
            return None

        try_exec = entry.get("TryExec", "").strip()
        if try_exec and self._resolve_executable(try_exec) is None:
            return None

        name = entry.get("Name", path.stem).strip() or path.stem
        categories = {
            _normalize(item)
            for item in entry.get("Categories", "").split(";")
            if item.strip()
        }
        identities = {
            _normalize(name),
            _normalize(path.stem),
            _normalize(Path(command[0]).name),
        }
        hinted_identities = self._profile_identities(profile)
        if not (
            categories.intersection(profile.desktop_categories)
            or identities.intersection(hinted_identities)
        ):
            return None

        return ResolvedCapability(
            capability=capability,
            app_id=path.stem,
            display_name=name,
            executable=executable,
            argv=command[1:],
            source="desktop",
            desktop_entry=str(path),
            startup_wm_class=entry.get("StartupWMClass", "").strip() or None,
        )

    def _resolve_executable(self, executable: str) -> str | None:
        candidate = Path(executable).expanduser()
        if candidate.is_absolute():
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
            return None
        return self._which(executable)

    @staticmethod
    def _desktop_command(value: str) -> tuple[str, ...]:
        try:
            tokens = shlex.split(value)
        except ValueError:
            return ()

        command: list[str] = []
        for token in tokens:
            if token == "%%":
                command.append("%")
                continue
            cleaned = _DESKTOP_FIELD_CODE.sub("", token).replace("%%", "%")
            if cleaned:
                command.append(cleaned)
        return tuple(command)

    @staticmethod
    def _profile_identities(profile: _CapabilityProfile) -> set[str]:
        identities: set[str] = set()
        for application in profile.applications:
            identities.add(_normalize(application.executable))
            identities.add(_normalize(application.display_name))
            identities.update(_normalize(alias) for alias in application.aliases)
        return identities

    @staticmethod
    def _canonical_hint(profile: _CapabilityProfile, hint: str | None) -> str | None:
        if not hint:
            return None
        normalized = _normalize(hint)
        for application in profile.applications:
            identities = {
                _normalize(application.executable),
                _normalize(application.display_name),
                *(_normalize(alias) for alias in application.aliases),
            }
            if normalized in identities:
                return _normalize(application.executable)
        return normalized

    @classmethod
    def _rank(
        cls,
        candidate: ResolvedCapability,
        profile: _CapabilityProfile,
        hint: str | None,
    ) -> tuple[int, int, int, str]:
        identities = {
            _normalize(candidate.app_id),
            _normalize(candidate.display_name),
            _normalize(Path(candidate.executable).name),
        }
        canonical_hint = cls._canonical_hint(profile, hint)
        hint_score = 0
        if canonical_hint:
            if canonical_hint in identities:
                hint_score = 2
            elif any(
                canonical_hint in identity or identity in canonical_hint
                for identity in identities
            ):
                hint_score = 1

        preference_score = 0
        for index, application in enumerate(profile.applications):
            app_id = _normalize(application.executable)
            app_names = {
                app_id,
                _normalize(application.display_name),
                *(_normalize(alias) for alias in application.aliases),
            }
            if identities.intersection(app_names):
                preference_score = len(profile.applications) - index
                break

        source_score = 1 if candidate.source == "path" else 0
        return hint_score, preference_score, source_score, candidate.display_name.casefold()


def resolve_capability(
    capability: str,
    hint: str | None = None,
    *,
    which: ExecutableLookup | None = None,
    desktop_dirs: Iterable[Path | str] | None = None,
) -> ResolvedCapability:
    """Convenience wrapper for one-off capability resolution."""

    return CapabilityResolver(which=which, desktop_dirs=desktop_dirs).resolve(
        capability,
        hint,
    )
