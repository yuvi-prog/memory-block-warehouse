"""
google_sheets.py — Push/pull warehouse pallet data to/from Google Sheets.
Credentials are loaded from the GOOGLE_CREDENTIALS_JSON env var.
"""
import json
import os
import logging

log = logging.getLogger(__name__)

SCOPES   = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')

HEADERS = [
    'Location', 'Level', 'Pallet Label', 'Product Name', 'SKU',
    'Fill %', 'Boxes', 'Units/Box', 'SKU 2', 'Boxes 2', 'UPB 2',
    'SKU 3', 'Boxes 3', 'UPB 3', 'Notes', 'Refurb Units',
]

LEVEL_MAP = {0: 'L1', 1: 'L2', 2: 'L3'}


def _client():
    import gspread
    from google.oauth2.service_account import Credentials
    raw = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
    if not raw:
        raise ValueError('GOOGLE_CREDENTIALS_JSON env var not set')
    info  = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _sheet():
    sid = os.environ.get('GOOGLE_SHEET_ID', '')
    if not sid:
        raise ValueError('GOOGLE_SHEET_ID env var not set')
    return _client().open_by_key(sid).sheet1


def push_to_sheet(pallets: list) -> int:
    """Overwrite the Google Sheet with current warehouse data. Returns row count."""
    ws = _sheet()
    ws.clear()

    rows = [HEADERS]
    for p in pallets:
        if p.get('is_printer'):
            continue
        if p.get('level') not in (0, 1, 2):
            continue
        rows.append([
            p.get('id', ''),
            LEVEL_MAP.get(p.get('level'), ''),
            p.get('pallet_label', '') or '',
            p.get('name', '') or '',
            p.get('sku', '') or '',
            p.get('fill', 0) or 0,
            p.get('units', 0) or 0,
            p.get('units_per_box', 0) or 0,
            p.get('sku2', '') or '',
            p.get('units2', 0) or 0,
            p.get('units_per_box2', 0) or 0,
            p.get('sku3', '') or '',
            p.get('units3', 0) or 0,
            p.get('units_per_box3', 0) or 0,
            p.get('notes', '') or '',
            p.get('refurbished_units', 0) or 0,
        ])

    ws.update('A1', rows)
    ws.format('A1:P1', {
        'textFormat': {'bold': True},
        'backgroundColor': {'red': 0.18, 'green': 0.18, 'blue': 0.18},
    })
    # Freeze header row
    ws.spreadsheet.batch_update({'requests': [{'updateSheetProperties': {
        'properties': {'sheetId': ws.id, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount',
    }}]})

    log.info(f'Google Sheets push: wrote {len(rows)-1} pallets')
    return len(rows) - 1


def pull_from_sheet() -> list:
    """Read the Google Sheet and return a list of update dicts keyed by pid."""
    ws   = _sheet()
    rows = ws.get_all_values()

    if not rows or len(rows) < 2:
        return []

    updates = []
    for row in rows[1:]:
        pid = row[0].strip() if row else ''
        if not pid:
            continue

        def v(i, default=''):
            return row[i].strip() if i < len(row) and row[i].strip() else default

        def n(i):
            try:    return int(float(v(i, '0')))
            except: return 0

        updates.append({
            'pid':              pid,
            'pallet_label':     v(2),
            'name':             v(3),
            'sku':              v(4),
            'fill':             n(5),
            'units':            n(6),
            'units_per_box':    n(7),
            'sku2':             v(8),
            'units2':           n(9),
            'units_per_box2':   n(10),
            'sku3':             v(11),
            'units3':           n(12),
            'units_per_box3':   n(13),
            'notes':            v(14),
            'refurbished_units': n(15),
        })

    log.info(f'Google Sheets pull: read {len(updates)} rows')
    return updates
