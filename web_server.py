# web_server.py
import os
import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Bot Sumou Al Arqam is Running!"

@app.route('/health')
def health():
    return {"status": "ok"}, 200

def run():
    # Render يعطي المنفذ عبر متغير البيئة PORT، وإذا لم يوجد يستخدم 10000
    port = int(os.environ.get("PORT", 10000))
    # تعطيل الـ reloader مهم جداً عند التشغيل داخل Thread
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def start_server():
    """تشغيل السيرفر في خلفية مستقلة (Thread) لضمان عدم توقف البوت"""
    server_thread = threading.Thread(target=run, daemon=True)
    server_thread.start()
