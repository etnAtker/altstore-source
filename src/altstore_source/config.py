from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

import yaml


DEFAULT_MAX_DOWNLOAD_SIZE = 512 * 1024 * 1024


class ConfigError(ValueError):
    """Raised when the local YAML config is invalid."""


@dataclass(frozen=True)
class SourceConfig:
    name: str
    identifier: str
    subtitle: str | None = None
    description: str | None = None
    iconURL: str | None = None
    website: str | None = None


@dataclass(frozen=True)
class AppConfig:
    id: str
    repo: str
    asset_pattern: str
    include_prerelease: bool = False
    keep_versions: int = 5
    max_download_size: int = DEFAULT_MAX_DOWNLOAD_SIZE
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def asset_regex(self) -> re.Pattern[str]:
        try:
            return re.compile(self.asset_pattern)
        except re.error as exc:
            raise ConfigError(f"app {self.id}: invalid assetPattern: {exc}") from exc


@dataclass(frozen=True)
class ProjectConfig:
    source: SourceConfig
    apps: list[AppConfig]


def load_config(path: Path) -> ProjectConfig:
    if not path.exists():
        raise ConfigError(f"config file does not exist: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse YAML config: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    source = _parse_source(raw.get("source"))
    apps = _parse_apps(raw.get("apps"))
    return ProjectConfig(source=source, apps=apps)


def _parse_source(raw: Any) -> SourceConfig:
    if not isinstance(raw, dict):
        raise ConfigError("source must be a mapping")

    name = _required_str(raw, "source.name")
    identifier = _required_str(raw, "source.identifier")
    return SourceConfig(
        name=name,
        identifier=identifier,
        subtitle=_optional_str(raw, "subtitle", "source.subtitle"),
        description=_optional_str(raw, "description", "source.description"),
        iconURL=_optional_str(raw, "iconURL", "source.iconURL"),
        website=_optional_str(raw, "website", "source.website"),
    )


def _parse_apps(raw: Any) -> list[AppConfig]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("apps must be a non-empty list")

    apps: list[AppConfig] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw):
        prefix = f"apps[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{prefix} must be a mapping")

        app_id = _required_str(item, f"{prefix}.id")
        if app_id in seen_ids:
            raise ConfigError(f"duplicate app id: {app_id}")
        seen_ids.add(app_id)

        repo = _required_str(item, f"{prefix}.repo")
        if "/" not in repo or repo.count("/") != 1:
            raise ConfigError(f"{prefix}.repo must look like owner/name")

        keep_versions = _optional_int(item, "keepVersions", f"{prefix}.keepVersions", default=5)
        if keep_versions <= 0:
            raise ConfigError(f"{prefix}.keepVersions must be greater than 0")

        max_download_size = _optional_int(
            item,
            "maxDownloadSize",
            f"{prefix}.maxDownloadSize",
            default=DEFAULT_MAX_DOWNLOAD_SIZE,
        )
        if max_download_size <= 0:
            raise ConfigError(f"{prefix}.maxDownloadSize must be greater than 0")

        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ConfigError(f"{prefix}.metadata must be a mapping")

        app = AppConfig(
            id=app_id,
            repo=repo,
            asset_pattern=_required_str(item, f"{prefix}.assetPattern", key="assetPattern"),
            include_prerelease=_optional_bool(
                item,
                "includePrerelease",
                f"{prefix}.includePrerelease",
                default=False,
            ),
            keep_versions=keep_versions,
            max_download_size=max_download_size,
            metadata=dict(metadata),
        )
        app.asset_regex
        apps.append(app)

    return apps


def _required_str(raw: dict[str, Any], label: str, key: str | None = None) -> str:
    value = raw.get(key or label.rsplit(".", 1)[-1])
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_str(raw: dict[str, Any], key: str, label: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{label} must be a string")
    value = value.strip()
    return value or None


def _optional_bool(raw: dict[str, Any], key: str, label: str, *, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{label} must be a boolean")
    return value


def _optional_int(raw: dict[str, Any], key: str, label: str, *, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{label} must be an integer")
    return value
