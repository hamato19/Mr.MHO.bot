import os
import logging
from aiohttp import web
import telegram

# إعداد السجلات لمراقبة الإشارات القادمة
logger = logging.getLogger(__name__)

# 1. تعريف الردود (Handlers)

async def home(request):
    return web.Response(text="🚀 Bot Sumou Al Arqam is Running!", content_type='text/plain')

async def health(request):
    return web.json_response({"status": "ok"})

async def tradingview_webhook(request):
    """
    استقبال الإشارات برابط ديناميكي:
    /webhook/{token}/{chat_id}
    """
    token = request.match_info.get('token')
    chat_id = request.match_info.get('chat_id')
    
    try:
        # قراءة محتوى الإشارة (نص من TradingView)
        body = await request.text()
        
        # جلب توكن البوت من ملف الإعدادات لإرسال الرسالة
        import config
        bot = telegram.Bot(token=config.BOT_TOKEN)
        
        if body:
            # إرسال الرسالة إلى القناة المحددة في الرابط
            await bot.send_message(
                chat_id=chat_id,
                text=body,
                parse_mode='HTML'
            )
            logger.info(f"✅ Signal sent to channel {chat_id}")
            return web.json_response({"status": "success", "destination": chat_id})
        else:
            return web.json_response({"status": "error", "message": "Empty body"}, status=400)
            
    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# 2. إعداد التطبيق والروابط المحدثة
def create_app():
    app = web.Application()
    app.router.add_get('/', home)
    app.router.add_get('/health', health)
    
    # إضافة رابط الويب هوك المتغير (Dynamic Route)
    # هذا السطر هو الذي سيحل مشكلة 404
    app.router.add_post('/webhook/{token}/{chat_id}', tradingview_webhook)
    
    return app

# 3. دالة التشغيل
async def start_server():
    """تشغيل السيرفر بنظام Async متوافق مع Render وبايثون 3.12+"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    print(f"🌐 Webhook Server is active on port {port} /webhook/{{token}}/{{chat_id}}")
