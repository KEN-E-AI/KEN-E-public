"""Conversation summarization utilities for session history management.

This module provides utilities for managing conversation history to stay
within token limits. It supports:
- Tracking message count and token usage
- Summarizing older messages when approaching budget
- Keeping recent messages intact for context continuity
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Try relative import first (when used as part of package)
# Fall back to standard logging (when imported directly in tests)
try:
    from .structured_logging import get_structured_logger, log_context
except ImportError:
    # Fallback for direct imports (e.g., in tests)
    def get_structured_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

    def log_context(**kwargs: Any) -> dict[str, Any]:
        return {"json_fields": kwargs}


logger = get_structured_logger(__name__)


# Token budget constants
MAX_CONVERSATION_TOKENS = 40_000  # Target max for conversation history
COMPACTION_THRESHOLD = 0.8  # Trigger compaction at 80% of budget
RECENT_MESSAGES_TO_KEEP = 10  # Keep last N messages intact
SUMMARY_TOKEN_TARGET = 2_000  # Target token count for summaries
CHARS_PER_TOKEN = 4  # Conservative estimate: 1 token ≈ 4 chars


@dataclass
class ConversationMessage:
    """Represents a message in a conversation.

    Attributes:
        role: Message role ('user' or 'assistant')
        content: Message content text
        timestamp: When the message was created
        token_count: Estimated token count for the message
    """

    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0

    def __post_init__(self) -> None:
        """Calculate token count after initialization."""
        if self.token_count == 0:
            self.token_count = len(self.content) // CHARS_PER_TOKEN


@dataclass
class ConversationSummary:
    """Summary of older conversation messages.

    Attributes:
        content: Summary text
        message_count: Number of messages summarized
        start_timestamp: Timestamp of first summarized message
        end_timestamp: Timestamp of last summarized message
        token_count: Token count of the summary
    """

    content: str
    message_count: int
    start_timestamp: datetime
    end_timestamp: datetime
    token_count: int = 0

    def __post_init__(self) -> None:
        """Calculate token count after initialization."""
        if self.token_count == 0:
            self.token_count = len(self.content) // CHARS_PER_TOKEN


class ConversationSummarizer:
    """Manages conversation history with automatic summarization.

    Tracks messages, monitors token usage, and summarizes older messages
    when the conversation approaches the token budget.

    Example:
        >>> summarizer = ConversationSummarizer()
        >>> summarizer.add_message("user", "Hello!")
        >>> summarizer.add_message("assistant", "Hi there!")
        >>> if summarizer.should_compact():
        ...     summarized_history = await summarizer.compact()
    """

    def __init__(
        self,
        max_tokens: int = MAX_CONVERSATION_TOKENS,
        compaction_threshold: float = COMPACTION_THRESHOLD,
        recent_messages_to_keep: int = RECENT_MESSAGES_TO_KEEP,
    ) -> None:
        """Initialize the conversation summarizer.

        Args:
            max_tokens: Maximum token budget for conversation history
            compaction_threshold: Percentage of budget to trigger compaction
            recent_messages_to_keep: Number of recent messages to preserve
        """
        self._max_tokens = max_tokens
        self._compaction_threshold = compaction_threshold
        self._recent_messages_to_keep = recent_messages_to_keep

        self._messages: list[ConversationMessage] = []
        self._summary: ConversationSummary | None = None
        self._total_token_count = 0

    @property
    def message_count(self) -> int:
        """Get total number of messages in the conversation."""
        return len(self._messages)

    @property
    def total_tokens(self) -> int:
        """Get estimated total token count."""
        summary_tokens = self._summary.token_count if self._summary else 0
        return summary_tokens + sum(m.token_count for m in self._messages)

    @property
    def token_budget_usage(self) -> float:
        """Get current token budget usage as a percentage (0.0 to 1.0)."""
        return self.total_tokens / self._max_tokens

    @property
    def messages(self) -> list[ConversationMessage]:
        """Get list of current messages (excluding summarized)."""
        return self._messages.copy()

    @property
    def summary(self) -> ConversationSummary | None:
        """Get current summary of older messages."""
        return self._summary

    def add_message(self, role: str, content: str) -> ConversationMessage:
        """Add a new message to the conversation.

        Args:
            role: Message role ('user' or 'assistant')
            content: Message content

        Returns:
            The created ConversationMessage
        """
        message = ConversationMessage(role=role, content=content)
        self._messages.append(message)
        logger.debug(
            "Added conversation message",
            extra=log_context(
                component="conversation",
                action="add_message",
                token_count=message.token_count,
                message_count=len(self._messages),
                extra={
                    "role": role,
                    "total_tokens": self.total_tokens,
                },
            ),
        )
        return message

    def should_compact(self) -> bool:
        """Check if conversation should be compacted.

        Returns:
            True if token usage exceeds compaction threshold
        """
        usage = self.token_budget_usage
        should = usage >= self._compaction_threshold
        if should:
            logger.info(
                "Conversation compaction triggered",
                extra=log_context(
                    component="compaction",
                    action="trigger",
                    token_count=self.total_tokens,
                    message_count=len(self._messages),
                    extra={
                        "usage_pct": round(usage * 100, 1),
                        "threshold_pct": round(self._compaction_threshold * 100, 1),
                        "max_tokens": self._max_tokens,
                    },
                ),
            )
        return should

    def get_messages_to_summarize(self) -> list[ConversationMessage]:
        """Get messages that should be summarized.

        Returns:
            List of older messages to summarize
        """
        if len(self._messages) <= self._recent_messages_to_keep:
            return []

        return self._messages[: -self._recent_messages_to_keep]

    def get_recent_messages(self) -> list[ConversationMessage]:
        """Get recent messages that should be preserved.

        Returns:
            List of recent messages
        """
        return self._messages[-self._recent_messages_to_keep :]

    async def compact(self, summarize_fn: Any | None = None) -> dict[str, Any]:
        """Compact the conversation by summarizing older messages.

        Args:
            summarize_fn: Optional async function to generate summary.
                If not provided, uses a simple concatenation.
                Function signature: async def fn(messages: list[dict]) -> str

        Returns:
            Dict with compaction results:
            - summarized_count: Number of messages summarized
            - tokens_before: Token count before compaction
            - tokens_after: Token count after compaction
            - tokens_saved: Tokens saved by compaction
        """
        messages_to_summarize = self.get_messages_to_summarize()

        if not messages_to_summarize:
            return {
                "summarized_count": 0,
                "tokens_before": self.total_tokens,
                "tokens_after": self.total_tokens,
                "tokens_saved": 0,
            }

        tokens_before = self.total_tokens

        # Generate summary
        if summarize_fn:
            messages_for_summary = [
                {"role": m.role, "content": m.content} for m in messages_to_summarize
            ]
            summary_text = await summarize_fn(messages_for_summary)
        else:
            summary_text = self._generate_simple_summary(messages_to_summarize)

        # Create new summary
        new_summary = ConversationSummary(
            content=summary_text,
            message_count=len(messages_to_summarize),
            start_timestamp=messages_to_summarize[0].timestamp,
            end_timestamp=messages_to_summarize[-1].timestamp,
        )

        # If there's an existing summary, combine them
        if self._summary:
            combined_content = (
                f"[EARLIER SUMMARY]\n{self._summary.content}\n\n"
                f"[RECENT SUMMARY]\n{new_summary.content}"
            )
            # Truncate if needed
            if len(combined_content) // CHARS_PER_TOKEN > SUMMARY_TOKEN_TARGET:
                combined_content = combined_content[
                    : SUMMARY_TOKEN_TARGET * CHARS_PER_TOKEN
                ]

            self._summary = ConversationSummary(
                content=combined_content,
                message_count=self._summary.message_count + new_summary.message_count,
                start_timestamp=self._summary.start_timestamp,
                end_timestamp=new_summary.end_timestamp,
            )
        else:
            self._summary = new_summary

        # Keep only recent messages
        self._messages = self.get_recent_messages()

        tokens_after = self.total_tokens
        tokens_saved = tokens_before - tokens_after

        logger.info(
            "Conversation compaction complete",
            extra=log_context(
                component="compaction",
                action="complete",
                message_count=len(messages_to_summarize),
                token_count=tokens_after,
                success=True,
                extra={
                    "tokens_before": tokens_before,
                    "tokens_after": tokens_after,
                    "tokens_saved": tokens_saved,
                    "reduction_pct": round((tokens_saved / tokens_before) * 100, 1)
                    if tokens_before > 0
                    else 0,
                    "messages_remaining": len(self._messages),
                },
            ),
        )

        return {
            "summarized_count": len(messages_to_summarize),
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_saved": tokens_saved,
        }

    def _generate_simple_summary(self, messages: list[ConversationMessage]) -> str:
        """Generate a simple summary by extracting key points.

        This is a fallback method when no LLM summarizer is available.

        Args:
            messages: Messages to summarize

        Returns:
            Simple summary text
        """
        lines = [f"Summary of {len(messages)} messages:"]

        # Group by role
        user_messages = [m for m in messages if m.role == "user"]
        assistant_messages = [m for m in messages if m.role == "assistant"]

        # Extract topics from user messages (first words of each)
        if user_messages:
            topics = []
            for msg in user_messages[:5]:  # First 5 user messages
                # Take first sentence or first 100 chars
                first_part = msg.content.split(".")[0][:100]
                topics.append(f"- {first_part}")
            lines.append("\nUser discussed:")
            lines.extend(topics)

        # Brief summary of assistant responses
        if assistant_messages:
            lines.append(
                f"\nAssistant provided {len(assistant_messages)} responses "
                f"covering the above topics."
            )

        return "\n".join(lines)

    def get_context_for_agent(self) -> str:
        """Get formatted context for agent including summary and recent messages.

        Returns:
            Formatted string with summary and recent conversation
        """
        parts = []

        if self._summary:
            parts.append("[CONVERSATION HISTORY SUMMARY]")
            parts.append(self._summary.content)
            parts.append(f"(Summarized {self._summary.message_count} earlier messages)")
            parts.append("[END SUMMARY]\n")

        if self._messages:
            parts.append("[RECENT CONVERSATION]")
            for msg in self._messages:
                parts.append(f"{msg.role.upper()}: {msg.content}")
            parts.append("[END RECENT CONVERSATION]")

        return "\n".join(parts)

    def load_from_state(self, state: dict[str, Any]) -> None:
        """Load conversation state from session state dict.

        Args:
            state: Session state dictionary containing conversation data
        """
        history = state.get("conversation_history", {})

        # Load summary
        summary_data = history.get("summary")
        if summary_data:
            self._summary = ConversationSummary(
                content=summary_data["content"],
                message_count=summary_data["message_count"],
                start_timestamp=datetime.fromisoformat(summary_data["start_timestamp"]),
                end_timestamp=datetime.fromisoformat(summary_data["end_timestamp"]),
            )

        # Load recent messages
        messages_data = history.get("recent_messages", [])
        self._messages = [
            ConversationMessage(
                role=m["role"],
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]),
            )
            for m in messages_data
        ]

        logger.info(
            "Loaded conversation state",
            extra=log_context(
                component="conversation",
                action="load_state",
                message_count=self.message_count,
                token_count=self.total_tokens,
                success=True,
                extra={
                    "has_summary": self._summary is not None,
                    "summarized_messages": self._summary.message_count
                    if self._summary
                    else 0,
                },
            ),
        )

    def save_to_state(self) -> dict[str, Any]:
        """Save conversation state to a dictionary for session storage.

        Returns:
            Dictionary with conversation state
        """
        state: dict[str, Any] = {"conversation_history": {}}

        if self._summary:
            state["conversation_history"]["summary"] = {
                "content": self._summary.content,
                "message_count": self._summary.message_count,
                "start_timestamp": self._summary.start_timestamp.isoformat(),
                "end_timestamp": self._summary.end_timestamp.isoformat(),
            }

        state["conversation_history"]["recent_messages"] = [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in self._messages
        ]

        return state

    def clear(self) -> None:
        """Clear all messages and summary."""
        old_count = len(self._messages)
        old_tokens = self.total_tokens
        self._messages.clear()
        self._summary = None
        logger.info(
            "Cleared conversation history",
            extra=log_context(
                component="conversation",
                action="clear",
                message_count=old_count,
                token_count=old_tokens,
            ),
        )


def estimate_message_tokens(content: str) -> int:
    """Estimate token count for a message.

    Args:
        content: Message content

    Returns:
        Estimated token count
    """
    return len(content) // CHARS_PER_TOKEN


def check_token_budget(
    messages: list[dict[str, str]],
    max_tokens: int = MAX_CONVERSATION_TOKENS,
) -> dict[str, Any]:
    """Check if messages are within token budget.

    Args:
        messages: List of message dicts with 'role' and 'content'
        max_tokens: Maximum token budget

    Returns:
        Dict with budget analysis:
        - total_tokens: Estimated total tokens
        - within_budget: Whether within budget
        - usage_percentage: Percentage of budget used
        - should_compact: Whether compaction is recommended
    """
    total_tokens = sum(estimate_message_tokens(m.get("content", "")) for m in messages)

    usage = total_tokens / max_tokens

    return {
        "total_tokens": total_tokens,
        "max_tokens": max_tokens,
        "within_budget": total_tokens <= max_tokens,
        "usage_percentage": usage * 100,
        "should_compact": usage >= COMPACTION_THRESHOLD,
    }
