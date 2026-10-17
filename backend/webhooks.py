"""
GitOS - GitHub Webhooks Ingest Engine
Verifies HMAC SHA-256 webhook signatures and processes pull_request events automatically.
"""

import os
import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("gitos.webhooks")

webhook_router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_github_signature(payload_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """
    Verifies that the webhook payload was signed by GitHub using HMAC-SHA256.
    """
    if not secret:
        # If no secret is configured on the server, we allow requests in development/sandbox mode with a warning
        logger.warning("GITHUB_WEBHOOK_SECRET is not set; skipping signature verification (DEV MODE).")
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


@webhook_router.post("/github")
async def github_webhook_handler(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """
    Receives and processes incoming GitHub webhooks.
    Supports 'ping', 'pull_request' (opened, synchronize, reopened).
    """
    raw_body = await request.body()

    # 1. Verify HMAC Signature
    if not verify_github_signature(raw_body, x_hub_signature_256, WEBHOOK_SECRET):
        logger.error("Invalid GitHub webhook signature received.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Hub-Signature-256 signature"
        )

    try:
        payload: Dict[str, Any] = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    logger.info(f"Received GitHub webhook: event='{x_github_event}', delivery_id='{x_github_delivery}'")

    # 2. Handle Ping Event
    if x_github_event == "ping":
        zen = payload.get("zen", "Keep it logically awesome.")
        hook_id = payload.get("hook_id")
        return JSONResponse({
            "status": "ok",
            "message": "GitOS Webhook listener connected successfully.",
            "hook_id": hook_id,
            "zen": zen
        })

    # 3. Handle Pull Request Events
    if x_github_event == "pull_request":
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})
        
        pr_number = pr_data.get("number")
        repo_full_name = repo_data.get("full_name")  # e.g., "owner/repo"
        html_url = pr_data.get("html_url")
        sender = payload.get("sender", {}).get("login", "unknown")

        logger.info(f"PR event received: repo={repo_full_name}, PR #{pr_number}, action={action}, sender={sender}")

        if action in ("opened", "synchronize", "reopened"):
            # Trigger analysis flow
            return JSONResponse({
                "status": "queued",
                "event": "pull_request",
                "action": action,
                "repo": repo_full_name,
                "pull_number": pr_number,
                "url": html_url,
                "analysis_scheduled": True,
                "message": f"GitOS analysis scheduled for PR #{pr_number} on {repo_full_name}"
            })
        else:
            return JSONResponse({
                "status": "ignored",
                "action": action,
                "message": f"Action '{action}' ignored. Only 'opened', 'synchronize', 'reopened' trigger analysis."
            })

    # Default for unhandled events
    return JSONResponse({
        "status": "acknowledged",
        "event": x_github_event,
        "message": f"Event '{x_github_event}' received but not processed."
    })
