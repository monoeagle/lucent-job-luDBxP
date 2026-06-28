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


import pytest
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader


@pytest.fixture
def inv_schema(inventory_url):
    return SqlAlchemyLoader(inventory_url).load()


def test_unknown_table_warns_with_schema(inv_schema):
    r = analyze("SELECT * FROM NoSuchTable", schema=inv_schema)
    assert "UNKNOWN_TABLE" in {w.code for w in r.warnings}


def test_known_table_case_insensitive_no_warning(inv_schema):
    # inventory has table "Networks"; lowercase must still be recognized
    r = analyze("SELECT NetworkID FROM networks", schema=inv_schema)
    assert "UNKNOWN_TABLE" not in {w.code for w in r.warnings}


def test_unknown_qualified_column_warns(inv_schema):
    r = analyze("SELECT n.NoSuchCol FROM Networks n", schema=inv_schema)
    assert "UNKNOWN_COLUMN" in {w.code for w in r.warnings}


def test_no_schema_no_unknown_warnings():
    r = analyze("SELECT * FROM TotallyUnknown")
    codes = {w.code for w in r.warnings}
    assert "UNKNOWN_TABLE" not in codes and "UNKNOWN_COLUMN" not in codes


# ---------------------------------------------------------------------------
# Fix 1 regression: PostgreSQL/MSSQL dialect names must not raise ValueError
# ---------------------------------------------------------------------------

def test_postgresql_dialect_does_not_raise():
    r = analyze("SELECT VLAN FROM Networks", dialect="postgresql")
    assert r.parse_error is None
    assert r.statement_type == "SELECT"


def test_mssql_dialect_does_not_raise():
    r = analyze("SELECT VLAN FROM Networks", dialect="mssql")
    assert r.parse_error is None
    assert r.statement_type == "SELECT"


# ---------------------------------------------------------------------------
# Fix 2 regression: NO_WHERE must fire even when a subquery provides a WHERE
# ---------------------------------------------------------------------------

def test_update_with_only_subquery_where_still_warns_no_where():
    r = analyze("UPDATE Host SET a = (SELECT max(x) FROM Other WHERE x > 1)")
    assert "NO_WHERE" in {w.code for w in r.warnings}


# ---------------------------------------------------------------------------
# Fix 3 regression: UNKNOWN_COLUMN must be case-insensitive
# ---------------------------------------------------------------------------

def test_lowercase_table_qualified_column_no_unknown(inv_schema):
    # Table in schema is "Networks"; query uses lowercase "networks" alias
    r = analyze("SELECT n.VLAN FROM networks n", schema=inv_schema)
    assert "UNKNOWN_COLUMN" not in {w.code for w in r.warnings}


def test_lowercase_column_name_no_unknown(inv_schema):
    # Column in schema is "VLAN"; query uses lowercase "vlan"
    r = analyze("SELECT n.vlan FROM Networks n", schema=inv_schema)
    assert "UNKNOWN_COLUMN" not in {w.code for w in r.warnings}


def test_genuinely_unknown_qualified_column_still_warns(inv_schema):
    r = analyze("SELECT n.NoSuchCol FROM Networks n", schema=inv_schema)
    assert "UNKNOWN_COLUMN" in {w.code for w in r.warnings}


# ===== AP-39: Struktur-/Klausel-Analyse, Graph-Kanten, Lints, Komplexität =====

_EX2 = (
    'SELECT "Cluster"."ClusterID", "Host"."HostID", "Folder"."FolderID" '
    'FROM "Cluster" '
    'JOIN "Host" ON "Cluster"."ClusterID" = "Host"."ClusterID" '
    'JOIN "VirtualMachine" ON "Host"."HostID" = "VirtualMachine"."HostID" '
    'JOIN "Folder" ON "VirtualMachine"."FolderID" = "Folder"."FolderID" '
    'WHERE "Cluster"."ClusterID" = 1 '
    'ORDER BY "Cluster"."ClusterID" ASC'
)


def test_columns_extracted():
    r = analyze(_EX2)
    joined = " ".join(r.columns)
    assert "ClusterID" in joined and "HostID" in joined and "FolderID" in joined
    assert len(r.columns) == 3


def test_joins_and_count():
    r = analyze(_EX2)
    assert len(r.joins) == 3
    assert all(j["kind"] for j in r.joins)            # every join has a kind label
    assert r.structure["joins"] == 3


def test_filters_and_order_by_extracted():
    r = analyze(_EX2)
    assert any("ClusterID" in f and "1" in f for f in r.filters)
    assert any("ClusterID" in o and o.strip().upper().endswith("ASC") for o in r.order_by)


def test_graph_edges_follow_joins():
    r = analyze(_EX2)
    pairs = {frozenset(e) for e in r.edges}
    assert frozenset({"Cluster", "Host"}) in pairs
    assert frozenset({"Host", "VirtualMachine"}) in pairs
    assert frozenset({"VirtualMachine", "Folder"}) in pairs


def test_structure_counts_basic():
    r = analyze(_EX2)
    s = r.structure
    assert s["tables"] == 4
    assert s["subqueries"] == 0 and s["ctes"] == 0 and s["unions"] == 0


def test_complexity_score_and_grade():
    r = analyze(_EX2)
    assert isinstance(r.complexity_score, int) and r.complexity_score >= 3  # 3 joins
    assert r.complexity_grade in ("A", "B", "C", "D", "E")


def test_lint_select_star():
    r = analyze("SELECT * FROM Host")
    assert "SELECT_STAR" in _codes(r)


def test_lint_leading_wildcard_like():
    r = analyze("SELECT HostID FROM Host WHERE Hostname LIKE '%web'")
    assert "LEADING_WILDCARD" in _codes(r)


def test_lint_function_on_column_in_where():
    r = analyze("SELECT HostID FROM Host WHERE LOWER(Hostname) = 'web01'")
    assert "FUNC_ON_COLUMN" in _codes(r)


def test_clean_select_has_no_lint_noise():
    r = analyze('SELECT "Host"."HostID" FROM "Host" WHERE "Host"."HostID" = 1')
    assert "SELECT_STAR" not in _codes(r)
    assert "LEADING_WILDCARD" not in _codes(r)


def test_lint_suspicious_alias_flags_join_keyword_typo():
    # sqlglot parses "LEFTI" as a table alias; the heuristic flags the likely typo.
    r = analyze("SELECT a FROM t LEFTI JOIN u ON t.x = u.y")
    assert "SUSPICIOUS_ALIAS" in _codes(r)


def test_lint_suspicious_alias_quiet_for_correct_keyword_and_normal_alias():
    assert "SUSPICIOUS_ALIAS" not in _codes(analyze("SELECT a FROM t LEFT JOIN u ON t.x = u.y"))
    assert "SUSPICIOUS_ALIAS" not in _codes(analyze("SELECT a FROM t t1 JOIN u ON t1.x = u.y"))


def test_parse_error_is_ansi_free():
    # sqlglot underlines the bad token with ANSI codes; the result must be clean text.
    r = analyze("SELECT a FROM t JOIN u ON x JOIN LEFTI w x y z")
    assert r.parse_error is not None
    assert "\x1b" not in r.parse_error and "[4m" not in r.parse_error


# --- AP-F: Optimierungs-Vorschläge ---------------------------------------

def _sugg_codes(sql):
    return {s.code for s in analyze(sql).suggestions}


def test_suggest_distinct_with_group_by():
    assert "DISTINCT_WITH_GROUP_BY" in _sugg_codes(
        "SELECT DISTINCT a FROM t GROUP BY a")


def test_no_distinct_suggestion_without_group_by():
    assert "DISTINCT_WITH_GROUP_BY" not in _sugg_codes("SELECT DISTINCT a FROM t")


def test_no_distinct_suggestion_without_distinct():
    assert "DISTINCT_WITH_GROUP_BY" not in _sugg_codes("SELECT a FROM t GROUP BY a")


def test_suggest_order_by_without_limit():
    assert "ORDER_BY_NO_LIMIT" in _sugg_codes("SELECT a FROM t ORDER BY a")


def test_no_order_by_suggestion_with_limit():
    assert "ORDER_BY_NO_LIMIT" not in _sugg_codes(
        "SELECT a FROM t ORDER BY a LIMIT 10")


def test_suggest_or_in_where():
    assert "OR_IN_WHERE" in _sugg_codes("SELECT a FROM t WHERE a = 1 OR b = 2")


def test_no_or_suggestion_for_and_only():
    assert "OR_IN_WHERE" not in _sugg_codes("SELECT a FROM t WHERE a = 1 AND b = 2")


def test_suggest_subquery_in_where():
    assert "SUBQUERY_IN_WHERE" in _sugg_codes(
        "SELECT a FROM t WHERE a IN (SELECT x FROM u)")


def test_no_subquery_suggestion_for_exists():
    assert "SUBQUERY_IN_WHERE" not in _sugg_codes(
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.t_id = t.id)")


def test_no_subquery_suggestion_without_subquery():
    assert "SUBQUERY_IN_WHERE" not in _sugg_codes("SELECT a FROM t WHERE a = 1")


def test_plain_select_has_no_suggestions():
    assert analyze("SELECT a FROM t").suggestions == ()


def test_non_select_has_no_suggestions():
    assert analyze("UPDATE t SET a = 1 WHERE id = 2").suggestions == ()
