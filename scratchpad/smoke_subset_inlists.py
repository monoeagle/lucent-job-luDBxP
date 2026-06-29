"""
Smoke test: UI-Button „IN-Listen (SQL)" + .sql-Download (AP-56c / Task 3)
Run with system python3 (NOT the venv):
    python3 scratchpad/smoke_subset_inlists.py
Expected output: PASS
"""

import pathlib
import sys

DB = pathlib.Path("sample_data/demo_cmdb.db").resolve()
if not DB.exists():
    print(f"SKIP — Demo-DB not found: {DB}")
    sys.exit(0)

from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://127.0.0.1:5057", wait_until="networkidle")

    # ── 1. Verbinden mit Demo-Verbindung (Topbar) ────────────────────────────
    # Wait for "Demo" to appear in the saved-connections dropdown
    page.wait_for_function(
        "Array.from(document.querySelector('#topbar_conn').options).some(o => o.value === 'Demo')",
        timeout=8000
    )
    page.select_option("#topbar_conn", "Demo")
    page.click("#btn_load")

    # Wait for Datacenter table to appear in the sidebar object browser (data-name attr)
    page.wait_for_function(
        "Array.from(document.querySelectorAll('.sidebar .objects li')).some(el => el.dataset.name === 'Datacenter')",
        timeout=15000
    )

    # ── 2. „Entität exportieren" Panel öffnen ───────────────────────────────
    page.click("li[data-action='subset']")
    page.wait_for_selector("#sub_table", timeout=8000)

    # ── 3. Start-Tabelle = Datacenter, Filter = DatacenterID = 1 ────────────
    page.select_option("#sub_table", "Datacenter")
    # Wait for fillSubsetColumns to populate sub_col with DatacenterID
    page.wait_for_function(
        "Array.from(document.querySelector('#sub_col').options).some(o => o.value === 'DatacenterID')",
        timeout=5000
    )
    page.select_option("#sub_col", "DatacenterID")
    page.select_option("#sub_op", "=")
    page.fill("#sub_val", "1")

    # ── 4. Footprint bauen ──────────────────────────────────────────────────
    page.click("#sub_run")
    # Wait for the IN-Listen button to appear (rendered by runSubset after API response)
    page.wait_for_selector("#sub_inlists", timeout=20000)

    # ── 5. IN-Listen (SQL) klicken — Download abfangen ──────────────────────
    with page.expect_download(timeout=15000) as dl_info:
        page.click("#sub_inlists")

    download = dl_info.value
    sql_text = pathlib.Path(download.path()).read_text(encoding="utf-8")

    # ── 6. Assertions ─────────────────────────────────────────────────────────
    expected = 'WHERE "DatacenterID" IN'
    if expected not in sql_text:
        print(f"FAIL — '{expected}' not found in downloaded .sql")
        print("First 500 chars of .sql:")
        print(sql_text[:500])
        browser.close()
        sys.exit(1)

    fname = download.suggested_filename
    assert fname.endswith("_inlists.sql"), f"Unexpected filename suffix: {fname}"
    assert "Datacenter" in fname, f"Start table not in filename: {fname}"

    print(f"PASS — Downloaded: {fname}")
    print(f"SQL snippet:\n{sql_text[:300]}")

    browser.close()
