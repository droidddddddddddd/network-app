"""Suppress auth request query strings in the standard uvicorn access log."""
import logging


class AuthQueryFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args)
            if isinstance(args[2], str) and args[2].startswith(("/api/auth/oauth/", "/api/extension/auth/")):
                args[2] = args[2].split("?", 1)[0]
                record.args = tuple(args)
        return True


logging.getLogger("uvicorn.access").addFilter(AuthQueryFilter())
