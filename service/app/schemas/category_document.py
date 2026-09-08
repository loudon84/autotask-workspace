from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class ExtraFieldSchema(CamelModel):
    key: str
    label: str
    field_type: str = Field(serialization_alias="fieldType")
    required: bool
    placeholder: str = ""
    help_text: str = Field("", serialization_alias="helpText")


class CategorySummary(CamelModel):
    code: str
    label: str
    document_count: int = Field(alias="documentCount")
    extra_fields: list[ExtraFieldSchema] = Field(
        default_factory=list, serialization_alias="extraFields"
    )


class CategoryDocumentResponse(CamelModel):
    id: str
    category: str
    original_filename: str = Field(alias="originalFilename")
    byte_size: int = Field(alias="byteSize")
    uploaded_by: str = Field(alias="uploadedBy")
    uploaded_by_name: str = Field(alias="uploadedByName")
    created_at: datetime = Field(alias="createdAt")
