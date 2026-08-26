from music_visual_intelligence.designs import DesignStore
from music_visual_intelligence.models import AutomaticDesign


def test_personal_design_round_trip(tmp_path):
    store = DesignStore(tmp_path)
    auto = AutomaticDesign(
        component_colors={"bass": [1, 2, 3]},
        multipliers={"bass": 1.2},
    )

    design = store.create_personal("Test Design", "abc", auto)
    store.save_personal(design)

    found = store.list_personal("abc")

    assert len(found) == 1
    assert found[0]["name"] == "Test Design"
    assert found[0]["base_analysis_fingerprint"] == "abc"


def test_save_personal_leaves_no_temp_files_behind(tmp_path):
    """Atomic writes should not leave .tmp artifacts after a successful save."""
    store = DesignStore(tmp_path)
    design = store.create_personal("Another Design", "xyz")
    store.save_personal(design)

    leftovers = list(store.personal_dir.glob("*.tmp"))
    assert leftovers == []

    saved = list(store.personal_dir.glob("*.json"))
    assert len(saved) == 1
