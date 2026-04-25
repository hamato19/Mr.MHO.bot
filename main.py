import os
import logging
import secrets
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat, Bot, ChatAdministratorRights
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
# رابط قاعدة البيانات Neon الخاص بك
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- إدارة قاعدة البيانات ---
def get_db():
    return psycopg2.connect(DB_URL)

def init_db():
    """إنشاء الجداول تلقائياً عند التشغيل"""
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

async def get_user_data(uid):
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    user = c.fetchone()
    if not user:
        token = secrets.token_urlsafe(12).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        return await get_user_data(uid)
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    user['entities'] = c.fetchall() or []
    c.close(); conn.close()
    return user

# --- بناء لوحة التحكم ---
async def get_main_menu(u):
    # طلب إضافة قناة مع كامل صلاحيات الإشراف
    admin_rights = ChatAdministratorRights(
        can_post_messages=True,
        can_edit_messages=True,
        can_delete_messages=True,
        can_manage_chat=True,
        can_invite_users=True
    )
    
    reply_kb = ReplyKeyboardMarkup([
        [
            KeyboardButton("📢 إضافة قناة", request_chat=KeyboardButtonRequestChat(
                request_id=1, 
                chat_is_channel=True, 
                bot_administrator_rights=admin_rights,
                user_administrator_rights=admin_rights
            )),
            KeyboardButton("💬 إضافة مجموعة", request_chat=KeyboardButtonRequestChat(
                request_id=2, 
                chat_is_channel=False,
                bot_administrator_rights=admin_rights
            ))
        ]
    ], resize_keyboard=True)
    
    inline_kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📺 قنواتي", callback_data='acc'), InlineKeyboardButton("📢 إضافة قناة", callback_data='info')],
        [InlineKeyboardButton("💬 إضافة مجموعة", callback_data='info')],
        [InlineKeyboardButton("❌ إزالة قناة/مجموعة", callback_data='acc')],
        [InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token'), InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url')],
        [InlineKeyboardButton("▶️ طريقة الاستخدام", callback_data='help'), InlineKeyboardButton("🌍 تغيير اللغة", callback_data='lang')],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", callback_data='support')]
    ]
    return reply_kb, InlineKeyboardMarkup(inline_kb)

# --- المعالجات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_user_data(update.effective_user.id)
    reply_kb, inline_kb = await get_main_menu(u)
    await update.message.reply_text(f"مرحباً بك في نظام الربط الذكي 🤖\nيرجى ربط قناتك أولاً لتتمكن من استقبال الإشارات.", reply_markup=reply_kb, parse_mode=ParseMode.HTML)
    await update.message.reply_text("<b>لوحة التحكم:</b>", reply_markup=inline_kb, parse_mode=ParseMode.HTML)

async def handle_shared_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.message.chat_shared.chat_id
    uid = update.effective_user.id
    try:
        chat = await context.bot.get_chat(cid)
        c_name = chat.title
    except: c_name = f"ID: {cid}"

    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO UPDATE SET entity_name = %s", (uid, str(cid), c_name, c_name))
    conn.commit(); c.close(); conn.close()
    await update.message.reply_text(f"✅ تم ربط <b>{c_name}</b> بنجاح كمشرف!\nيمكنك الآن الحصول على رابط الويب هوك.")

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    u = await get_user_data(uid)
    
    if query.data == 'url':
        # شرط منع إرسال الرابط إذا لم تكن هناك قنوات
        if not u['entities']:
            await query.edit_message_text("⚠️ <b>عذراً!</b>\nلا يمكنك الحصول على رابط الويب هوك قبل إضافة قناة واحدة على الأقل.", reply_markup=query.message.reply_markup, parse_mode=ParseMode.HTML)
        else:
            msg = f"🌐 <b>رابط الويب هوك الخاص بك:</b>\n\n<code>{RENDER_URL}/webhook/{u['secret_token']}</code>\n\nقم بنسخه ووضعه في TradingView."
            await query.edit_message_text(msg, reply_markup=query.message.reply_markup, parse_mode=ParseMode.HTML)
    
    elif query.data == 'gen_token':
        new_token = secrets.token_urlsafe(12).upper()
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, uid))
        conn.commit(); c.close(); conn.close()
        await query.edit_message_text("🔄 تم تحديث رمز الأمان بنجاح!", reply_markup=query.message.reply_markup)

    elif query.data == 'acc':
        entities = "\n".join([f"- {e['entity_name']}" for e in u['entities']]) if u['entities'] else "لا توجد قنوات."
        await query.edit_message_text(f"👤 <b>حسابك:</b> <code>{uid}</code>\n📡 <b>القنوات:</b>\n{entities}", reply_markup=query.message.reply_markup, parse_mode=ParseMode.HTML)

# --- Webhook (TradingView) ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook_handler(token):
    data = request.json
    msg = data.get('message', '🚨 إشارة جديدة!')
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token = %s", (token,))
    user = c.fetchone()
    if user:
        c.execute("SELECT entity_id FROM entities WHERE user_id = %s", (user['user_id'],))
        bot = Bot(token=BOT_TOKEN)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for row in c.fetchall():
            try: loop.run_until_complete(bot.send_message(chat_id=row['entity_id'], text=msg, parse_mode=ParseMode.HTML))
            except: pass
        loop.close()
    c.close(); conn.close()
    return "OK", 200

if __name__ == '__main__':
    init_db()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000))), daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_cb))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_shared_chat))
    application.run_polling()
