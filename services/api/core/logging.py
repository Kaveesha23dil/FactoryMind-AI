"""Consistent safe JSON logs for API and standalone investigation workers."""
import json
import logging
from datetime import datetime, timezone
from services.api.core import config


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        entry = {'timestamp': datetime.now(timezone.utc).isoformat(),
                 'level': record.levelname, 'logger': record.name, 'message': record.getMessage()}
        if record.exc_info:
            entry['exception'] = self.formatException(record.exc_info)
        if hasattr(record, 'usage'):
            entry.update(record.usage)
        return json.dumps(entry)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logging.basicConfig(level=getattr(logging, config.settings.log_level.upper(), logging.INFO), handlers=[handler])
    # Provider tracebacks can contain responses; use our safe request summaries.
    for dependency in ('google_adk', 'google.adk', 'google_genai', 'google.genai'):
        logging.getLogger(dependency).setLevel(logging.CRITICAL)
