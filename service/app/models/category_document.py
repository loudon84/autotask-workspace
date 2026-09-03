from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class CategoryDocument(BaseModel):
    """Customer-category file (handbook etc.), keyed by hardcoded category code."""

    __tablename__ = "category_documents"
    __table_args__ = (
        Index("ix_category_documents_tenant_category", "tenant_id", "category"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    uploaded_by_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
