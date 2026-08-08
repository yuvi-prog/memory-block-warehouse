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

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = ''
        try: body = e.read().decode()
        except Exception: pass
        raise RuntimeError(f'Unleashed API HTTP {e.code}: {body[:300]}')
    except Exception as e:
        raise RuntimeError(f'Unleashed API error: {e}')


def get_completed_orders(start_date: str, page: int = 1) -> dict:
    """
    Fetch completed sales orders on or after start_date ('yyyy-MM-dd').
    Returns Unleashed response with 'Items' list and 'Pagination' dict.
    """
    return _get(f'/SalesOrders/{page}', {
        'orderStatus': 'Completed',
        'startDate':   start_date,
        'pageSize':    '200',
    })
