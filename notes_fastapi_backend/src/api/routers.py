from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.orm import Session, selectinload

from src.api.schemas import (
    NotesListResponse,
    NoteCreate,
    NoteRead,
    NoteUpdate,
    PageMeta,
    SortField,
    SortOrder,
    TagCreate,
    TagRead,
)
from src.db.models import Note, Tag
from src.db.session import get_db

router = APIRouter(tags=["notes"])


def _normalize_tag_name(name: str) -> str:
    return name.strip()


def _sort_clause(sort_by: SortField, order: SortOrder):
    mapping = {
        "updated_at": Note.updated_at,
        "created_at": Note.created_at,
        "title": Note.title,
    }
    col = mapping[sort_by]
    return asc(col) if order == "asc" else desc(col)


def _get_or_create_tags(db: Session, tag_names: List[str]) -> List[Tag]:
    normalized = [_normalize_tag_name(n) for n in tag_names if _normalize_tag_name(n)]
    if not normalized:
        return []

    # Case-insensitive uniqueness: match existing by lower(name)
    lower_names = {n.lower() for n in normalized}
    existing = db.execute(select(Tag).where(func.lower(Tag.name).in_(lower_names))).scalars().all()
    existing_map = {t.name.lower(): t for t in existing}

    tags: List[Tag] = []
    for original in normalized:
        key = original.lower()
        tag = existing_map.get(key)
        if tag is None:
            tag = Tag(name=original)
            db.add(tag)
            db.flush()  # ensure id
            existing_map[key] = tag
        tags.append(tag)
    return tags


@router.post(
    "/notes",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
    description="Create a new note with optional tags (tags are created if missing).",
    operation_id="create_note",
)
# PUBLIC_INTERFACE
def create_note(payload: NoteCreate, db: Session = Depends(get_db)) -> Note:
    """Create a note and optionally attach tags."""
    note = Note(title=payload.title, content=payload.content)
    note.tags = _get_or_create_tags(db, payload.tags)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get(
    "/notes/{note_id}",
    response_model=NoteRead,
    summary="Get a note by ID",
    operation_id="get_note",
)
# PUBLIC_INTERFACE
def get_note(note_id: int, db: Session = Depends(get_db)) -> Note:
    """Fetch a note by its ID."""
    note = (
        db.execute(
            select(Note).where(Note.id == note_id).options(selectinload(Note.tags))
        )
        .scalars()
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put(
    "/notes/{note_id}",
    response_model=NoteRead,
    summary="Update a note",
    description="Update title/content and optionally replace tags.",
    operation_id="update_note",
)
# PUBLIC_INTERFACE
def update_note(note_id: int, payload: NoteUpdate, db: Session = Depends(get_db)) -> Note:
    """Update a note. If tags is provided, it replaces existing tags."""
    note = (
        db.execute(
            select(Note).where(Note.id == note_id).options(selectinload(Note.tags))
        )
        .scalars()
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content
    if payload.tags is not None:
        note.tags = _get_or_create_tags(db, payload.tags)

    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    operation_id="delete_note",
)
# PUBLIC_INTERFACE
def delete_note(note_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a note by ID."""
    note = db.execute(select(Note).where(Note.id == note_id)).scalars().first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/notes",
    response_model=NotesListResponse,
    summary="List/search notes",
    description=(
        "List notes with optional free-text search (title/content) and optional tag filters.\n\n"
        "Query params supported for compatibility:\n"
        "  - query: free-text search\n"
        "  - tag: single tag filter\n"
        "  - tags: repeated tag filter (?tags=work&tags=todo)\n\n"
        "Tag filtering semantics: if multiple tags are provided, notes must contain ALL of them."
    ),
    operation_id="list_notes",
)
# PUBLIC_INTERFACE
def list_notes(
    query: Optional[str] = Query(None, description="Search query applied to title and content."),
    tag: Optional[str] = Query(None, description="Filter notes by a single tag name."),
    tags: Optional[List[str]] = Query(
        None, description="Filter notes by tag names (repeat query param: ?tags=work&tags=todo)."
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)."),
    sort_by: SortField = Query("updated_at", description="Sort field."),
    order: SortOrder = Query("desc", description="Sort order."),
    db: Session = Depends(get_db),
) -> NotesListResponse:
    """List notes with pagination, sorting, and optional search/tag filters."""
    base_stmt = select(Note).options(selectinload(Note.tags))

    filters = []

    # Search filter (compat: `query` is expected by smoke checks; keep behavior same as previous `q`)
    if query and query.strip():
        like = f"%{query.strip()}%"
        filters.append(or_(Note.title.ilike(like), Note.content.ilike(like)))  # type: ignore[name-defined]

    # Tag filters (compat: accept both `tag` and `tags`)
    requested_tags: List[str] = []
    if tag and tag.strip():
        requested_tags.append(tag.strip())
    if tags:
        requested_tags.extend([t.strip() for t in tags if t and t.strip()])

    if requested_tags:
        lower_names = [t.lower() for t in requested_tags]
        # For "must include all tags", we use a group-by/having count distinct.
        tag_subq = (
            select(Note.id)
            .join(Note.tags)
            .where(func.lower(Tag.name).in_(lower_names))
            .group_by(Note.id)
            .having(func.count(func.distinct(func.lower(Tag.name))) == len(set(lower_names)))
            .subquery()
        )
        filters.append(Note.id.in_(select(tag_subq.c.id)))  # type: ignore[attr-defined]

    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(_sort_clause(sort_by, order))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()
    return NotesListResponse(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


tags_router = APIRouter(prefix="/tags", tags=["tags"])


@tags_router.get(
    "",
    response_model=List[TagRead],
    summary="List tags",
    description="List all tags sorted by name.",
    operation_id="list_tags",
)
# PUBLIC_INTERFACE
def list_tags(db: Session = Depends(get_db)) -> List[Tag]:
    """List all tags."""
    return db.execute(select(Tag).order_by(asc(Tag.name))).scalars().all()


@tags_router.post(
    "",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
    description="Create a tag (name must be unique).",
    operation_id="create_tag",
)
# PUBLIC_INTERFACE
def create_tag(payload: TagCreate, db: Session = Depends(get_db)) -> Tag:
    """Create a tag by name."""
    name = _normalize_tag_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Tag name cannot be empty")

    existing = db.execute(select(Tag).where(func.lower(Tag.name) == name.lower())).scalars().first()
    if existing:
        return existing

    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@tags_router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag",
    description="Delete a tag. Notes remain; only the association is removed.",
    operation_id="delete_tag",
)
# PUBLIC_INTERFACE
def delete_tag(tag_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a tag by ID."""
    tag = db.execute(select(Tag).where(Tag.id == tag_id)).scalars().first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# local import for or_ used above (kept near bottom to avoid clutter in the top section)
from sqlalchemy import or_  # noqa: E402
