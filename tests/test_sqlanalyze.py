from core.sqlanalyze import analyze, AnalysisResult, AnalysisWarning


def test_select_with_join_reads_both_tables():
    r = analyze("SELECT v.Name, n.VLAN FROM VirtualMachine v "
                "JOIN Network n ON v.NetworkID = n.NetworkID")
    assert r.statement_type == "SELECT"
    assert r.tables_read == ("Network", "VirtualMachine")  # sorted, dedup
    assert r.tables_written == ()
    assert r.parse_error is None


def test_update_target_is_written():
    r = analyze("UPDATE Host SET Hostname = 'x' WHERE HostID = 1")
    assert r.statement_type == "UPDATE"
    assert r.tables_written == ("Host",)
    assert r.tables_read == ()


def test_insert_select_splits_read_and_written():
    r = analyze("INSERT INTO Audit (id) SELECT VMID FROM VirtualMachine")
    assert r.statement_type == "INSERT"
    assert r.tables_written == ("Audit",)
    assert r.tables_read == ("VirtualMachine",)


def test_ddl_create_is_ddl_type():
    r = analyze("CREATE TABLE T (id INT)")
    assert r.statement_type == "DDL"
    assert r.tables_written == ("T",)


def test_unparseable_sets_parse_error_no_exception():
    r = analyze("NOT SQL @@@ ;;;")
    assert r.parse_error is not None
    assert r.statement_type == "OTHER"
    assert r.tables_read == () and r.tables_written == ()


def test_determinism_sorted_dedup():
    a = analyze("SELECT * FROM A, B, A")
    assert a.tables_read == ("A", "B")


def _codes(r):
    return {w.code for w in r.warnings}


def test_write_statement_warns_danger():
    r = analyze("DELETE FROM Host WHERE HostID = 1")
    assert "WRITE_STATEMENT" in _codes(r)
    assert any(w.code == "WRITE_STATEMENT" and w.level == "danger" for w in r.warnings)


def test_update_without_where_warns():
    r = analyze("UPDATE Host SET Hostname = 'x'")
    assert {"WRITE_STATEMENT", "NO_WHERE"} <= _codes(r)


def test_delete_with_where_no_nowhere_warning():
    r = analyze("DELETE FROM Host WHERE HostID = 1")
    assert "NO_WHERE" not in _codes(r)


def test_select_has_no_write_warning():
    r = analyze("SELECT * FROM Host WHERE HostID = 1")
    assert "WRITE_STATEMENT" not in _codes(r)


def test_cartesian_join_without_on_warns():
    r = analyze("SELECT * FROM A JOIN B")
    assert "CARTESIAN_JOIN" in _codes(r)


def test_comma_join_with_linking_where_not_flagged():
    # heuristic: a WHERE clause is assumed to link the tables -> no cartesian warning
    r = analyze("SELECT * FROM A, B WHERE A.id = B.id")
    assert "CARTESIAN_JOIN" not in _codes(r)


def test_ddl_is_write_statement():
    r = analyze("DROP TABLE Host")
    assert "WRITE_STATEMENT" in _codes(r)
