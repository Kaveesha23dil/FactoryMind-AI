"""Portable single-workspace authentication and persisted expensive-operation limits."""
from datetime import datetime, timezone
import httpx
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from services.api.core import config


def verify_user(token):
    s = config.settings
    # Auth's getUser verifies JWT signature/expiry/revocation, including legacy HS256.
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        response = client.get(s.supabase_url.rstrip('/') + '/auth/v1/user',
            headers={'apikey': s.supabase_anon_key, 'Authorization': f'Bearer {token}'})
        response.raise_for_status()
        user = response.json()
    if not user.get('id') or not user.get('email_confirmed_at'):
        raise ValueError('Confirmed Supabase user required')
    return user['id']


def consume_ai_budget(principal):
    from services.api.db.postgres import PostgresDatabase
    day = datetime.now(timezone.utc).date().isoformat()
    with PostgresDatabase().connect() as connection:
        connection.execute('SELECT pg_advisory_xact_lock(71192002)')
        row = connection.execute('SELECT requests FROM portable_ai_usage WHERE day=? AND principal=?', (day, principal)).fetchone()
        if row and row['requests'] >= config.settings.portable_daily_limit:
            return False
        connection.execute('INSERT INTO portable_ai_usage VALUES(?,?,1) ON CONFLICT(day,principal) DO UPDATE SET requests=portable_ai_usage.requests+1', (day, principal))
        connection.commit()
    return True


async def authorize_portable(request, call_next):
    s = config.settings
    value = request.headers.get('Authorization', '')
    if not value.startswith('Bearer ') or len(value) > 16384:
        return JSONResponse({'detail': 'Sign in to the demo workspace'}, status_code=401)
    try:
        principal = await run_in_threadpool(verify_user, value[7:])
    except Exception:
        return JSONResponse({'detail': 'Invalid, expired or unverifiable user session'}, status_code=401)
    if principal not in set(s.portable_readers + s.portable_writers):
        return JSONResponse({'detail': 'This user is not a member of the demo workspace'}, status_code=403)
    if request.url.path.endswith('/process'):
        return JSONResponse({'detail': 'Cloud Tasks endpoint is unavailable in portable mode'}, status_code=403)
    write = request.method not in ('GET', 'HEAD', 'OPTIONS')
    if write and (not s.portable_writes_enabled or principal not in s.portable_writers):
        return JSONResponse({'detail': 'Presenter write access is required; this workspace may be read-only'}, status_code=403)
    if write and request.url.path.endswith(('/investigate', '/counterfactual', '/analyze', '/execute')):
        if not s.ai_investigation_enabled:
            return JSONResponse({'detail': 'Live AI execution is disabled for this demo'}, status_code=503)
        if not await run_in_threadpool(consume_ai_budget, principal):
            return JSONResponse({'detail': 'Daily workspace AI-operation limit reached'}, status_code=429, headers={'Retry-After': '86400'})
    request.state.principal = principal
    return await call_next(request)
