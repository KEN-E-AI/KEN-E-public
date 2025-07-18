"""Test account ID generation functions."""

import re
import uuid
from datetime import datetime

import pytest

from src.kene_api.routers.accounts import (
    generate_unique_account_id,
    generate_timestamp_account_id,
)


def test_generate_unique_account_id():
    """Test UUID-based account ID generation."""
    # Generate multiple IDs
    id1 = generate_unique_account_id()
    id2 = generate_unique_account_id()
    id3 = generate_unique_account_id()

    # Should all be different
    assert id1 != id2
    assert id2 != id3
    assert id1 != id3

    # Should all start with 'acc_'
    assert id1.startswith("acc_")
    assert id2.startswith("acc_")
    assert id3.startswith("acc_")

    # Should be correct length (4 chars for 'acc_' + 32 chars for UUID without hyphens)
    assert len(id1) == 36
    assert len(id2) == 36
    assert len(id3) == 36

    # Should match UUID pattern (hex characters only after 'acc_')
    uuid_pattern = re.compile(r"^acc_[0-9a-f]{32}$")
    assert uuid_pattern.match(id1)
    assert uuid_pattern.match(id2)
    assert uuid_pattern.match(id3)


def test_generate_timestamp_account_id():
    """Test timestamp-based account ID generation."""
    # Generate multiple IDs
    id1 = generate_timestamp_account_id()
    id2 = generate_timestamp_account_id()
    id3 = generate_timestamp_account_id()

    # Should all be different
    assert id1 != id2
    assert id2 != id3
    assert id1 != id3

    # Should all start with 'acc_'
    assert id1.startswith("acc_")
    assert id2.startswith("acc_")
    assert id3.startswith("acc_")

    # Should match timestamp pattern: acc_<timestamp>_<8-char-uuid>
    timestamp_pattern = re.compile(r"^acc_\d{13}_[0-9a-f]{8}$")
    assert timestamp_pattern.match(id1)
    assert timestamp_pattern.match(id2)
    assert timestamp_pattern.match(id3)

    # Extract timestamp and verify it's reasonable (within last few seconds)
    timestamp1 = int(id1.split("_")[1])
    timestamp2 = int(id2.split("_")[1])
    timestamp3 = int(id3.split("_")[1])

    current_timestamp = int(datetime.now().timestamp() * 1000)

    # Timestamps should be recent (within 5 seconds)
    assert abs(current_timestamp - timestamp1) < 5000
    assert abs(current_timestamp - timestamp2) < 5000
    assert abs(current_timestamp - timestamp3) < 5000


def test_account_id_uniqueness():
    """Test that both generation methods produce unique IDs."""
    # Generate 100 IDs of each type
    uuid_ids = [generate_unique_account_id() for _ in range(100)]
    timestamp_ids = [generate_timestamp_account_id() for _ in range(100)]

    # Check uniqueness within each type
    assert len(set(uuid_ids)) == 100
    assert len(set(timestamp_ids)) == 100

    # Check uniqueness across types
    all_ids = uuid_ids + timestamp_ids
    assert len(set(all_ids)) == 200


def test_account_id_format_consistency():
    """Test that account IDs follow consistent format."""
    uuid_id = generate_unique_account_id()
    timestamp_id = generate_timestamp_account_id()

    # Both should start with 'acc_'
    assert uuid_id.startswith("acc_")
    assert timestamp_id.startswith("acc_")

    # Both should contain only valid characters (including 'acc_' prefix)
    valid_chars = set("0123456789abcdef_acc")
    assert set(uuid_id) <= valid_chars
    assert set(timestamp_id) <= valid_chars

    # Both should be reasonable lengths
    assert 30 <= len(uuid_id) <= 50  # UUID: 'acc_' + 32 chars = 36 chars
    assert (
        20 <= len(timestamp_id) <= 35
    )  # Timestamp: 'acc_' + 13 digits + '_' + 8 chars = 26 chars


def test_uuid_generation_performance():
    """Test that UUID generation is reasonably fast."""
    import time

    start_time = time.time()

    # Generate 1000 UUIDs
    for _ in range(1000):
        generate_unique_account_id()

    end_time = time.time()

    # Should complete in less than 1 second
    assert end_time - start_time < 1.0


def test_timestamp_generation_performance():
    """Test that timestamp generation is reasonably fast."""
    import time

    start_time = time.time()

    # Generate 1000 timestamp IDs
    for _ in range(1000):
        generate_timestamp_account_id()

    end_time = time.time()

    # Should complete in less than 1 second
    assert end_time - start_time < 1.0


def test_account_id_vs_organization_id_format():
    """Test that account IDs use different prefix than organization IDs."""
    account_id = generate_unique_account_id()

    # Account ID should start with 'acc_', not 'org_'
    assert account_id.startswith("acc_")
    assert not account_id.startswith("org_")

    # Should follow the same UUID4 format but with different prefix
    uuid_pattern = re.compile(r"^acc_[0-9a-f]{32}$")
    assert uuid_pattern.match(account_id)


def test_account_id_collision_resistance():
    """Test collision resistance by generating many IDs."""
    # Generate a large number of IDs to test collision resistance
    num_ids = 10000
    ids = [generate_unique_account_id() for _ in range(num_ids)]

    # All IDs should be unique
    assert len(set(ids)) == num_ids

    # All should follow correct format
    uuid_pattern = re.compile(r"^acc_[0-9a-f]{32}$")
    assert all(uuid_pattern.match(id_val) for id_val in ids)


def test_mixed_generation_methods_uniqueness():
    """Test that mixing UUID and timestamp methods produces unique IDs."""
    # Generate mix of UUID and timestamp IDs
    uuid_ids = [generate_unique_account_id() for _ in range(50)]
    timestamp_ids = [generate_timestamp_account_id() for _ in range(50)]

    # Combine all IDs
    all_ids = uuid_ids + timestamp_ids

    # All should be unique (extremely unlikely to have collisions)
    assert len(set(all_ids)) == 100

    # All should start with 'acc_'
    assert all(id_val.startswith("acc_") for id_val in all_ids)
