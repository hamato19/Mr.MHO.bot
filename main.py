import os, logging, secrets, psycopg2, asyncio, threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- الإعدادات ---
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382
DOMAIN = "https://your-domain.com" # استبدله برابط السيرفر الفعلي

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- إعداد مجمع الاتصالات (Connection Pool) ---
try:
    db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
    logging.info("✅ Database pool connected")
except Exception as e:
    logging.error(f"❌ DB Pool Error: {e}")

def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- الدوال المساعدة وقاعدة البيانات ---
async def get_user_data(uid):
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s) RETURNING *", (uid, token))
                conn.commit()
                user = cur.fetchone()
        return user
    finally:
        if conn: release_db_conn(conn)

def generate_webhook_url(token, entity_id):
    return f"{DOMAIN}/webhook/{token}/{entity_id}"

# --- لوحة التحكم (الأزرار الأصلية) ---
async def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📺 قنواتي", callback_data='my_channels')],
        [InlineKeyboardButton("💬 إضافة مجموعة", callback_data='add_group')],
        [InlineKeyboardButton("❌ إزالة قناة/مجموعة", callback_data='del_entity')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url'), InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token')],
        [InlineKeyboardButton("🌍 تغيير اللغة", callback_data='change_lang'), InlineKeyboardButton("▶️ طريقة الاستخدام", url='https://servernet.ct.ws')],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖🚀", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", url=f'tg://user?id={ADMIN_ID}')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- مسار الـ Webhook الجديد (رابط لكل قناة) ---
@app.route('/webhook/<token>/<int:target_id>', methods=['POST'])
def webhook(token, target_id):
    conn = None
    try:
        data = request.get_json()
        conn = get_db_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token = %s AND e.entity_id = %s
            """, (token, str(target_id)))
            if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403

        msg = (
            f"🔔 <b>تنبيه تداول جديد!</b>\n"
            f"📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
            f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n"
            f"💰 السعر: <code>{data.get('price', 'N/A')}</code>\n"
            f"📝 الرسالة: {data.get('message', '')}"
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML))
        loop.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: release_db_conn(conn)

# --- معالجة الأوامر والأزرار ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك في بوت Mr.MHO!", reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()
    user = await get_user_data(uid)

    if query.data == 'my_channels':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                entities = cur.fetchall()
            if not entities:
                await query.edit_message_text("❌ لم تقم بإضافة أي قنوات بعد.")
            else:
                resp = "📋 <b>روابط الويب هوك لقنواتك:</b>\n\n"
                for ent in entities:
                    url = generate_webhook_url(user['secret_token'], ent['entity_id'])
                    resp += f"📢 قناة <code>{ent['entity_id']}</code>:\n🔗 <code>{url}</code>\n\n"
                await query.edit_message_text(resp, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
        finally: release_db_conn(conn)

    elif query.data == 'url':
        await query.edit_message_text("🌐 اختر 'قنواتي' لنسخ رابط الويب هوك المخصص لكل قناة لديك.", reply_markup=await get_main_menu())

    elif query.data == 'add_channel':
        await query.edit_message_text("📢 أرسل الآن ID القناة (يجب أن يكون البوت أدمن فيها):")
        context.user_data['waiting_for_channel'] = True

# --- تشغيل التطبيق ---
application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_callback))

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    application.run_polling()
