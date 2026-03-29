"""
GoatRaw — Unit Tests: Individual Route Functions
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.utils.export       import leads_to_csv, task_result_to_csv, flatten_dict
from app.utils.email_finder import guess_email_patterns, verify_email_format
from app.services.notification_service import format_task_result


# ── Export Utils ──────────────────────────────────────────────

class TestExportUtils:
    def test_flatten_dict_simple(self):
        d = {"name": "GoatRaw", "count": 5}
        result = flatten_dict(d)
        assert result == {"name": "GoatRaw", "count": 5}

    def test_flatten_dict_nested(self):
        d = {"company": {"name": "Acme", "size": 50}, "score": 90}
        result = flatten_dict(d)
        assert result["company_name"] == "Acme"
        assert result["company_size"] == 50
        assert result["score"]        == 90

    def test_flatten_dict_list(self):
        d = {"tags": ["python", "ai", "saas"], "name": "Test"}
        result = flatten_dict(d)
        assert "python" in result["tags"]
        assert result["name"] == "Test"

    def test_leads_to_csv_basic(self):
        leads = [
            {"company_name": "Acme Corp",  "email": "ceo@acme.com",    "phone": "+1234567890"},
            {"company_name": "Beta Ltd",   "email": "info@beta.co",    "phone": "+9876543210"},
        ]
        csv_output = leads_to_csv(leads)
        assert "company_name" in csv_output
        assert "Acme Corp"    in csv_output
        assert "ceo@acme.com" in csv_output

    def test_leads_to_csv_empty(self):
        result = leads_to_csv([])
        assert "No leads" in result

    def test_leads_to_csv_priority_columns_first(self):
        leads = [{"company_name": "X", "email": "x@x.com", "score": 95, "random_field": "abc"}]
        csv = leads_to_csv(leads)
        lines = csv.strip().split("\n")
        header = lines[0]
        # company_name should appear before random_field
        assert header.index("company_name") < header.index("random_field")

    def test_task_result_to_csv_with_list_data(self):
        task_result = {
            "output": {
                "data": [{"company_name": "Acme", "email": "a@acme.com"}],
                "status": "success",
            }
        }
        csv = task_result_to_csv(task_result)
        assert "Acme" in csv

    def test_task_result_to_csv_no_list(self):
        task_result = {"output": {"summary": "Done", "status": "success"}}
        csv = task_result_to_csv(task_result)
        assert "summary" in csv
        assert "Done" in csv


# ── Email Finder ──────────────────────────────────────────────

class TestEmailFinder:
    @pytest.mark.asyncio
    async def test_verify_valid_email(self):
        assert await verify_email_format("user@company.com")       is True
        assert await verify_email_format("first.last@domain.co.uk") is True
        assert await verify_email_format("test+alias@example.org") is True

    @pytest.mark.asyncio
    async def test_verify_invalid_email(self):
        assert await verify_email_format("notanemail")          is False
        assert await verify_email_format("@nodomain.com")       is False
        assert await verify_email_format("missing@")            is False

    @pytest.mark.asyncio
    async def test_guess_patterns_generates_candidates(self):
        candidates = await guess_email_patterns("john", "doe", "acme.com")
        assert len(candidates) >= 3
        assert "john@acme.com"      in candidates
        assert "john.doe@acme.com"  in candidates

    @pytest.mark.asyncio
    async def test_guess_patterns_all_valid(self):
        candidates = await guess_email_patterns("alice", "smith", "example.com")
        for email in candidates:
            assert await verify_email_format(email), f"Invalid: {email}"

    @pytest.mark.asyncio
    async def test_find_email_no_keys_returns_guesses(self):
        with patch("app.utils.email_finder.APOLLO_KEY", ""), \
             patch("app.utils.email_finder.HUNTER_KEY", ""):
            from app.utils.email_finder import tool_find_email
            result = await tool_find_email("john", "doe", "acme.com")
            assert result["status"] in ("guessed", "not_found")
            if result["status"] == "guessed":
                assert result["email"] is not None
                assert result["confidence"] < 0.5


# ── Notification Service ──────────────────────────────────────

class TestNotificationService:
    def test_format_task_result_success(self):
        result = {
            "task_id": "abc123",
            "output":  {
                "summary": "Found 5 leads in Mumbai.",
                "status":  "success",
                "data": [
                    {"company": "Acme",  "email": "ceo@acme.com"},
                    {"company": "Beta",  "email": "info@beta.co"},
                ],
                "stats": {"leads_found": 5},
            },
            "steps_taken": 7,
        }
        msg = format_task_result(result)
        assert "✅" in msg
        assert "Found 5 leads" in msg
        assert "Acme" in msg

    def test_format_task_result_failed(self):
        result = {
            "task_id": "xyz",
            "output":  {"summary": "Search failed.", "status": "failed", "data": []},
            "steps_taken": 2,
        }
        msg = format_task_result(result)
        assert "❌" in msg

    def test_format_task_result_partial(self):
        result = {
            "task_id": "pqr",
            "output":  {"summary": "Partial results.", "status": "partial", "data": {"count": 3}},
            "steps_taken": 4,
        }
        msg = format_task_result(result)
        assert "⚠️" in msg

    def test_format_task_result_dict_data(self):
        result = {
            "task_id": "dict-test",
            "output":  {
                "summary": "Market research complete.",
                "status":  "success",
                "data":    {"market_size": "$5.4B", "growth_rate": "22% CAGR"},
            },
            "steps_taken": 5,
        }
        msg = format_task_result(result)
        assert "market_size" in msg or "$5.4B" in msg


# ── Rate Limiting ─────────────────────────────────────────────

class TestRateLimitMiddleware:
    def test_is_rate_limited_under_quota(self):
        from app.middlewares.rate_limit import IPRateLimitMiddleware
        from fastapi import FastAPI
        mw = IPRateLimitMiddleware(FastAPI(), requests_per_minute=10)
        for _ in range(9):
            limited, _ = mw._is_rate_limited("1.2.3.4", "/task/create")
            assert limited is False

    def test_is_rate_limited_over_quota(self):
        from app.middlewares.rate_limit import IPRateLimitMiddleware
        from fastapi import FastAPI
        mw = IPRateLimitMiddleware(FastAPI(), requests_per_minute=5)
        for _ in range(5):
            mw._is_rate_limited("5.6.7.8", "/api/test")
        limited, retry = mw._is_rate_limited("5.6.7.8", "/api/test")
        assert limited   is True
        assert retry     > 0

    def test_heavy_path_lower_limit(self):
        from app.middlewares.rate_limit import IPRateLimitMiddleware
        from fastapi import FastAPI
        mw = IPRateLimitMiddleware(FastAPI(), requests_per_minute=100, heavy_per_minute=5)
        for _ in range(5):
            mw._is_rate_limited("9.8.7.6", "/task/create")
        limited, _ = mw._is_rate_limited("9.8.7.6", "/task/create")
        assert limited is True


# ── Webhook Security ──────────────────────────────────────────

class TestWebhookSecurity:
    def test_slack_valid_signature(self):
        import hmac, hashlib
        from app.middlewares.webhook_security import verify_slack_signature
        import time
        secret    = "test_slack_secret"
        ts        = str(int(time.time()))
        body      = b'{"event": {"type": "message"}}'
        base      = f"v0:{ts}:{body.decode()}"
        signature = "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()

        assert verify_slack_signature(body, ts, signature, secret) is True

    def test_slack_invalid_signature(self):
        from app.middlewares.webhook_security import verify_slack_signature
        import time
        assert verify_slack_signature(b"body", str(int(time.time())), "v0=wrong", "secret") is False

    def test_slack_replay_attack_rejected(self):
        from app.middlewares.webhook_security import verify_slack_signature
        old_ts = str(int(1000000000))   # Very old timestamp
        assert verify_slack_signature(b"body", old_ts, "v0=sig", "secret") is False

    def test_meta_valid_signature(self):
        import hmac, hashlib
        from app.middlewares.webhook_security import verify_meta_signature
        secret    = "meta_secret"
        body      = b'{"object": "whatsapp_business_account"}'
        sig       = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_meta_signature(body, sig, secret) is True

    def test_meta_invalid_signature(self):
        from app.middlewares.webhook_security import verify_meta_signature
        assert verify_meta_signature(b"body", "sha256=wrong", "secret") is False

    def test_no_secret_always_passes(self):
        from app.middlewares.webhook_security import verify_slack_signature, verify_meta_signature
        assert verify_slack_signature(b"any", "123", "any", "")  is True
        assert verify_meta_signature(b"any", "any", "")          is True
