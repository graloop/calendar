# The Import tab's API: the text box's draft, the preview (saves nothing), the
# apply (saves exactly what the preview showed), and the list of past imports
# with their undo.
#
# Why a hash: the page sends back the hash of the preview it showed. Apply
# makes the preview again from the same text and refuses if anything differs
# (the calendar changed, or it's another day), so nothing is ever saved that
# wasn't seen first.

import datetime as dt
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..importing.matching import PreviewRow, classify, counts
from ..importing.parser import guess_source_kind, parse_text
from ..importing.saving import save_import, undo_import
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


# --- Preview and apply ---


def _source(requested: str, rows: list[PreviewRow]) -> str:
    """The import's source: as chosen, or (auto) what every line's source column
    points to. Lines from several kinds, or none: other."""
    if requested != "auto":
        return requested
    kinds = {guess_source_kind(r.event.source_link) for r in rows if r.event and r.event.source_link}
    return kinds.pop() if len(kinds) == 1 else "other"


def _preview(db: Session, body: ImportRequest) -> tuple[list[PreviewRow], dict]:
    parsed = parse_text(body.text, today())
    rows = classify(db, parsed.items)
    source = _source(body.source, rows)
    out = {
        "rows": [r.to_json() for r in rows],
        "counts": counts(rows),
        "source": source,
        "line_count": parsed.line_count,
    }
    digest = json.dumps(out, sort_keys=True, ensure_ascii=False).encode()
    out["hash"] = hashlib.sha256(digest).hexdigest()
    return rows, out


@router.post("/import/preview")
def preview(body: ImportRequest, db: Session = Depends(get_db)):
    """{rows, counts, source, line_count, hash}. Saves nothing, not even a new course."""
    return _preview(db, body)[1]


def apply_import(db: Session, body: ImportApply, extra_fields: dict | None = None) -> dict:
    """Saves the previewed rows if the preview is still the same. `extra_fields`
    go on every new event (e.g. a calendar chosen on the page)."""
    rows, out = _preview(db, body)
    if out["hash"] != body.hash:
        raise HTTPException(status.HTTP_409_CONFLICT, "The calendar changed since the preview. Press Preview again.")
    run = save_import(db, rows, out["source"], out["line_count"], extra_fields)
    db.commit()
    c = out["counts"]
    return {
        "import_id": run.id if run else None,
        "added": c["new"],
        "changed": c["changed"],
        "skipped": c["already"],
        "errors": c["error"],
    }


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
