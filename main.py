import os
import logging
import secrets
import asyncio
import threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from werkzeug.serving import make_server

# --- الإعدادات ---
DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com") 

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# متغير عالمي لتخزين الـ Loop
main_loop = None

# --- قاعدة البيانات ---
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- النصوص والدوال المساعدة ---
STRINGS = {
    'العربية': {
        'start_msg': "👋 أهلاً بك في بوت <b>Mr.MHO</b>",
        'main_menu': "🏠 القائمة الرئيسية لبوت <b>Mr.MHO</b>",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{token}</code>",
        'btns': {'acc': "👤 حسابي", 'home': "🏠 الرئيسية", 'url': "🌐 الويب هوك"}
    }
}

async def get_user_data(uid):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s) RETURNING *", (uid, token, 'العربية'))
                conn.commit()
                user = cur.fetchone()
        return user
    finally: release_db_conn(conn)

async def get_main_menu(lang='العربية'):
    B = STRINGS['العربية']['btns']
    keyboard = [[InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['url'], callback_data='url')]]
    return InlineKeyboardMarkup(keyboard)

# --- بناء تطبيق التلجرام ---
application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- مسارات Flask ---
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    global main_loop
    try:
        update_data = request.get_json(force=True)
        if main_loop and main_loop.is_running():
            update = Update.de_json(update_data, application.bot)
            # استخدام المتغير العالمي main_loop بدلاً من الـ attribute المحمي
            asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
            return 'OK', 200
        return 'Loop not ready', 503
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return 'Error', 500

@app.route('/')
def index(): return "Bot is Running!", 200

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_data(update.effective_user.id)
    await update.message.reply_text(STRINGS['العربية']['start_msg'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

application.add_handler(CommandHandler("start", start))

# --- تشغيل موحد (The Bridge) ---
async def run_bot():
    global main_loop
    await application.initialize()
    
    # حفظ الـ Loop الحالي في المتغير العالمي
    main_loop = asyncio.get_running_loop()
    
    # ضبط الويب هوك
    await application.bot.set_webhook(url=f"{DOMAIN}/telegram")
    await application.start()
    logging.info("✅ Bot & Webhook Started Successfully.")
    
    # تشغيل Flask في Thread منفصل مع استخدام مخدّم Werkzeug مستقر
    def run_flask():
        port = int(os.environ.get('PORT', 10000))
        server = make_server('0.0.0.0', port, app)
        server.serve_forever()

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info(f"🚀 Flask Server running on port {os.environ.get('PORT', 10000)}")

    # إبقاء البوت يعمل
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot Stopped.")
