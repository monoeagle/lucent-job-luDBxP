import sync_version


def test_bump_patch():
    assert sync_version.bump("0.1.0", "patch") == "0.1.1"


def test_bump_minor():
    assert sync_version.bump("0.1.3", "minor") == "0.2.0"


def test_bump_major():
    assert sync_version.bump("1.2.3", "major") == "2.0.0"


def test_set_explicit_validates():
    assert sync_version.bump("0.1.0", "set", "3.4.5") == "3.4.5"
