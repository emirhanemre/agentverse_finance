from pubhedge_svc import grounding


def test_numbers_must_come_from_tools():
    outs = [{"shortfall_gbp": 3477.12, "payroll_date": "2026-09-04", "model_prob": 0.2412, "gbp_per_mm": 115.88}]
    r = grounding.check("Payroll on 4 Sep is £3,477 short. Rain costs £116 per mm. The market is at 24%. "
                        "Takings will fall by £9,999.", outs)
    assert r["ungrounded"] == ["£9,999."[:-1]] or r["ungrounded"] == ["£9,999"]
    assert "9,999" not in r["text"] and "£3,477" in r["text"]
    assert not r["ok"]


def test_clean_narration_passes():
    r = grounding.check("Nothing is worth buying at 0.05.", [{"ask": 0.05}])
    assert r["ok"] and r["numbers"][0]["grounded"]
