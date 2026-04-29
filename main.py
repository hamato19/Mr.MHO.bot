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
DOMAIN = "https://your-domain.com" # ضع رابط سيرفرك هنا

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# إعداد مجمع الاتصالات
try:
    db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
    logging.info("✅ Database pool connected")
except Exception as e:
    logging.error(f"❌ DB Pool Error: {e}")

def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- الدوال المساعدة ---
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

async def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📺 قنواتي", callback_data='my_channels')],
        [InlineKeyboardButton("💬 إضافة مجموعة", callback_data='add_group')],
        [InlineKeyboardButton("❌ إزالة قناة محدودة", callback_data='del_menu')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='home'), InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token')],
        [InlineKeyboardButton("🌍 تغيير اللغة", callback_data='change_lang'), InlineKeyboardButton("▶️ طريقة الاستخدام", url='https://servernet.ct.ws')],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖🚀", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", url=f'tg://user?id={ADMIN_ID}')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- مسار الـ Webhook الموحد لكل القنوات ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def webhook(token, target_id):
    conn = None
    try:
        data = request.get_json()
        conn = get_db_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # التحقق من ملكية التوكن والقناة
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token = %s AND e.entity_id = %s
            """, (token, str(target_id)))
            if not cur.fetchone(): 
                return jsonify({"status": "unauthorized"}), 403

        # تجهيز الرسالة
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

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك في بوت <b>Mr.MHO</b>", reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, text = update.effective_user.id, update.message.text
    state = context.user_data.get('state')
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            if state == 'wait_ch':
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (uid, text))
                conn.commit()
                await update.message.reply_text("✅ تم إضافة القناة بنجاح!", reply_markup=await get_main_menu())
            elif state == 'wait_key':
                cur.execute("UPDATE users SET alpaca_key_id = %s WHERE user_id = %s", (text, uid))
                conn.commit()
                await update.message.reply_text("✅ تم حفظ Alpaca Key ID.")
            elif state == 'wait_sec':
                cur.execute("UPDATE users SET alpaca_secret_key = %s WHERE user_id = %s", (text, uid))
                conn.commit()
                await update.message.reply_text("✅ تم حفظ Alpaca Secret Key.")
    finally:
        release_db_conn(conn)
        context.user_data['state'] = None

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; uid = update.effective_user.id
    await query.answer(); user = await get_user_data(uid)

    if query.data == 'acc':
        await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{user['secret_token']}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())

    elif query.data == 'del_menu':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
            if not ents: await query.edit_message_text("❌ لا توجد قنوات لحذفها.")
            else:
                kb = [[InlineKeyboardButton(f"🗑 حذف: {e['entity_id']}", callback_data=f"remove_{e['entity_id']}")] for e in ents]
                kb.append([InlineKeyboardButton("🔙 عودة", callback_data='home')])
                await query.edit_message_text("❌ اختر القناة لإزالتها:", reply_markup=InlineKeyboardMarkup(kb))
        finally: release_db_conn(conn)

    elif query.data.startswith('remove_'):
        target_id = query.data.split('_')[1]
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (uid, target_id))
                conn.commit()
            await query.edit_message_text(f"✅ تم إزالة القناة <code>{target_id}</code>.", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
        finally: release_db_conn(conn)

    elif query.data == 'my_channels':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
            if not ents: await query.edit_message_text("❌ لا يوجد قنوات.")
            else:
                txt = "📋 <b>روابط الويب هوك:</b>\n\n"
                for e in ents: 
                    txt += f"📢 القناة: <code>{e['entity_id']}</code>\n🔗 الرابط: <code>{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}</code>\n\n"
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
        finally: release_db_conn(conn)

    elif query.data == 'add_channel':
        await query.edit_message_text("📢 أرسل ID القناة (مثلاً: -100xxxxxxxx):")
        context.user_data['state'] = 'wait_ch'

    elif query.data == 'gen_token':
        new_t = secrets.token_hex(8)
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_t, uid))
                conn.commit()
            await query.edit_message_text(f"🔄 تم تحديث التوكن: <code>{new_t}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
        finally: release_db_conn(conn)

    elif query.data == 'alpaca':
        kb = [[InlineKeyboardButton("🔑 Key ID", callback_data='set_k'), InlineKeyboardButton("🔐 Secret Key", callback_data='set_s')], [InlineKeyboardButton("🔙 عودة", callback_data='home')]]
        await query.edit_message_text("🚀 إعدادات Alpaca لربط التداول:", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data in ['set_k', 'set_s']:
        await query.edit_message_text("📝 أرسل المفتاح الآن:"); context.user_data['state'] = 'wait_key' if query.data == 'set_k' else 'wait_sec'

    elif query.data == 'home':
        await query.edit_message_text("🏠 القائمة الرئيسية", reply_markup=await get_main_menu())

# --- تشغيل التطبيق ---
application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    application.run_polling()
