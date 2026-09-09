"""Vercel Flask entry point.

Vercel detects the WSGI application exported as ``app`` from ``src/app.py``.
All route and application logic remains in backend.app.
"""

from backend.app import app
