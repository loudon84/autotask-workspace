from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel


class McpToolDefinition(CamelModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(serialization_alias="inputSchema")


class McpToolsListResponse(CamelModel):
    tools: list[McpToolDefinition]


class McpToolCallRequest(CamelModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpToolCallResponse(CamelModel):
    content: list[dict[str, Any]]
    is_error: bool = Field(False, serialization_alias="isError")
