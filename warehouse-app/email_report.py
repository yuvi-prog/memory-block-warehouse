"""
email_report.py — Weekly warehouse snapshot via SendGrid
Scheduled: Monday 09:00 AEST (UTC+10) = Monday 23:00 UTC previous day
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, date

TO_EMAILS = [
    'hd@memoryblock.com.au',
    'admin@memoryblock.com.au',
    'shay@memoryblock.com.au',
    'love@memoryblock.com.au',
    'laki@memoryblock.com.au',
    'lauren@memoryblock.com.au',
]


def _status_badge(fill):
    if fill == 0:   return ('Empty',  '#888888')
    if fill < 30:   return ('Low',    '#e74c3c')
    if fill < 60:   return ('Medium', '#f5c800')
    return               ('Full',   '#27ae60')


def build_html_email(data):
    today       = date.today().strftime('%A, %d %B %Y')
    by_sec      = data['by_section']
    low         = data['low_stock']
    empty       = data['empty_list']
    printer     = data.get('printer', {})
    storage     = data.get('storage', [])
    spare_parts = data.get('spare_parts', [])
    recent      = data['recent_changes']

    # Section summary rows
    section_rows = ''
    for sec in sorted(by_sec.keys()):
        s = by_sec[sec]
        pct_full = round(s['full'] / s['total'] * 100) if s['total'] else 0
        bar_green  = pct_full
        bar_yellow = round(s['medium'] / s['total'] * 100) if s['total'] else 0
        bar_red    = round(s['low']    / s['total'] * 100) if s['total'] else 0
        bar_grey   = max(0, 100 - bar_green - bar_yellow - bar_red)
        section_rows += f'''
        <tr>
          <td style="padding:10px 14px;font-weight:700;font-size:15px">{sec}</td>
          <td style="padding:10px 14px;text-align:center">{s["total"]}</td>
          <td style="padding:10px 14px;text-align:center;color:#27ae60;font-weight:600">{s["full"]}</td>
          <td style="padding:10px 14px;text-align:center;color:#d4ac0d;font-weight:600">{s["medium"]}</td>
          <td style="padding:10px 14px;text-align:center;color:#e74c3c;font-weight:600">{s["low"]}</td>
          <td style="padding:10px 14px;text-align:center;color:#888">{s["empty"]}</td>
          <td style="padding:10px 14px;min-width:120px">
            <div style="display:flex;height:10px;border-radius:5px;overflow:hidden;background:#eee">
              <div style="width:{bar_green}%;background:#27ae60"></div>
              <div style="width:{bar_yellow}%;background:#f5c800"></div>
              <div style="width:{bar_red}%;background:#e74c3c"></div>
              <div style="width:{bar_grey}%;background:#ddd"></div>
            </div>
          </td>
        </tr>'''

    # Low stock rows
    low_rows = ''
    if low:
        for p in low[:20]:
            low_rows += f'''
            <tr>
              <td style="padding:7px 12px;font-weight:600">{p["id"]}</td>
              <td style="padding:7px 12px">Section {p["section"]}</td>
              <td style="padding:7px 12px">{p["name"]}</td>
              <td style="padding:7px 12px">{p["sku"]}</td>
              <td style="padding:7px 12px;color:#e74c3c;font-weight:700">{p["fill"]}%</td>
              <td style="padding:7px 12px">{p["units"]} units</td>
            </tr>'''
    else:
        low_rows = '<tr><td colspan="6" style="padding:14px;text-align:center;color:#27ae60;font-weight:600">✓ No low stock this week</td></tr>'

    # Empty rows
    empty_rows = ''
    if empty:
        for p in empty[:15]:
            empty_rows += f'<tr><td style="padding:6px 12px;font-weight:600">{p["id"]}</td><td style="padding:6px 12px">Section {p["section"]}</td><td style="padding:6px 12px">{p["name"]}</td><td style="padding:6px 12px;color:#888">0%</td></tr>'
    else:
        empty_rows = '<tr><td colspan="4" style="padding:14px;text-align:center;color:#27ae60;font-weight:600">✓ No empty pallets this week</td></tr>'

    # Recent changes
    change_rows = ''
    if recent:
        for r in recent[:10]:
            change_rows += f'''
            <tr>
              <td style="padding:6px 12px;color:#888;font-size:11px;white-space:nowrap">{r["changed_at"]}</td>
              <td style="padding:6px 12px;font-weight:600">{r["pallet_id"]}</td>
              <td style="padding:6px 12px">{r["changed_by"]}</td>
              <td style="padding:6px 12px;color:#888">{r["field"]}</td>
              <td style="padding:6px 12px;color:#e74c3c">{r["old_value"]}</td>
              <td style="padding:6px 12px;color:#27ae60">{r["new_value"]}</td>
            </tr>'''
    else:
        change_rows = '<tr><td colspan="6" style="padding:14px;text-align:center;color:#888">No changes this week</td></tr>'

    # Storage Room rows
    storage_rows = ''
    for s in storage:
        color = '#27ae60' if s['quantity'] > 0 else '#bbb'
        storage_rows += f'''
        <tr>
          <td style="padding:7px 12px;color:#aaa">{s["slot"]}</td>
          <td style="padding:7px 12px;font-weight:{'600' if s['quantity'] > 0 else '400'};color:{'#111' if s['quantity'] > 0 else '#bbb'}">{s["name"] or "—"}</td>
          <td style="padding:7px 12px;font-family:monospace;color:#888;font-size:11px">{s["sku"] or "—"}</td>
          <td style="padding:7px 12px;font-weight:700;color:{color}">{s["quantity"]}</td>
          <td style="padding:7px 12px;color:#aaa;font-size:11px">{s.get("notes","")}</td>
        </tr>'''
    if not storage_rows:
        storage_rows = '<tr><td colspan="5" style="padding:14px;text-align:center;color:#bbb">No storage items</td></tr>'

    # Spare Parts rows
    spare_rows = ''
    for s in spare_parts:
        color = '#27ae60' if s['quantity'] > 0 else '#bbb'
        spare_rows += f'''
        <tr>
          <td style="padding:7px 12px;color:#aaa">{s["slot"]}</td>
          <td style="padding:7px 12px;font-weight:{'600' if s['quantity'] > 0 else '400'};color:{'#111' if s['quantity'] > 0 else '#bbb'}">{s["name"] or "—"}</td>
          <td style="padding:7px 12px;font-family:monospace;color:#888;font-size:11px">{s["sku"] or "—"}</td>
          <td style="padding:7px 12px;font-weight:700;color:{color}">{s["quantity"]}</td>
          <td style="padding:7px 12px;color:#aaa;font-size:11px">{s.get("notes","")}</td>
        </tr>'''
    if not spare_rows:
        spare_rows = '<tr><td colspan="5" style="padding:14px;text-align:center;color:#bbb">No spare parts</td></tr>'

    printer_units = printer.get('units', 0)
    total_pallets = sum(s['total'] for s in by_sec.values())
    total_low     = sum(s['low']   for s in by_sec.values())
    total_empty   = sum(s['empty'] for s in by_sec.values())

    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">

  <!-- Header -->
  <tr><td style="background:#1a1200;padding:28px 32px">
    <div style="font-size:11px;letter-spacing:3px;color:#f5c800;font-weight:800;text-transform:uppercase;margin-bottom:6px">Memory Block</div>
    <div style="font-size:22px;font-weight:700;color:#fff">Weekly Warehouse Report</div>
    <div style="font-size:13px;color:rgba(255,255,255,0.55);margin-top:4px">{today} &nbsp;·&nbsp; 5 Remont Court, Cheltenham VIC</div>
  </td></tr>

  <!-- Summary pills -->
  <tr><td style="padding:24px 32px 0">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="width:25%;padding-right:8px">
        <div style="background:#f8f8f8;border-radius:10px;padding:14px;text-align:center">
          <div style="font-size:28px;font-weight:800;color:#111">{total_pallets}</div>
          <div style="font-size:11px;color:#888;margin-top:2px">Total pallets</div>
        </div>
      </td>
      <td style="width:25%;padding-right:8px">
        <div style="background:#f0fbf4;border-radius:10px;padding:14px;text-align:center;border:1px solid #c3e6cb">
          <div style="font-size:28px;font-weight:800;color:#27ae60">{total_pallets - total_low - total_empty}</div>
          <div style="font-size:11px;color:#27ae60;margin-top:2px">Good stock</div>
        </div>
      </td>
      <td style="width:25%;padding-right:8px">
        <div style="background:#fff8f8;border-radius:10px;padding:14px;text-align:center;border:1px solid #f5c6cb">
          <div style="font-size:28px;font-weight:800;color:#e74c3c">{total_low}</div>
          <div style="font-size:11px;color:#e74c3c;margin-top:2px">Low stock</div>
        </div>
      </td>
      <td style="width:25%">
        <div style="background:#f8f8f8;border-radius:10px;padding:14px;text-align:center;border:1px solid #ddd">
          <div style="font-size:28px;font-weight:800;color:#555">{total_empty}</div>
          <div style="font-size:11px;color:#888;margin-top:2px">Empty bays</div>
        </div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Printer units banner -->
  <tr><td style="padding:16px 32px 0">
    <div style="background:#1a1200;border-radius:10px;padding:14px 20px;display:flex;align-items:center">
      <span style="font-size:13px;color:#f5c800;font-weight:700">🖨 Printer Units in Warehouse:</span>
      <span style="font-size:22px;font-weight:800;color:#fff;margin-left:12px">{printer_units}</span>
    </div>
  </td></tr>

  <!-- Section breakdown -->
  <tr><td style="padding:24px 32px 0">
    <div style="font-size:13px;font-weight:700;color:#111;letter-spacing:0.5px;margin-bottom:10px;text-transform:uppercase">Section Breakdown</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden">
      <thead><tr style="background:#f8f8f8">
        <th style="padding:10px 14px;text-align:left;font-size:11px;color:#888;font-weight:600">SECTION</th>
        <th style="padding:10px 14px;text-align:center;font-size:11px;color:#888;font-weight:600">TOTAL</th>
        <th style="padding:10px 14px;text-align:center;font-size:11px;color:#27ae60;font-weight:600">FULL</th>
        <th style="padding:10px 14px;text-align:center;font-size:11px;color:#d4ac0d;font-weight:600">MED</th>
        <th style="padding:10px 14px;text-align:center;font-size:11px;color:#e74c3c;font-weight:600">LOW</th>
        <th style="padding:10px 14px;text-align:center;font-size:11px;color:#888;font-weight:600">EMPTY</th>
        <th style="padding:10px 14px;font-size:11px;color:#888;font-weight:600">FILL</th>
      </tr></thead>
      <tbody>{section_rows}</tbody>
    </table>
  </td></tr>

  <!-- Low stock alerts -->
  <tr><td style="padding:24px 32px 0">
    <div style="font-size:13px;font-weight:700;color:#e74c3c;letter-spacing:0.5px;margin-bottom:10px;text-transform:uppercase">⚠ Low Stock Alerts</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #fde8e8;border-radius:8px;overflow:hidden">
      <thead><tr style="background:#fff8f8">
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">ID</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">SECTION</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">PRODUCT</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">SKU</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">FILL</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">UNITS</th>
      </tr></thead>
      <tbody>{low_rows}</tbody>
    </table>
  </td></tr>

  <!-- Empty pallets -->
  <tr><td style="padding:20px 32px 0">
    <div style="font-size:13px;font-weight:700;color:#888;letter-spacing:0.5px;margin-bottom:10px;text-transform:uppercase">Empty Bays</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden">
      <thead><tr style="background:#f8f8f8">
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">ID</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">SECTION</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">PRODUCT</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">FILL</th>
      </tr></thead>
      <tbody>{empty_rows}</tbody>
    </table>
  </td></tr>

  <!-- Storage Room -->
  <tr><td style="padding:20px 32px 0">
    <div style="font-size:13px;font-weight:700;color:#111;letter-spacing:0.5px;margin-bottom:10px;text-transform:uppercase">📦 Storage Room</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden">
      <thead><tr style="background:#f8f8f8">
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">#</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">PRODUCT</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">SKU</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">QTY</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">NOTES</th>
      </tr></thead>
      <tbody>{storage_rows}</tbody>
    </table>
  </td></tr>

  <!-- Spare Parts -->
  <tr><td style="padding:20px 32px 0">
    <div style="font-size:13px;font-weight:700;color:#111;letter-spacing:0.5px;margin-bottom:10px;text-transform:uppercase">🔧 Spare Parts</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden">
      <thead><tr style="background:#f8f8f8">
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">#</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">PART</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">SKU</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">QTY</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">NOTES</th>
      </tr></thead>
      <tbody>{spare_rows}</tbody>
    </table>
  </td></tr>

  <!-- Recent changes -->
  <tr><td style="padding:20px 32px 0">
    <div style="font-size:13px;font-weight:700;color:#111;letter-spacing:0.5px;margin-bottom:10px;text-transform:uppercase">Recent Changes</div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden">
      <thead><tr style="background:#f8f8f8">
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">TIME (UTC)</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">PALLET</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">WHO</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">FIELD</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">BEFORE</th>
        <th style="padding:7px 12px;text-align:left;font-size:11px;color:#888;font-weight:600">AFTER</th>
      </tr></thead>
      <tbody>{change_rows}</tbody>
    </table>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:28px 32px;text-align:center">
    <div style="font-size:11px;color:#bbb">Memory Block Warehouse &nbsp;·&nbsp; Auto-generated Monday 9:00 AM AEST</div>
    <div style="font-size:11px;color:#bbb;margin-top:4px">5 Remont Court, Cheltenham VIC 3192</div>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>'''


def send_restock_alert(alerts: list) -> tuple[bool, int, str]:
    """
    Send a restock alert email when L1 pallets drop low or empty after an order.
    alerts = list of dicts with keys: pallet_id, sku, product_name, new_units,
             new_fill, order_number, customer, above_pallets
    """
    api_key    = os.environ.get('SENDGRID_API_KEY', '').strip()
    from_email = os.environ.get('REPORT_FROM_EMAIL', 'admin@memoryblock.com.au').strip()
    if not api_key:
        return False, 0, 'SENDGRID_API_KEY not set'

    today = date.today().strftime('%d %b %Y')

    rows_html = ''
    for a in alerts:
        status     = 'EMPTY — pull stock now' if a['new_fill'] == 0 else f"LOW ({a['new_fill']}% remaining)"
        status_col = '#e74c3c' if a['new_fill'] == 0 else '#d4ac0d'
        above_list = ', '.join(
            f"{p['id']} ({p['fill']}% full)" for p in a.get('above_pallets', []) if p['fill'] > 0
        ) or 'None with stock above'
        rows_html += f'''
        <tr style="border-bottom:1px solid #eee">
          <td style="padding:12px 16px;font-weight:700;font-family:monospace">{a["pallet_id"]}</td>
          <td style="padding:12px 16px">{a["sku"]}</td>
          <td style="padding:12px 16px">{a["product_name"]}</td>
          <td style="padding:12px 16px;font-weight:700;color:{status_col}">{status}</td>
          <td style="padding:12px 16px;color:#555;font-size:12px">{above_list}</td>
        </tr>'''

    order_ref = alerts[0].get('order_number','') if alerts else ''
    customer  = alerts[0].get('customer','') if alerts else ''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
  <tr><td style="background:#7b1200;padding:24px 32px">
    <div style="font-size:11px;letter-spacing:3px;color:#ffb3a7;font-weight:800;text-transform:uppercase;margin-bottom:6px">Memory Block · Warehouse Alert</div>
    <div style="font-size:20px;font-weight:700;color:#fff">⚠ Restock Required</div>
    <div style="font-size:13px;color:rgba(255,255,255,0.6);margin-top:4px">{today} &nbsp;·&nbsp; Order {order_ref} · {customer}</div>
  </td></tr>
  <tr><td style="padding:24px 32px 0">
    <p style="font-size:13px;color:#555;margin-bottom:16px">
      The following L1 pallets need restocking after order <strong>{order_ref}</strong> was completed.
      Pull stock down from L2 or L3 above and update the warehouse map.
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden">
      <thead><tr style="background:#f8f8f8">
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;font-weight:600">PALLET</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;font-weight:600">SKU</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;font-weight:600">PRODUCT</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;font-weight:600">STATUS</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;font-weight:600">STOCK ABOVE</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </td></tr>
  <tr><td style="padding:24px 32px;text-align:center">
    <div style="font-size:11px;color:#bbb">Memory Block Warehouse &nbsp;·&nbsp; Auto-generated restock alert</div>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>'''

    payload = json.dumps({
        'personalizations': [{'to': [{'email': e} for e in TO_EMAILS]}],
        'from': {'email': from_email, 'name': 'Memory Block Warehouse'},
        'subject': f'⚠ Restock Alert — Order {order_ref} · {len(alerts)} pallet(s) low/empty',
        'content': [{'type': 'text/html', 'value': html}],
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=payload,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return True, resp.status, f'Restock alert sent for {len(alerts)} pallet(s)'
    except urllib.error.HTTPError as e:
        body = ''
        try: body = e.read().decode()
        except Exception: pass
        return False, e.code, body[:300]
    except Exception as e:
        return False, 0, str(e)


def send_weekly_report() -> tuple[bool, int, str]:
    """
    Send the weekly warehouse report via SendGrid.
    Returns (success, http_code, detail_message).
    """
    from database import get_weekly_report_data

    # Read env vars at call time so Railway env changes take effect without redeploy
    api_key    = os.environ.get('SENDGRID_API_KEY', '').strip()
    from_email = os.environ.get('REPORT_FROM_EMAIL', 'admin@memoryblock.com.au').strip()

    if not api_key:
        msg = 'SENDGRID_API_KEY is not set — check Railway environment variables'
        print(f'[email] ERROR: {msg}')
        return False, 0, msg

    data    = get_weekly_report_data()
    html    = build_html_email(data)
    today   = date.today().strftime('%d %b %Y')
    subject = f'Memory Block Warehouse Report — {today}'

    payload = json.dumps({
        'personalizations': [{'to': [{'email': e} for e in TO_EMAILS]}],
        'from': {'email': from_email, 'name': 'Memory Block Warehouse'},
        'subject': subject,
        'content': [{'type': 'text/html', 'value': html}],
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            detail = f'Sent to {len(TO_EMAILS)} recipients'
            print(f'[email] SUCCESS HTTP {resp.status}: {detail}')
            return True, resp.status, detail
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()
        except Exception:
            pass
        detail = f'HTTP {e.code}: {body[:300]}'
        print(f'[email] FAILED {detail}')
        return False, e.code, detail
    except Exception as e:
        detail = f'Unexpected error: {e}'
        print(f'[email] ERROR: {detail}')
        return False, 0, detail


if __name__ == '__main__':
    ok, code, msg = send_weekly_report()
    print(f'Result: {"OK" if ok else "FAILED"} (HTTP {code}) — {msg}')
