from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import plistlib
import re
import zipfile


class IPAError(RuntimeError):
    """Raised when an IPA cannot be inspected."""


@dataclass(frozen=True)
class IPAMetadata:
    bundle_identifier: str
    version: str
    build_version: str
    name: str
    minimum_os_version: str | None
    device_family: list[int] | None


INFO_PLIST_RE = re.compile(r"^Payload/[^/]+\.app/Info\.plist$")


def inspect_ipa(path: Path) -> IPAMetadata:
    try:
        with zipfile.ZipFile(path) as archive:
            info_name = _find_info_plist(archive)
            with archive.open(info_name) as plist_file:
                plist = plistlib.load(plist_file)
    except (zipfile.BadZipFile, plistlib.InvalidFileException, OSError) as exc:
        raise IPAError(f"failed to read IPA metadata from {path.name}: {exc}") from exc

    if not isinstance(plist, dict):
        raise IPAError(f"Info.plist in {path.name} is not a dictionary")

    return IPAMetadata(
        bundle_identifier=_required_plist_str(plist, "CFBundleIdentifier", path),
        version=_required_plist_str(plist, "CFBundleShortVersionString", path),
        build_version=_required_plist_str(plist, "CFBundleVersion", path),
        name=_display_name(plist, path),
        minimum_os_version=_optional_plist_str(plist, "MinimumOSVersion"),
        device_family=_device_family(plist.get("UIDeviceFamily")),
    )


def _find_info_plist(archive: zipfile.ZipFile) -> str:
    matches = [name for name in archive.namelist() if INFO_PLIST_RE.match(name)]
    if not matches:
        raise IPAError("IPA does not contain Payload/*.app/Info.plist")
    return sorted(matches, key=len)[0]


def _display_name(plist: dict[str, Any], path: Path) -> str:
    return (
        _optional_plist_str(plist, "CFBundleDisplayName")
        or _optional_plist_str(plist, "CFBundleName")
        or _required_plist_str(plist, "CFBundleIdentifier", path)
    )


def _required_plist_str(plist: dict[str, Any], key: str, path: Path) -> str:
    value = plist.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IPAError(f"{path.name}: missing required Info.plist field {key}")
    return value.strip()


def _optional_plist_str(plist: dict[str, Any], key: str) -> str | None:
    value = plist.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _device_family(value: Any) -> list[int] | None:
    if not isinstance(value, list):
        return None
    families: list[int] = []
    for item in value:
        if isinstance(item, int) and not isinstance(item, bool):
            families.append(item)
    return families or None
