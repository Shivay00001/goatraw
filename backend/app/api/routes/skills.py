"""
GoatRaw - Skills API Routes
GET  /skills/list              — list workspace skills
GET  /skills/{id}              — get skill detail
POST /skills/generate          — AI-generates a new skill from description
POST /skills/run               — run a skill directly
DELETE /skills/{id}            — delete custom skill
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import uuid

from app.agents.skill_system import skill_registry
from app.api.deps import get_current_user, check_rate_limit_for_user
from app.core.redis_client import enqueue_task

router = APIRouter()


class GenerateSkillRequest(BaseModel):
    description: str = Field(..., min_length=15, max_length=500,
                             description="Natural language description of the skill to create")


class RunSkillRequest(BaseModel):
    skill_id: str
    inputs: dict = Field(..., description="Input values matching the skill's input_schema")
    async_run: bool = Field(True, description="True = queue and return task_id. False = run inline.")


class InstallSkillRequest(BaseModel):
    name: str
    description: str
    category: str = "custom"
    tags: list = []
    steps: list
    input_schema: dict
    output_schema: dict


@router.get("/list")
async def list_skills(user=Depends(get_current_user)):
    workspace_id = str(user.get("workspace_id", user["id"]))
    skills = await skill_registry.list_skills(workspace_id)
    return {
        "skills": skills,
        "total": len(skills),
        "builtin": sum(1 for s in skills if s.get("author") == "system"),
        "custom": sum(1 for s in skills if s.get("author") != "system"),
    }


@router.get("/{skill_id}")
async def get_skill(skill_id: str, user=Depends(get_current_user)):
    workspace_id = str(user.get("workspace_id", user["id"]))
    skill = await skill_registry.get_skill(skill_id, workspace_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
    return skill.to_dict()


@router.post("/generate")
async def generate_skill(body: GenerateSkillRequest, user=Depends(get_current_user)):
    """
    AI-generates a new skill from plain English description.
    OpenClaw equivalent: autonomous skill creation.
    """
    await check_rate_limit_for_user(user)
    workspace_id = str(user.get("workspace_id", user["id"]))

    skill = await skill_registry.generate_skill(
        workspace_id=workspace_id,
        description=body.description,
    )

    return {
        "skill_id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "steps": len(skill.steps),
        "status": "generated_and_installed",
        "message": f"Skill '{skill.name}' generated and installed to your workspace.",
    }


@router.post("/run")
async def run_skill(body: RunSkillRequest, user=Depends(get_current_user)):
    """Run a skill with given inputs."""
    await check_rate_limit_for_user(user)
    workspace_id = str(user.get("workspace_id", user["id"]))

    # Verify skill exists
    skill = await skill_registry.get_skill(body.skill_id, workspace_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{body.skill_id}' not found.")

    task_id = str(uuid.uuid4())

    if body.async_run:
        await enqueue_task(task_id, {
            "goal": f"Run skill: {skill.name}",
            "agent_type": skill.category,
            "context": {**body.inputs, "skill_name": skill.name},
            "skill_id": body.skill_id,
            "user_id": str(user["id"]),
        })
        return {
            "task_id": task_id,
            "skill_id": body.skill_id,
            "skill_name": skill.name,
            "status": "queued",
            "poll_url": f"/task/{task_id}",
        }
    else:
        from app.agents.orchestrator_v2 import GoatRawAgentV2
        agent = GoatRawAgentV2(
            task_id=task_id,
            goal=f"Run skill: {skill.name}",
            user_id=str(user["id"]),
            agent_type=skill.category,
            context=body.inputs,
            skill_id=body.skill_id,
            workspace_id=workspace_id,
        )
        result = await agent.run()
        return result


@router.post("/install")
async def install_skill(body: InstallSkillRequest, user=Depends(get_current_user)):
    """Install a manually-defined skill to the workspace."""
    workspace_id = str(user.get("workspace_id", user["id"]))
    skill_dict = body.dict()
    skill_id = await skill_registry.install_skill(workspace_id, skill_dict)
    return {"skill_id": skill_id, "status": "installed", "name": body.name}


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, user=Depends(get_current_user)):
    """Delete a custom skill (cannot delete built-in skills)."""
    from app.agents.skill_system import BUILTIN_SKILLS
    if skill_id in BUILTIN_SKILLS:
        raise HTTPException(status_code=400, detail="Cannot delete built-in skills.")

    workspace_id = str(user.get("workspace_id", user["id"]))
    r_key = f"goatraw:skills:{workspace_id}"
    from app.core.redis_client import get_redis
    import json
    r = get_redis()
    all_raw = await r.lrange(r_key, 0, -1)
    kept = [raw for raw in all_raw if json.loads(raw).get("id") != skill_id]
    await r.delete(r_key)
    for item in kept:
        await r.rpush(r_key, item)

    return {"skill_id": skill_id, "status": "deleted"}
