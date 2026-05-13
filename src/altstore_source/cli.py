from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import argparse
import json
import logging
import sys
import tempfile

from .builder import VersionRecord, build_source, validate_source
from .config import AppConfig, ConfigError, load_config
from .github import GitHubClient, GitHubError, Release, ReleaseAsset
from .ipa import IPAError, inspect_ipa


LOGGER = logging.getLogger(__name__)


@dataclass
class AppSummary:
    app_id: str
    version_count: int = 0
    missing_assets: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate AltStore source JSON from GitHub releases.")
    parser.add_argument("--config", type=Path, default=Path("config.yml"), help="YAML config path.")
    parser.add_argument("--output", type=Path, default=Path("dist/apps.json"), help="Output JSON path.")
    parser.add_argument("--app", help="Only update one configured app id.")
    parser.add_argument("--force", action="store_true", help="Reserved for future cache invalidation.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        config = load_config(args.config)
        apps = _select_apps(config.apps, args.app)
        client = GitHubClient()
        app_results: list[tuple[AppConfig, list[VersionRecord]]] = []
        summaries: list[AppSummary] = []

        for app in apps:
            records, summary = process_app(client, app)
            summaries.append(summary)
            if records:
                app_results.append((app, records))

        source = build_source(config.source, app_results)
        validate_source(source)
        write_json(args.output, source)
        print_summary(summaries, args.output)
        return 0
    except ConfigError as exc:
        LOGGER.error("configuration error: %s", exc)
        return 2
    except (OSError, ValueError) as exc:
        LOGGER.error("generation failed: %s", exc)
        return 1


def process_app(client: GitHubClient, app: AppConfig) -> tuple[list[VersionRecord], AppSummary]:
    LOGGER.info("Updating app %s from %s", app.id, app.repo)
    summary = AppSummary(app_id=app.id)
    records: list[VersionRecord] = []

    try:
        releases = client.list_releases(app.repo)
    except GitHubError as exc:
        summary.failures.append(str(exc))
        LOGGER.error("Failed to fetch releases for %s: %s", app.id, exc)
        return records, summary

    with tempfile.TemporaryDirectory(prefix=f"altstore-source-{app.id}-") as tmpdir:
        tmp_path = Path(tmpdir)
        for release in releases:
            if release.draft:
                continue
            if release.prerelease and not app.include_prerelease:
                continue

            asset = _match_asset(app, release)
            if asset is None:
                summary.missing_assets.append(release.tag_name)
                continue

            destination = tmp_path / _safe_asset_filename(asset.name)
            try:
                client.download_asset(asset, destination, max_size=app.max_download_size)
                ipa_metadata = inspect_ipa(destination)
            except (GitHubError, IPAError, OSError) as exc:
                message = f"{release.tag_name}/{asset.name}: {exc}"
                summary.failures.append(message)
                LOGGER.warning("%s", message)
                continue

            records.append(VersionRecord(release=release, asset=asset, ipa=ipa_metadata))
            if len(records) >= app.keep_versions:
                break

    summary.version_count = len(records)
    return records, summary


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def print_summary(summaries: list[AppSummary], output: Path) -> None:
    LOGGER.info("Summary:")
    for summary in summaries:
        if summary.version_count:
            LOGGER.info("  %s: updated %s version(s)", summary.app_id, summary.version_count)
        else:
            LOGGER.warning("  %s: no versions generated", summary.app_id)

        if summary.missing_assets:
            LOGGER.info(
                "  %s: releases without matching IPA: %s",
                summary.app_id,
                ", ".join(summary.missing_assets),
            )
        for failure in summary.failures:
            LOGGER.warning("  %s: %s", summary.app_id, failure)

    LOGGER.info("Output written to %s", output)


def _select_apps(apps: list[AppConfig], app_id: str | None) -> list[AppConfig]:
    if app_id is None:
        return apps
    selected = [app for app in apps if app.id == app_id]
    if not selected:
        raise ConfigError(f"unknown app id: {app_id}")
    return selected


def _match_asset(app: AppConfig, release: Release) -> ReleaseAsset | None:
    for asset in release.assets:
        if asset.name.lower().endswith(".ipa") and app.asset_regex.search(asset.name):
            return asset
    return None


def _safe_asset_filename(name: str) -> str:
    return Path(name).name or "asset.ipa"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
