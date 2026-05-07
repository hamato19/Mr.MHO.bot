# web_server.py
import os
import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!"

@app.route('/health')
def health():
    return {"status": "ok"}, 200

def run():
    # Render يعطي المنفذ عبر متغير البيئة PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def start_server():
    """تشغيل السيرفر في خلفية مستقلة (Thread)"""
    server_thread = threading.Thread(target=run, daemon=True)
    server_thread.start()
