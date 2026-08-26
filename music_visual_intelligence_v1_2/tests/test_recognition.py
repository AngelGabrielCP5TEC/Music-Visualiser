from music_visual_intelligence.identity import IdentityCache
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


def test_identity_cache_round_trip(tmp_path):
    cache = IdentityCache(tmp_path)
    identity = SongIdentity(matched=True, confidence=0.8, title="Song")

    cache.put("fp123", identity)
    loaded = cache.get("fp123")

    assert loaded is not None
    assert loaded.title == "Song"
    assert loaded.confidence == 0.8


def test_identity_cache_tolerates_unknown_fields(tmp_path):
    """Extra/future fields in a stored identity JSON must not break loading."""
    cache = IdentityCache(tmp_path)
    identity = SongIdentity(matched=True, confidence=0.5)
    cache.put("fp456", identity)

    path = cache.path_for("fp456")
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    data["field_added_in_a_future_version"] = "ignore me"
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = cache.get("fp456")
    assert loaded is not None
    assert loaded.confidence == 0.5
