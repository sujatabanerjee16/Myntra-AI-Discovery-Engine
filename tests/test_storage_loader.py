"""Tests for JSON corpus loader (mocked session)."""

from unittest.mock import MagicMock, patch

from storage.loader import load_corpus_json


@patch("storage.loader.refresh_analytical_aggregates", return_value={"signal_aggregates": 4})
@patch("storage.loader.document_exists", return_value=False)
@patch("storage.loader.create_chunk")
@patch("storage.loader.create_document")
def test_load_corpus_json_creates_docs_and_chunks(
    mock_create_doc,
    mock_create_chunk,
    _mock_exists,
    mock_refresh,
):
    session = MagicMock()
    mock_create_doc.return_value = MagicMock(id="00000000-0000-0000-0000-000000000001")

    payload = {
        "run_version": "test-run",
        "documents": [
            {
                "source": "research",
                "source_ref": "research:row:0",
                "text": "Wishlist price hesitation about fit and sale waiting behavior.",
                "matched_signals": ["wishlist_usage", "price_sensitivity_waiting"],
                "chunks": [
                    {
                        "chunk_index": 0,
                        "text": "Wishlist price hesitation",
                        "matched_signals": ["wishlist_usage"],
                        "segment": "price_sensitive",
                        "quality_score": 0.8,
                    }
                ],
            }
        ],
    }

    with patch("storage.loader.Path.read_text", return_value=__import__("json").dumps(payload)):
        with patch("storage.loader.Path.exists", return_value=True):
            result = load_corpus_json(session, "fake.json")

    assert result.documents_created == 1
    assert result.chunks_created == 1
    mock_create_doc.assert_called_once()
    mock_create_chunk.assert_called_once()
    mock_refresh.assert_called_once()
    session.commit.assert_called_once()
