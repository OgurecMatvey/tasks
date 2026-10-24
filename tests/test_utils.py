"""Чистые функции: БД не нужна."""

from app.utils import escape_like


def test_escape_like_neutralizes_wildcards():
    assert escape_like("100%") == "100\\%"
    assert escape_like("a_b") == "a\\_b"
    assert escape_like("back\\slash") == "back\\\\slash"
    assert escape_like("plain text") == "plain text"
    assert escape_like("") == ""
