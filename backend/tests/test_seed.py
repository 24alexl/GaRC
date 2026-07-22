from app.db.seed_nist_800_171 import NIST_CONTROLS_DATA, seed_database

def test_nist_seed_data():
    assert len(NIST_CONTROLS_DATA) >= 8
    first_ctrl = NIST_CONTROLS_DATA[0]
    assert "id" in first_ctrl
    assert "family" in first_ctrl
    assert "small_biz_guidance" in first_ctrl

def test_seed_database_mock():
    res = seed_database()
    assert res["status"] in ["seeded", "mock_seeded"]
    assert res["count"] >= 8
