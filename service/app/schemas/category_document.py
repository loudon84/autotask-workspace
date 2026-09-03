from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class CategorySummary(CamelModel):
    code: str
    label: str
    document_count: int = Field(alias="documentCount")


class CategoryDocumentResponse(CamelModel):
    id: str
    category: str
    original_filename: str = Field(alias="originalFilename")
    byte_size: int = Field(alias="byteSize")
    uploaded_by: str = Field(alias="uploadedBy")
    uploaded_by_name: str = Field(alias="uploadedByName")
    created_at: datetime = Field(alias="createdAt")
