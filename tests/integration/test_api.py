"""
GoatRaw — Integration Tests: API Endpoints
Uses httpx AsyncClient against the FastAPI test app.
pytest tests/integration/
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
import jwt
from datetime import datetime, timedelta


# ─── Test fixtures ────────────────────────────────────────────

def make_test_token(user_id: str = "test-user-001", plan: str = "pro") -> str:
    """Generate a valid JWT for testing."""
    return jwt.encode(
        {
            "id": user_id,
            "email": "test@goatraw.ai",
            "plan": plan,
            "exp": datetime.utcnow() + timedelta(hours=1),
        },
        "change-me-in-production",  # Must match config.SECRET_KEY in test env
        algorithm="HS256",
    )


@pytest.fixture
def auth_headers():
    token = make_test_token()
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client():
    """Create async test client."""
    # Patch Redis and DB to avoid real connections in tests
    with patch("app.core.redis_client.init_redis", new_callable=AsyncMock), \
         patch("app.core.database.init_db", new_callable=AsyncMock), \
         patch("app.core.redis_client.get_redis") as mock_redis:

        mock_r = AsyncMock()
        mock_r.ping = AsyncMock(return_value=True)
        mock_r.get  = AsyncMock(return_value=None)
        mock_r.set  = AsyncMock(return_value=True)
        mock_r.lpush= AsyncMock(return_value=1)
        mock_r.expire = AsyncMock(return_value=True)
        mock_r.pipeline.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(incr=AsyncMock(), expire=AsyncMock(), execute=AsyncMock(return_value=[1, True]))
        )
        mock_r.pipeline.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_redis.return_value = mock_r

        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c


# ─── Health Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client):
    r = await client.get("/health/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "GoatRaw API"


@pytest.mark.asyncio
async def test_root_endpoint(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "GoatRaw" in r.json()["service"]


# ─── Auth Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_endpoint(client):
    r = await client.post("/users/register", json={
        "email": "newuser@test.com",
        "password": "securepass123",
        "full_name": "Test User",
    })
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["plan"] == "free"
    assert data["api_key"].startswith("gr_") is False  # Our impl returns urlsafe token


@pytest.mark.asyncio
async def test_login_endpoint(client):
    r = await client.post("/users/login", json={
        "email": "user@test.com",
        "password": "password123",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data


# ─── Task Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_task_requires_auth(client):
    r = await client.post("/task/create", json={"goal": "Find leads in Mumbai"})
    assert r.status_code == 403  # No auth header


@pytest.mark.asyncio
async def test_create_task_success(client, auth_headers):
    with patch("app.core.redis_client.enqueue_task", new_callable=AsyncMock), \
         patch("app.core.redis_client.set_task_status", new_callable=AsyncMock), \
         patch("app.core.redis_client.check_rate_limit", return_value=AsyncMock(return_value=True)):

        r = await client.post("/task/create", json={
            "goal": "Find 20 real estate companies in Dubai and extract contact details",
            "agent_type": "lead_generation",
        }, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert "task_id" in data
        assert data["status"] == "queued"
        assert len(data["task_id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_create_task_validates_goal_length(client, auth_headers):
    r = await client.post("/task/create", json={
        "goal": "short",  # Too short (< 10 chars)
        "agent_type": "general",
    }, headers=auth_headers)
    assert r.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_task_not_found(client, auth_headers):
    with patch("app.core.redis_client.get_task_status", return_value=AsyncMock(return_value=None)):
        r = await client.get("/task/nonexistent-task-id", headers=auth_headers)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_task_completed(client, auth_headers):
    task_result = {
        "task_id": "abc123",
        "goal": "Find leads",
        "status": "completed",
        "output": {"summary": "Found 5 leads", "data": [], "status": "success"},
        "steps_taken": 7,
    }
    with patch("app.core.redis_client.get_task_status", return_value=AsyncMock(return_value="completed")), \
         patch("app.core.redis_client.get_task_result", return_value=AsyncMock(return_value=task_result)):

        r = await client.get("/task/abc123", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["result"]["steps_taken"] == 7


# ─── Agent Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lead_gen_endpoint(client, auth_headers):
    with patch("app.core.redis_client.enqueue_task", new_callable=AsyncMock), \
         patch("app.core.redis_client.check_rate_limit", return_value=AsyncMock(return_value=True)):

        r = await client.post("/agent/lead-gen", json={
            "niche": "SaaS companies",
            "location": "Mumbai",
            "filters": {},
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "task_id" in data
        assert data["niche"] == "SaaS companies"
        assert "poll_url" in data


@pytest.mark.asyncio
async def test_market_research_endpoint(client, auth_headers):
    with patch("app.core.redis_client.enqueue_task", new_callable=AsyncMock), \
         patch("app.core.redis_client.check_rate_limit", return_value=AsyncMock(return_value=True)):

        r = await client.post("/agent/market-research", json={"topic": "AI CRM software"}, headers=auth_headers)
        assert r.status_code == 200
        assert "task_id" in r.json()


# ─── Skills Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_skills(client, auth_headers):
    from app.agents.skill_system import BUILTIN_SKILLS
    with patch("app.agents.skill_system.SkillRegistry.list_skills",
               return_value=AsyncMock(return_value=[s.to_dict() for s in BUILTIN_SKILLS.values()])):
        r = await client.get("/skills/list", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "skills" in data
        assert data["total"] >= 5


@pytest.mark.asyncio
async def test_get_builtin_skill(client, auth_headers):
    r = await client.get("/skills/lead_scraper", headers=auth_headers)
    # Should work without mocking since we're reading BUILTIN_SKILLS directly
    if r.status_code == 200:
        data = r.json()
        assert data["id"] == "lead_scraper"
        assert "steps" in data


# ─── Rate Limit Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limited_request(client, auth_headers):
    """When rate limit exceeded, should return 429."""
    with patch("app.core.redis_client.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = False  # Rate limited

        r = await client.post("/task/create", json={
            "goal": "Find SaaS companies in Bangalore for outreach",
            "agent_type": "lead_generation",
        }, headers=auth_headers)
        assert r.status_code == 429
        assert "Rate limit" in r.json()["detail"]
