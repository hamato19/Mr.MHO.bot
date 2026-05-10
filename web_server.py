import os
import logging
import asyncio
import aiohttp
from aiohttp import web
import telegram
import database  # استدعاء ملف القاعدة للتحقق من المشتركين
import config

# إعداد السجلات
logger = logging.getLogger(__name__)

# --- 1. تعريف الردود (Handlers) ---

async def home(request):
    """صفحة رئيسية للتأكد من عمل السيرفر"""
    return web.Response(text="🚀 Bot Sumou Al Arqam is Running & Awake!", content_type='text/plain')

async def health(request):
    """رابط فحص الحالة"""
    return web.json_response({"status": "ok"})

async def tradingview_webhook(request):
    """استقبال الإشارات مع نظام التحقق من الاشتراك"""
    token = request.match_info.get('token')
    chat_id = request.match_info.get('chat_id')
    
    try:
        # 1. التحقق من التوكن (الآمان)
        user = database.get_user_by_token(token)
        if not user:
            logger.warning(f"❌ محاولة وصول غير مصرح بها بتوكن: {token}")
            return web.json_response({"status": "error", "message": "Invalid Token"}, status=401)

        uid = user['user_id']

        # 2. التحقق من صلاحية الاشتراك (نظام البيع)
        is_valid, expiry = database.check_subscription(uid)
        if not is_valid:
            logger.info(f"🚫 إشارة محجوبة للمستخدم {uid}: اشتراك منتهي في {expiry}")
            return web.json_response({"status": "error", "message": f"Subscription expired on {expiry}"}, status=403)

        # 3. معالجة بيانات الإشارة
        body = await request.text()
        if not body:
            return web.json_response({"status": "error", "message": "Empty body"}, status=400)

        # إرسال الرسالة عبر البوت
        bot = telegram.Bot(token=config.BOT_TOKEN)
        await bot.send_message(
            chat_id=chat_id,
            text=body,
            parse_mode='HTML'
        )
        
        logger.info(f"✅ تم إرسال الإشارة بنجاح للمشترك {uid} في القناة {chat_id}")
        return web.json_response({"status": "success"})

    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# --- 2. نظام البقاء مستيقظاً (Self-Ping) ---

async def keep_alive_task():
    """منع النوم على منصة Render"""
    await asyncio.sleep(60) 
    app_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app-name.onrender.com')}"
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(app_url) as response:
                    if response.status == 200:
                        logger.info("📡 Self-Ping: OK")
            except:
                pass
            await asyncio.sleep(600) # كل 10 دقائق

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
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    print(f"🌐 Secure Webhook Server active on port {port}")
    
    asyncio.create_task(keep_alive_task())
