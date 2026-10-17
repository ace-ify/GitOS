import os
import hmac
import hashlib
import json
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.webhooks import verify_github_signature


class TestWebhooks(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.secret = "test_webhook_secret_key_123"

    def test_verify_github_signature_helper(self):
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        
        # Valid signature
        self.assertTrue(verify_github_signature(body, sig, self.secret))
        
        # Invalid signature
        self.assertFalse(verify_github_signature(body, "sha256=invalid_hex", self.secret))
        
        # Missing header
        self.assertFalse(verify_github_signature(body, None, self.secret))

    def test_webhook_ping_event(self):
        response = self.client.post(
            "/api/webhooks/github",
            headers={"X-GitHub-Event": "ping", "X-GitHub-Delivery": "deliv-123"},
            json={"zen": "Design for failure.", "hook_id": 98765}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["zen"], "Design for failure.")

    def test_webhook_pull_request_opened(self):
        response = self.client.post(
            "/api/webhooks/github",
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "deliv-456"},
            json={
                "action": "opened",
                "repository": {"full_name": "ace-ify/GitOS"},
                "pull_request": {
                    "number": 42,
                    "html_url": "https://github.com/ace-ify/GitOS/pull/42"
                },
                "sender": {"login": "test-contributor"}
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "queued")
        self.assertTrue(data["analysis_scheduled"])
        self.assertEqual(data["pull_number"], 42)

    def test_webhook_pull_request_ignored_action(self):
        response = self.client.post(
            "/api/webhooks/github",
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "deliv-789"},
            json={
                "action": "labeled",
                "repository": {"full_name": "ace-ify/GitOS"},
                "pull_request": {"number": 42}
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ignored")


if __name__ == "__main__":
    unittest.main()
