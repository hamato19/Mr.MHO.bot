import os
import logging
import sqlite3
import secrets
import threading
import time
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
import requests
from cryptography.fernet import Fernet

# --- ⚙️ الإعدادات الأساسية (Render Environment) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = "5674313264" 
DB_NAME = "moh_signals.db"

# نظام التشفير
env_key = os.getenv('ELIAS_SECRET_KEY', Fernet.generate_key().decode())
cipher_suite = Fernet(env_key.encode() if isinstance(env_key, str) else env_key)

app = Flask(__name__)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 🛠 إدارة قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 10, total_paid REAL DEFAULT 0.0,
                  alpaca_key TEXT, alpaca_secret TEXT, is_algo_active INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS entities 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                  entity_id TEXT, entity_name TEXT, entity_secret TEXT)''')
    conn.commit()
    conn.close()

# --- 👤 جلب بيانات المستخدم (تم إصلاح خطأ الـ SQL هنا) ---
def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT lang, signals_left, total_paid, secret_token, is_algo_active, alpaca_key, alpaca_secret FROM users WHERE user_id = ?", (uid,))
    res = c.fetchone()
    if not res:
        initial_token = secrets.token_hex(4).upper()
        # ✅ تم التصحيح: 3 علامات استفهام لـ 3 قيم
        c.execute("INSERT INTO users (user_id, signals_left, secret_token) VALUES (?, ?, ?)", (uid, 10, initial_token))
        conn.commit()
        res = ('ar', 10, 0.0, initial_token, 0, None, None)
    
    c.execute("SELECT COUNT(*) FROM entities WHERE user_id = ?", (uid,))
    chans = c.fetchone()[0]
    conn.close()
    return {'lang': res[0], 'sigs': res[1], 'paid': res[2], 'token': res[3], 'algo': res[4], 'key': res[5], 'sec': res[6], 'chans': chans}

# --- 🌍 نظام القائمة والردود ---
def get_main_keyboard(lang):
    app_url = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
    kb = [
        [InlineKeyboardButton("👤 حسابي" if lang=='ar' else "👤 Account", callback_data='acc'), 
         InlineKeyboardButton("🛒 تفعيل الاشتراك" if lang=='ar' else "🛒 Subscribe", callback_data='sub')],
        [InlineKeyboardButton("📊 فتح الشارت (Mini App)" if lang=='ar' else "📊 Open Chart", web_app=WebAppInfo(url=f"{app_url}/chart"))],
        [InlineKeyboardButton("📢 إضافة قناة" if lang=='ar' else "📢 Add Channel", url=f"https://t.me/MOH_SignalsBot?startchannel=true"),
         InlineKeyboardButton("👥 إضافة مجموعة" if lang=='ar' else "👥 Add Group", url=f"https://t.me/MOH_SignalsBot?startgroup=true")],
        [InlineKeyboardButton("🖥 قنواتي" if lang=='ar' else "🖥 My Channels", callback_data='list')],
        [InlineKeyboardButton("🔑 إعدادات Alpaca" if lang=='ar' else "🔑 Alpaca Settings", callback_data='alp_set')],
        [InlineKeyboardButton("🔄 توليد رمز أمان" if lang=='ar' else "🔄 Gen Token", callback_data='gen_tok'), 
         InlineKeyboardButton("🌐 رابط ويب هوك" if lang=='ar' else "🌐 Webhook URL", callback_data='get_hook')],
        [InlineKeyboardButton("🚀 التداول الآلي" if lang=='ar' else "🚀 Auto-Trade", callback_data='tog_algo')],
        [InlineKeyboardButton("🇺🇸 English", callback_data='set_en'), InlineKeyboardButton("🇸🇦 العربية", callback_data='set_ar')],
        [InlineKeyboardButton("☎️ الدعم" if lang=='ar' else "☎️ Support", callback_data='support')]
    ]
    return InlineKeyboardMarkup(kb)

STRINGS = {
    'ar': {'start': "👋 مرحباً بك في <b>MOH_SignalsBot</b>. المنصة جاهزة للعمل:", 'acc': "👤 <b>حسابي:</b>\n- المعرف: <code>{uid}</code>\n- القنوات: {chans}\n- الإشارات: {sigs}\n- المدفوع: ${paid}"},
    'en': {'start': "👋 Welcome to <b>MOH_SignalsBot</b>. Dashboard is ready:", 'acc': "👤 <b>Account:</b>\n- ID: <code>{uid}</code>\n- Channels: {chans}\n- Signals: {sigs}\n- Paid: ${paid}"}
}

# --- ⚡ منع النوم (Keep-Alive) ---
def keep_alive():
    while True:
        try:
            app_url = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
            requests.get(app_url, timeout=10)
        except: pass
        time.sleep(600)

# --- 🌐 مسارات Flask ---
@app.route('/')
def home(): return "MOH_SignalsBot is Active ✅"

@app.route('/chart')
def show_chart():
    return """<!DOCTYPE html><html><body style="margin:0;"><div id="tv" style="height:100vh;"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize":true,"symbol":"NASDAQ:AAPL","theme":"dark","container_id":"tv"});</script></body></html>"""

# --- 🤖 نظام التفاعل ---
def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user(uid)
    update.message.reply_text(STRINGS[u['lang']]['start'], reply_markup=get_main_keyboard(u['lang']), parse_mode=ParseMode.HTML)

def handle_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user(uid)
    query.answer()
    if query.data == 'acc':
        query.edit_message_text(STRINGS[u['lang']]['acc'].format(uid=uid, chans=u['chans'], sigs=u['sigs'], paid=u['paid']), 
                                reply_markup=get_main_keyboard(u['lang']), parse_mode=ParseMode.HTML)

def track_entity(update: Update, context: CallbackContext):
    if update.message and update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                chat = update.message.chat
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (?, ?, ?)", (update.message.from_user.id, str(chat.id), chat.title))
                conn.commit()
                conn.close()

# --- 🚀 تشغيل المحرك ---
if __name__ == '__main__':
    init_db()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # تشغيل Flask في خيط منفصل
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    
    up = Updater(BOT_TOKEN, use_context=True)
    dp = up.dispatcher
    
    # حذف الويب هوك القديم برمجياً لضمان الاستجابة
    up.bot.delete_webhook()
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_buttons))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, track_entity))
    
    logging.info("Bot is Polling...")
    up.start_polling(drop_pending_updates=True)
    up.idle()
