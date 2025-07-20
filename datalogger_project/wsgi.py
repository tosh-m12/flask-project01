# wsgi.py
from app import app, start_background_tasks

start_background_tasks()  # ← これを追加
application = app
