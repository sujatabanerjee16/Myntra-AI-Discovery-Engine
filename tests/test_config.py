"""Tests for settings and derived database URL."""

from common.config import Settings


def test_sqlalchemy_url_from_parts():
    s = Settings(
        database_url=None,
        postgres_user="u",
        postgres_password="p",
        postgres_host="h",
        postgres_port=1234,
        postgres_db="d",
    )
    assert s.sqlalchemy_url == "postgresql+psycopg://u:p@h:1234/d"


def test_sqlalchemy_url_explicit_override():
    url = "postgresql+psycopg://a:b@c:5555/e"
    s = Settings(database_url=url)
    assert s.sqlalchemy_url == url


def test_default_embedding_dim_matches_bge_large():
    assert Settings().embedding_dim == 1024
