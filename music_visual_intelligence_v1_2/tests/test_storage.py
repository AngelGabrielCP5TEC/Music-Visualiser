from pathlib import Path

from music_visual_intelligence.models import (
    AudioProperties,
    SongAnalysis,
)
from music_visual_intelligence.storage import AnalysisCache


def make_analysis() -> SongAnalysis:
    return SongAnalysis(
        schema_version="1.1",
        analysis_version="canonical-v1",
        salience_model_version="salience-v1",
        source_fingerprint="abc",
        audio=AudioProperties(
            sample_rate=44_100,
            channels=1,
            duration_seconds=1.0,
            samples=44_100,
            source_path="test.wav",
        ),
        global_features={},
        timeline=[],
        beats=[],
        events=[],
        segments=[],
        automatic_design=None,
        performance={},
        created_at_utc="now",
    )


def test_cache_round_trip(tmp_path: Path):
    cache = AnalysisCache(tmp_path)
    original = make_analysis()
    cache.put(original)

    loaded = cache.get("abc", "canonical-v1")

    assert loaded is not None
    assert loaded.source_fingerprint == "abc"
    assert loaded.analysis_version == "canonical-v1"


def test_cache_survives_unknown_future_fields(tmp_path: Path):
    """A JSON payload from a newer schema (extra fields) should still load."""
    cache = AnalysisCache(tmp_path)
    original = make_analysis()
    path = cache.put(original)

    payload = path.read_text(encoding="utf-8")
    import json
    data = json.loads(payload)
    data["audio"]["a_field_from_the_future"] = "should be ignored"
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = cache.get("abc", "canonical-v1")
    assert loaded is not None
    assert loaded.audio.sample_rate == 44_100
