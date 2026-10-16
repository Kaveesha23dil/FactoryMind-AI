"""Private Supabase Storage via bounded server-side REST requests; never public URLs."""
from urllib.parse import quote
import httpx
from services.api.core import config
from services.api.services.object_storage import GcsObjectStore


class SupabaseObjectStore:
    def __init__(self, client=None):
        s = config.settings
        self.base = s.supabase_url.rstrip('/')
        self.bucket = s.upload_bucket
        self.headers = {'apikey': s.supabase_service_key, 'Authorization': f'Bearer {s.supabase_service_key}'}
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)

    def path(self, name):
        return f'{quote(self.bucket, safe="")}/{quote(GcsObjectStore.key(name), safe="/")}'

    def check(self):
        response = self.client.get(f'{self.base}/storage/v1/bucket/{quote(self.bucket, safe="")}', headers=self.headers)
        if response.status_code != 200 or response.json().get('public') is not False:
            raise RuntimeError('Supabase evidence bucket is unavailable or not private')

    def write(self, name, data, mime_type):
        if len(data) > config.VISUAL_MAX_IMAGE_BYTES or mime_type not in config.VISUAL_ALLOWED_MIME_TYPES:
            raise ValueError('Invalid evidence upload')
        self.check()
        response = self.client.post(f'{self.base}/storage/v1/object/{self.path(name)}', headers={**self.headers, 'Content-Type': mime_type, 'x-upsert': 'false'}, content=data)
        if response.status_code not in (200, 201):
            raise RuntimeError('Private evidence upload failed')

    def signed_url(self, name, expires=60):
        if not 1 <= expires <= 300:
            raise ValueError('Signed evidence access must expire within five minutes')
        self.check()
        response = self.client.post(f'{self.base}/storage/v1/object/sign/{self.path(name)}', headers=self.headers, json={'expiresIn': expires})
        if response.status_code != 200:
            raise RuntimeError('Private evidence access unavailable')
        path = response.json().get('signedURL', '')
        if not path.startswith('/object/sign/'):
            raise RuntimeError('Invalid storage response')
        return self.base + '/storage/v1' + path

    def read(self, name):
        try:
            return self._read(name)
        except httpx.HTTPError:
            raise RuntimeError('Private evidence transport unavailable') from None

    def _read(self, name):
        # Signed URLs stay server-side; clients receive the authenticated API response.
        with self.client.stream('GET', self.signed_url(name)) as response:
            if response.status_code != 200:
                raise RuntimeError('Private evidence download failed')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > config.VISUAL_MAX_IMAGE_BYTES:
                    raise ValueError('Stored evidence exceeds upload size limit')
                chunks.append(chunk)
            return b''.join(chunks)

    def exists(self, name):
        response = self.client.head(f'{self.base}/storage/v1/object/authenticated/{self.path(name)}', headers=self.headers)
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            raise RuntimeError('Private evidence metadata unavailable')
        return True
