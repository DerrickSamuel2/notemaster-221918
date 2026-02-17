from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Table, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""


note_tags = Table(
    "note_tags",
    Base.metadata,
    mapped_column("note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    mapped_column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    """Tag entity used to categorize notes."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    notes: Mapped[List["Note"]] = relationship(
        secondary=note_tags,
        back_populates="tags",
        lazy="selectin",
    )


class Note(Base):
    """Note entity containing title/content and optional tags."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tags: Mapped[List[Tag]] = relationship(
        secondary=note_tags,
        back_populates="notes",
        lazy="selectin",
    )


Index("ix_notes_title_lower", func.lower(Note.title))
Index("ix_tags_name_lower", func.lower(Tag.name))
