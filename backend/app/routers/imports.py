# The Import tab's API: the text box's draft, the preview (saves nothing), the
# apply (saves exactly what the preview showed), and the list of past imports
# with their undo.
#
# The preview and apply themselves are in importing/preview.py, shared with
# Claude's connector (mcp/server.py); see there why apply checks a hash.

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..importing.preview import StalePreview, apply_preview, build_preview
from ..importing.saving import undo_import
from ..models import AppState, ImportRun
from ..schemas import ImportApply, ImportDraft, ImportOut, ImportRequest

router = APIRouter(prefix="/api", tags=["import"])

DRAFT_KEY = "import_draft"


def today() -> dt.date:
    """The day the dates without a year are read around. A function, so tests can set it."""
    return dt.date.today()


# --- The draft: the text box, kept while typing so a reload doesn't lose it ---


@router.get("/import/draft", response_model=ImportDraft)
def get_draft(db: Session = Depends(get_db)):
    state = db.get(AppState, DRAFT_KEY)
    return ImportDraft(text=(state.value or {}).get("text", "") if state else "")


@router.put("/import/draft", response_model=ImportDraft)
def put_draft(body: ImportDraft, db: Session = Depends(get_db)):
    state = db.get(AppState, DRAFT_KEY)
    if state is None:
        db.add(AppState(key=DRAFT_KEY, value={"text": body.text}))
    else:
        state.value = {"text": body.text}  # a new dict, so SQLAlchemy sees the change
    db.commit()
    return body


# --- Preview and apply (the work is in importing/preview.py, shared with the connector) ---


@router.post("/import/preview")
def preview(body: ImportRequest, db: Session = Depends(get_db)):
    """{rows, counts, source, line_count, hash}. Saves nothing, not even a new course."""
    return build_preview(db, body, today())[1]


def apply_import(db: Session, body: ImportApply, extra_fields: dict | None = None) -> dict:
    """Saves the previewed rows if the preview is still the same (409 otherwise)."""
    try:
        return apply_preview(db, body, today(), extra_fields)
    except StalePreview as stale:
        raise HTTPException(status.HTTP_409_CONFLICT, str(stale)) from None


@router.post("/import/apply")
def apply(body: ImportApply, db: Session = Depends(get_db)):
    """{import_id, added, changed, skipped, errors}. import_id is null when there was nothing to save."""
    return apply_import(db, body)


# --- Past imports ---


@router.get("/imports", response_model=list[ImportOut])
def list_imports(db: Session = Depends(get_db)):
    return db.scalars(select(ImportRun).order_by(ImportRun.created_at.desc(), ImportRun.id.desc())).all()


@router.post("/imports/{import_id}/undo")
def undo(import_id: int, db: Session = Depends(get_db)):
    """{import, removed, restored}."""
    run = db.get(ImportRun, import_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found.")
    if run.undone_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This import was already undone.")
    removed, restored = undo_import(db, run)
    db.commit()
    return {"import": ImportOut.model_validate(run), "removed": removed, "restored": restored}
