"""JSON/demo backend must not block the dashboard on a Postgres probe."""

from unittest.mock import patch

from api.backend import use_json_backend


def test_json_fallback_skips_database_probe():
    def boom() -> bool:
        raise AssertionError("database_available should not be called")

    with (
        patch("api.backend.json_data_available", return_value=False),
        patch("api.backend.database_available", side_effect=boom),
        patch("api.backend.get_settings", return_value=type("S", (), {"use_json_fallback": True})()),
    ):
        assert use_json_backend() is True


def test_missing_json_without_fallback_probes_database():
    with (
        patch("api.backend.json_data_available", return_value=False),
        patch("api.backend.database_available", return_value=True),
        patch("api.backend.get_settings", return_value=type("S", (), {"use_json_fallback": False})()),
    ):
        assert use_json_backend() is False
