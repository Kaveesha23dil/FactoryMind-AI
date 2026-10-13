"""Shared Firestore request leases and cooldowns for Cloud Run instances."""
import hashlib
import time
from services.api.core import config
from services.api.services.firestore_repository import FirestoreRepository


def acquire(token, ttl):
    store = FirestoreRepository('request_controls', 'control_id')
    ref = store.collection.document('gemini-concurrency')
    def operation(tx):
        snapshot = ref.get(transaction=tx)
        live = {k:v for k,v in (snapshot.to_dict() if snapshot.exists else {}).get('leases', {}).items() if v > time.time()}
        if len(live) >= config.settings.gemini_concurrency:
            return False
        live[token] = time.time()+ttl
        tx.set(ref, {'leases': live})
        return True
    return store._tx(operation)


def release(token):
    store = FirestoreRepository('request_controls', 'control_id')
    ref = store.collection.document('gemini-concurrency')
    def operation(tx):
        snapshot = ref.get(transaction=tx)
        live = (snapshot.to_dict() if snapshot.exists else {}).get('leases', {})
        live.pop(token, None)
        tx.set(ref, {'leases': live})
    store._tx(operation)


def cooldown(model):
    store = FirestoreRepository('provider_cooldowns', 'control_id')
    record = store.get(hashlib.sha256(model.encode()).hexdigest())
    if record and record['expires_at'] > time.time():
        return record['category'], record['expires_at']-time.time()
    return None


def save(model, category, delay):
    store = FirestoreRepository('provider_cooldowns', 'control_id')
    ref = store.collection.document(hashlib.sha256(model.encode()).hexdigest())
    def operation(tx):
        snapshot = ref.get(transaction=tx)
        previous = snapshot.to_dict() if snapshot.exists else {}
        tx.set(ref, {'category':category, 'expires_at':max(previous.get('expires_at', 0), time.time()+delay)})
    store._tx(operation)
