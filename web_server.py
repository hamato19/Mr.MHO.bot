# web_server.py
import os
from aiohttp import web

# 1. تعريف الصفحات (الردود)
async def home(request):
    return web.Response(text="🚀 Bot Sumou Al Arqam is Running!", content_type='text/plain')

async def health(request):
    return web.json_response({"status": "ok"})

# 2. إعداد التطبيق والروابط
def create_app():
    app = web.Application()
    app.router.add_get('/', home)
    app.router.add_get('/health', health)
    return app

# 3. دالة التشغيل (يجب أن تكون async)
async def start_server():
    """تشغيل السيرفر بنظام Async ليتوافق مع بايثون 3.14 وبدون Threading"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render يطلب المنفذ 10000 افتراضياً
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    print(f"🌐 Web server started on port {port} (Using aiohttp)")
