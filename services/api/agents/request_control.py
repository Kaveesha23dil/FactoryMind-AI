"""Cross-process Gemini request leases, shared by API and standalone worker."""
import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from services.api.core import config
from services.api.db.database import Database


@asynccontextmanager
async def request_slot():
    database = Database()
    database.initialize()
    token = uuid.uuid4().hex
    limit = max(1, config.settings.gemini_concurrency)
    ttl = config.settings.investigation_timeout_seconds + 60
    acquired = False
    try:
        while not acquired:
            now = time.time()
            with database.connect() as connection:
                connection.execute('BEGIN IMMEDIATE')
                connection.execute('DELETE FROM gemini_request_leases WHERE expires_at <= ?', (now,))
                count = connection.execute('SELECT COUNT(*) FROM gemini_request_leases').fetchone()[0]
                if count < limit:
                    connection.execute('INSERT INTO gemini_request_leases VALUES (?, ?)', (token, now + ttl))
                    acquired = True
                connection.commit()
            if not acquired:
                await asyncio.sleep(0.1)
        yield
    finally:
        if acquired:
            with database.connect() as connection:
                connection.execute('DELETE FROM gemini_request_leases WHERE token = ?', (token,))
                connection.commit()


def provider_cooldown(model):
    database = Database()
    database.initialize()
    with database.connect() as connection:
        row = connection.execute('SELECT category,expires_at FROM gemini_provider_cooldowns WHERE model=? AND expires_at>?',
                                 (model, time.time())).fetchone()
    return (row['category'], row['expires_at'] - time.time()) if row else None


def save_cooldown(model, failure):
    delay = failure.retry_after_seconds
    if failure.category in ('RPD', 'spending_limit', 'model_allocation') and not delay:
        # Unknown reset cannot be inferred: short protective cooldown, not a
        # claim that the account quota will reset in five minutes.
        delay = 300
    if not delay or delay <= 60:
        return
    database = Database()
    database.initialize()
    with database.connect() as connection:
        connection.execute('INSERT INTO gemini_provider_cooldowns VALUES (?,?,?) ON CONFLICT(model) DO UPDATE SET category=excluded.category, expires_at=MAX(expires_at,excluded.expires_at)',
                           (model, failure.category, time.time() + delay))
        connection.commit()
