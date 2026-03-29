"""
GoatRaw — Unit Tests: Specialised Agents
"""

import pytest
from unittest.mock import AsyncMock, patch

MOCK_SEARCH = {
    "results": [
        {"title": "Notion - Connected Workspace", "url": "https://notion.so", "snippet": "Notion raised $275M Series C. Features: docs, wikis, databases."},
        {"title": "Notion Pricing", "url": "https://notion.so/pricing", "snippet": "Free tier + $8/month Pro + $15/month Business"},
    ]
}

MOCK_SCRAPE = {
    "content": "Notion is a connected workspace. Features include docs, databases, wikis, calendars. Used by 30M+ users.",
    "title":   "Notion - The connected workspace",
    "status":  "success",
}

MOCK_EXTRACT = {
    "data": {
        "company_name":    "Notion",
        "tagline":         "The connected workspace",
        "pricing_model":   "freemium",
        "pricing_tiers":   ["Free", "Plus $8/mo", "Business $15/mo"],
        "key_features":    ["Docs", "Databases", "Wikis", "AI"],
        "target_customer": "teams and individuals",
        "funding":         "$275M Series C",
    },
    "status": "success",
}

MOCK_SWOT = {
    "summary":                "Notion is a strong competitor in connected workspaces.",
    "strengths":              ["Large user base", "Strong brand", "AI features"],
    "weaknesses":             ["Complex for simple use cases", "Slow performance"],
    "opportunities":          ["Target users frustrated with slow performance"],
    "threats":                ["May expand into our core market"],
    "win_angles":             ["Faster performance", "Better AI automation"],
    "avoid_in_sales":         ["Don't compare pricing directly"],
    "overall_threat_level":   "high",
}


class TestCompetitorAgent:
    @pytest.mark.asyncio
    async def test_competitor_agent_run(self):
        with patch("app.agents.competitor_agent.tool_search_web",      return_value=AsyncMock(return_value=MOCK_SEARCH)()) as _sw, \
             patch("app.agents.competitor_agent.tool_web_scrape",       return_value=AsyncMock(return_value=MOCK_SCRAPE)()) as _sc, \
             patch("app.agents.competitor_agent.tool_extract_structured_data", return_value=AsyncMock(return_value=MOCK_EXTRACT)()) as _ex, \
             patch("app.agents.competitor_agent.generate_json",         return_value=AsyncMock(return_value=MOCK_SWOT)()) as _gj, \
             patch("app.core.redis_client.set_task_status",             new_callable=AsyncMock), \
             patch("app.core.redis_client.set_task_result",             new_callable=AsyncMock):

            from app.agents.competitor_agent import CompetitorAnalysisAgent
            agent  = CompetitorAnalysisAgent("task-c-001", "Notion", "GoatRaw", "productivity")
            result = await agent.run()

            assert result["status"] == "completed"
            assert result["agent_type"] == "competitor_analysis"
            assert "swot" in result["output"]["data"]
            assert result["output"]["data"]["threat_level"] == "high"
            assert len(result["output"]["data"]["win_angles"]) > 0

    @pytest.mark.asyncio
    async def test_competitor_agent_output_structure(self):
        with patch("app.agents.competitor_agent.tool_search_web",       return_value=AsyncMock(return_value=MOCK_SEARCH)()), \
             patch("app.agents.competitor_agent.tool_web_scrape",        return_value=AsyncMock(return_value=MOCK_SCRAPE)()), \
             patch("app.agents.competitor_agent.tool_extract_structured_data", return_value=AsyncMock(return_value=MOCK_EXTRACT)()), \
             patch("app.agents.competitor_agent.generate_json",          return_value=AsyncMock(return_value=MOCK_SWOT)()), \
             patch("app.core.redis_client.set_task_status",              new_callable=AsyncMock), \
             patch("app.core.redis_client.set_task_result",              new_callable=AsyncMock):

            from app.agents.competitor_agent import CompetitorAnalysisAgent
            agent  = CompetitorAnalysisAgent("task-c-002", "Notion", "GoatRaw")
            result = await agent.run()

            output = result["output"]
            assert "summary"   in output
            assert "data"      in output
            assert "stats"     in output
            assert "next_steps" in output
            assert output["status"] == "success"
            # Verify key fields present
            data = output["data"]
            assert "competitor"    in data
            assert "pricing"       in data
            assert "reviews"       in data
            assert "recent_news"   in data


MOCK_MARKET_DATA = {
    "market_name":    "AI CRM",
    "estimated_size": "$5.4B",
    "growth_rate":    "22% CAGR",
    "key_players":    ["Salesforce", "HubSpot", "Zoho"],
    "funding_activity":"Multiple Series A rounds in 2024-2025",
    "trends":         ["AI-powered automation", "No-code workflows"],
}

MOCK_PAIN_DATA = {
    "primary_pain_points":  ["Too expensive", "Hard to integrate", "Bad mobile app"],
    "underserved_segments": ["SMBs under 50 employees", "Indian market"],
    "willingness_to_pay":   "$200-$500/month for right solution",
    "buying_triggers":      ["Sales team scaling", "Lost deals due to poor follow-up"],
    "decision_makers":      ["CEO", "Sales Director", "RevOps"],
}

MOCK_REPORT = {
    "executive_summary":      "AI CRM is a $5.4B growing market at 22% CAGR.",
    "market_size":            "$5.4B, 22% CAGR",
    "top_players":            ["Salesforce", "HubSpot"],
    "key_pain_points":        ["Too expensive for SMBs", "Complex setup"],
    "biggest_trends":         ["AI automation", "No-code"],
    "entry_opportunities":    ["Target Indian SMBs priced out of Salesforce"],
    "recommended_positioning": "Affordable AI CRM for Indian SMBs",
    "icp": {"company_type": "B2B SMB 10-100 employees", "job_titles": ["CEO", "Sales Director"]},
    "market_maturity":        "growing",
}


class TestMarketResearchAgent:
    @pytest.mark.asyncio
    async def test_market_research_run(self):
        with patch("app.agents.market_research_agent.tool_search_web",
                   return_value=AsyncMock(return_value=MOCK_SEARCH)()) as _sw, \
             patch("app.agents.market_research_agent.tool_extract_structured_data",
                   new_callable=AsyncMock) as _ex, \
             patch("app.agents.market_research_agent.generate_json",
                   return_value=AsyncMock(return_value=MOCK_REPORT)()) as _gj, \
             patch("app.core.redis_client.set_task_status", new_callable=AsyncMock), \
             patch("app.core.redis_client.set_task_result", new_callable=AsyncMock):

            _ex.side_effect = [
                {"data": MOCK_MARKET_DATA, "status": "success"},  # overview
                {"data": MOCK_PAIN_DATA,   "status": "success"},  # pain points
            ]

            from app.agents.market_research_agent import MarketResearchAgent
            agent  = MarketResearchAgent("task-m-001", "AI CRM software")
            result = await agent.run()

            assert result["status"]     == "completed"
            assert result["agent_type"] == "market_research"
            output = result["output"]
            assert output["status"]     == "success"
            assert output["data"]["market_size"] == "$5.4B, 22% CAGR"
            assert len(output["data"]["pain_points"]) > 0
            assert output["data"]["maturity"] == "growing"

    @pytest.mark.asyncio
    async def test_market_research_output_structure(self):
        with patch("app.agents.market_research_agent.tool_search_web",
                   return_value=AsyncMock(return_value=MOCK_SEARCH)()) as _sw, \
             patch("app.agents.market_research_agent.tool_extract_structured_data",
                   new_callable=AsyncMock) as _ex, \
             patch("app.agents.market_research_agent.generate_json",
                   return_value=AsyncMock(return_value=MOCK_REPORT)()) as _gj, \
             patch("app.core.redis_client.set_task_status", new_callable=AsyncMock), \
             patch("app.core.redis_client.set_task_result", new_callable=AsyncMock):

            _ex.side_effect = [
                {"data": MOCK_MARKET_DATA, "status": "success"},
                {"data": MOCK_PAIN_DATA,   "status": "success"},
            ]

            from app.agents.market_research_agent import MarketResearchAgent
            agent  = MarketResearchAgent("task-m-002", "SaaS tools", focus="size")
            result = await agent.run()

            data = result["output"]["data"]
            for key in ["topic", "market_size", "top_players", "pain_points",
                        "trends", "opportunities", "positioning", "icp", "maturity"]:
                assert key in data, f"Missing key: {key}"


class TestAgentRouter:
    @pytest.mark.asyncio
    async def test_routes_lead_gen(self):
        from app.agents.agent_router import create_agent
        from app.agents.lead_gen_agent import LeadGenAgent

        agent = await create_agent(
            task_id    = "t1",
            goal       = "Find leads in Mumbai",
            agent_type = "lead_generation",
            user_id    = "u1",
            context    = {"specialized": True, "niche": "SaaS", "location": "Mumbai"},
        )
        assert isinstance(agent, LeadGenAgent)

    @pytest.mark.asyncio
    async def test_routes_competitor(self):
        from app.agents.agent_router import create_agent
        from app.agents.competitor_agent import CompetitorAnalysisAgent

        agent = await create_agent(
            task_id    = "t2",
            goal       = "Analyse Notion",
            agent_type = "competitor_analysis",
            user_id    = "u1",
            context    = {"specialized": True, "competitor_name": "Notion", "your_product": "GoatRaw"},
        )
        assert isinstance(agent, CompetitorAnalysisAgent)

    @pytest.mark.asyncio
    async def test_routes_market_research(self):
        from app.agents.agent_router import create_agent
        from app.agents.market_research_agent import MarketResearchAgent

        agent = await create_agent(
            task_id    = "t3",
            goal       = "Research AI CRM market",
            agent_type = "market_research",
            user_id    = "u1",
            context    = {"specialized": True, "topic": "AI CRM"},
        )
        assert isinstance(agent, MarketResearchAgent)

    @pytest.mark.asyncio
    async def test_routes_general_fallback(self):
        from app.agents.agent_router import create_agent
        from app.agents.orchestrator_v2 import GoatRawAgentV2

        agent = await create_agent(
            task_id    = "t4",
            goal       = "Summarize this article",
            agent_type = "general",
            user_id    = "u1",
            context    = {},
        )
        assert isinstance(agent, GoatRawAgentV2)
