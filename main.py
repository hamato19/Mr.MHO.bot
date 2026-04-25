import os
import logging
import secrets
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def get_db():
    return psycopg2.connect(DB_URL)

# --- جلب بيانات المستخدم ---
async def get_user_data(uid):
    user = {"user_id": uid, "lang": "ar"}
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            result = cur.fetchone()
            if not result:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
                conn.commit()
                user = {"user_id": uid, "secret_token": token, "lang": "ar"}
            else:
                user = result
        conn.close()
    except Exception as e:
        logging.error(f"DB Error: {e}")
    return user

# --- القائمة الرئيسية (تنسيق زرين في الصف) ---
async def get_main_menu(u):
    reply_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📢 إضافة قناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True)),
         KeyboardButton("💬 إضافة مجموعة", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=False))]
    ], resize_keyboard=True)

    inline_kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📺 قنواتي", callback_data='acc'), InlineKeyboardButton("📢 إضافة قناة", callback_data='info')],
        [InlineKeyboardButton("💬 إضافة مجموعة", callback_data='info'), InlineKeyboardButton("❌ إزالة قناة/مجموعة", callback_data='acc')],
        [InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token'), InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url')],
        [InlineKeyboardButton("▶️ طريقة الاستخدام", callback_data='help'), InlineKeyboardButton("🌍 تغيير اللغة", callback_data='lang')],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", callback_data='support')]
    ]
    return reply_kb, InlineKeyboardMarkup(inline_kb)

# --- معالج ضغطات الأزرار (تفعيل الأزرار) ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # لإزالة علامة التحميل من الزر
    
    data = query.data
    u = await get_user_data(update.effective_user.id)

    if data == 'acc':
        await query.edit_message_text(f"👤 <b>معلومات حسابك:</b>\n\nID: <code>{u['user_id']}</code>\nToken: <code>{u.get('secret_token', 'N/A')}</code>", parse_mode=ParseMode.HTML, reply_markup=query.message.reply_markup)
    elif data == 'url':
        webhook_url = f"https://mr-mho-bot.onrender.com/webhook/{u.get('secret_token')}"
        await query.edit_message_text(f"🌐 <b>رابط الويب هوك الخاص بك:</b>\n\n<code>{webhook_url}</code>", parse_mode=ParseMode.HTML, reply_markup=query.message.reply_markup)
    elif data == 'support':
        await query.edit_message_text("☎️ للدعم الفني تواصل مع: @YourSupportHandle", reply_markup=query.message.reply_markup)
    else:
        await query.edit_message_text(f"الزر {data} قيد التطوير حالياً ⚠️", reply_markup=query.message.reply_markup)

# --- الأوامر الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_user_data(update.effective_user.id)
    reply_kb, inline_kb = await get_main_menu(u)
    await update.message.reply_text("مرحباً بك في نظام الربط الذكي 🤖", reply_markup=reply_kb)
    await update.message.reply_text("<b>لوحة التحكم:</b>", reply_markup=inline_kb, parse_mode=ParseMode.HTML)

# --- Flask لـ Render ---
@app.route('/')
def index(): return "Bot is running!"

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # ربط المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback)) # هذا السطر يفعل الأزرار
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, lambda u, c: None)) # أضف دالة الربط هنا لاحقاً
    
    application.run_polling()
