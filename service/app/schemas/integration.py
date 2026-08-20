from pydantic import Field

from app.schemas.common import CamelModel


class IntegrationEndpointsResponse(CamelModel):
    sdms_base_url: str = Field("", alias="sdmsBaseUrl")
