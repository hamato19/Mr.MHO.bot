import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
import requests
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, Bot
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

# --- الإعدادات الأساسية ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
ALPACA_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET_KEY')
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# --- إدارة قاعدة البيانات ---
def get_db():
    try:
        return psycopg2.connect(DB_URL, sslmode='require')
    except:
        return None

def init_db():
    conn = get_db()
    if conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar', state TEXT DEFAULT 'IDLE')")
        c.execute("CREATE TABLE IF NOT EXISTS entities (id SERIAL PRIMARY KEY, user_id BIGINT, entity_id TEXT UNIQUE, entity_name TEXT)")
        conn.commit(); c.close(); conn.close()

def get_user(uid):
    conn = get_db()
    if not conn: return None
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res:
        token = secrets.token_urlsafe(12).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        return get_user(uid)
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    res['chans'] = c.fetchall() or []
    c.close(); conn.close()
    return res

# --- لوحة التحكم ---
def main_kb(u):
    l = u['lang']
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 " + ("حسابي" if l=='ar' else "Account"), callback_data='acc')],
        [InlineKeyboardButton("📈 " + ("تحليل الأسهم" if l=='ar' else "AI Analysis"), callback_data='analyze')],
        [InlineKeyboardButton("🌐 " + ("رابط الويب هوك" if l=='ar' else "Webhook URL"), callback_data='url')],
        [InlineKeyboardButton("🇸🇦 / 🇺🇸 Change Language", callback_data='lang')]
    ])

# --- معالجات تليجرام ---
def start(update, context):
    u = get_user(update.effective_user.id)
    if u: update.message.reply_text("👋 <b>MOH Engine</b>\nالنظام متصل وقاعد البيانات جاهزة.", reply_markup=main_kb(u), parse_mode='HTML')

def handle_cb(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)
    l = u['lang']
    q.answer()

    if q.data == 'acc':
        txt = f"👤 <b>حسابي</b>\n\nID: <code>{u['user_id']}</code>\nالقنوات: {len(u['chans'])}\nالتوكن: <code>{u['secret_token']}</code>"
        q.edit_message_text(txt, reply_markup=main_kb(u), parse_mode='HTML')
    elif q.data == 'url':
        q.edit_message_text(f"🌐 <b>رابط الويب هوك:</b>\n\n<code>{RENDER_URL}/webhook/{u['secret_token']}</code>", reply_markup=main_kb(u), parse_mode='HTML')
    elif q.data == 'analyze':
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE users SET state='AWAIT' WHERE user_id=%s", (u['user_id'],)); conn.commit(); c.close(); conn.close()
        q.edit_message_text("✍️ أرسل رمز السهم (مثال: AAPL):", reply_markup=main_kb(u))

def handle_msg(update, context):
    uid = update.effective_user.id
    chat = update.effective_chat
    
    # ربط القناة تلقائياً
    if chat.type != 'private':
        conn = get_db(); c = conn.cursor()
        c.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO NOTHING", (uid, str(chat.id), chat.title))
        conn.commit(); c.close(); conn.close()
        return

    u = get_user(uid)
    if u and u['state'] == 'AWAIT':
        sym = update.message.text.upper()
        h = {'APCA-API-KEY-ID': ALPACA_KEY, 'APCA-API-SECRET-KEY': ALPACA_SECRET}
        try:
            r = requests.get(f"https://data.alpaca.markets/v2/stocks/{sym}/quotes/latest", headers=h)
            p = r.json().get('quote', {}).get('ap', 'N/A')
            update.message.reply_text(f"📊 <b>{sym}</b>\nالسعر: <code>${p}</code>", parse_mode='HTML', reply_markup=main_kb(u))
        except: update.message.reply_text("❌ خطأ في جلب البيانات.")
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE users SET state='IDLE' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()

# --- نظام الويب هوك (Flask) ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token=%s", (token,))
    u = c.fetchone()
    if u:
        c.execute("SELECT entity_id FROM entities WHERE user_id=%s", (u['user_id'],))
        for row in c.fetchall():
            msg = request.json.get('message', '🚨 تنبيه جديد!')
            try: bot.send_message(row['entity_id'], msg, parse_mode='HTML')
            except: pass
    c.close(); conn.close()
    return {"status": "ok"}

@app.route('/')
def home(): return "MOH Engine is LIVE"

if __name__ == '__main__':
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_cb))
    dp.add_handler(MessageHandler(Filters.all, handle_msg))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
