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
