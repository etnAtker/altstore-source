from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging
import os

import requests


GITHUB_API_URL = "https://api.github.com"


class GitHubError(RuntimeError):
    """Raised when a GitHub API request or asset download fails."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    size: int
    browser_download_url: str


@dataclass(frozen=True)
class Release:
    name: str | None
    tag_name: str
    draft: bool
    prerelease: bool
    created_at: str
    published_at: str | None
    assets: list[ReleaseAsset]

    @property
    def published_or_created_at(self) -> str:
        return self.published_at or self.created_at


class GitHubClient:
    def __init__(self, *, timeout: float = 30.0, max_pages: int = 5) -> None:
        self.timeout = timeout
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "altstore-source-generator",
            }
        )
        token = os.getenv("GITHUB_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            logging.getLogger(__name__).warning(
                "GITHUB_TOKEN is not set; anonymous GitHub API requests may hit rate limits."
            )

    def list_releases(self, repo: str) -> list[Release]:
        releases: list[Release] = []
        url = f"{GITHUB_API_URL}/repos/{repo}/releases"
        params: dict[str, Any] | None = {"per_page": 100}

        for _ in range(self.max_pages):
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code >= 400:
                raise GitHubError(
                    f"GitHub releases request failed for {repo}: "
                    f"{response.status_code} {response.text[:300]}"
                )

            payload = response.json()
            if not isinstance(payload, list):
                raise GitHubError(f"unexpected GitHub releases response for {repo}")

            releases.extend(_parse_release(item) for item in payload)
            next_url = response.links.get("next", {}).get("url")
            if not next_url:
                break
            url = next_url
            params = None

        return releases

    def download_asset(self, asset: ReleaseAsset, destination: Path, *, max_size: int) -> None:
        if asset.size > max_size:
            raise GitHubError(
                f"asset {asset.name} is {asset.size} bytes, exceeds limit {max_size} bytes"
            )

        with self.session.get(
            asset.browser_download_url,
            stream=True,
            timeout=self.timeout,
            allow_redirects=True,
        ) as response:
            if response.status_code >= 400:
                raise GitHubError(
                    f"download failed for {asset.name}: "
                    f"{response.status_code} {response.text[:300]}"
                )

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_size:
                raise GitHubError(
                    f"asset {asset.name} content length exceeds limit {max_size} bytes"
                )

            bytes_written = 0
            with destination.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > max_size:
                        raise GitHubError(
                            f"asset {asset.name} exceeded limit {max_size} bytes while downloading"
                        )
                    file.write(chunk)


def _parse_release(raw: Any) -> Release:
    if not isinstance(raw, dict):
        raise GitHubError("unexpected release item in GitHub response")

    assets_raw = raw.get("assets") or []
    if not isinstance(assets_raw, list):
        raise GitHubError("unexpected release assets in GitHub response")

    return Release(
        name=_optional_str(raw.get("name")),
        tag_name=_required_str(raw.get("tag_name"), "tag_name"),
        draft=bool(raw.get("draft")),
        prerelease=bool(raw.get("prerelease")),
        created_at=_required_str(raw.get("created_at"), "created_at"),
        published_at=_optional_str(raw.get("published_at")),
        assets=[_parse_asset(item) for item in assets_raw],
    )


def _parse_asset(raw: Any) -> ReleaseAsset:
    if not isinstance(raw, dict):
        raise GitHubError("unexpected asset item in GitHub response")

    return ReleaseAsset(
        name=_required_str(raw.get("name"), "asset.name"),
        size=int(raw.get("size") or 0),
        browser_download_url=_required_str(
            raw.get("browser_download_url"),
            "asset.browser_download_url",
        ),
    )


def _required_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise GitHubError(f"missing GitHub field: {label}")
    return value


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
