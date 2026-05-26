"""Skills endpoints.

Implements POST, GET list, PUT, dry-run validate, GET detail, GET content,
GET resources, and DELETE for the Skills component (SK-PRD-01 §6).

POST   /api/v1/accounts/{account_id}/skills                                  — create version 1
GET    /api/v1/accounts/{account_id}/skills                                  — paginated list
PUT    /api/v1/accounts/{account_id}/skills/{skill_id}                       — create next immutable version
POST   /api/v1/accounts/{account_id}/skills/validate                         — dry-run validation (SK-16)
GET    /api/v1/accounts/{account_id}/skills/{skill_id}                       — fetch metadata (SK-19)
GET    /api/v1/accounts/{account_id}/skills/{skill_id}/content               — fetch SKILL.md body (SK-19)
GET    /api/v1/accounts/{account_id}/skills/{skill_id}/resources/{rel_path}  — fetch L3 file (SK-19)
DELETE /api/v1/accounts/{account_id}/skills/{skill_id}                       — soft-archive (SK-19)

Auth:
  Layer 1 — ``check_account_access`` (router-level dependency): rejects
  non-members of ``account_id`` with 403 before any handler runs.
  Layer 2 — handler-side assertion: if a Firestore doc exists at the
  account's path but ``owner.account_id`` differs (inconsistent document),
  the handler returns 403 ``owner_mismatch``.  Natural cross-account
  absence (doc simply not stored at the path) continues to return 404.

Tracing:
  Every endpoint emits one ``api.skills.*`` Weave span via ``_skills_safe_op``.
  Attributes: ``account_id`` on all spans; ``skill_id`` on per-skill endpoints;
  ``bundle_bytes`` + ``file_count`` on POST/PUT; ``archived=True`` on DELETE;
  ``version`` on GET content/resource only when the request pinned one.

PRD reference:
  docs/design/components/skills/projects/SK-PRD-01-skills-backend.md
  §5 Upload payload, §6 API contract, §7 AC-1 / AC-5 / AC-9 / AC-10, §9 Concurrent PUTs
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from google.cloud import firestore
from pydantic import BaseModel

from ..auth.models import UserContext
from ..auth.user_context import check_account_access
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
from ..services.skill_storage import (
    SkillStorageService,
    get_skill_storage_service,
)
from ..services.skill_storage import (
    safe_rel_path as _safe_rel_path,
)
from ..services.skill_validator import (
    ValidationReport,
    validate_bundle,
)

logger = logging.getLogger(__name__)

try:
    import weave

    WEAVE_AVAILABLE = True

    def _skills_safe_op(name: str) -> Callable:  # type: ignore[misc]
        # Only scalars pass through to Weave: UploadFile bytes are a PII risk and
        # ValidationReport/SkillVersion lists are too large to record.  Intentional
        # span attributes are injected via weave.attributes() / _maybe_weave_attrs().
        def _filter(inputs: dict[str, object]) -> dict[str, object]:
            return {
                k: v
                for k, v in inputs.items()
                if isinstance(v, (str, int, float, bool, type(None)))
            }

        return weave.op(name=name, postprocess_inputs=_filter)

except ImportError:
    WEAVE_AVAILABLE = False
    weave = None  # type: ignore[assignment]

    def _skills_safe_op(name: str) -> Callable:  # type: ignore[misc]
        def _identity(fn: Callable) -> Callable:  # type: ignore[misc]
            return fn

        return _identity

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
        db.collection("accounts")
        .document(account_id)
        .collection("skills")
        .document(skill_id)
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


def _check_name_exists(db: firestore.Client, account_id: str, name: str) -> bool:
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
    version_ref = _version_doc_ref(
        db, account_id, skill.skill_id, skill.current_version
    )

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


def _content_type_for(rel_path: str) -> str:
    """Return the HTTP Content-Type for a resource file based on extension.

    Decision (D-2): `.md` → `text/markdown`; everything else → `text/plain`.
    Using an explicit map rather than `mimetypes.guess_type` because Python's
    mimetypes module does not include `.md` reliably across all platforms.
    """
    if rel_path.lower().endswith(".md"):
        return "text/markdown"
    return "text/plain"


def _skill_from_dict(d: dict) -> Skill:
    return Skill.model_validate(d)


# ---------------------------------------------------------------------------
# Weave span helpers
# ---------------------------------------------------------------------------


def _maybe_weave_attrs(attrs: dict[str, object]) -> AbstractContextManager[None]:
    """Return ``weave.attributes(attrs)`` when Weave is available, else a no-op context manager."""
    if WEAVE_AVAILABLE and weave is not None:
        try:
            return weave.attributes(attrs)
        except Exception as exc:
            logger.warning("weave.attributes failed: %s", exc)
    return nullcontext()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/skills",
    tags=["skills"],
    dependencies=[Depends(check_account_access)],
)


# --- validate (SK-16) — defined before /{skill_id} to avoid path shadowing ---
@router.post("/validate", response_model=SkillValidationResponse)
async def validate_skill_bundle(
    account_id: str,
    skill_md: UploadFile = File(...),
    files: list[UploadFile] | None = File(None),
) -> SkillValidationResponse:
    """Dry-run validation of a skill bundle. Creates no Firestore or GCS state.

    Returns HTTP 200 with {"valid": true, "errors": []} on success or
    {"valid": false, "errors": [...]} with field-pointer errors on failure.
    AC-10: validates bundle without writing state.
    """
    raw_files = files or []
    if len(raw_files) > MAX_BUNDLE_FILES:
        return SkillValidationResponse(
            valid=False,
            errors=[
                SkillValidationError(
                    field="files",
                    code="too_many_files",
                    message=f"Bundle contains {len(raw_files)} files; maximum is {MAX_BUNDLE_FILES}.",
                )
            ],
        )
    skill_md_bytes = await skill_md.read()
    files_tuples: list[tuple[str, bytes]] = [
        ((f.filename or "")[:512], await f.read()) for f in raw_files
    ]
    bundle_bytes = len(skill_md_bytes) + sum(len(c) for _, c in files_tuples)
    with _maybe_weave_attrs(
        {
            "account_id": account_id,
            "bundle_bytes": bundle_bytes,
            "file_count": len(files_tuples),
        }
    ):
        return await _validate_traced(
            skill_md_bytes=skill_md_bytes,
            files_tuples=files_tuples,
        )


@_skills_safe_op(name="api.skills.validate")
async def _validate_traced(
    *,
    skill_md_bytes: bytes,
    files_tuples: list[tuple[str, bytes]],
) -> SkillValidationResponse:
    report = validate_bundle(skill_md_bytes, files_tuples, outer_name=None)
    errors = [
        SkillValidationError(field=issue.field, code=issue.code, message=issue.message)
        for issue in report.issues
    ]
    return SkillValidationResponse(valid=report.valid, errors=errors)


# --- GET /{skill_id}/content — declared before /{skill_id} to avoid path shadowing ---
@router.get("/{skill_id}/content")
async def get_skill_content(
    account_id: str,
    skill_id: str,
    version: int | None = Query(default=None, ge=1),
    include_archived: bool = Query(default=False),
    db: firestore.Client = Depends(get_firestore),
    storage: SkillStorageService = Depends(get_skill_storage_service),
) -> Response:
    """Return the SKILL.md body bytes for a versioned skill.

    `Content-Type: text/markdown`.  `?version=N` pins to a specific version;
    omitting uses `current_version`.  Missing version → 404.
    Archived skills return 404 unless `?include_archived=true`.

    AC-4 (content fetched with correct content-type), AC-5 (version pinning).
    """
    attrs: dict[str, object] = {"account_id": account_id, "skill_id": skill_id}
    if version is not None:
        attrs["version"] = version
    with _maybe_weave_attrs(attrs):
        return await _get_skill_content_traced(
            account_id=account_id,
            skill_id=skill_id,
            version=version,
            include_archived=include_archived,
            db=db,
            storage=storage,
        )


@_skills_safe_op(name="api.skills.get_content")
async def _get_skill_content_traced(
    *,
    account_id: str,
    skill_id: str,
    version: int | None,
    include_archived: bool,
    db: firestore.Client,
    storage: SkillStorageService,
) -> Response:
    def _read() -> tuple[str | None, int]:
        snap = _skill_doc_ref(db, account_id, skill_id).get()
        if not snap.exists:
            return "skill_not_found", 0
        skill = _skill_from_dict(snap.to_dict())
        if skill.owner.account_id != account_id:
            return "owner_mismatch", 0
        if skill.status == SkillStatus.ARCHIVED and not include_archived:
            return "skill_not_found", 0
        return None, skill.current_version

    error, current_version = await asyncio.to_thread(_read)
    if error == "owner_mismatch":
        raise HTTPException(status_code=403, detail="owner_mismatch")
    elif error is not None:
        raise HTTPException(status_code=404, detail=error)
    version_to_read = version if version is not None else current_version

    try:
        data = await asyncio.to_thread(
            storage.read_skill_md, account_id, skill_id, version_to_read
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="version_not_found") from exc

    return Response(
        content=data,
        media_type="text/markdown",
        headers={"X-Content-Type-Options": "nosniff"},
    )


# --- GET /{skill_id}/resources/{rel_path} — declared before /{skill_id} ---
@router.get("/{skill_id}/resources/{rel_path:path}")
async def get_skill_resource(
    account_id: str,
    skill_id: str,
    rel_path: str,
    version: int | None = Query(default=None, ge=1),
    include_archived: bool = Query(default=False),
    db: firestore.Client = Depends(get_firestore),
    storage: SkillStorageService = Depends(get_skill_storage_service),
) -> Response:
    """Return the bytes for a single L3 resource file (references/assets/scripts).

    Content-type inferred from extension: `.md` → `text/markdown`, otherwise
    `text/plain`.  Path-traversal attempts return 400 (via `safe_rel_path`).
    Manifest miss or absent version returns 404.  `?version=N` pins version.
    Archived skills return 404 unless `?include_archived=true`.

    AC-4 (path-traversal returns 400; content-type `text/markdown` for `.md`).
    """
    attrs: dict[str, object] = {"account_id": account_id, "skill_id": skill_id}
    if version is not None:
        attrs["version"] = version
    with _maybe_weave_attrs(attrs):
        return await _get_skill_resource_traced(
            account_id=account_id,
            skill_id=skill_id,
            rel_path=rel_path,
            version=version,
            include_archived=include_archived,
            db=db,
            storage=storage,
        )


@_skills_safe_op(name="api.skills.get_resource")
async def _get_skill_resource_traced(
    *,
    account_id: str,
    skill_id: str,
    rel_path: str,
    version: int | None,
    include_archived: bool,
    db: firestore.Client,
    storage: SkillStorageService,
) -> Response:
    # Syntactic safety check: reject path traversal attempts before any GCS read.
    # Use the canonical form returned by safe_rel_path for the GCS lookup so
    # any harmless redundant dots (references/./style.md) normalise away.
    safe_path = _safe_rel_path(rel_path)
    if safe_path is None:
        raise HTTPException(status_code=400, detail="invalid_rel_path")

    def _read() -> tuple[str | None, int]:
        snap = _skill_doc_ref(db, account_id, skill_id).get()
        if not snap.exists:
            return "skill_not_found", 0
        skill = _skill_from_dict(snap.to_dict())
        if skill.owner.account_id != account_id:
            return "owner_mismatch", 0
        if skill.status == SkillStatus.ARCHIVED and not include_archived:
            return "skill_not_found", 0
        return None, skill.current_version

    error, current_version = await asyncio.to_thread(_read)
    if error == "owner_mismatch":
        raise HTTPException(status_code=403, detail="owner_mismatch")
    elif error is not None:
        raise HTTPException(status_code=404, detail=error)
    version_to_read = version if version is not None else current_version

    data = await asyncio.to_thread(
        storage.read_file, account_id, skill_id, version_to_read, safe_path
    )
    if data is None:
        raise HTTPException(status_code=404, detail="resource_not_found")

    return Response(
        content=data,
        media_type=_content_type_for(safe_path),
        headers={"X-Content-Type-Options": "nosniff"},
    )


# --- GET /{skill_id} — declared after /content and /resources/{path} ---
@router.get("/{skill_id}", response_model=Skill)
async def get_skill(
    account_id: str,
    skill_id: str,
    include_archived: bool = Query(default=False),
    db: firestore.Client = Depends(get_firestore),
) -> Skill:
    """Return the Skill metadata document.

    Returns 404 for archived skills unless `?include_archived=true`.
    Returns 403 when the Firestore doc exists but owner.account_id != path account_id
    (inconsistent document — two-layer auth Layer 2). Returns 404 when the doc is
    simply absent at the path (natural cross-account absence).

    AC-7 (has_scripts round-trips through GET detail).
    """
    with _maybe_weave_attrs({"account_id": account_id, "skill_id": skill_id}):
        return await _get_skill_traced(
            account_id=account_id,
            skill_id=skill_id,
            include_archived=include_archived,
            db=db,
        )


@_skills_safe_op(name="api.skills.get")
async def _get_skill_traced(
    *,
    account_id: str,
    skill_id: str,
    include_archived: bool,
    db: firestore.Client,
) -> Skill:
    def _read() -> tuple[str | None, Skill | None]:
        snap = _skill_doc_ref(db, account_id, skill_id).get()
        if not snap.exists:
            return "skill_not_found", None
        skill = _skill_from_dict(snap.to_dict())
        if skill.owner.account_id != account_id:
            return "owner_mismatch", None
        if skill.status == SkillStatus.ARCHIVED and not include_archived:
            return "skill_not_found", None
        return None, skill

    error, skill = await asyncio.to_thread(_read)
    if error == "owner_mismatch":
        raise HTTPException(status_code=403, detail="owner_mismatch")
    elif error is not None:
        raise HTTPException(status_code=404, detail=error)
    assert skill is not None
    return skill


# --- DELETE /{skill_id} — soft-archive ---
@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    account_id: str,
    skill_id: str,
    user: UserContext = Depends(check_account_access),
    db: firestore.Client = Depends(get_firestore),
    storage: SkillStorageService = Depends(get_skill_storage_service),
) -> None:
    """Soft-archive a skill.

    Sets ``status="archived"``, moves the GCS prefix to the trash bucket,
    and returns 204 No Content.  Does NOT delete the Firestore doc or version
    subdocs — the metadata is retained for audit purposes.

    Already-archived skills return 404 (Decision D-1: idempotent UX consistent
    with GET detail's default-archived 404).

    AC-6 (status="archived"; GCS prefix in trash; list excludes it by default).
    """
    with _maybe_weave_attrs(
        {"account_id": account_id, "skill_id": skill_id, "archived": True}
    ):
        return await _delete_skill_traced(
            account_id=account_id,
            skill_id=skill_id,
            user=user,
            db=db,
            storage=storage,
        )


@_skills_safe_op(name="api.skills.delete")
async def _delete_skill_traced(
    *,
    account_id: str,
    skill_id: str,
    user: UserContext,
    db: firestore.Client,
    storage: SkillStorageService,
) -> None:
    now = datetime.now(timezone.utc)

    def _archive() -> str | None:
        snap = _skill_doc_ref(db, account_id, skill_id).get()
        if not snap.exists:
            return "skill_not_found"
        skill = _skill_from_dict(snap.to_dict())
        if skill.owner.account_id != account_id:
            return "owner_mismatch"
        if skill.status == SkillStatus.ARCHIVED:
            return "skill_not_found"
        _skill_doc_ref(db, account_id, skill_id).update(
            {
                "status": SkillStatus.ARCHIVED.value,
                "updated_at": now.isoformat(),
                "updated_by": user.user_id,
            }
        )
        return None

    error = await asyncio.to_thread(_archive)
    if error == "owner_mismatch":
        raise HTTPException(status_code=403, detail="owner_mismatch")
    elif error is not None:
        raise HTTPException(status_code=404, detail=error)

    try:
        await asyncio.to_thread(storage.move_to_trash, account_id, skill_id)
    except Exception:
        # Firestore is already archived; GCS move failure is non-fatal.
        # Log for manual follow-up — the trash lifecycle will not run on this prefix
        # until GCS is moved, but the skill is invisible to users immediately.
        logger.exception(
            "skills_delete_gcs_move_failed",
            extra={"account_id": account_id, "skill_id": skill_id},
        )


@router.post("/", response_model=Skill, status_code=201)
async def create_skill(
    account_id: str,
    skill_md: UploadFile = File(...),
    files: list[UploadFile] = File(default_factory=list),
    name: str = Form(..., max_length=64),
    user: UserContext = Depends(check_account_access),
    db: firestore.Client = Depends(get_firestore),
    storage: SkillStorageService = Depends(get_skill_storage_service),
) -> Skill:
    """Create a new skill (version 1).

    AC-1: Firestore doc at ``accounts/{account_id}/skills/{skill_id}``;
          GCS bundle at ``gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/1/``.
    AC-9: 409 when ``name`` already exists in this account.
    """
    report, skill_md_bytes, files_data = await _parse_and_validate_bundle(
        skill_md, files, outer_name=name
    )
    bundle_bytes = len(skill_md_bytes) + sum(len(c) for _, c in files_data)
    skill_id = uuid4().hex
    with _maybe_weave_attrs(
        {
            "account_id": account_id,
            "bundle_bytes": bundle_bytes,
            "file_count": len(files_data),
            "skill_id": skill_id,
        }
    ):
        return await _create_skill_traced(
            account_id=account_id,
            report=report,
            skill_md_bytes=skill_md_bytes,
            files_data=files_data,
            skill_id=skill_id,
            user=user,
            db=db,
            storage=storage,
        )


@_skills_safe_op(name="api.skills.create")
async def _create_skill_traced(
    *,
    account_id: str,
    report: ValidationReport,
    skill_md_bytes: bytes,
    files_data: list[tuple[str, bytes]],
    skill_id: str,
    user: UserContext,
    db: firestore.Client,
    storage: SkillStorageService,
) -> Skill:
    if (
        report.frontmatter is None
    ):  # invariant: validate_bundle always sets frontmatter on valid
        raise HTTPException(status_code=500, detail="internal_error")

    # Step 1: name uniqueness.
    name_taken = await asyncio.to_thread(
        _check_name_exists, db, account_id, report.frontmatter.name
    )
    if name_taken:
        raise HTTPException(
            status_code=409,
            detail={"code": "skill_name_conflict", "name": report.frontmatter.name},
        )

    # Step 2: allocate version + timestamp.
    version = 1
    now = datetime.now(timezone.utc)

    # Step 3: GCS write (before Firestore commit per PRD §9).
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

    # Step 4: build Skill doc.
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

    # Step 5: Firestore transaction — create skill doc + version subdoc.
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
    db: firestore.Client = Depends(get_firestore),
) -> ListSkillsResponse:
    """List account's skills with cursor pagination.

    Default excludes archived skills unless ``include_archived=true`` or an
    explicit ``status[]=archived`` is supplied.
    """
    with _maybe_weave_attrs({"account_id": account_id}):
        return await _list_skills_traced(
            account_id=account_id,
            status=status,
            has_scripts=has_scripts,
            cursor=cursor,
            page_size=page_size,
            include_archived=include_archived,
            db=db,
        )


@_skills_safe_op(name="api.skills.list")
async def _list_skills_traced(
    *,
    account_id: str,
    status: list[str],
    has_scripts: bool | None,
    cursor: str | None,
    page_size: int,
    include_archived: bool,
    db: firestore.Client,
) -> ListSkillsResponse:
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
                    detail=[
                        {
                            "field": "status",
                            "code": "invalid_status",
                            "message": f"Unknown status value(s): {invalid}",
                        }
                    ],
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
        query = query.order_by(
            "updated_at", direction=firestore.Query.DESCENDING
        ).order_by("skill_id")

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
            rows = rows[:page_size]

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
    name: str = Form(..., max_length=64),
    commit_message: str | None = Form(default=None, max_length=1000),
    user: UserContext = Depends(check_account_access),
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
    # Step 1: parse + validate. outer_name=None → name taken from frontmatter.
    report, skill_md_bytes, files_data = await _parse_and_validate_bundle(
        skill_md, files, outer_name=None
    )
    if report.frontmatter is None:  # invariant
        raise HTTPException(status_code=500, detail="internal_error")
    # The name on the form field must match frontmatter to prevent surprises.
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
    bundle_bytes = len(skill_md_bytes) + sum(len(c) for _, c in files_data)
    with _maybe_weave_attrs(
        {
            "account_id": account_id,
            "skill_id": skill_id,
            "bundle_bytes": bundle_bytes,
            "file_count": len(files_data),
        }
    ):
        return await _update_skill_traced(
            account_id=account_id,
            skill_id=skill_id,
            report=report,
            skill_md_bytes=skill_md_bytes,
            files_data=files_data,
            commit_message=commit_message,
            user=user,
            db=db,
            storage=storage,
        )


async def _perform_update_attempt(
    *,
    account_id: str,
    skill_id: str,
    current_data: dict[str, object],
    report: ValidationReport,
    skill_md_bytes: bytes,
    files_data: list[tuple[str, bytes]],
    commit_message: str | None,
    user: UserContext,
    storage: SkillStorageService,
) -> tuple[Skill, SkillVersion, int]:
    """Parse the current Firestore doc, write the GCS bundle, and build the updated Skill.

    Called for both the initial attempt and each retry so the per-attempt triple
    (parse → GCS write → Skill construction) lives in exactly one place.
    Returns ``(updated_skill, skill_version, expected_version)`` where
    ``expected_version`` is the version read from ``current_data`` and must be
    passed to ``_bump_skill_version`` to detect a concurrent PUT.

    Not decorated with ``@_skills_safe_op``; the owning Weave span is emitted
    by the calling ``_update_skill_traced``.
    """
    existing_skill = _skill_from_dict(current_data)
    new_name = report.frontmatter.name  # type: ignore[union-attr]  # caller asserts not None
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
        description=report.frontmatter.description,  # type: ignore[union-attr]
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
    return updated_skill, skill_version, expected_version


@_skills_safe_op(name="api.skills.update")
async def _update_skill_traced(
    *,
    account_id: str,
    skill_id: str,
    report: ValidationReport,
    skill_md_bytes: bytes,
    files_data: list[tuple[str, bytes]],
    commit_message: str | None,
    user: UserContext,
    db: firestore.Client,
    storage: SkillStorageService,
) -> Skill:
    if report.frontmatter is None:  # invariant
        raise HTTPException(status_code=500, detail="internal_error")

    # Used only for the one-time rename-uniqueness guard below; _perform_update_attempt
    # re-reads it from report.frontmatter for the actual Skill construction.
    new_name = report.frontmatter.name

    # Step 1: read current skill to get current_version (and 404 if not found).
    def _read_skill() -> dict:
        snap = _skill_doc_ref(db, account_id, skill_id).get()
        if not snap.exists:
            raise HTTPException(status_code=404, detail="skill_not_found")
        return snap.to_dict()

    current_data = await asyncio.to_thread(_read_skill)

    # One-time guard checks (not repeated on retry — ownership and rename uniqueness
    # are stable for the life of this request).
    guard_skill = _skill_from_dict(current_data)
    if guard_skill.owner.account_id != account_id:
        raise HTTPException(status_code=403, detail="owner_mismatch")

    # Step 2: name uniqueness for renames.
    if new_name != guard_skill.name:
        name_taken = await asyncio.to_thread(
            _check_name_exists, db, account_id, new_name
        )
        if name_taken:
            raise HTTPException(
                status_code=409,
                detail={"code": "skill_name_conflict", "name": new_name},
            )

    # Steps 3-5: GCS write + Skill build + Firestore transaction, retrying up to 3
    # times on concurrent PUT race.  All per-attempt logic lives in _perform_update_attempt.
    max_retries = 3
    for attempt in range(max_retries):
        updated_skill, skill_version, expected_version = await _perform_update_attempt(
            account_id=account_id,
            skill_id=skill_id,
            current_data=current_data,
            report=report,
            skill_md_bytes=skill_md_bytes,
            files_data=files_data,
            commit_message=commit_message,
            user=user,
            storage=storage,
        )
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

    raise HTTPException(
        status_code=409,
        detail="skill_version_conflict_exhausted",
    )
