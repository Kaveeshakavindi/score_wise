from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolDefinitionOut(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
