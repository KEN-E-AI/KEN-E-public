"""Service for synchronizing competitor data with monitoring topics."""

import logging
from datetime import datetime
from typing import Literal

from ..firestore import FirestoreService
from ..models.monitoring_models import CompetitorEntry, MonitoringTopics

logger = logging.getLogger(__name__)


def _monitoring_topics_subcollection(account_id: str) -> str:
    return f"accounts/{account_id}/monitoring_topics"


class MonitoringSyncService:
    """Service for syncing competitors with monitoring topics in Firestore."""

    @staticmethod
    async def sync_competitor_to_monitoring(
        firestore: FirestoreService,
        account_id: str,
        competitor_name: str,
        website: str | None,
        keywords: list[str],
        operation: Literal["add", "remove"],
    ) -> bool:
        """
        Sync competitor changes to monitoring topics in Firestore.

        Args:
            firestore: Firestore service instance
            account_id: Account ID
            competitor_name: Name of the competitor
            website: Competitor website URL (optional)
            keywords: List of keywords for monitoring
            operation: "add" to add competitor, "remove" to remove

        Returns:
            True if sync succeeded, False otherwise

        Note:
            This function logs errors but does not raise exceptions,
            allowing the primary operation to succeed even if monitoring
            sync fails.
        """
        try:
            # Get existing monitoring topics document
            doc = firestore.get_document(
                collection=_monitoring_topics_subcollection(account_id),
                document_id="default",
            )

            if not doc:
                if operation == "remove":
                    # Nothing to remove from
                    return True

                # Create new monitoring topics document if adding
                logger.warning(
                    f"No monitoring topics found for account {account_id}, "
                    "cannot add competitor. Consider creating monitoring topics first."
                )
                return False

            monitoring_topics = MonitoringTopics(**doc)

            if operation == "add":
                # Auto-populate keywords with competitor name if empty
                final_keywords = keywords or [competitor_name.lower()]

                competitor_entry = CompetitorEntry(
                    name=competitor_name,
                    website=website,
                    keywords=final_keywords,
                )

                # Check for duplicates
                existing_names = {
                    entry.name for entry in monitoring_topics.competitor_entries
                }
                if competitor_name not in existing_names:
                    monitoring_topics.competitor_entries.append(competitor_entry)
                    monitoring_topics.updated_at = datetime.utcnow().isoformat()

                    firestore.update_document(
                        collection=_monitoring_topics_subcollection(account_id),
                        document_id="default",
                        data=monitoring_topics.model_dump(),
                    )

                    logger.info(
                        f"Added competitor {competitor_name} to monitoring topics "
                        f"for account {account_id}"
                    )
                else:
                    logger.debug(
                        f"Competitor {competitor_name} already in monitoring topics"
                    )

            elif operation == "remove":
                original_count = len(monitoring_topics.competitor_entries)
                monitoring_topics.competitor_entries = [
                    entry
                    for entry in monitoring_topics.competitor_entries
                    if entry.name != competitor_name
                ]

                if len(monitoring_topics.competitor_entries) < original_count:
                    monitoring_topics.updated_at = datetime.utcnow().isoformat()
                    firestore.update_document(
                        collection=_monitoring_topics_subcollection(account_id),
                        document_id="default",
                        data=monitoring_topics.model_dump(),
                    )
                    logger.info(
                        f"Removed competitor {competitor_name} from monitoring topics "
                        f"for account {account_id}"
                    )
                else:
                    logger.debug(
                        f"Competitor {competitor_name} not found in monitoring topics"
                    )

            return True

        except Exception as e:
            logger.error(
                f"Failed to {operation} competitor {competitor_name} "
                f"to/from monitoring topics: {e}",
                exc_info=True,
            )
            return False
