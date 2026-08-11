from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.mcp import McpToolCallRequest, McpToolCallResponse, McpToolsListResponse
from app.services import mcp_service

router = APIRouter()


@router.post("/tools/list", response_model=ApiResponse[McpToolsListResponse])
async def list_tools(user: UserCache = Depends(get_current_user)):
    tools = await mcp_service.list_tools()
    return ApiResponse(data=McpToolsListResponse(tools=tools))


@router.post("/tools/call", response_model=ApiResponse[McpToolCallResponse])
async def call_tool(
    body: McpToolCallRequest,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    result = await mcp_service.call_tool(db, user, body)
    return ApiResponse(
        data=McpToolCallResponse(
            content=[{"type": "text", "text": str(result)}],
            is_error=False,
        )
    )
