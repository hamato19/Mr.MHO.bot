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

# --- دالة جلب البيانات (المعدلة) ---
async def get_user_data(uid):
    # تعريف المتغير user لضمان عدم ظهور خطأ NameError في السطر 50
    user = {"user_id": uid, "lang": "ar"} 
    
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            result = cur.fetchone()
            if result:
                user = result
            else:
                # إذا لم يكن موجوداً، نقوم بإنشاء توكن جديد وحفظه
                token = secrets.token_hex(16)
                cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
                conn.commit()
                user = {"user_id": uid, "secret_token": token, "lang": "ar"}
        conn.close()
    except Exception as e:
        logging.error(f"Database error in get_user_data: {e}")
        
    return user # السطر 50 يعمل الآن بنجاح

# --- دالة القائمة الرئيسية ---
async def get_main_menu(u):
    admin_rights = ChatAdministratorRights(
        is_anonymous=False, can_manage_chat=True, can_post_messages=True,
        can_edit_messages=True, can_delete_messages=True, can_manage_video_chats=True,
        can_restrict_members=True, can_promote_members=True, can_change_info=True,
        can_invite_users=True, can_pin_messages=True
    )
    
    reply_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📢 إضافة قناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True, bot_administrator_rights=admin_rights))],
        [KeyboardButton("💬 إضافة مجموعة", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=False, bot_administrator_rights=admin_rights))]
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
    if not update.message: return
    u = await get_user_data(update.effective_user.id)
    reply_kb, inline_kb = await get_main_menu(u)
    
    welcome_msg = f"مرحباً بك في نظام الربط الذكي 🤖\nيرجى ربط قناتك أولاً لتتمكن من استقبال الإشارات."
    await update.message.reply_text(welcome_msg, reply_markup=reply_kb, parse_mode=ParseMode.HTML)
    await update.message.reply_text("<b>لوحة التحكم:</b>", reply_markup=inline_kb, parse_mode=ParseMode.HTML)

# --- تشغيل Flask ---
@app.route('/')
def index(): return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# --- تشغيل البوت ---
if __name__ == '__main__':
    init_db()
    # تشغيل Flask في خيط منفصل لـ Render
    threading.Thread(target=run_flask, daemon=True).start()
    
    # بناء تطبيق تيليجرام
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    
    logging.info("Application starting...")
    application.run_polling()
