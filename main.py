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
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382
DOMAIN = os.getenv('DOMAIN', "https://your-domain.com") # يفضل وضعه في Environment Variables

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# متغير عالمي للـ Loop الأساسي للربط بين الخيوط
main_loop = None

# إعداد مجمع الاتصالات بشكل ثابت
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)

def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- بناء تطبيق التلجرام ---
application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- مسار استقبال رسائل تلجرام (Webhook) المطور ---
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    global main_loop
    try:
        update_data = request.get_json(force=True)
        if main_loop and main_loop.is_running():
            update = Update.de_json(update_data, application.bot)
            # النقل الآمن للمهمة إلى الـ Loop الأساسي لضمان السرعة
            asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
            return 'OK', 200
    except Exception as e:
        logging.error(f"❌ Webhook Error: {e}")
    return 'Error', 500

# --- مسار الويب هوك الخاص بالتداول (TradingView) ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
async def trading_webhook(token, target_id):
    conn = get_db_conn()
    try:
        data = request.get_json()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token = %s AND e.entity_id = %s
            """, (token, str(target_id)))
            if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403

        msg = (f"🔔 <b>تنبيه تداول جديد!</b>\n"
               f"📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n"
               f"💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        
        # إرسال الرسالة مباشرة عبر تطبيق البوت
        await application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML)
        return jsonify({"status": "success"}), 200
    finally:
        release_db_conn(conn)

# --- الدوال المساعدة ---
async def get_user_data(uid):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s) RETURNING *", (uid, token))
                conn.commit()
                user = cur.fetchone()
        return user
    finally: release_db_conn(conn)

async def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📺 قنواتي", callback_data='url')],
        [InlineKeyboardButton("🌐 الويب هوك", callback_data='url'), InlineKeyboardButton("🚀 Alpaca", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", url=f'tg://user?id={ADMIN_ID}')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك في بوت <b>Mr.MHO</b>", 
                                  reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer() # سرعة استجابة فورية للأزرار
    
    user = await get_user_data(uid)
    if query.data == 'acc':
        await query.edit_message_text(f"👤 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{user['secret_token']}</code>", 
                                      parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
    
    elif query.data == 'url':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
            if not ents:
                await query.edit_message_text("❌ لم تضف قنوات بعد.", reply_markup=await get_main_menu())
            else:
                txt = "🌐 روابط الويب هوك:\n\n"
                for e in ents:
                    txt += f"📢 <code>{e['entity_id']}</code>:\n🔗 <code>{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}</code>\n\n"
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
        finally: release_db_conn(conn)

# --- تشغيل البوت والسيرفر بذكاء ---
async def run_bot():
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    # تهيئة تطبيق التلجرام
    await application.initialize()
    await application.start()
    
    # ضبط الويب هوك تلقائياً عند التشغيل
    webhook_path = f"{DOMAIN}/telegram"
    await application.bot.set_webhook(url=webhook_path)
    logging.info(f"✅ Webhook set to {webhook_path}")

    # تشغيل Flask في Thread منفصل
    def start_flask():
        port = int(os.environ.get('PORT', 5000))
        server = make_server('0.0.0.0', port, app)
        server.serve_forever()

    threading.Thread(target=start_flask, daemon=True).start()
    
    # إبقاء البوت يعمل للأبد
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # إضافة Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Stopping...")
