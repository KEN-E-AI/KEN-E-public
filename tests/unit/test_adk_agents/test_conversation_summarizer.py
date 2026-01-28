"""Tests for ConversationSummarizer functionality."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add the utils path to import the module directly without triggering __init__.py imports
utils_path = (
    Path(__file__).parent.parent.parent.parent / "app" / "adk" / "agents" / "utils"
)
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

# Import directly from the module file (path manipulation required)
from conversation_summarizer import (  # noqa: E402
    CHARS_PER_TOKEN,
    COMPACTION_THRESHOLD,
    ConversationMessage,
    ConversationSummarizer,
    ConversationSummary,
    check_token_budget,
    estimate_message_tokens,
)


class TestConversationMessage:
    """Tests for ConversationMessage dataclass."""

    def test_create_message(self):
        msg = ConversationMessage(role="user", content="Hello, world!")
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert msg.token_count > 0

    def test_token_count_calculated(self):
        content = "a" * 100  # 100 characters
        msg = ConversationMessage(role="user", content=content)
        expected_tokens = 100 // CHARS_PER_TOKEN
        assert msg.token_count == expected_tokens

    def test_custom_timestamp(self):
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        msg = ConversationMessage(
            role="assistant", content="Hi!", timestamp=custom_time
        )
        assert msg.timestamp == custom_time


class TestConversationSummary:
    """Tests for ConversationSummary dataclass."""

    def test_create_summary(self):
        now = datetime.now()
        summary = ConversationSummary(
            content="Summary of discussion",
            message_count=5,
            start_timestamp=now - timedelta(hours=1),
            end_timestamp=now,
        )
        assert summary.message_count == 5
        assert summary.token_count > 0


class TestConversationSummarizer:
    """Tests for ConversationSummarizer class."""

    @pytest.fixture
    def summarizer(self) -> ConversationSummarizer:
        return ConversationSummarizer(
            max_tokens=1000,
            compaction_threshold=0.8,
            recent_messages_to_keep=3,
        )

    def test_init_empty(self, summarizer: ConversationSummarizer):
        assert summarizer.message_count == 0
        assert summarizer.total_tokens == 0
        assert summarizer.summary is None

    def test_add_message(self, summarizer: ConversationSummarizer):
        msg = summarizer.add_message("user", "Hello!")
        assert summarizer.message_count == 1
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_add_multiple_messages(self, summarizer: ConversationSummarizer):
        summarizer.add_message("user", "Hello!")
        summarizer.add_message("assistant", "Hi there!")
        summarizer.add_message("user", "How are you?")

        assert summarizer.message_count == 3

    def test_token_budget_usage(self, summarizer: ConversationSummarizer):
        # Add message with known size
        content = "a" * 400  # 100 tokens
        summarizer.add_message("user", content)

        # 100 tokens / 1000 max = 0.1 (10%)
        assert 0.09 <= summarizer.token_budget_usage <= 0.11

    def test_should_compact_below_threshold(self, summarizer: ConversationSummarizer):
        # Small message - should not trigger compaction
        summarizer.add_message("user", "Hi")
        assert not summarizer.should_compact()

    def test_should_compact_above_threshold(self, summarizer: ConversationSummarizer):
        # Large message - should trigger compaction
        # Need 800 tokens to hit 80% of 1000
        large_content = "a" * (800 * CHARS_PER_TOKEN)
        summarizer.add_message("user", large_content)
        assert summarizer.should_compact()

    def test_get_messages_to_summarize(self, summarizer: ConversationSummarizer):
        # Add 5 messages
        for i in range(5):
            summarizer.add_message("user", f"Message {i}")

        # Should summarize first 2, keep last 3
        to_summarize = summarizer.get_messages_to_summarize()
        assert len(to_summarize) == 2
        assert to_summarize[0].content == "Message 0"
        assert to_summarize[1].content == "Message 1"

    def test_get_recent_messages(self, summarizer: ConversationSummarizer):
        for i in range(5):
            summarizer.add_message("user", f"Message {i}")

        recent = summarizer.get_recent_messages()
        assert len(recent) == 3
        assert recent[0].content == "Message 2"
        assert recent[1].content == "Message 3"
        assert recent[2].content == "Message 4"

    def test_get_messages_to_summarize_not_enough_messages(
        self, summarizer: ConversationSummarizer
    ):
        # Only 2 messages, need 3 recent - nothing to summarize
        summarizer.add_message("user", "Message 1")
        summarizer.add_message("assistant", "Message 2")

        to_summarize = summarizer.get_messages_to_summarize()
        assert len(to_summarize) == 0

    @pytest.mark.asyncio
    async def test_compact_with_custom_summarizer(
        self, summarizer: ConversationSummarizer
    ):
        # Add messages
        for i in range(5):
            summarizer.add_message("user", f"Message {i}")

        async def mock_summarizer(messages: list) -> str:
            return f"Summary of {len(messages)} messages"

        result = await summarizer.compact(summarize_fn=mock_summarizer)

        assert result["summarized_count"] == 2
        assert summarizer.message_count == 3  # Recent messages kept
        assert summarizer.summary is not None
        assert "Summary of 2 messages" in summarizer.summary.content

    @pytest.mark.asyncio
    async def test_compact_with_default_summarizer(
        self, summarizer: ConversationSummarizer
    ):
        for i in range(5):
            summarizer.add_message("user", f"Message {i}")

        result = await summarizer.compact()

        assert result["summarized_count"] == 2
        assert summarizer.summary is not None

    @pytest.mark.asyncio
    async def test_compact_no_messages_to_summarize(
        self, summarizer: ConversationSummarizer
    ):
        summarizer.add_message("user", "Only message")

        result = await summarizer.compact()

        assert result["summarized_count"] == 0
        assert result["tokens_saved"] == 0

    @pytest.mark.asyncio
    async def test_multiple_compactions(self, summarizer: ConversationSummarizer):
        # First batch
        for i in range(5):
            summarizer.add_message("user", f"Batch1 Message {i}")

        await summarizer.compact()
        first_summary = summarizer.summary
        assert first_summary is not None

        # Second batch
        for i in range(5):
            summarizer.add_message("user", f"Batch2 Message {i}")

        await summarizer.compact()

        # Summary should combine both
        assert summarizer.summary is not None
        assert summarizer.summary.message_count > first_summary.message_count

    def test_get_context_for_agent_no_summary(self, summarizer: ConversationSummarizer):
        summarizer.add_message("user", "Hello")
        summarizer.add_message("assistant", "Hi there")

        context = summarizer.get_context_for_agent()

        assert "[RECENT CONVERSATION]" in context
        assert "USER: Hello" in context
        assert "ASSISTANT: Hi there" in context

    @pytest.mark.asyncio
    async def test_get_context_for_agent_with_summary(
        self, summarizer: ConversationSummarizer
    ):
        for i in range(5):
            summarizer.add_message("user", f"Message {i}")

        await summarizer.compact()

        context = summarizer.get_context_for_agent()

        assert "[CONVERSATION HISTORY SUMMARY]" in context
        assert "[RECENT CONVERSATION]" in context

    def test_save_and_load_state(self, summarizer: ConversationSummarizer):
        summarizer.add_message("user", "Hello")
        summarizer.add_message("assistant", "Hi there")

        state = summarizer.save_to_state()

        new_summarizer = ConversationSummarizer()
        new_summarizer.load_from_state(state)

        assert new_summarizer.message_count == 2
        assert new_summarizer.messages[0].content == "Hello"
        assert new_summarizer.messages[1].content == "Hi there"

    @pytest.mark.asyncio
    async def test_save_and_load_state_with_summary(
        self, summarizer: ConversationSummarizer
    ):
        for i in range(5):
            summarizer.add_message("user", f"Message {i}")

        await summarizer.compact()
        state = summarizer.save_to_state()

        new_summarizer = ConversationSummarizer()
        new_summarizer.load_from_state(state)

        assert new_summarizer.summary is not None
        assert new_summarizer.message_count == 3

    def test_clear(self, summarizer: ConversationSummarizer):
        summarizer.add_message("user", "Hello")
        summarizer.add_message("assistant", "Hi")

        summarizer.clear()

        assert summarizer.message_count == 0
        assert summarizer.summary is None


class TestUtilityFunctions:
    """Tests for module-level utility functions."""

    def test_estimate_message_tokens(self):
        content = "a" * 100
        tokens = estimate_message_tokens(content)
        assert tokens == 100 // CHARS_PER_TOKEN

    def test_estimate_message_tokens_empty(self):
        tokens = estimate_message_tokens("")
        assert tokens == 0

    def test_check_token_budget_within(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = check_token_budget(messages, max_tokens=1000)

        assert result["within_budget"] is True
        assert result["should_compact"] is False
        assert result["usage_percentage"] < 80

    def test_check_token_budget_exceeds(self):
        messages = [
            {"role": "user", "content": "a" * 5000},  # Large message
        ]

        result = check_token_budget(messages, max_tokens=100)

        assert result["within_budget"] is False
        assert result["should_compact"] is True

    def test_check_token_budget_at_threshold(self):
        # Create message that hits exactly 80%
        target_chars = int(1000 * COMPACTION_THRESHOLD * CHARS_PER_TOKEN)
        messages = [{"role": "user", "content": "a" * target_chars}]

        result = check_token_budget(messages, max_tokens=1000)

        assert result["should_compact"] is True
