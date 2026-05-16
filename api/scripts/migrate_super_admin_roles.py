"""Bootstrap migration — seed the super_admin role (DM-81 Phase 4).

DM-80 closed the live privilege-escalation hole; DM-81 then replaced the
`@ken-e.ai` email-domain super-admin check with an explicit
`roles: ["super_admin"]` array on `users/{uid}`. At deploy, `is_super_admin`
cuts over to that array.

**This migration must run BEFORE the DM-81 code is deployed.** If the code
deploys first, `is_super_admin` reads an empty `roles` for everyone and every
super admin is locked out — including the ability to grant the role back.
Running under the OLD code is harmless: it only adds a field the old code
ignores.

It seeds the role from the OLD criterion, used here once as the old->new
bridge: every Firebase Auth user with a *verified* `@ken-e.ai` email gets
`roles: ArrayUnion(["super_admin"])` merged into their `users/{uid}` doc.
Staff who have no `users/{uid}` doc yet get a baseline skeleton.

Idempotent — re-running is a no-op for users already holding the role.

Usage:
    # Dry run (no writes)
    python api/scripts/migrate_super_admin_roles.py --dry-run

    # Execute
    python api/scripts/migrate_super_admin_roles.py

    # Specify environment
    python api/scripts/migrate_super_admin_roles.py --project-id ken-e-dev
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from google.cloud import firestore

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.auth.firebase_admin import initialize_firebase_admin
from src.kene_api.auth.models import SUPER_ADMIN_ROLE
from src.kene_api.firestore import FirestoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"/tmp/migrate_super_admin_roles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

KEN_E_DOMAIN = "@ken-e.ai"


class SuperAdminRoleMigrator:
    """Seeds the super_admin role from verified @ken-e.ai Firebase users."""

    def __init__(self, dry_run: bool = False) -> None:
        self.firestore = FirestoreService()
        self.dry_run = dry_run
        self.stats: dict[str, int] = {
            "candidates": 0,
            "role_added": 0,
            "skeleton_created": 0,
            "already_seeded": 0,
            "unverified_skipped": 0,
            "errors": 0,
        }

    def initialize(self) -> bool:
        """Initialize Firestore and the Firebase Admin SDK."""
        try:
            logger.info("Initializing Firestore service...")
            if not self.firestore.initialize() or not self.firestore.health_check():
                logger.error("Firestore initialization / health check failed")
                return False

            logger.info("Initializing Firebase Admin SDK...")
            initialize_firebase_admin()
            logger.info("Initialization complete")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return False

    def _seed_user(self, uid: str, email: str) -> None:
        """Grant the super_admin role to one user (idempotent)."""
        client = self.firestore.get_client()
        user_ref = client.collection("users").document(uid)
        snapshot = user_ref.get()

        if snapshot.exists:
            roles = (snapshot.to_dict() or {}).get("roles", [])
            if SUPER_ADMIN_ROLE in roles:
                self.stats["already_seeded"] += 1
                logger.info(f"  {uid} ({email}): already has super_admin — skip")
                return
            if self.dry_run:
                logger.info(f"  [DRY RUN] {uid} ({email}): would add super_admin role")
            else:
                user_ref.update({"roles": firestore.ArrayUnion([SUPER_ADMIN_ROLE])})
            self.stats["role_added"] += 1
            logger.info(f"  {uid} ({email}): super_admin role added")
        else:
            if self.dry_run:
                logger.info(
                    f"  [DRY RUN] {uid} ({email}): would create baseline doc "
                    "with super_admin"
                )
            else:
                user_ref.set(
                    {
                        "uid": uid,
                        "email": email,
                        "profile": {"email": email},
                        "permissions": {
                            "organizations": {},
                            "account_permissions": {},
                        },
                        "roles": [SUPER_ADMIN_ROLE],
                        "created_at": firestore.SERVER_TIMESTAMP,
                    }
                )
            self.stats["skeleton_created"] += 1
            logger.info(f"  {uid} ({email}): baseline doc created with super_admin")

    def run(self) -> dict[str, int]:
        """Iterate Firebase Auth users and seed verified @ken-e.ai staff."""
        from firebase_admin import auth

        mode = "DRY RUN" if self.dry_run else "EXECUTE"
        logger.info(f"Starting super-admin role migration ({mode})")

        for user in auth.list_users().iterate_all():
            email = user.email or ""
            if not email.lower().endswith(KEN_E_DOMAIN):
                continue

            if not user.email_verified:
                self.stats["unverified_skipped"] += 1
                logger.warning(
                    f"  {user.uid} ({email}): @ken-e.ai but email NOT verified — "
                    "skipped (grant explicitly via the admin API if intended)"
                )
                continue

            self.stats["candidates"] += 1
            try:
                self._seed_user(user.uid, email)
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"  {user.uid} ({email}): error — {e}")

        return self.stats


def main() -> int:
    """CLI entry point. Returns a non-zero exit code if any user errored."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intended changes without writing to Firestore",
    )
    parser.add_argument(
        "--project-id",
        help="GCP project ID (sets GOOGLE_CLOUD_PROJECT_ID for this run)",
    )
    args = parser.parse_args()

    if args.project_id:
        os.environ["GOOGLE_CLOUD_PROJECT_ID"] = args.project_id
        os.environ["GOOGLE_CLOUD_PROJECT"] = args.project_id

    migrator = SuperAdminRoleMigrator(dry_run=args.dry_run)
    if not migrator.initialize():
        return 1

    stats = migrator.run()

    logger.info("=" * 60)
    logger.info("Super-admin role migration summary:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)
    if args.dry_run:
        logger.info("DRY RUN — no changes were written.")

    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
