# Zuper-data

pulling zuper data

A unidirectional Waiting-on-Parts notify service lives in [`zuper-wop-notify/`](zuper-wop-notify/). It receives Zuper webhooks, GETs job detail (read-only), and fans JSON out to Shop Manager Bot and Parts Bot. See that folder’s README for env, gunicorn deploy, and webhook setup.
