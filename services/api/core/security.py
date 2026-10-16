"""Verified Google OIDC service principals; local development stays unchanged."""
from google.oauth2 import id_token
from google.auth.transport.requests import Request as GoogleRequest
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from services.api.core import config


async def authorize(request, call_next):
    if config.settings.app_env != 'production' or request.url.path in ('/healthz', '/readyz') or request.method == 'OPTIONS':
        return await call_next(request)
    if config.settings.deployment_target == 'render':
        from services.api.core.portable import authorize_portable
        return await authorize_portable(request, call_next)
    value = request.headers.get('Authorization', '')
    if not value.startswith('Bearer '):
        return JSONResponse({'detail': 'Authentication required'}, status_code=401)
    try:
        claims = await run_in_threadpool(id_token.verify_oauth2_token, value[7:], GoogleRequest(), config.settings.auth_audience)
        email = claims.get('email')
        worker_path = request.url.path.startswith('/api/investigations/') and request.url.path.endswith('/process')
        allowed = config.settings.worker_callers if worker_path else config.settings.api_callers
        if claims.get('email_verified') is not True or email not in allowed:
            return JSONResponse({'detail': 'Principal is not authorized for this operation'}, status_code=403)
        request.state.principal = email
    except Exception:
        return JSONResponse({'detail': 'Invalid or expired authentication token'}, status_code=401)
    return await call_next(request)
