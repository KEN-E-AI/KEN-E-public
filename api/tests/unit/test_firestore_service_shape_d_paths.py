"""Service-layer unit tests confirming Shape B (accounts/{account_id}) call paths.

Every test drives a real FirestoreService method body with a MagicMock _db and
asserts on the exact Firestore call chain and field-path strings. A regression
that left Shape D paths (organizations/{org_id}.accounts.{account_id}.*) in place
would cause these assertions to fail — CI would then catch it before any endpoint
breaks at runtime.
"""

from unittest.mock import MagicMock

from google.cloud.exceptions import NotFound
from src.kene_api.firestore import FirestoreService


def _make_service() -> tuple[FirestoreService, MagicMock]:
    service = FirestoreService()
    service._initialized = True
    mock_db = MagicMock()
    service._db = mock_db
    return service, mock_db


def _snap(exists: bool, data: dict) -> MagicMock:
    snap = MagicMock()
    snap.exists = exists
    snap.to_dict.return_value = data
    return snap


class TestFirestoreServiceShapeDPaths:
    def test_get_kpi_setting_uses_accounts_collection(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {"account_settings": {"overview_kpis": {"income_kpi": "m_abc"}}},
        )

        result = service.get_kpi_setting("acc_123", "income_kpi")

        mock_db.collection.assert_called_once_with("accounts")
        mock_db.collection.return_value.document.assert_called_once_with("acc_123")
        assert result == "m_abc"

    def test_update_kpi_setting_happy_path(self):
        service, mock_db = _make_service()
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.update_kpi_setting("acc_123", "income_kpi", "m_abc")

        assert result is True
        mock_doc_ref.update.assert_called_once_with(
            {"account_settings.overview_kpis.income_kpi": "m_abc"}
        )
        all_calls_str = str(mock_doc_ref.update.call_args_list)
        assert "accounts.acc_123" not in all_calls_str
        mock_db.collection.assert_called_once_with("accounts")

    def test_update_kpi_setting_not_found_creates_with_correct_shape(self):
        service, mock_db = _make_service()
        mock_doc_ref = mock_db.collection.return_value.document.return_value
        mock_doc_ref.update.side_effect = NotFound("not found")

        result = service.update_kpi_setting("acc_123", "income_kpi", "m_abc")

        assert result is True
        mock_doc_ref.set.assert_called_once_with(
            {"account_settings": {"overview_kpis": {"income_kpi": "m_abc"}}},
            merge=True,
        )
        set_call_str = str(mock_doc_ref.set.call_args_list)
        assert "accounts.acc_123" not in set_call_str

    def test_create_funnel_step_organization_uses_accounts_collection(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True, {}
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.create_funnel_step(
            "acc_123", "organization", None, 1, {"name": "Awareness"}
        )

        assert result is True
        mock_db.collection.assert_called_once_with("accounts")
        mock_db.collection.return_value.document.assert_called_once_with("acc_123")
        mock_doc_ref.get.assert_called_once()
        mock_doc_ref.set.assert_called_once()
        set_args, set_kwargs = mock_doc_ref.set.call_args
        assert set_kwargs.get("merge") is True
        payload = set_args[0]
        assert payload == {"funnels": {"organization": {"1": {"name": "Awareness"}}}}

    def test_create_funnel_step_big_bet_uses_accounts_collection(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True, {}
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.create_funnel_step(
            "acc_123", "big_bet", "bet_alpha", 1, {"name": "Awareness"}
        )

        assert result is True
        mock_doc_ref.get.assert_called_once()
        set_args, set_kwargs = mock_doc_ref.set.call_args
        assert set_kwargs.get("merge") is True
        payload = set_args[0]
        assert payload == {
            "funnels": {"big_bets": {"bet_alpha": {"1": {"name": "Awareness"}}}}
        }

    def test_update_funnel_step_organization_field_path(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {"funnels": {"organization": {"1": {"name": "Awareness"}}}},
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.update_funnel_step(
            "acc_123", "organization", None, 1, {"name": "Updated"}
        )

        assert result is True
        mock_doc_ref.update.assert_called_once_with(
            {"funnels.organization.1": {"name": "Updated"}}
        )
        all_calls_str = str(mock_doc_ref.update.call_args_list)
        assert "accounts.acc_123" not in all_calls_str

    def test_update_funnel_step_big_bet_field_path(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {"funnels": {"big_bets": {"bet_alpha": {"2": {"name": "Consideration"}}}}},
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.update_funnel_step(
            "acc_123", "big_bet", "bet_alpha", 2, {"name": "Updated"}
        )

        assert result is True
        mock_doc_ref.update.assert_called_once_with(
            {"funnels.big_bets.bet_alpha.2": {"name": "Updated"}}
        )

    def test_delete_funnel_step_organization_shifts_and_writes_back(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {
                "funnels": {
                    "organization": {
                        "1": {"name": "Awareness"},
                        "2": {"name": "Consideration"},
                    }
                }
            },
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.delete_funnel_step("acc_123", "organization", None, 1)

        assert result is True
        mock_doc_ref.set.assert_called_once()
        set_args, set_kwargs = mock_doc_ref.set.call_args
        assert set_kwargs.get("merge") is True
        remaining = set_args[0]["funnels"]["organization"]
        assert "1" in remaining
        assert remaining["1"] == {"name": "Consideration"}
        assert "2" not in remaining

    def test_delete_funnel_step_big_bet_shifts_and_writes_back(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {
                "funnels": {
                    "big_bets": {
                        "bet_alpha": {
                            "1": {"name": "Awareness"},
                            "2": {"name": "Consideration"},
                        }
                    }
                }
            },
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.delete_funnel_step("acc_123", "big_bet", "bet_alpha", 1)

        assert result is True
        set_args, set_kwargs = mock_doc_ref.set.call_args
        assert set_kwargs.get("merge") is True
        remaining = set_args[0]["funnels"]["big_bets"]["bet_alpha"]
        assert "1" in remaining
        assert remaining["1"] == {"name": "Consideration"}
        assert "2" not in remaining

    def test_update_channel_organization_field_path(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {
                "funnels": {
                    "organization": {
                        "1": {"channels": {"paid_search": {"budget": 1000}}}
                    }
                }
            },
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.update_channel(
            "acc_123", "organization", None, 1, "paid_search", {"cpc": 2.5}
        )

        assert result == {"budget": 1000, "cpc": 2.5}
        mock_doc_ref.update.assert_called_once_with(
            {"funnels.organization.1.channels.paid_search": {"budget": 1000, "cpc": 2.5}}
        )
        all_calls_str = str(mock_doc_ref.update.call_args_list)
        assert "accounts.acc_123" not in all_calls_str

    def test_update_channel_big_bet_field_path(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {
                "funnels": {
                    "big_bets": {
                        "bet_alpha": {
                            "1": {"channels": {"paid_search": {"budget": 1000}}}
                        }
                    }
                }
            },
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.update_channel(
            "acc_123", "big_bet", "bet_alpha", 1, "paid_search", {"cpc": 2.5}
        )

        assert result == {"budget": 1000, "cpc": 2.5}
        mock_doc_ref.update.assert_called_once_with(
            {
                "funnels.big_bets.bet_alpha.1.channels.paid_search": {
                    "budget": 1000,
                    "cpc": 2.5,
                }
            }
        )

    def test_update_tactic_organization_field_path(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {
                "funnels": {
                    "organization": {
                        "1": {
                            "channels": {
                                "paid_search": {
                                    "tactics": {"retargeting": {"spend": 500}}
                                }
                            }
                        }
                    }
                }
            },
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.update_tactic(
            "acc_123",
            "organization",
            None,
            1,
            "paid_search",
            "retargeting",
            {"cpm": 10},
        )

        assert result == {"spend": 500, "cpm": 10}
        mock_doc_ref.update.assert_called_once_with(
            {
                "funnels.organization.1.channels.paid_search.tactics.retargeting": {
                    "spend": 500,
                    "cpm": 10,
                }
            }
        )
        all_calls_str = str(mock_doc_ref.update.call_args_list)
        assert "accounts.acc_123" not in all_calls_str

    def test_update_tactic_big_bet_field_path(self):
        service, mock_db = _make_service()
        mock_db.collection.return_value.document.return_value.get.return_value = _snap(
            True,
            {
                "funnels": {
                    "big_bets": {
                        "bet_alpha": {
                            "1": {
                                "channels": {
                                    "paid_search": {
                                        "tactics": {"retargeting": {"spend": 500}}
                                    }
                                }
                            }
                        }
                    }
                }
            },
        )
        mock_doc_ref = mock_db.collection.return_value.document.return_value

        result = service.update_tactic(
            "acc_123",
            "big_bet",
            "bet_alpha",
            1,
            "paid_search",
            "retargeting",
            {"cpm": 10},
        )

        assert result == {"spend": 500, "cpm": 10}
        mock_doc_ref.update.assert_called_once_with(
            {
                "funnels.big_bets.bet_alpha.1.channels.paid_search.tactics.retargeting": {
                    "spend": 500,
                    "cpm": 10,
                }
            }
        )
