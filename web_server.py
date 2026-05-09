import os
import logging
import asyncio
import aiohttp
from aiohttp import web
import telegram

# إعداد السجلات
logger = logging.getLogger(__name__)

# --- 1. تعريف الردود (Handlers) ---

async def home(request):
    # هذه الصفحة التي يراها ريندر ليعرف أن البوت يعمل
    return web.Response(text="🚀 Bot Sumou Al Arqam is Running & Awake!", content_type='text/plain')

async def health(request):
    return web.json_response({"status": "ok"})

async def tradingview_webhook(request):
    """استقبال الإشارات برابط ديناميكي: /webhook/{token}/{chat_id}"""
    token = request.match_info.get('token')
    chat_id = request.match_info.get('chat_id')
    
    try:
        body = await request.text()
        import config
        bot = telegram.Bot(token=config.BOT_TOKEN)
        
        if body:
            await bot.send_message(
                chat_id=chat_id,
                text=body,
                parse_mode='HTML'
            )
            logger.info(f"✅ Signal sent to channel {chat_id}")
            return web.json_response({"status": "success"})
        else:
            return web.json_response({"status": "error", "message": "Empty body"}, status=400)
    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# --- 2. نظام البقاء مستيقظاً (Self-Ping) ---

async def keep_alive_task():
    """وظيفة تقوم بزيارة رابط البوت كل 10 دقائق لمنع النوم على Render"""
    # انتظر دقيقة قبل بدء أول محاولة للتأكد من تشغيل السيرفر بالكامل
    await asyncio.sleep(60) 
    
    # استبدل هذا بالرابط الخاص بك على ريندر (مهم جداً)
    app_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app-name.onrender.com')}"
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(app_url) as response:
                    if response.status == 200:
                        logger.info("📡 Self-Ping: Stay awake signal sent successfully.")
                    else:
                        logger.warning(f"📡 Self-Ping: Unexpected status {response.status}")
            except Exception as e:
                logger.error(f"📡 Self-Ping Failed: {e}")
            
            # الانتظار 10 دقائق قبل المحاولة التالية
            await asyncio.sleep(600)

# --- 3. إعداد التطبيق والروابط ---

def create_app():
    app = web.Application()
    app.router.add_get('/', home)
    app.router.add_get('/health', health)
    app.router.add_post('/webhook/{token}/{chat_id}', tradingview_webhook)
    return app

async def start_server():
    """تشغيل السيرفر وتفعيل مهمة البقاء مستيقظاً"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render يستخدم المتغير PORT بشكل تلقائي
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    print(f"🌐 Webhook Server active on port {port}")
    
    # تفعيل مهمة الـ Self-Ping في الخلفية
    asyncio.create_task(keep_alive_task())
