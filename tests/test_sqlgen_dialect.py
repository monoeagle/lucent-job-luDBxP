"""AP-29 — dialect-aware SQL generation: identifier quoting + row limiting."""
import pytest

from core.pathfinder import JoinPath, JoinStep
from core.sqlgen import (
    generate_sql, Selection, Filter,
    SQLITE, POSTGRES, MYSQL, MSSQL, ORACLE, dialect_for,
)


def _path():
    return JoinPath(
        tables=("VirtualMachine", "Host"),
        steps=(JoinStep("VirtualMachine", "Host", (("HostID", "HostID"),)),),
    )


def _sel():
    return (Selection("VirtualMachine", "VMID"),)


# ── Identifier quoting per dialect ──────────────────────────────────────────

def test_default_dialect_double_quotes():
    g = generate_sql(_path(), selects=_sel())
    assert '    "VirtualMachine"."VMID"' in g.sql       # column on its own line
    assert 'FROM "VirtualMachine"' in g.sql
    assert 'JOIN "Host"' in g.sql
    assert '    ON "VirtualMachine"."HostID" = "Host"."HostID"' in g.sql


def test_mysql_backtick_quoting():
    g = generate_sql(_path(), selects=_sel(), dialect=MYSQL)
    assert "    `VirtualMachine`.`VMID`" in g.sql
    assert "FROM `VirtualMachine`" in g.sql


def test_mssql_bracket_quoting():
    g = generate_sql(_path(), selects=_sel(), dialect=MSSQL)
    assert "    [VirtualMachine].[VMID]" in g.sql
    assert "JOIN [Host]" in g.sql
    assert "    ON [VirtualMachine].[HostID] = [Host].[HostID]" in g.sql


def test_postgres_and_oracle_double_quote():
    for d in (POSTGRES, ORACLE):
        g = generate_sql(_path(), selects=_sel(), dialect=d)
        assert '    "VirtualMachine"."VMID"' in g.sql


def test_quote_escaping_doubles_close_char():
    # A column whose name contains the quote char must escape it by doubling.
    g = generate_sql(_path(), selects=(Selection("VirtualMachine", 'we"ird'),))
    assert '"VirtualMachine"."we""ird"' in g.sql
    g2 = generate_sql(_path(), selects=(Selection("VirtualMachine", "we]ird"),),
                      dialect=MSSQL)
    assert "[VirtualMachine].[we]]ird]" in g2.sql


# ── Row limiting per dialect ────────────────────────────────────────────────

def test_limit_suffix_for_sqlite_pg_mysql():
    for d in (SQLITE, POSTGRES, MYSQL):
        g = generate_sql(_path(), selects=_sel(), limit=10, dialect=d)
        assert g.sql.rstrip().endswith("LIMIT 10")
        assert "TOP" not in g.sql and "FETCH" not in g.sql


def test_limit_mssql_uses_top():
    g = generate_sql(_path(), selects=_sel(), limit=10, dialect=MSSQL)
    assert g.sql.splitlines()[0] == "SELECT TOP 10"
    assert "LIMIT" not in g.sql


def test_distinct_top_order_mssql():
    g = generate_sql(_path(), selects=_sel(), distinct=True, limit=10, dialect=MSSQL)
    assert g.sql.splitlines()[0] == "SELECT DISTINCT TOP 10"


def test_limit_oracle_fetch_first():
    g = generate_sql(_path(), selects=_sel(), limit=10, dialect=ORACLE)
    assert g.sql.rstrip().endswith("FETCH FIRST 10 ROWS ONLY")
    assert "LIMIT" not in g.sql and "TOP" not in g.sql


def test_filter_still_parameterized_with_quoting():
    g = generate_sql(_path(), selects=_sel(),
                     filters=(Filter("Host", "ClusterID", "=", 3),), dialect=MYSQL)
    assert "WHERE `Host`.`ClusterID` = :p0" in g.sql
    assert g.params == {"p0": 3}


# ── dialect_for() resolver ──────────────────────────────────────────────────

def test_dialect_for_maps_db_types():
    assert dialect_for("postgresql") is POSTGRES
    assert dialect_for("mysql") is MYSQL
    assert dialect_for("mssql") is MSSQL
    assert dialect_for("sqlite") is SQLITE
    assert dialect_for("oracle") is ORACLE


def test_dialect_for_unknown_falls_back_to_sqlite():
    assert dialect_for("") is SQLITE
    assert dialect_for("informix") is SQLITE
    assert dialect_for(None) is SQLITE
