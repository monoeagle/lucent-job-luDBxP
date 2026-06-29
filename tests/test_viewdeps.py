from core.viewdeps import referenced_routines


def test_plain_function_call_matched():
    out = referenced_routines("SELECT calc_total(x) FROM t", {"calc_total"})
    assert out == ("calc_total",)


def test_builtin_not_matched():
    # COUNT/UPPER parsen als getypte sqlglot-Knoten, nicht als Anonymous.
    out = referenced_routines("SELECT COUNT(x), UPPER(y) FROM t", {"count", "upper"})
    assert out == ()


def test_case_insensitive_returns_canonical():
    out = referenced_routines("SELECT myfn(x) FROM t", {"MYFN"}, dialect="oracle")
    assert out == ("MYFN",)


def test_package_qualified_call_matches_package():
    out = referenced_routines("SELECT pkg.fn(x) FROM dual", {"PKG"}, dialect="oracle")
    assert out == ("PKG",)


def test_schema_package_qualified_matches_package():
    out = referenced_routines("SELECT myschema.pkg.fn(x) FROM dual", {"PKG"}, dialect="oracle")
    assert out == ("PKG",)


def test_dedup_and_sorted():
    out = referenced_routines("SELECT b_fn(x), a_fn(y), b_fn(z) FROM t", {"a_fn", "b_fn"})
    assert out == ("a_fn", "b_fn")


def test_no_match_returns_empty():
    assert referenced_routines("SELECT a, b FROM t", {"calc_total"}) == ()


def test_empty_definition_returns_empty():
    assert referenced_routines("", {"calc_total"}) == ()
    assert referenced_routines("   ", {"calc_total"}) == ()


def test_empty_known_names_returns_empty():
    assert referenced_routines("SELECT calc_total(x) FROM t", set()) == ()


def test_parse_error_returns_empty():
    # Unparsebarer Müll → () statt Exception.
    assert referenced_routines("]]] not sql (((", {"calc_total"}) == ()
