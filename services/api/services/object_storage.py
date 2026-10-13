"""Private GCS object storage; no signed/public object URL is exposed."""
from functools import lru_cache
from services.api.core import config


class GcsObjectStore:
    def __init__(self, bucket=None):
        if bucket is None:
            from google.cloud import storage
            bucket = storage.Client(project=config.settings.gcp_project).bucket(config.settings.upload_bucket)
        self.bucket = bucket

    @staticmethod
    def key(name):
        if not name or '/' in name or '\\' in name or name in ('.', '..'):
            raise ValueError('Invalid object reference')
        return f'uploads/{name}'

    def write(self, name, data, mime_type):
        self.bucket.blob(self.key(name)).upload_from_string(data, content_type=mime_type, if_generation_match=0, timeout=30)

    def read(self, name):
        blob = self.bucket.blob(self.key(name))
        blob.reload(timeout=10)
        if blob.size > config.VISUAL_MAX_IMAGE_BYTES:
            raise ValueError('Stored image exceeds the upload budget')
        return blob.download_as_bytes(if_generation_match=blob.generation, timeout=30)

    def exists(self, name):
        return self.bucket.blob(self.key(name)).exists(timeout=10)

    def check(self):
        if not self.bucket.exists(timeout=5, retry=None):
            raise RuntimeError('Upload bucket unavailable')


@lru_cache(maxsize=1)
def object_store():
    return GcsObjectStore()
