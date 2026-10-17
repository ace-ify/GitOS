"""
GitOS GitHub OAuth Handshake & Role Permission Router
Handles secure OAuth login, CSRF state verification, session management,
and dynamic repository permission checks (Admin/Write -> Maintainer, Read/Author -> Contributor).
"""

import os
import time
import hmac
import json
import base64
import hashlib
import secrets
import logging
from typing import Any, Dict, Optional, Tuple
import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

logger = logging.getLogger("gitos.auth")

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))

# Ephemeral state cache for CSRF protection: state -> timestamp
_oauth_states: Dict[str, float] = {}

# Active sessions: session_id -> { "user": {...}, "token": "...", "expires_at": float }
_active_sessions: Dict[str, Dict[str, Any]] = {}


# ==============================================================================
# Helper Functions: State & Session Cryptography
# ==============================================================================

def generate_csrf_state() -> str:
    """Generates and records a cryptographically secure CSRF state token."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time()
    # Prune old states older than 10 minutes
    now = time.time()
    for s in list(_oauth_states.keys()):
        if now - _oauth_states[s] > 600:
            _oauth_states.pop(s, None)
    return state


def verify_csrf_state(state: str) -> bool:
    """Verifies that the incoming OAuth state token is valid and unconsumed."""
    created = _oauth_states.pop(state, None)
    if not created:
        return False
    return (time.time() - created) < 600


def create_session(user_info: Dict[str, Any], access_token: str) -> str:
    """Stores session and returns a signed session token."""
    session_id = secrets.token_urlsafe(32)
    _active_sessions[session_id] = {
        "user": user_info,
        "token": access_token,
        "created_at": time.time(),
        "expires_at": time.time() + (7 * 86400),  # 7 days
    }
    return session_id


def get_session(session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Retrieves and validates an active user session."""
    if not session_id:
        return None
    session = _active_sessions.get(session_id)
    if not session:
        return None
    if time.time() > session["expires_at"]:
        _active_sessions.pop(session_id, None)
        return None
    return session


async def resolve_repo_role(
    username: str, owner: str, repo: str, token: str
) -> str:
    """
    Queries GitHub API to determine if user has 'admin' or 'write' permissions on a repository.
    Returns: 'maintainer' | 'contributor' | 'guest'
    """
    # Repo owners are automatically maintainers
    if username.lower() == owner.lower():
        return "maintainer"

    url = f"https://api.github.com/repos/{owner}/{repo}/collaborators/{username}/permission"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitOS-Defense-Engine/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                perm_data = resp.json()
                permission = perm_data.get("permission", "read")
                # Admin or Write permissions route to Maintainer Mode
                if permission in ("admin", "write"):
                    return "maintainer"
                return "contributor"
    except Exception as e:
        logger.warning("Error checking repo collaborator permission: %s", e)

    return "contributor"


# ==============================================================================
# OAuth Endpoints
# ==============================================================================

@auth_router.get("/github/login")
async def github_login(redirect_url: Optional[str] = None):
    """
    Initiates GitHub OAuth flow.
    Redirects to GitHub authorization page with state and requested scopes.
    """
    if not GITHUB_CLIENT_ID:
        # If OAuth app credentials are not yet configured, return sandbox mock login
        return {
            "oauth_configured": False,
            "message": "GitHub OAuth App credentials (GITHUB_CLIENT_ID) not configured in .env. Use /api/auth/mock-login for testing.",
            "auth_url": None,
        }

    state = generate_csrf_state()
    scope = "read:user,repo,workflow"
    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&scope={scope}"
        f"&state={state}"
    )
    return {
        "oauth_configured": True,
        "auth_url": auth_url,
    }


@auth_router.get("/github/callback")
async def github_callback(code: str, state: str, response: Response):
    """
    GitHub OAuth Callback.
    Validates CSRF state, exchanges code for access token, and sets secure HttpOnly cookie.
    """
    if not verify_csrf_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired CSRF state token.",
        )

    # Exchange code for access token
    token_url = "https://github.com/login/oauth/access_token"
    token_payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
    }
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(token_url, json=token_payload, headers=headers)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code with GitHub.",
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=token_data.get("error_description", "Access token missing from response."),
            )

        # Fetch user profile
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "GitOS-Defense-Engine/1.0",
            },
        )
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to fetch GitHub user profile.",
            )

        user_info = user_resp.json()

    # Create session
    session_id = create_session(user_info, access_token)

    # Set secure HttpOnly cookie
    response.set_cookie(
        key="gitos_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production HTTPS
        max_age=7 * 86400,
        path="/",
    )

    return {
        "status": "authenticated",
        "user": {
            "login": user_info.get("login"),
            "name": user_info.get("name"),
            "avatar_url": user_info.get("avatar_url"),
        },
    }


@auth_router.get("/me")
async def get_current_user_profile(
    request: Request,
    gitos_session: Optional[str] = Cookie(None),
):
    """
    Returns the currently authenticated user's profile and default role.
    """
    session = get_session(gitos_session)
    if not session:
        return {"authenticated": False, "user": None, "role": "guest"}

    user = session["user"]
    return {
        "authenticated": True,
        "user": {
            "login": user.get("login"),
            "name": user.get("name") or user.get("login"),
            "avatar_url": user.get("avatar_url"),
            "html_url": user.get("html_url"),
        },
        "role": "maintainer",  # Default; dynamically checked per repo via /check-permission
    }


@auth_router.get("/check-permission")
async def check_repo_permission(
    owner: str,
    repo: str,
    gitos_session: Optional[str] = Cookie(None),
):
    """
    Dynamically routes role to 'maintainer' or 'contributor'
    based on user's GitHub permissions on the target repository.
    """
    session = get_session(gitos_session)
    if not session:
        return {"role": "guest", "is_collaborator": False}

    username = session["user"].get("login", "")
    token = session["token"]

    role = await resolve_repo_role(username, owner, repo, token)
    return {
        "username": username,
        "owner": owner,
        "repo": repo,
        "role": role,
        "is_collaborator": role == "maintainer",
    }


@auth_router.post("/mock-login")
async def mock_login(
    role: str = "maintainer",
    response: Response = None,
):
    """
    Developer Mock Login for sandbox environments without OAuth App credentials.
    Allows instant switching between Maintainer and Contributor personas.
    """
    mock_user = {
        "login": "octocat-maintainer" if role == "maintainer" else "contributor-alex",
        "name": "Octocat Maintainer" if role == "maintainer" else "Alex Contributor",
        "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4",
        "html_url": "https://github.com/octocat",
    }
    session_id = create_session(mock_user, "mock_gh_token_sandbox")

    if response:
        response.set_cookie(
            key="gitos_session",
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=86400,
            path="/",
        )

    return {
        "status": "authenticated",
        "user": mock_user,
        "role": role,
        "session_id": session_id,
    }


@auth_router.post("/logout")
async def logout(response: Response, gitos_session: Optional[str] = Cookie(None)):
    """Clears the active session and HttpOnly cookie."""
    if gitos_session:
        _active_sessions.pop(gitos_session, None)
    response.delete_cookie(key="gitos_session", path="/")
    return {"status": "logged_out"}
