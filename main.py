import os
import logging
import secrets
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat, ChatAdministratorRights
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- إدارة قاعدة البيانات ---
def get_db():
    return psycopg2.connect(DB_URL)

def init_db():
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
            random_tag TEXT UNIQUE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    conn.commit(); c.close(); conn.close()

# --- جلب بيانات المستخدم وتوليد توكن ---
async def get_main_menu(u):
    # أزرار الكيبورد السفلي (التي تفتح قائمة القنوات الخارجية)
    reply_kb = ReplyKeyboardMarkup([
        [
            KeyboardButton("📢 إضافة قناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True)),
            KeyboardButton("💬 إضافة مجموعة", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=False))
        ]
    ], resize_keyboard=True)

    # أزرار لوحة التحكم (التي تظهر تحت الرسالة) - منسقة زرين في كل صف
    inline_kb = [
        [
            InlineKeyboardButton("👤 حسابي", callback_data='acc'),
            InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')
        ],
        [
            InlineKeyboardButton("📺 قنواتي", callback_data='acc'),
            InlineKeyboardButton("📢 إضافة قناة", callback_data='info')
        ],
        [
            InlineKeyboardButton("💬 إضافة مجموعة", callback_data='info'),
            InlineKeyboardButton("❌ إزالة قناة/مجموعة", callback_data='acc')
        ],
        [
            InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token'),
            InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url')
        ],
        [
            InlineKeyboardButton("▶️ طريقة الاستخدام", callback_data='help'),
            InlineKeyboardButton("🌍 تغيير اللغة", callback_data='lang')
        ],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", callback_data='support')]
    ]
    return reply_kb, InlineKeyboardMarkup(inline_kb)


# --- معالجة اختيار القناة وربطها ---
async def handle_entity_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared_chat = update.message.chat_shared if update.message.chat_shared else update.message.user_shared
    if not shared_chat: return

    uid = update.effective_user.id
    entity_id = str(shared_chat.chat_id)
    random_id = secrets.token_hex(4).upper() # توليد ID عشوائي للقناة
    
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO entities (user_id, entity_id, random_tag) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (entity_id) DO NOTHING
        """, (uid, entity_id, random_id))
        conn.commit(); cur.close(); conn.close()
        
        await update.message.reply_text(
            f"✅ تم ربط القناة بنجاح!\n\n"
            f"🆔 معرف القناة: <code>{entity_id}</code>\n"
            f"🔑 الكود العشوائي: <code>{random_id}</code>\n\n"
            f"تأكد الآن من رفع البوت رتبة 'مشرف' في القناة لضمان وصول الرسائل.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء الربط: {e}")

# --- الأوامر الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_user_data(update.effective_user.id)
    reply_kb, inline_kb = await get_main_menu(u)
    await update.message.reply_text("مرحباً بك في نظام الربط الذكي 🤖\nاضغط على الزر أدناه لاختيار قناتك:", reply_markup=reply_kb)
    await update.message.reply_text("<b>لوحة التحكم:</b>", reply_markup=inline_kb, parse_mode=ParseMode.HTML)

# --- تشغيل السيرفر ---
@app.route('/')
def index(): return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    # معالج لاستقبال بيانات القناة المختارة من واجهة تيليجرام
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_entity_shared))
    
    application.run_polling()
