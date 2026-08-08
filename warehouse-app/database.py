"""
database.py — Memory Block Warehouse
Physical layout:
  Right wall:  Section A (11 segments) — single sided
  Aisle 1
  Back-to-back: Section B (8 seg, faces aisle 1) + Section C (8 seg, faces aisle 2)
  Aisle 2
  Back-to-back: Section D (8 seg, faces aisle 2) + Section E (8 seg, faces aisle 3)
  Aisle 3
  Left wall:   Section F (7 segments) — single sided

  Segment numbering starts from printer/entry end (front of warehouse).
  Printer pallet: front centre entry.
  Storage room:   front-right corner (in front of Section F after mirror).
"""

import sqlite3, random, os
from datetime import datetime

# Use explicit env var first, then /data (Railway persistent volume), then local file.
# To persist data on Railway: add a Volume mounted at /data in the Railway dashboard.
DB_PATH = (
    os.environ.get('DATABASE_PATH')
    or ('/data/warehouse.db' if os.path.isdir('/data') else None)
    or os.path.join(os.path.dirname(__file__), 'warehouse.db')
)

SECTIONS = ['A','B','C','D','E','F']
LEVELS   = 3
SLOTS    = 2   # pallets wide per segment

# Segments per section
SECTION_SEGMENTS = {'A':11,'B':8,'C':8,'D':8,'E':8,'F':7}

# Physical rack blocks (right→left in the 3D world, mirrored so A is right wall)
# Each block: (block_id, sec_right_wall_side, sec_left_wall_side)
# 'wall' means single-sided against wall, 'double' means back-to-back
RACK_BLOCKS = [
    {'id':0, 'type':'wall',   'section':'A', 'wall_side':'R'},
    {'id':1, 'type':'double', 'sectionR':'B', 'sectionL':'C'},
    {'id':2, 'type':'double', 'sectionR':'D', 'sectionL':'E'},
    {'id':3, 'type':'wall',   'section':'F', 'wall_side':'L'},
]

MB_PRODUCTS = [
    ('Rectangle Block A4',    'MB-REC-A4'),
    ('Rectangle Block A3',    'MB-REC-A3'),
    ('Square Block 20cm',     'MB-SQ-20'),
    ('Square Block 30cm',     'MB-SQ-30'),
    ('Large Hanger XL',       'MB-LH-XL'),
    ('Round Puzzle 500pc',    'MB-PUZZ-R500'),
    ('Square Puzzle 1000pc',  'MB-PUZZ-SQ1K'),
    ('Rectangle Puzzle Table','MB-PUZZ-RT'),
    ('Jigsaw Frame Set',      'MB-JIG-FRM'),
    ('Photo Block Square',    'MB-PHB-SQ'),
    ('Canvas Roll A3',        'MB-CVS-A3'),
    ('Gift Box Premium',      'MB-GIFT-P'),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS pallets (
        id         TEXT PRIMARY KEY,
        section    TEXT NOT NULL,
        block_id   INTEGER NOT NULL DEFAULT 0,
        face       TEXT NOT NULL DEFAULT "R",
        segment    INTEGER NOT NULL,
        slot       INTEGER NOT NULL,
        level      INTEGER NOT NULL,
        name       TEXT NOT NULL,
        sku        TEXT NOT NULL,
        fill       INTEGER NOT NULL DEFAULT 0,
        units      INTEGER NOT NULL DEFAULT 0,
        notes      TEXT DEFAULT "",
        is_printer INTEGER NOT NULL DEFAULT 0,
        max_units  INTEGER NOT NULL DEFAULT 0
    )''')
    # Migrations: add columns to existing DBs that don't have them yet
    for col_sql in [
        ('max_units',         'ALTER TABLE pallets ADD COLUMN max_units         INTEGER NOT NULL DEFAULT 0'),
        ('units_per_box',     'ALTER TABLE pallets ADD COLUMN units_per_box     INTEGER NOT NULL DEFAULT 0'),
        ('refurbished_units', 'ALTER TABLE pallets ADD COLUMN refurbished_units INTEGER NOT NULL DEFAULT 0'),
        ('sku2',              'ALTER TABLE pallets ADD COLUMN sku2              TEXT NOT NULL DEFAULT ""'),
        ('sku3',              'ALTER TABLE pallets ADD COLUMN sku3              TEXT NOT NULL DEFAULT ""'),
        ('pallet_label',      'ALTER TABLE pallets ADD COLUMN pallet_label      TEXT NOT NULL DEFAULT ""'),
        ('units2',            'ALTER TABLE pallets ADD COLUMN units2            INTEGER NOT NULL DEFAULT 0'),
        ('units_per_box2',    'ALTER TABLE pallets ADD COLUMN units_per_box2    INTEGER NOT NULL DEFAULT 0'),
        ('units3',            'ALTER TABLE pallets ADD COLUMN units3            INTEGER NOT NULL DEFAULT 0'),
        ('units_per_box3',    'ALTER TABLE pallets ADD COLUMN units_per_box3    INTEGER NOT NULL DEFAULT 0'),
    ]:
        col_name, sql = col_sql
        try:
            c.execute(sql)
            conn.commit()
            print(f'  Migration: added column {col_name}')
        except Exception:
            pass  # column already exists

    c.execute('''CREATE TABLE IF NOT EXISTS storage_items (
        id       INTEGER PRIMARY KEY,
        slot     INTEGER NOT NULL UNIQUE,
        name     TEXT NOT NULL DEFAULT "",
        sku      TEXT NOT NULL DEFAULT "",
        quantity INTEGER NOT NULL DEFAULT 0,
        notes    TEXT DEFAULT ""
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        pallet_id  TEXT NOT NULL,
        changed_by TEXT NOT NULL DEFAULT "Stock User",
        field      TEXT NOT NULL,
        old_value  TEXT,
        new_value  TEXT,
        changed_at TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS spare_parts (
        id       INTEGER PRIMARY KEY,
        slot     INTEGER NOT NULL UNIQUE,
        name     TEXT NOT NULL DEFAULT "",
        sku      TEXT NOT NULL DEFAULT "",
        quantity INTEGER NOT NULL DEFAULT 0,
        notes    TEXT DEFAULT ""
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS printer_items (
        row_num    INTEGER PRIMARY KEY,
        printer_id TEXT NOT NULL DEFAULT "",
        laptop_id  TEXT NOT NULL DEFAULT "",
        notes      TEXT NOT NULL DEFAULT ""
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS weekly_snapshots (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        captured_at TEXT NOT NULL,
        total       INTEGER NOT NULL DEFAULT 0,
        full_high   INTEGER NOT NULL DEFAULT 0,
        medium      INTEGER NOT NULL DEFAULT 0,
        low_stock   INTEGER NOT NULL DEFAULT 0,
        empty       INTEGER NOT NULL DEFAULT 0,
        avg_fill    REAL NOT NULL DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS order_log (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number     TEXT NOT NULL,
        processed_at     TEXT NOT NULL,
        customer         TEXT NOT NULL DEFAULT "",
        lines_processed  INTEGER NOT NULL DEFAULT 0,
        lines_skipped    INTEGER NOT NULL DEFAULT 0,
        alerts_fired     INTEGER NOT NULL DEFAULT 0,
        notes            TEXT NOT NULL DEFAULT "",
        raw_payload      TEXT NOT NULL DEFAULT ""
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS location_assignments (
        pallet_id     TEXT PRIMARY KEY,
        sku           TEXT NOT NULL DEFAULT "",
        product_name  TEXT NOT NULL DEFAULT "",
        sku2          TEXT NOT NULL DEFAULT "",
        product_name2 TEXT NOT NULL DEFAULT "",
        sku3          TEXT NOT NULL DEFAULT "",
        product_name3 TEXT NOT NULL DEFAULT "",
        assigned_by   TEXT NOT NULL DEFAULT "",
        assigned_at   TEXT NOT NULL DEFAULT ""
    )''')
    # Migrations for existing location_assignments tables
    for col_sql in [
        ('sku2',          'ALTER TABLE location_assignments ADD COLUMN sku2          TEXT NOT NULL DEFAULT ""'),
        ('product_name2', 'ALTER TABLE location_assignments ADD COLUMN product_name2 TEXT NOT NULL DEFAULT ""'),
        ('sku3',          'ALTER TABLE location_assignments ADD COLUMN sku3          TEXT NOT NULL DEFAULT ""'),
        ('product_name3', 'ALTER TABLE location_assignments ADD COLUMN product_name3 TEXT NOT NULL DEFAULT ""'),
    ]:
        try:
            c.execute(col_sql[1]); conn.commit()
        except Exception:
            pass

    c.execute('''CREATE TABLE IF NOT EXISTS email_log (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        attempted_at  TEXT NOT NULL,
        status        TEXT NOT NULL,
        response_code INTEGER,
        detail        TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS app_settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')

    conn.commit()

    if c.execute('SELECT COUNT(*) FROM pallets').fetchone()[0] == 0:
        print('  Seeding warehouse...')
        _seed(conn)
        total = c.execute('SELECT COUNT(*) FROM pallets').fetchone()[0]
        print(f'  Seeded {total} pallets (300 rack + 1 printer).')

    if c.execute('SELECT COUNT(*) FROM storage_items').fetchone()[0] == 0:
        for slot in range(1, 11):
            conn.execute('INSERT INTO storage_items (slot,name,sku,quantity) VALUES (?,?,?,?)',
                         (slot,'','',0))
        conn.commit()
        print('  Seeded 10 storage room slots.')

    if c.execute('SELECT COUNT(*) FROM printer_items').fetchone()[0] == 0:
        for row in range(1, 11):
            conn.execute('INSERT INTO printer_items (row_num) VALUES (?)', (row,))
        conn.commit()
        print('  Seeded 10 printer tracker rows.')

    if c.execute('SELECT COUNT(*) FROM spare_parts').fetchone()[0] == 0:
        for slot in range(1, 81):
            conn.execute('INSERT INTO spare_parts (slot,name,sku,quantity) VALUES (?,?,?,?)',
                         (slot,'','',0))
        conn.commit()
        print('  Seeded 80 spare parts slots.')

    # Rename pallet IDs on existing DBs so S1 = south/printer end
    _migrate_segment_ids(conn)
    # Swap P1/P2 so the slot closest to the printer end = P1
    _migrate_slot_ids(conn)

    conn.close()


def _migrate_slot_ids(conn):
    """Swap P1/P2: slot 1 (south/printer end of segment) becomes P1."""
    # Old scheme: slot=0 → P1. Detect by finding slot=0 with P1 in the ID.
    row = conn.execute(
        "SELECT id FROM pallets WHERE slot=0 AND id LIKE '%-P1-%' AND is_printer=0 LIMIT 1"
    ).fetchone()
    if not row:
        return  # already using new scheme or no rack data

    print('  Migrating pallet slot IDs (P1/P2 swap)...')
    c = conn.cursor()
    pallets = conn.execute(
        'SELECT id, section, segment, slot, level FROM pallets WHERE is_printer=0'
    ).fetchall()

    # Phase 1: rename to TMP_ to avoid PK conflicts
    for p in pallets:
        pid, sec, seg, slot, lv = p[0], p[1], p[2], p[3], p[4]
        n = SECTION_SEGMENTS.get(sec, 0)
        if not n:
            continue
        new_id = f'TMP_{sec}-S{n-seg}-P{SLOTS-slot}-L{lv+1}'
        c.execute('UPDATE pallets   SET id=?        WHERE id=?',        (new_id, pid))
        c.execute('UPDATE audit_log SET pallet_id=? WHERE pallet_id=?', (new_id, pid))

    # Phase 2: strip TMP_ prefix
    c.execute("UPDATE pallets   SET id=substr(id,5)                WHERE id LIKE 'TMP_%'")
    c.execute("UPDATE audit_log SET pallet_id=substr(pallet_id,5)  WHERE pallet_id LIKE 'TMP_%'")
    conn.commit()
    print('  Slot ID migration complete.')


def _migrate_segment_ids(conn):
    """One-time migration: re-number segment IDs so S1 = south/printer end."""
    # Old seeding used seg+1 so A-S1-P1-L1 had segment=0 (north/far end).
    # New convention: A-S1-P1-L1 has segment=numSegs-1 (south/printer end).
    # Detect old data by checking if A-S1-P1-L1 exists with segment=0.
    row = conn.execute("SELECT segment FROM pallets WHERE id='A-S1-P1-L1'").fetchone()
    if row is None or row[0] != 0:
        return  # freshly seeded with new IDs, or no data yet

    print('  Migrating pallet IDs to south-first numbering...')
    c = conn.cursor()

    pallets = conn.execute(
        'SELECT id, section, segment, slot, level FROM pallets WHERE is_printer=0'
    ).fetchall()

    # Phase 1: rename to TMP_ prefixed IDs (avoids primary-key conflicts during swap)
    for p in pallets:
        pid, sec, seg, slot, lv = p[0], p[1], p[2], p[3], p[4]
        n = SECTION_SEGMENTS.get(sec, 0)
        if not n:
            continue
        new_id = f'TMP_{sec}-S{n-seg}-P{slot+1}-L{lv+1}'
        c.execute('UPDATE pallets   SET id=?         WHERE id=?',         (new_id, pid))
        c.execute('UPDATE audit_log SET pallet_id=?  WHERE pallet_id=?',  (new_id, pid))

    # Phase 2: strip the TMP_ prefix (4 chars, SQLite substr is 1-based so start=5)
    c.execute("UPDATE pallets   SET id=substr(id,5)         WHERE id LIKE 'TMP_%'")
    c.execute("UPDATE audit_log SET pallet_id=substr(pallet_id,5) WHERE pallet_id LIKE 'TMP_%'")
    conn.commit()
    print('  Pallet ID migration complete.')


def _seed(conn):
    rows = []
    for block in RACK_BLOCKS:
        if block['type'] == 'wall':
            sec   = block['section']
            face  = block['wall_side']
            segs  = SECTION_SEGMENTS[sec]
            bid   = block['id']
            for seg in range(segs):
                for slot in range(SLOTS):
                    for lv in range(LEVELS):
                        name, sku = random.choice(MB_PRODUCTS)
                        fill = (random.randint(55,100) if lv==0
                                else 0 if random.random()<.12
                                else random.randint(0,100))
                        pid = f'{sec}-S{segs-seg}-P{SLOTS-slot}-L{lv+1}'
                        rows.append((pid, sec, bid, face, seg, slot, lv,
                                     name, sku, fill, round(fill*.52), '', 0, 52))
        else:
            for face_key, sec_key in [('R','sectionR'),('L','sectionL')]:
                sec  = block[sec_key]
                segs = SECTION_SEGMENTS[sec]
                bid  = block['id']
                for seg in range(segs):
                    for slot in range(SLOTS):
                        for lv in range(LEVELS):
                            name, sku = random.choice(MB_PRODUCTS)
                            fill = (random.randint(55,100) if lv==0
                                    else 0 if random.random()<.12
                                    else random.randint(0,100))
                            pid = f'{sec}-S{segs-seg}-P{SLOTS-slot}-L{lv+1}'
                            rows.append((pid, sec, bid, face_key, seg, slot, lv,
                                         name, sku, fill, round(fill*.52), '', 0, 52))

    # Printer pallet (no box capacity tracking)
    rows.append(('PRINTER-MAIN','PRINTER',0,'C',0,0,0,
                 'Printer Units','MB-PRINTER',0,0,'Central printer tracker',1,0))

    conn.executemany('''INSERT INTO pallets
        (id,section,block_id,face,segment,slot,level,name,sku,fill,units,notes,is_printer,max_units,units_per_box,refurbished_units)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0)''', rows)
    conn.commit()


def get_all_pallets():
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM pallets ORDER BY section,segment,slot,level'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_printer_pallet():
    conn = get_conn()
    r = conn.execute('SELECT * FROM pallets WHERE is_printer=1').fetchone()
    conn.close()
    return dict(r) if r else None


def get_storage_items():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM storage_items ORDER BY slot').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_storage_item(slot: int, updates: dict):
    conn = get_conn()
    allowed = {'name','sku','quantity','notes'}
    updates = {k:v for k,v in updates.items() if k in allowed}
    if updates:
        set_cl = ', '.join(f'{k}=?' for k in updates)
        conn.execute(f'UPDATE storage_items SET {set_cl} WHERE slot=?',
                     list(updates.values())+[slot])
        conn.commit()
    row = conn.execute('SELECT * FROM storage_items WHERE slot=?',(slot,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_spare_parts():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM spare_parts ORDER BY slot').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_spare_part(slot: int, updates: dict):
    conn = get_conn()
    allowed = {'name','sku','quantity','notes'}
    updates = {k:v for k,v in updates.items() if k in allowed}
    if updates:
        set_cl = ', '.join(f'{k}=?' for k in updates)
        conn.execute(f'UPDATE spare_parts SET {set_cl} WHERE slot=?',
                     list(updates.values())+[slot])
        conn.commit()
    row = conn.execute('SELECT * FROM spare_parts WHERE slot=?',(slot,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_pallet(pallet_id: str, updates: dict, changed_by: str='Stock User'):
    conn = get_conn()
    row  = conn.execute('SELECT * FROM pallets WHERE id=?',(pallet_id,)).fetchone()
    if not row:
        conn.close(); return None
    old = dict(row)
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    for field, new_val in updates.items():
        if str(old.get(field,'')) != str(new_val):
            conn.execute('''INSERT INTO audit_log
                (pallet_id,changed_by,field,old_value,new_value,changed_at)
                VALUES (?,?,?,?,?,?)''',
                (pallet_id, changed_by, field, str(old.get(field,'')), str(new_val), now))
    set_cl = ', '.join(f'{k}=?' for k in updates)
    conn.execute(f'UPDATE pallets SET {set_cl} WHERE id=?',
                 list(updates.values())+[pallet_id])
    conn.commit()
    updated = conn.execute('SELECT * FROM pallets WHERE id=?',(pallet_id,)).fetchone()
    conn.close()
    return dict(updated)


def bulk_update_pallets(pallet_ids: list, updates: dict, changed_by: str='Stock User'):
    conn = get_conn()
    now  = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    for pid in pallet_ids:
        row = conn.execute('SELECT * FROM pallets WHERE id=?',(pid,)).fetchone()
        if not row: continue
        old = dict(row)
        for field, new_val in updates.items():
            if str(old.get(field,'')) != str(new_val):
                conn.execute('''INSERT INTO audit_log
                    (pallet_id,changed_by,field,old_value,new_value,changed_at)
                    VALUES (?,?,?,?,?,?)''',
                    (pid,changed_by,field,str(old.get(field,'')),str(new_val),now))
        set_cl = ', '.join(f'{k}=?' for k in updates)
        conn.execute(f'UPDATE pallets SET {set_cl} WHERE id=?',
                     list(updates.values())+[pid])
        count += 1
    conn.commit(); conn.close()
    return count


def get_audit_log(limit: int=150):
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM audit_log ORDER BY changed_at DESC LIMIT ?',(limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    total    = c.execute('SELECT COUNT(*) FROM pallets WHERE is_printer=0').fetchone()[0]
    full     = c.execute('SELECT COUNT(*) FROM pallets WHERE is_printer=0 AND fill>=60').fetchone()[0]
    med      = c.execute('SELECT COUNT(*) FROM pallets WHERE is_printer=0 AND fill>=30 AND fill<60').fetchone()[0]
    low      = c.execute('SELECT COUNT(*) FROM pallets WHERE is_printer=0 AND fill>0 AND fill<30').fetchone()[0]
    empty    = c.execute('SELECT COUNT(*) FROM pallets WHERE is_printer=0 AND fill=0').fetchone()[0]
    assigned    = c.execute("SELECT COUNT(*) FROM location_assignments WHERE sku != ''").fetchone()[0]
    orders      = c.execute('SELECT COUNT(*) FROM order_log').fetchone()[0]
    total_boxes = c.execute('SELECT COALESCE(SUM(units),0) FROM pallets WHERE is_printer=0').fetchone()[0]
    total_units = c.execute('SELECT COALESCE(SUM(units*units_per_box),0) FROM pallets WHERE is_printer=0 AND units_per_box>0').fetchone()[0]
    conn.close()
    return {'total':total,'full':full,'medium':med,'low':low,'empty':empty,
            'locations_assigned': assigned, 'orders_synced': orders,
            'total_boxes': total_boxes, 'total_units': total_units}


def search_pallets(query: str, limit: int = 40):
    conn = get_conn()
    q = f'%{query}%'
    rows = conn.execute(
        '''SELECT * FROM pallets WHERE is_printer=0
           AND (name LIKE ? OR sku LIKE ? OR id LIKE ?)
           ORDER BY
             CASE WHEN fill=0 THEN 2 WHEN fill<30 THEN 1 ELSE 0 END,
             section, segment, slot, level
           LIMIT ?''',
        (q, q, q, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_printer_items():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM printer_items ORDER BY row_num').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_printer_item(row_num: int, updates: dict):
    conn = get_conn()
    allowed = {'printer_id', 'laptop_id', 'notes'}
    updates = {k: v for k, v in updates.items() if k in allowed}
    if updates:
        set_cl = ', '.join(f'{k}=?' for k in updates)
        conn.execute(f'UPDATE printer_items SET {set_cl} WHERE row_num=?',
                     list(updates.values()) + [row_num])
        conn.commit()
    row = conn.execute('SELECT * FROM printer_items WHERE row_num=?', (row_num,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_weekly_report_data():
    conn = get_conn()
    pallets = [dict(r) for r in conn.execute(
        'SELECT * FROM pallets WHERE is_printer=0 ORDER BY section,segment,slot,level'
    ).fetchall()]
    printer     = conn.execute('SELECT * FROM pallets WHERE is_printer=1').fetchone()
    storage     = [dict(r) for r in conn.execute('SELECT * FROM storage_items ORDER BY slot').fetchall()]
    spare_parts = [dict(r) for r in conn.execute('SELECT * FROM spare_parts ORDER BY slot').fetchall()]
    recent  = [dict(r) for r in conn.execute(
        'SELECT * FROM audit_log ORDER BY changed_at DESC LIMIT 20'
    ).fetchall()]
    conn.close()
    by_section = {}
    for p in pallets:
        sec = p['section']
        if sec not in by_section:
            by_section[sec] = {'total':0,'full':0,'medium':0,'low':0,'empty':0,'fill_sum':0}
        s = by_section[sec]; s['total'] += 1
        s['fill_sum'] += p['fill']
        f = p['fill']
        if f==0: s['empty']+=1
        elif f<30: s['low']+=1
        elif f<60: s['medium']+=1
        else: s['full']+=1
    for s in by_section.values():
        s['avg_fill'] = round(s.pop('fill_sum') / s['total']) if s['total'] else 0
    return {
        'by_section':    by_section,
        'low_stock':     [p for p in pallets if 0<p['fill']<30],
        'empty_list':    [p for p in pallets if p['fill']==0],
        'printer':       dict(printer) if printer else {},
        'storage':       storage,
        'spare_parts':   spare_parts,
        'recent_changes':recent,
    }


def log_audit(item_id: str, changed_by: str, field: str, old_value, new_value):
    conn = get_conn()
    conn.execute('''INSERT INTO audit_log
        (pallet_id, changed_by, field, old_value, new_value, changed_at)
        VALUES (?,?,?,?,?,?)''',
        (item_id, changed_by, field, str(old_value), str(new_value),
         datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


# ── Email log ──────────────────────────────────────────────────────────────────

def log_email_attempt(status: str, response_code: int, detail: str):
    """Record every send attempt (success or failure) with timestamp."""
    conn = get_conn()
    conn.execute(
        '''INSERT INTO email_log (attempted_at, status, response_code, detail)
           VALUES (?,?,?,?)''',
        (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), status, response_code, detail)
    )
    conn.commit()
    conn.close()


def get_last_email_sent() -> str | None:
    """Return the timestamp of the last SUCCESSFUL send, or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT attempted_at FROM email_log WHERE status='success' ORDER BY attempted_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_last_email_attempt() -> str | None:
    """Return the timestamp of the most recent attempt (any status)."""
    conn = get_conn()
    row = conn.execute(
        'SELECT attempted_at FROM email_log ORDER BY attempted_at DESC LIMIT 1'
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_email_log(limit: int = 50):
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM email_log ORDER BY attempted_at DESC LIMIT ?', (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Weekly snapshots (trend data) ──────────────────────────────────────────────

def save_weekly_snapshot():
    """Capture a point-in-time inventory snapshot for the trend chart."""
    conn = get_conn()
    fills = [r[0] for r in conn.execute(
        'SELECT fill FROM pallets WHERE is_printer=0'
    ).fetchall()]
    total = len(fills)
    if not total:
        conn.close(); return
    conn.execute('''INSERT INTO weekly_snapshots
        (captured_at, total, full_high, medium, low_stock, empty, avg_fill)
        VALUES (?,?,?,?,?,?,?)''', (
        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        total,
        sum(1 for f in fills if f >= 60),
        sum(1 for f in fills if 30 <= f < 60),
        sum(1 for f in fills if 0 < f < 30),
        sum(1 for f in fills if f == 0),
        round(sum(fills) / total, 1),
    ))
    conn.commit()
    conn.close()


def is_order_processed(order_number: str) -> bool:
    conn = get_conn()
    row = conn.execute('SELECT id FROM order_log WHERE order_number=?', (order_number,)).fetchone()
    conn.close()
    return row is not None


def log_order(order_number: str, customer: str, lines_processed: int,
              lines_skipped: int, alerts_fired: int, notes: str, raw_payload: str):
    conn = get_conn()
    conn.execute('''INSERT INTO order_log
        (order_number, processed_at, customer, lines_processed, lines_skipped, alerts_fired, notes, raw_payload)
        VALUES (?,?,?,?,?,?,?,?)''', (
        order_number,
        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        customer, lines_processed, lines_skipped, alerts_fired, notes, raw_payload
    ))
    conn.commit()
    conn.close()


def get_order_log(limit: int = 50):
    conn = get_conn()
    rows = conn.execute('SELECT * FROM order_log ORDER BY processed_at DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pallet_with_above(pallet_id: str):
    """Return the L1 pallet and the L2/L3 pallets directly above it."""
    conn = get_conn()
    p = conn.execute('SELECT * FROM pallets WHERE id=?', (pallet_id,)).fetchone()
    if not p:
        conn.close(); return None, []
    p = dict(p)
    above = [dict(r) for r in conn.execute(
        'SELECT * FROM pallets WHERE section=? AND segment=? AND slot=? AND level>0 ORDER BY level',
        (p['section'], p['segment'], p['slot'])
    ).fetchall()]
    conn.close()
    return p, above


def get_location_assignments():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM location_assignments').fetchall()
    conn.close()
    return {r['pallet_id']: dict(r) for r in rows}


def set_location_assignment(pallet_id: str, sku: str, product_name: str, assigned_by: str,
                            sku2: str = '', product_name2: str = '',
                            sku3: str = '', product_name3: str = ''):
    conn = get_conn()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    if sku.strip():
        conn.execute('''INSERT INTO location_assignments
            (pallet_id, sku, product_name, sku2, product_name2, sku3, product_name3, assigned_by, assigned_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(pallet_id) DO UPDATE SET
                sku=excluded.sku, product_name=excluded.product_name,
                sku2=excluded.sku2, product_name2=excluded.product_name2,
                sku3=excluded.sku3, product_name3=excluded.product_name3,
                assigned_by=excluded.assigned_by, assigned_at=excluded.assigned_at''',
            (pallet_id, sku.strip(), product_name.strip(),
             sku2.strip(), product_name2.strip(),
             sku3.strip(), product_name3.strip(),
             assigned_by, now))
    else:
        conn.execute('DELETE FROM location_assignments WHERE pallet_id=?', (pallet_id,))
    conn.commit()
    conn.close()


def sync_l1_pallets_from_assignments():
    """Update name and SKU on every assigned L1 pallet to match location assignments."""
    conn = get_conn()
    assignments = conn.execute('SELECT * FROM location_assignments').fetchall()
    now     = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    updated = 0
    for a in assignments:
        a = dict(a)
        pid = a['pallet_id']
        # For multi-SKU pallets combine names, use primary SKU
        name = ' / '.join(filter(None, [a.get('product_name',''), a.get('product_name2',''), a.get('product_name3','')]))
        sku  = a.get('sku', '')
        if not sku:
            continue
        row = conn.execute('SELECT * FROM pallets WHERE id=? AND level=0', (pid,)).fetchone()
        if not row:
            continue
        old = dict(row)
        for field, new_val in [('name', name), ('sku', sku)]:
            if str(old.get(field, '')) != str(new_val):
                conn.execute('''INSERT INTO audit_log
                    (pallet_id, changed_by, field, old_value, new_value, changed_at)
                    VALUES (?,?,?,?,?,?)''',
                    (pid, 'Location Sync', field, str(old.get(field,'')), str(new_val), now))
        conn.execute('UPDATE pallets SET name=?, sku=? WHERE id=? AND level=0', (name, sku, pid))
        updated += 1
    conn.commit()
    conn.close()
    return updated


def get_l1_pallets():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, section, segment, slot FROM pallets WHERE level=0 AND is_printer=0 ORDER BY section, segment, slot"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_setting(key: str, default: str = None):
    conn = get_conn()
    row = conn.execute('SELECT value FROM app_settings WHERE key=?', (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute('''INSERT INTO app_settings (key, value) VALUES (?,?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value''',
                 (key, value))
    conn.commit()
    conn.close()


def get_weekly_snapshots(limit: int = 10):
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM weekly_snapshots ORDER BY captured_at DESC LIMIT ?', (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]  # oldest first for the chart
