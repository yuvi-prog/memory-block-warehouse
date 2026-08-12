"""
unleashed.py — Unleashed Software API client
HMAC-SHA256 authentication as per Unleashed API docs.
"""
import hmac as _hmac
import hashlib
import base64
import json
import urllib.request
import urllib.parse
import urllib.error
import os
import logging

log      = logging.getLogger(__name__)
BASE_URL = 'https://api.unleashedsoftware.com'


def _sign(api_key: str, query_string: str) -> str:
    return base64.b64encode(
        _hmac.new(
            api_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).digest()
    ).decode('utf-8')


import time as _time

TIMEOUT = 10   # seconds per request
RETRIES = 3    # attempts before giving up


def _get(path: str, params: dict = None) -> dict:
    api_id  = os.environ.get('UNLEASHED_API_ID',  '').strip()
    api_key = os.environ.get('UNLEASHED_API_KEY', '').strip()
    if not api_id or not api_key:
        raise ValueError('UNLEASHED_API_ID and UNLEASHED_API_KEY env vars not set')

    qs  = urllib.parse.urlencode(params or {})
    url = f'{BASE_URL}{path}' + (f'?{qs}' if qs else '')
    sig = _sign(api_key, qs)

    req = urllib.request.Request(url)
    req.add_header('api-auth-id',        api_id)
    req.add_header('api-auth-signature', sig)
    req.add_header('Accept',             'application/json')
    req.add_header('Content-Type',       'application/json')
    req.add_header('client-type',        'MemoryBlockWarehouse/1.0')

    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()
            except Exception: pass
            raise RuntimeError(f'Unleashed API HTTP {e.code}: {body[:300]}')
        except Exception as e:
            last_err = e
            if attempt < RETRIES:
                wait = 2 ** attempt   # 2s, 4s
                log.warning(f'Unleashed API attempt {attempt} failed ({e}), retrying in {wait}s…')
                _time.sleep(wait)

    raise RuntimeError(f'Unleashed API error after {RETRIES} attempts: {last_err}')


def get_completed_orders(start_date: str) -> list:
    """
    Fetch ALL completed sales orders on or after start_date ('yyyy-MM-dd').
    Walks all pages and returns the combined Items list.
    """
    all_items = []
    page = 1
    while True:
        resp  = _get(f'/SalesOrders/{page}', {
            'orderStatus': 'Completed',
            'startDate':   start_date,
            'pageSize':    '200',
        })
        items = resp.get('Items') or []
        all_items.extend(items)

        pagination   = resp.get('Pagination') or {}
        total_pages  = int(pagination.get('NumberOfPages') or 1)
        log.info(f'Unleashed: fetched page {page}/{total_pages} ({len(items)} orders)')
        if page >= total_pages:
            break
        page += 1

    return all_items
