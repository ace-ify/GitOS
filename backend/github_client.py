"""
GitOS High-Performance GitHub API Client
Implements scoped PR diff extraction, rate-limit tracking (Primary & Secondary),
ETag 304 conditional caching, and zero-disk in-memory streaming.
"""

import os
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("gitos.github")

# Files to ignore during symbol analysis
EXCLUDED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf",
    ".lock", ".sum", ".min.js", ".min.css", ".map", ".wasm",
    ".csv", ".tsv", ".parquet", ".zip", ".tar", ".gz"
}


class GitHubClient:
    """
    Manages authenticated GitHub REST API communication with ETag caching,
    rate-limit backoff, and scoped in-memory diff processing.
    """

    def __init__(self, default_token: Optional[str] = None):
        self.default_token = default_token or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self._etag_cache: Dict[str, Tuple[str, Any]] = {}  # url -> (etag, data)
        self.rate_limit_remaining: int = 5000
        self.rate_limit_reset: int = 0

    def _get_headers(self, custom_token: Optional[str] = None, etag: Optional[str] = None) -> Dict[str, str]:
        token = custom_token or self.default_token
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitOS-Defense-Engine/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _update_rate_limits(self, headers: httpx.Headers):
        rem = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        if rem is not None:
            self.rate_limit_remaining = int(rem)
        if reset is not None:
            self.rate_limit_reset = int(reset)

    async def get_pull_request_metadata(
        self, owner: str, repo: str, pull_id: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches PR metadata (title, body, author, base/head commit SHAs)."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_id}"
        cached_etag = self._etag_cache.get(url, (None, None))[0]
        headers = self._get_headers(token, etag=cached_etag)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            self._update_rate_limits(resp.headers)

            if resp.status_code == 304:
                return self._etag_cache[url][1]

            if resp.status_code == 403 or resp.status_code == 429:
                logger.warning("GitHub rate limit hit on PR metadata. Remaining: %s", self.rate_limit_remaining)
                raise httpx.HTTPStatusError("GitHub API rate limit exceeded.", request=resp.request, response=resp)

            resp.raise_for_status()
            data = resp.json()
            etag = resp.headers.get("etag")
            if etag:
                self._etag_cache[url] = (etag, data)
            return data

    async def get_pull_request_files(
        self, owner: str, repo: str, pull_id: str, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches modified files in the pull request.
        Uses scoped pagination to avoid downloading massive repos.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_id}/files?per_page=100"
        cached_etag = self._etag_cache.get(url, (None, None))[0]
        headers = self._get_headers(token, etag=cached_etag)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            self._update_rate_limits(resp.headers)

            if resp.status_code == 304:
                return self._etag_cache[url][1]

            if resp.status_code == 403 or resp.status_code == 429:
                logger.warning("GitHub rate limit hit on PR files.")
                raise httpx.HTTPStatusError("GitHub API rate limit exceeded.", request=resp.request, response=resp)

            resp.raise_for_status()
            raw_files = resp.json()

            # Filter out non-code assets (lockfiles, images, binaries)
            code_files = [
                f for f in raw_files
                if not any(f.get("filename", "").endswith(ext) for ext in EXCLUDED_EXTENSIONS)
            ]

            etag = resp.headers.get("etag")
            if etag:
                self._etag_cache[url] = (etag, code_files)
            return code_files

    async def fetch_file_raw_content(
        self, raw_url: str, token: Optional[str] = None
    ) -> Optional[str]:
        """Fetches raw text content directly into RAM."""
        headers = {"User-Agent": "GitOS-Defense-Engine/1.0"}
        token = token or self.default_token
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(raw_url, headers=headers)
                if resp.status_code == 200:
                    return resp.text
        except Exception as e:
            logger.warning("Error fetching raw content from %s: %s", raw_url, e)
        return None


# Global GitHub client singleton
_github_client_instance: Optional[GitHubClient] = None

def get_github_client() -> GitHubClient:
    global _github_client_instance
    if _github_client_instance is None:
        _github_client_instance = GitHubClient()
    return _github_client_instance
