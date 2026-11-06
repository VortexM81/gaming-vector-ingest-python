from src.ingest_service import chunk_text


def test_moderation_notes_split_at_paragraph_boundary():
    text = "Player asset flagged by the queue.\n\nLive event reward needs review."
    assert chunk_text(text, limit=40) == [
        "Player asset flagged by the queue.",
        "Live event reward needs review.",
    ]
