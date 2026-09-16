"""Vercel entrypoint: exposes the Flask WSGI app for zero-config deployment."""

from webhook_receiver import app

__all__ = ["app"]
