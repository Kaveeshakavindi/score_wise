from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, get_tool_service, rate_limit_per_user
from app.schemas.tool import ToolDefinitionOut
from app.services.tool_service import ToolService

router = APIRouter(
    prefix="/api/v1/tools",
    tags=["tools"],
    dependencies=[Depends(rate_limit_per_user("tools_generic", limit=120, window_s=60))],
)


@router.get("", response_model=list[ToolDefinitionOut])
async def list_tools(
    current_user: CurrentUser, tool_service: Annotated[ToolService, Depends(get_tool_service)]
) -> list[ToolDefinitionOut]:
    """List tool definitions available to the model (name, description, JSON
    schema). Requires auth. Introspection only — tools are not directly
    invocable through this API; only the model can call them mid-conversation
    (§6.6, explicit non-goal — see api.md §16.6)."""
    return [
        ToolDefinitionOut(name=d.name, description=d.description, parameters=d.parameters)
        for d in tool_service.list_definitions()
    ]
