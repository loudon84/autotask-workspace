from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RpaComponent(BaseModel):
    __tablename__ = "rpa_components"
    __table_args__ = (
        Index("ix_rpa_components_type", "type"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
