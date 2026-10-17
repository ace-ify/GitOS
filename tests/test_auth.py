import unittest
from backend.auth import (
    generate_csrf_state,
    verify_csrf_state,
    create_session,
    get_session,
    resolve_repo_role,
)


class TestAuthModule(unittest.TestCase):
    def test_csrf_state_generation_and_consumption(self):
        state = generate_csrf_state()
        self.assertTrue(len(state) > 20)
        # First verification should succeed
        self.assertTrue(verify_csrf_state(state))
        # Replay attack: second verification of same state must fail
        self.assertFalse(verify_csrf_state(state))
        # Non-existent state must fail
        self.assertFalse(verify_csrf_state("forged_state_12345"))

    def test_session_creation_and_retrieval(self):
        user_info = {"login": "testuser", "name": "Test User", "avatar_url": "https://example.com/avatar.png"}
        session_id = create_session(user_info, "gh_token_abc123")

        session = get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session["user"]["login"], "testuser")
        self.assertEqual(session["token"], "gh_token_abc123")

    def test_repo_owner_maintainer_role(self):
        import asyncio
        # Repo owner should automatically be maintainer without extra API call
        role = asyncio.run(resolve_repo_role("octocat", "octocat", "Hello-World", "dummy_token"))
        self.assertEqual(role, "maintainer")


if __name__ == "__main__":
    unittest.main()
