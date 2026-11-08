import sqlite3

import pytest

from pubhedge_svc import audit


def test_chain_verifies_and_is_append_only():
    audit.append("r1", "s", "c", {"a": 1}, {"b": 2}, "REAL")
    audit.append("r1", "s", "c2", {"a": 2}, {"b": 3}, "SYNTHETIC")
    assert audit.verify()["ok"]
    with pytest.raises(sqlite3.DatabaseError):
        audit.db().execute("UPDATE audit SET result='{}' WHERE seq=1")
    with pytest.raises(sqlite3.DatabaseError):
        audit.db().execute("DELETE FROM audit")


def test_tamper_is_detected():
    con = audit.db()
    audit.append("r2", "s", "c", {}, {"x": 1}, "REAL")
    con.execute("DROP TRIGGER audit_no_update")  # simulate someone with raw DB access
    con.execute("UPDATE audit SET result='{\"x\": 999}' WHERE seq = (SELECT MAX(seq) FROM audit)")
    v = audit.verify()
    assert not v["ok"] and v["broken_at_seq"]
    con.executescript(audit.SCHEMA)
