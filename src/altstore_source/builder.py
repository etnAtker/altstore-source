from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import AppConfig, SourceConfig
from .github import Release, ReleaseAsset
from .ipa import IPAMetadata


@dataclass(frozen=True)
class VersionRecord:
    release: Release
    asset: ReleaseAsset
    ipa: IPAMetadata


def build_source(source: SourceConfig, app_results: list[tuple[AppConfig, list[VersionRecord]]]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "name": source.name,
        "identifier": source.identifier,
    }
    _put_optional(output, "subtitle", source.subtitle)
    _put_optional(output, "description", source.description)
    _put_optional(output, "iconURL", source.iconURL)
    _put_optional(output, "website", source.website)
    output["apps"] = [
        build_app(app_config, records)
        for app_config, records in app_results
        if records
    ]
    return output


def build_app(app_config: AppConfig, records: list[VersionRecord]) -> dict[str, Any]:
    records = sorted(
        records,
        key=lambda record: record.release.published_or_created_at,
        reverse=True,
    )[: app_config.keep_versions]
    latest = records[0].ipa
    metadata = app_config.metadata

    app: dict[str, Any] = {
        "name": str(metadata.get("name") or latest.name),
        "bundleIdentifier": latest.bundle_identifier,
        "developerName": str(metadata.get("developerName") or "Unknown"),
    }
    _put_optional(app, "subtitle", _metadata_str(metadata, "subtitle"))
    _put_optional(app, "localizedDescription", _metadata_str(metadata, "localizedDescription"))
    _put_optional(app, "iconURL", _metadata_str(metadata, "iconURL"))
    _put_optional(app, "tintColor", _metadata_str(metadata, "tintColor"))
    _put_optional(app, "category", _metadata_str(metadata, "category"))
    _put_optional(app, "minimumOSVersion", latest.minimum_os_version)
    if latest.device_family:
        app["deviceFamilies"] = latest.device_family

    app["versions"] = [build_version(record) for record in records]
    return app


def build_version(record: VersionRecord) -> dict[str, Any]:
    version: dict[str, Any] = {
        "version": record.ipa.version,
        "buildVersion": record.ipa.build_version,
        "date": record.release.published_or_created_at,
        "downloadURL": record.asset.browser_download_url,
        "size": record.asset.size,
    }
    _put_optional(version, "minimumOSVersion", record.ipa.minimum_os_version)
    return version


def validate_source(source: dict[str, Any]) -> None:
    for key in ("name", "identifier", "apps"):
        if key not in source:
            raise ValueError(f"generated source is missing {key}")
    if not isinstance(source["apps"], list):
        raise ValueError("generated source apps must be a list")
    for app in source["apps"]:
        for key in ("name", "bundleIdentifier", "developerName", "versions"):
            if key not in app:
                raise ValueError(f"generated app is missing {key}")
        if not isinstance(app["versions"], list):
            raise ValueError(f"generated app {app['name']} versions must be a list")


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _put_optional(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value
