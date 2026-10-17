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

    async def get_repository_metadata(
        self, owner: str, repo: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches repo metadata (default_branch, permissions, stars, description)."""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        cached_etag = self._etag_cache.get(url, (None, None))[0]
        headers = self._get_headers(token, etag=cached_etag)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            self._update_rate_limits(resp.headers)
            if resp.status_code == 304:
                return self._etag_cache[url][1]
            resp.raise_for_status()
            data = resp.json()
            etag = resp.headers.get("etag")
            if etag:
                self._etag_cache[url] = (etag, data)
            return data

    async def get_repository_tree(
        self, owner: str, repo: str, branch: str = "main", token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches in-memory file tree recursively without cloning (FR-2.2).
        Filters out non-code assets and returns code files.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        cached_etag = self._etag_cache.get(url, (None, None))[0]
        headers = self._get_headers(token, etag=cached_etag)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            self._update_rate_limits(resp.headers)
            if resp.status_code == 304:
                return self._etag_cache[url][1]
            if resp.status_code != 200:
                logger.warning("Failed to fetch tree for %s/%s branch %s: %s", owner, repo, branch, resp.status_code)
                return []
            data = resp.json()
            tree = data.get("tree", [])
            code_files = [
                item for item in tree
                if item.get("type") == "blob"
                and not any(item.get("path", "").endswith(ext) for ext in EXCLUDED_EXTENSIONS)
            ]
            etag = resp.headers.get("etag")
            if etag:
                self._etag_cache[url] = (etag, code_files)
            return code_files

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

    async def get_issue_metadata(
        self, owner: str, repo: str, issue_id: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches issue metadata (title, body, state, labels) for Issue-to-Code pathfinding."""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_id}"
        cached_etag = self._etag_cache.get(url, (None, None))[0]
        headers = self._get_headers(token, etag=cached_etag)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            self._update_rate_limits(resp.headers)

            if resp.status_code == 304:
                return self._etag_cache[url][1]

            if resp.status_code == 403 or resp.status_code == 429:
                logger.warning("GitHub rate limit hit on issue metadata.")
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

    async def fetch_repo_file_by_path(
        self, owner: str, repo: str, file_path: str, ref: str = "main", token: Optional[str] = None
    ) -> Optional[str]:
        """Fetches raw text of any file in the repository at a given ref/branch."""
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{file_path}"
        return await self.fetch_file_raw_content(raw_url, token=token)

    async def search_code_references(
        self, owner: str, repo: str, symbol_name: str, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Uses GitHub Code Search API to locate repo-wide references to a modified symbol.
        Discovers true callers without cloning the repository to disk.
        """
        url = f"{self.base_url}/search/code?q={symbol_name}+repo:{owner}/{repo}&per_page=10"
        headers = self._get_headers(token)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                self._update_rate_limits(resp.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("items", [])
                elif resp.status_code == 403 or resp.status_code == 429:
                    logger.warning("GitHub code search rate-limited or forbidden for %s", symbol_name)
        except Exception as e:
            logger.warning("Error searching code references for '%s': %s", symbol_name, e)
        return []

    async def find_sticky_comment(
        self,
        owner: str,
        repo: str,
        pr_id: str,
        marker: str = "<!-- gitos-sticky-intelligence -->",
        token: Optional[str] = None,
    ) -> Optional[int]:
        """
        Searches issue/PR comments for the sticky intelligence marker to avoid PR thread spam.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_id}/comments?per_page=50"
        headers = self._get_headers(token)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                self._update_rate_limits(resp.headers)
                if resp.status_code == 200:
                    comments = resp.json()
                    for comment in comments:
                        if marker in comment.get("body", ""):
                            return comment.get("id")
        except Exception as e:
            logger.warning("Error searching for sticky comment on PR #%s: %s", pr_id, e)
        return None

    async def patch_pr_comment(
        self, owner: str, repo: str, comment_id: int, body: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Updates an existing PR comment in-place (PATCH) to prevent spamming the PR timeline.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        headers = self._get_headers(token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(url, headers=headers, json={"body": body})
            self._update_rate_limits(resp.headers)
            if resp.status_code != 200:
                logger.error("Failed to update comment #%s: %s %s", comment_id, resp.status_code, resp.text)
                raise httpx.HTTPStatusError(f"GitHub update comment failed ({resp.status_code})", request=resp.request, response=resp)
            data = resp.json()
            return {
                "id": data.get("id"),
                "html_url": data.get("html_url"),
                "updated_at": data.get("updated_at"),
                "action": "updated",
            }

    async def upsert_sticky_pr_comment(
        self,
        owner: str,
        repo: str,
        pr_id: str,
        body: str,
        marker: str = "<!-- gitos-sticky-intelligence -->",
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Zero-Spam Self-Updating Comment:
        If a GitOS comment already exists on the PR, updates it in-place.
        Otherwise creates a new comment with the sticky marker.
        """
        if marker not in body:
            body = f"{marker}\n{body}"

        existing_id = await self.find_sticky_comment(owner, repo, pr_id, marker, token)
        if existing_id:
            logger.info("Found existing sticky comment #%s on PR #%s. Patching in-place.", existing_id, pr_id)
            res = await self.patch_pr_comment(owner, repo, existing_id, body, token)
            res["action"] = "updated"
            return res

        logger.info("No existing sticky comment on PR #%s. Posting new comment.", pr_id)
        res = await self.post_pr_comment(owner, repo, pr_id, body, token)
        res["action"] = "created"
        return res

    async def post_pr_comment(
        self, owner: str, repo: str, pr_id: str, body: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Posts a verified triage markdown comment to a PR using the user's OAuth token.
        Zero-Spam: Only invoked on explicit user confirmation.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_id}/comments"
        headers = self._get_headers(token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json={"body": body})
            self._update_rate_limits(resp.headers)
            if resp.status_code not in (200, 201):
                logger.error("Failed to post comment to PR #%s: %s %s", pr_id, resp.status_code, resp.text)
                raise httpx.HTTPStatusError(f"GitHub comment failed ({resp.status_code})", request=resp.request, response=resp)
            data = resp.json()
            return {
                "id": data.get("id"),
                "html_url": data.get("html_url"),
                "created_at": data.get("created_at"),
            }


    async def close_pull_request(
        self, owner: str, repo: str, pr_id: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Closes a pull request on GitHub via user OAuth token.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_id}"
        headers = self._get_headers(token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(url, headers=headers, json={"state": "closed"})
            self._update_rate_limits(resp.headers)
            if resp.status_code != 200:
                logger.error("Failed to close PR #%s: %s %s", pr_id, resp.status_code, resp.text)
                raise httpx.HTTPStatusError(f"GitHub close PR failed ({resp.status_code})", request=resp.request, response=resp)
            data = resp.json()
            return {
                "id": data.get("id"),
                "state": data.get("state"),
                "html_url": data.get("html_url"),
            }

    async def add_issue_labels(
        self, owner: str, repo: str, pr_id: str, labels: List[str], token: Optional[str] = None
    ) -> List[str]:
        """
        Applies labels to a pull request/issue.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_id}/labels"
        headers = self._get_headers(token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json={"labels": labels})
            self._update_rate_limits(resp.headers)
            if resp.status_code not in (200, 201):
                logger.error("Failed to add labels to PR #%s: %s", pr_id, resp.text)
                return []
            return [l.get("name") for l in resp.json()]


# Global GitHub client singleton
_github_client_instance: Optional[GitHubClient] = None

def get_github_client() -> GitHubClient:
    global _github_client_instance
    if _github_client_instance is None:
        _github_client_instance = GitHubClient()
    return _github_client_instance
