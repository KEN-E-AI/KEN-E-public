"""Skills endpoints.

Implements POST, GET list, PUT, and dry-run validate for the Skills component
(SK-PRD-01 §6).

POST   /api/v1/accounts/{account_id}/skills             — create version 1
GET    /api/v1/accounts/{account_id}/skills             — paginated list
PUT    /api/v1/accounts/{account_id}/skills/{skill_id}  — create next immutable version
POST   /api/v1/accounts/{account_id}/skills/validate    — dry-run validation (SK-16)

Auth:
  This router ships a placeholder that asserts the caller is a member of
  ``account_id`` via ``user.has_account_access(account_id)``. The full
  two-layer check (account-access dependency + owner.account_id assertion)
  is added in SK-20 (``check_account_access`` helper + 404 isolation).
  TODO SK-20: replace ``_require_account_membership`` below with the canonical
  ``check_account_access`` helper once it lands in SK-20.

Tracing:
  Deferred to SK-21. No Weave spans emitted here.

PRD reference:
  docs/design/components/skills/projects/SK-PRD-01-skills-backend.md
  §5 Upload payload, §6 API contract, §7 AC-1 / AC-5 / AC-9 / AC-10, §9 Concurrent PUTs
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from google.cloud import firestore
from pydantic import BaseModel

from ..auth.models import UserContext
from ..auth.user_context import get_current_user_context
from ..dependencies import get_firestore
from ..models.skill_models import (
    MAX_BUNDLE_FILES,
    Skill,
    SkillOwner,
    SkillSource,
    SkillStatus,
    SkillValidationError,
    SkillValidationResponse,
    SkillVersion,
    SkillVisibility,
)
from ..services.skill_storage import SkillStorageService, get_skill_storage_service
from ..services.skill_validator import (
    ValidationReport,
    validate_bundle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class ListSkillsResponse(BaseModel):
    items: list[Skill]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Cursor codec — opaque, base64-encoded JSON
# ---------------------------------------------------------------------------


def _encode_cursor(updated_at: datetime, skill_id: str) -> str:
    payload = json.dumps({"updated_at": updated_at.isoformat(), "skill_id": skill_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(token: str) -> tuple[datetime, str] | None:
    """Return ``(updated_at, skill_id)`` or ``None`` on any parse failure.

    Treats malformed cursors as "start from beginning" — no 422 raised.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(token.encode()))
        updated_at = datetime.fromisoformat(payload["updated_at"])
        skill_id = str(payload["skill_id"])
        return updated_at, skill_id
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Auth placeholder — replaced by check_account_access in SK-20
# ---------------------------------------------------------------------------


def _require_account_membership(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
) -> UserContext:
    """403 if the caller is not a member of ``account_id``.

    TODO SK-20: swap this for the canonical ``check_account_access`` dependency
    which also adds the owner.account_id == path.account_id assertion (404 on
    cross-account doc inconsistency) and per-endpoint role gating.
    """
    if not user.has_account_access(account_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return user


# ---------------------------------------------------------------------------
# Multipart parse helper — shared by POST and PUT
# ---------------------------------------------------------------------------


async def _parse_and_validate_bundle(
    skill_md: UploadFile,
    files: list[UploadFile],
    outer_name: str | None,
) -> tuple[ValidationReport, bytes, list[tuple[str, bytes]]]:
    """Read every UploadFile exactly once, validate, and return materialized bytes.

    Raises ``HTTPException(422)`` if the bundle is invalid.  On success returns
    ``(report, skill_md_bytes, [(rel_path, content), …])``.

    ``outer_name`` is the ``name`` form field for POST (must match frontmatter.name).
    Pass ``None`` from PUT where the name is allowed to change (the new name comes
    from the frontmatter directly).
    """
    skill_md_bytes = await skill_md.read()
    files_data: list[tuple[str, bytes]] = []
    for f in files:
        rel_path = f.filename or ""
        content = await f.read()
        files_data.append((rel_path, content))

    report = validate_bundle(skill_md_bytes, files_data, outer_name)
    if not report.valid:
        raise HTTPException(
            status_code=422,
            detail=[
                {"field": issue.field, "code": issue.code, "message": issue.message}
                for issue in report.issues
            ],
        )
    return report, skill_md_bytes, files_data


# ---------------------------------------------------------------------------
# Firestore helpers — run sync Firestore calls off the event loop
# ---------------------------------------------------------------------------


def _skill_doc_ref(
    db: firestore.Client, account_id: str, skill_id: str
) -> firestore.DocumentReference:
    return (
        db.collection("accounts").document(account_id).collection("skills").document(skill_id)
    )


def _version_doc_ref(
    db: firestore.Client, account_id: str, skill_id: str, version: int
) -> firestore.DocumentReference:
    return (
        db.collection("accounts")
        .document(account_id)
        .collection("skills")
        .document(skill_id)
        .collection("versions")
        .document(str(version))
    )


def _check_name_exists(
    db: firestore.Client, account_id: str, name: str
) -> bool:
    """Return True if a non-archived skill with ``name`` already exists in this account.

    A pre-write equality query — adequate for v1's human authoring write rate.
    Decision: pre-write query rather than Firestore transaction for name uniqueness.
    What would invalidate: a regression test showing two POSTs <100ms apart both
    succeeding with the same name.  TODO: make this a Firestore transaction if the
    race ever needs to be airtight.  (Pattern from routers/admin.py:193.)
    """
    query = (
        db.collection("accounts")
        .document(account_id)
        .collection("skills")
        .where("name", "==", name)
        .where("status", "in", [SkillStatus.DRAFT.value, SkillStatus.PUBLISHED.value])
        .limit(1)
    )
    return len(list(query.stream())) > 0


def _write_skill_and_version(
    db: firestore.Client,
    skill: Skill,
    skill_version: SkillVersion,
    account_id: str,
) -> None:
    """Write ``Skill`` + ``SkillVersion`` in a single Firestore transaction.

    Uses ``transaction.create()`` for both docs so the write is idempotent
    against retries (a second attempt with the same skill_id + version will
    fail the ``create()`` call, which the caller should treat as a success —
    the doc is already there).
    """
    skill_ref = _skill_doc_ref(db, account_id, skill.skill_id)
    version_ref = _version_doc_ref(db, account_id, skill.skill_id, skill.current_version)

    transaction = db.transaction()

    @firestore.transactional
    def _run(tx: firestore.Transaction) -> None:
        tx.create(skill_ref, _skill_to_dict(skill))
        tx.create(version_ref, _version_to_dict(skill_version))

    _run(transaction)


def _bump_skill_version(
    db: firestore.Client,
    account_id: str,
    skill_id: str,
    skill_version: SkillVersion,
    updated_skill: Skill,
    expected_current_version: int,
) -> bool:
    """Increment ``current_version`` atomically.

    Reads the Skill doc inside the transaction to guard against a concurrent PUT
    that already bumped the version.  Returns False when a concurrent PUT won
    the race (caller should retry the whole pipeline).

    GCS write has already happened at ``expected_current_version + 1`` before
    this is called.  On retry the caller re-runs the GCS write at N+2, leaving
    the N+1 prefix as an orphan.
    TODO: a daily sweeper job reconciles orphan GCS prefixes against Firestore
    ``versions/*`` docs (PRD §9 / SK-15 Implementation Notes).
    """
    skill_ref = _skill_doc_ref(db, account_id, skill_id)
    version_ref = _version_doc_ref(
        db, account_id, skill_id, expected_current_version + 1
    )

    _race_detected = False
    _not_found = False

    transaction = db.transaction()

    @firestore.transactional
    def _run(tx: firestore.Transaction) -> None:
        nonlocal _race_detected, _not_found
        snap = skill_ref.get(transaction=tx)
        if not snap.exists:
            _not_found = True
            return
        current = snap.to_dict().get("current_version", 0)
        if current != expected_current_version:
            _race_detected = True
            return
        tx.create(version_ref, _version_to_dict(skill_version))
        tx.update(skill_ref, _skill_update_dict(updated_skill))

    _run(transaction)
    if _not_found:
        raise HTTPException(status_code=404, detail="skill_not_found")
    return not _race_detected


# ---------------------------------------------------------------------------
# Firestore ↔ Pydantic serialisation helpers
# ---------------------------------------------------------------------------


def _skill_to_dict(skill: Skill) -> dict:
    d = skill.model_dump(mode="json")
    # Store owner as a flat sub-dict; Firestore handles nested maps.
    return d


def _version_to_dict(version: SkillVersion) -> dict:
    return version.model_dump(mode="json")


def _skill_update_dict(skill: Skill) -> dict:
    """Subset of Skill fields written on a PUT (version bump)."""
    return {
        "current_version": skill.current_version,
        "name": skill.name,
        "description": skill.description,
        "has_scripts": skill.has_scripts,
        "updated_at": skill.updated_at.isoformat(),
        "updated_by": skill.updated_by,
    }


def _skill_from_dict(d: dict) -> Skill:
    return Skill.model_validate(d)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/skills",
    tags=["skills"],
)


# --- validate (SK-16) — defined before /{skill_id} to avoid path shadowing ---
@router.post("/validate", response_model=SkillValidationResponse)
async def validate_skill_bundle(
    account_id: str,
    skill_md: UploadFile = File(...),
    files: list[UploadFile] | None = File(None),
    _user: UserContext = Depends(_require_account_membership),
) -> SkillValidationResponse:
    """Dry-run validation of a skill bundle. Creates no Firestore or GCS state.

    Returns HTTP 200 with {"valid": true, "errors": []} on success or
    {"valid": false, "errors": [...]} with field-pointer errors on failure.
    AC-10: validates bundle without writing state.
    """
    # Guard file count before reading bytes to limit memory allocation.
    if files and len(files) > MAX_BUNDLE_FILES:
        return SkillValidationResponse(
            valid=False,
            errors=[
                SkillValidationError(
                    field="files",
                    code="too_many_files",
                    message=f"Bundle contains {len(files)} files; maximum is {MAX_BUNDLE_FILES}.",
                )
            ],
        )

    skill_md_bytes = await skill_md.read()
    files_tuples: list[tuple[str, bytes]] = []
    if files:
        for f in files:
            rel_path = (f.filename or "")[:512]  # bound filename length
            data = await f.read()
            files_tuples.append((rel_path, data))

    report = validate_bundle(skill_md_bytes, files_tuples, outer_name=None)
    errors = [
        SkillValidationError(field=issue.field, code=issue.code, message=issue.message)
        for issue in report.issues
    ]
    return SkillValidationResponse(valid=report.valid, errors=errors)


@router.post("/", response_model=Skill, status_code=201)
async def create_skill(
    account_id: str,
    skill_md: UploadFile = File(...),
    files: list[UploadFile] = File(default_factory=list),
    name: str = Form(..., max_length=64),
    user: UserContext = Depends(_require_account_membership),
    db: firestore.Client = Depends(get_firestore),
    storage: SkillStorageService = Depends(get_skill_storage_service),
) -> Skill:
    """Create a new skill (version 1).

    AC-1: Firestore doc at ``accounts/{account_id}/skills/{skill_id}``;
          GCS bundle at ``gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/1/``.
    AC-9: 409 when ``name`` already exists in this account.
    """
    # Step 1: parse + validate.
    report, skill_md_bytes, files_data = await _parse_and_validate_bundle(
        skill_md, files, outer_name=name
    )

    # Step 2: name uniqueness.
    name_taken = await asyncio.to_thread(
        _check_name_exists, db, account_id, name
    )
    if name_taken:
        raise HTTPException(
            status_code=409,
            detail={"code": "skill_name_conflict", "name": name},
        )

    # Step 3: allocate IDs.
    skill_id = uuid4().hex
    version = 1
    now = datetime.now(timezone.utc)

    # Step 4: GCS write (before Firestore commit per PRD §9).
    if report.frontmatter is None:  # invariant: validate_bundle always sets frontmatter on valid
        raise HTTPException(status_code=500, detail="internal_error")
    skill_version = await asyncio.to_thread(
        storage.write_bundle,
        account_id=account_id,
        skill_id=skill_id,
        version=version,
        skill_md_bytes=skill_md_bytes,
        files=files_data,
        frontmatter=report.frontmatter,
        created_by=user.user_id,
        commit_message=None,
    )

    # Step 5: build Skill doc.
    skill = Skill(
        skill_id=skill_id,
        owner=SkillOwner(account_id=account_id),
        name=report.frontmatter.name,
        description=report.frontmatter.description,
        current_version=1,
        visibility=SkillVisibility.PRIVATE,
        status=SkillStatus.DRAFT,
        source=SkillSource(),
        has_scripts=report.has_scripts,
        created_at=now,
        created_by=user.user_id,
        updated_at=now,
        updated_by=user.user_id,
    )

    # Step 6: Firestore transaction — create skill doc + version subdoc.
    await asyncio.to_thread(
        _write_skill_and_version, db, skill, skill_version, account_id
    )

    return skill


@router.get("/", response_model=ListSkillsResponse)
async def list_skills(
    account_id: str,
    status: list[str] = Query(default=[]),
    has_scripts: bool | None = Query(default=None),
    cursor: str | None = Query(default=None),
    page_size: int = Query(default=50, ge=1, le=100),
    include_archived: bool = Query(default=False),
    user: UserContext = Depends(_require_account_membership),
    db: firestore.Client = Depends(get_firestore),
) -> ListSkillsResponse:
    """List account's skills with cursor pagination.

    Default excludes archived skills unless ``include_archived=true`` or an
    explicit ``status[]=archived`` is supplied.
    """

    def _run() -> tuple[list[Skill], str | None]:
        coll = db.collection("accounts").document(account_id).collection("skills")
        query: firestore.Query = coll  # type: ignore[assignment]

        # Status filter.
        if status:
            valid_statuses = {s.value for s in SkillStatus}
            invalid = [s for s in status if s not in valid_statuses]
            if invalid:
                raise HTTPException(
                    status_code=422,
                    detail=[{"field": "status", "code": "invalid_status", "message": f"Unknown status value(s): {invalid}"}],
                )
            query = query.where("status", "in", status)
        elif not include_archived:
            query = query.where(
                "status", "in", [SkillStatus.DRAFT.value, SkillStatus.PUBLISHED.value]
            )

        # has_scripts filter.
        if has_scripts is not None:
            query = query.where("has_scripts", "==", has_scripts)

        # Stable ordering by (updated_at DESC, skill_id ASC) for cursor pagination.
        query = query.order_by("updated_at", direction=firestore.Query.DESCENDING).order_by(
            "skill_id"
        )

        # Cursor.
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            updated_at_val, skill_id_val = decoded
            # Positional field values matching order_by(updated_at, skill_id).
            query = query.start_after(updated_at_val.isoformat(), skill_id_val)

        # Over-fetch by 1 to detect next page.
        query = query.limit(page_size + 1)

        rows = list(query.stream())
        has_next = len(rows) > page_size
        if has_next:
            rows = rows[: page_size]

        items: list[Skill] = []
        for doc in rows:
            try:
                items.append(_skill_from_dict(doc.to_dict()))
            except Exception:
                logger.warning(
                    "skills_list_invalid_doc",
                    extra={"account_id": account_id, "doc_id": doc.id},
                )

        next_cursor: str | None = None
        if has_next and items:
            last = items[-1]
            next_cursor = _encode_cursor(last.updated_at, last.skill_id)

        return items, next_cursor

    items, next_cursor = await asyncio.to_thread(_run)
    return ListSkillsResponse(items=items, next_cursor=next_cursor)


@router.put("/{skill_id}", response_model=Skill)
async def update_skill(
    account_id: str,
    skill_id: str,
    skill_md: UploadFile = File(...),
    files: list[UploadFile] = File(default_factory=list),
    name: str = Form(...),
    commit_message: str | None = Form(default=None, max_length=1000),
    user: UserContext = Depends(_require_account_membership),
    db: firestore.Client = Depends(get_firestore),
    storage: SkillStorageService = Depends(get_skill_storage_service),
) -> Skill:
    """Create the next immutable version of an existing skill.

    AC-5: ``current_version`` increments; new files at ``…/{N+1}/``; old version
          GCS objects are preserved.

    The Firestore transaction (PRD §9 Concurrent PUTs) re-reads
    ``current_version`` inside the transaction to detect a concurrent PUT that
    won the race; on conflict the whole pipeline retries up to 3 times.
    """
    # Step 1: parse + validate.  On PUT, outer_name=None → name taken from frontmatter.
    report, skill_md_bytes, files_data = await _parse_and_validate_bundle(
        skill_md, files, outer_name=None
    )
    if report.frontmatter is None:  # invariant: validate_bundle always sets frontmatter on valid
        raise HTTPException(status_code=500, detail="internal_error")

    # The name on the form field must still match frontmatter to prevent surprises,
    # even on PUT (the user may be renaming). Enforce here.
    if name != report.frontmatter.name:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "field": "name",
                    "code": "name_mismatch",
                    "message": (
                        f"The 'name' form field ({name!r}) does not match the "
                        f"name in SKILL.md frontmatter ({report.frontmatter.name!r})."
                    ),
                }
            ],
        )

    new_name = report.frontmatter.name

    # Step 2: read current skill to get current_version (and 404 if not found).
    def _read_skill() -> dict:
        snap = _skill_doc_ref(db, account_id, skill_id).get()
        if not snap.exists:
            raise HTTPException(status_code=404, detail="skill_not_found")
        return snap.to_dict()

    current_data = await asyncio.to_thread(_read_skill)
    existing_skill = _skill_from_dict(current_data)

    # Ownership assertion: path account_id must match stored owner.
    if existing_skill.owner.account_id != account_id:
        raise HTTPException(status_code=404, detail="skill_not_found")

    # Step 3: name uniqueness for renames.  PRD §7 "name is mutable … subject
    # to the same regex + uniqueness rules."
    if new_name != existing_skill.name:
        name_taken = await asyncio.to_thread(
            _check_name_exists, db, account_id, new_name
        )
        if name_taken:
            raise HTTPException(
                status_code=409,
                detail={"code": "skill_name_conflict", "name": new_name},
            )

    expected_version = existing_skill.current_version
    next_version = expected_version + 1
    now = datetime.now(timezone.utc)

    # Step 4: GCS write first at predicted prefix ``{N+1}/`` (PRD §9).
    skill_version = await asyncio.to_thread(
        storage.write_bundle,
        account_id=account_id,
        skill_id=skill_id,
        version=next_version,
        skill_md_bytes=skill_md_bytes,
        files=files_data,
        frontmatter=report.frontmatter,
        created_by=user.user_id,
        commit_message=commit_message,
    )

    # Step 5: build the updated Skill for atomic write.
    updated_skill = Skill(
        skill_id=skill_id,
        owner=existing_skill.owner,
        name=new_name,
        description=report.frontmatter.description,
        current_version=next_version,
        visibility=existing_skill.visibility,
        status=existing_skill.status,
        source=existing_skill.source,
        has_scripts=report.has_scripts,
        created_at=existing_skill.created_at,
        created_by=existing_skill.created_by,
        updated_at=now,
        updated_by=user.user_id,
    )

    # Step 6: Firestore transaction — retry up to 3 times on concurrent PUT race.
    max_retries = 3
    for attempt in range(max_retries):
        success = await asyncio.to_thread(
            _bump_skill_version,
            db,
            account_id,
            skill_id,
            skill_version,
            updated_skill,
            expected_version,
        )
        if success:
            return updated_skill

        # A concurrent PUT won the race.  Re-read current_version and retry with N+2.
        # The orphaned GCS prefix ({N+1}/) is left for the daily sweeper job.
        # TODO: daily sweeper job reconciles orphan GCS prefixes (PRD §9).
        logger.info(
            "skills_put_version_race_retry",
            extra={
                "account_id": account_id,
                "skill_id": skill_id,
                "attempt": attempt + 1,
            },
        )
        current_data = await asyncio.to_thread(_read_skill)
        existing_skill = _skill_from_dict(current_data)
        expected_version = existing_skill.current_version
        next_version = expected_version + 1
        now = datetime.now(timezone.utc)

        skill_version = await asyncio.to_thread(
            storage.write_bundle,
            account_id=account_id,
            skill_id=skill_id,
            version=next_version,
            skill_md_bytes=skill_md_bytes,
            files=files_data,
            frontmatter=report.frontmatter,
            created_by=user.user_id,
            commit_message=commit_message,
        )
        updated_skill = Skill(
            skill_id=skill_id,
            owner=existing_skill.owner,
            name=new_name,
            description=report.frontmatter.description,
            current_version=next_version,
            visibility=existing_skill.visibility,
            status=existing_skill.status,
            source=existing_skill.source,
            has_scripts=report.has_scripts,
            created_at=existing_skill.created_at,
            created_by=existing_skill.created_by,
            updated_at=now,
            updated_by=user.user_id,
        )

    raise HTTPException(
        status_code=409,
        detail="skill_version_conflict_exhausted",
    )
