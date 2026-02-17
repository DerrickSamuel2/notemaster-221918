from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TagBase(BaseModel):
    name: str = Field(..., description="Tag name (unique, case-insensitive matching is applied by the API).", max_length=64)


class TagCreate(TagBase):
    pass


class TagRead(TagBase):
    id: int = Field(..., description="Tag ID.")

    class Config:
        from_attributes = True


class NoteBase(BaseModel):
    title: str = Field(..., description="Note title.", max_length=255)
    content: str = Field(..., description="Note content (markdown/plain text).")


class NoteCreate(NoteBase):
    tags: List[str] = Field(default_factory=list, description="List of tag names to attach to the note.")


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Updated title.", max_length=255)
    content: Optional[str] = Field(None, description="Updated content.")
    tags: Optional[List[str]] = Field(None, description="Replace tags with this list of tag names.")


class NoteRead(NoteBase):
    id: int = Field(..., description="Note ID.")
    tags: List[TagRead] = Field(default_factory=list, description="Tags attached to the note.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")

    class Config:
        from_attributes = True


class PageMeta(BaseModel):
    page: int = Field(..., description="Current page number (1-indexed).", ge=1)
    page_size: int = Field(..., description="Number of items per page.", ge=1, le=100)
    total: int = Field(..., description="Total number of matching items.", ge=0)


class NotesListResponse(BaseModel):
    items: List[NoteRead] = Field(..., description="Notes in the current page.")
    meta: PageMeta = Field(..., description="Pagination metadata.")


SortField = Literal["updated_at", "created_at", "title"]
SortOrder = Literal["asc", "desc"]
