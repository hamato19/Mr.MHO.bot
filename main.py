import os
import logging
import secrets
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat, Bot
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
# الرابط الذي زودتني به لـ Neon.tech
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- إدارة قاعدة البيانات ---
def get_db():
    return psycopg2.connect(DB_URL)

def init_db():
    """إنشاء الجداول في Neon.tech عند التشغيل"""
    conn = get_db(); c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            secret_token TEXT UNIQUE,
            lang TEXT DEFAULT 'ar'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            entity_id TEXT UNIQUE,
            entity_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    conn.commit(); c.close(); conn.close()

async def get_user_full_data(uid):
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    user = c.fetchone()
    if not user:
        token = secrets.token_urlsafe(12).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        return await get_user_full_data(uid)
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    user['chans'] = c.fetchall() or []
    c.close(); conn.close()
    return user

# --- القوائم ---
async def get_menus(u):
    has_chans = len(u['chans']) > 0
    reply_kb = ReplyKeyboardMarkup([
        [KeyboardButton("➕ ربط قناة جديدة", request_chat=KeyboardButtonRequestChat(
            request_id=100, chat_is_channel=True, user_administrator_rights={"can_post_messages": True}, bot_administrator_rights={"can_post_messages": True}
        ))]
    ], resize_keyboard=True)
    
    inline_kb = [[InlineKeyboardButton("👤 حسابي", callback_data='acc')]]
    if has_chans:
        inline_kb.append([InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url')])
    else:
        inline_kb.append([InlineKeyboardButton("🔄 تحديث البيانات", callback_data='refresh')])
    return reply_kb, InlineKeyboardMarkup(inline_kb)

# --- معالجة الربط التلقائي ---
async def handle_shared_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_shared:
        cid = update.message.chat_shared.chat_id
        uid = update.effective_user.id
        try:
            chat_obj = await context.bot.get_chat(cid)
            c_name = chat_obj.title
        except:
            c_name = f"قناة {cid}"

        conn = get_db(); c = conn.cursor()
        c.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO UPDATE SET user_id = %s, entity_name = %s", (uid, str(cid), c_name, uid, c_name))
        conn.commit(); c.close(); conn.close()
        
        await asyncio.sleep(1) # تأمين وقت الحفظ في السحابة
        u = await get_user_full_data(uid)
        _, inline_kb = await get_menus(u)
        await update.message.reply_text(f"✅ تم ربط <b>{c_name}</b> بنجاح بقاعدة البيانات الخارجية!", reply_markup=inline_kb, parse_mode=ParseMode.HTML)

# --- الأوامر المعتادة ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_user_full_data(update.effective_user.id)
    reply_kb, inline_kb = await get_menus(u)
    await update.message.reply_text("👋 <b>نظام MrMOH الذكي</b>\nاضغط بالأسفل لربط قناتك:", reply_markup=reply_kb, parse_mode=ParseMode.HTML)
    await update.message.reply_text("لوحة التحكم:", reply_markup=inline_kb)

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    u = await get_user_full_data(uid)
    _, inline_kb = await get_menus(u)

    if query.data == 'url':
        await query.edit_message_text(f"🌐 <b>الويب هوك:</b>\n<code>{RENDER_URL}/webhook/{u['secret_token']}</code>", reply_markup=inline_kb, parse_mode=ParseMode.HTML)
    elif query.data == 'acc':
        names = "\n- ".join([c['entity_name'] for c in u['chans']]) if u['chans'] else "لا يوجد"
        await query.edit_message_text(f"👤 حسابك: {uid}\n📡 القنوات:\n- {names}", reply_markup=inline_kb)
    elif query.data == 'refresh':
        await query.edit_message_text("✅ تم تحديث البيانات من Neon.tech", reply_markup=inline_kb)

# --- Webhook لاستقبال إشارات TradingView ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook_api(token):
    temp_bot = Bot(token=BOT_TOKEN)
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token=%s", (token,))
    user = c.fetchone()
    if user:
        c.execute("SELECT entity_id FROM entities WHERE user_id=%s", (user['user_id'],))
        for row in c.fetchall():
            msg = request.json.get('message', '🚨 إشارة جديدة!')
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(temp_bot.send_message(row['entity_id'], msg, parse_mode=ParseMode.HTML))
                loop.close()
            except: pass
    c.close(); conn.close()
    return {"status": "ok"}

if __name__ == '__main__':
    init_db() # تفعيل الجداول في Neon عند التشغيل
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000))), daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_cb))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_shared_chat))
    application.run_polling()
