from music_visual_intelligence.recognition import (
    SongIdentity,
    choose_best_acoustid,
    cover_url_for_release,
)


def test_choose_best_acoustid():
    best = choose_best_acoustid([
        {"id": "a", "score": 0.4},
        {"id": "b", "score": 0.9},
    ])
    assert best["id"] == "b"


def test_identity_serialization():
    identity = SongIdentity(
        matched=True,
        confidence=0.95,
        title="Test",
        artist="Artist",
    )
    assert identity.to_dict()["title"] == "Test"


def test_cover_url():
    assert cover_url_for_release("abc", 500).endswith(
        "/release/abc/front-500"
    )
