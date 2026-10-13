"""Durable OIDC-authenticated Cloud Tasks delivery, never an in-process cloud thread."""
from services.api.core import config


def dispatch(identifier, client=None):
    from google.cloud import tasks_v2
    from google.protobuf.duration_pb2 import Duration
    from google.api_core.exceptions import AlreadyExists
    settings = config.settings
    if not identifier or not settings.tasks_queue or not settings.tasks_target or not settings.tasks_service_account:
        raise RuntimeError('Incomplete Cloud Tasks configuration')
    target = settings.tasks_target.rstrip('/')
    task = {'name': f'{settings.tasks_queue}/tasks/{identifier}',
        'dispatch_deadline': Duration(seconds=settings.tasks_deadline),
        'http_request': {'http_method': tasks_v2.HttpMethod.POST,
            'url': f'{target}/api/investigations/{identifier}/process',
            'oidc_token': {'service_account_email': settings.tasks_service_account, 'audience': settings.auth_audience}}}
    try:
        (client or tasks_v2.CloudTasksClient()).create_task(parent=settings.tasks_queue, task=task, timeout=10)
    except AlreadyExists:
        pass
