import os
import logging
import sqlite3
import secrets
import threading
from flask import Flask, request, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
import requests
from cryptography.fernet import Fernet

# --- ⚙️ الإعدادات الأساسية (سحب البيانات من Render) ---
# يتم سحب التوكن من خانة Environment Variables التي أسميتها BOT_TOKEN في الصورة
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_NAME = "elias_hook.db"

# --- 🔐 إعداد نظام التشفير الاحترافي ---
# سحب مفتاح التشفير من Render، وفي حال عدم وجوده نستخدم مفتاحاً عشوائياً (لحماية البيانات المشفرة)
env_key = os.getenv('ELIAS_SECRET_KEY')
if not env_key:
    # توليد مفتاح افتراضي إذا لم يتم ضبطه في المتغيرات
    env_key = Fernet.generate_key().decode()
    logging.warning("⚠️ لم يتم العثور على ELIAS_SECRET_KEY، تم استخدام مفتاح مؤقت.")

if not BOT_TOKEN:
    logging.error("❌ خطأ فادح: BOT_TOKEN غير موجود في إعدادات السيرفر!")
    raise ValueError("يجب ضبط BOT_TOKEN في Environment Variables على Render")

cipher_suite = Fernet(env_key.encode())

app = Flask(__name__)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 🛠 وظائف التشفير وقاعدة البيانات ---
def encrypt_data(data):
    if not data: return None
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(data):
    if not data: return None
    try:
        return cipher_suite.decrypt(data.encode()).decode()
    except Exception:
        return "ERROR_DECRYPT"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, secret_token TEXT, 
                  alpaca_key TEXT, alpaca_secret TEXT, is_algo_active INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id TEXT, channel_name TEXT)''')
    conn.commit()
    conn.close()

# --- 🤖 لوحة تحكم التليجرام (Elias System Dashboard) ---
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    init_db()
    
    keyboard = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='sub')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add'), InlineKeyboardButton("🖥 قنواتي", callback_data='list')],
        [InlineKeyboardButton("🔑 إعدادات Alpaca", callback_data='alp_set')],
        [InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_tok'), InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='get_hook')],
        [InlineKeyboardButton("🚀 التداول الآلي", callback_data='tog_algo')],
        [InlineKeyboardButton("📖 طريقة الاستخدام", callback_data='guide')],
        [InlineKeyboardButton("☎️ الدعم", callback_data='support')]
    ]
    
    update.message.reply_text(
        f"👋 مرحباً بك يا <b>{update.effective_user.first_name}</b> في إلياس سيستم.\nلوحة التحكم جاهزة لإدارة الويبهوك والتداول الآلي:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

def handle_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    
    if query.data == 'alp_set':
        query.edit_message_text("🛠 <b>إعدادات Alpaca:</b>\nيرجى إرسال الـ API Key هكذا:\n<code>key:المفتاح</code>\nثم الـ Secret هكذا:\n<code>secret:المفتاح_السري</code>", parse_mode=ParseMode.HTML)
    
    elif query.data == 'gen_tok':
        new_token = secrets.token_hex(4).upper()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        c.execute("UPDATE users SET secret_token = ? WHERE user_id = ?", (new_token, user_id))
        conn.commit()
        conn.close()
        query.edit_message_text(f"✅ تم تحديث رمز الأمان:\n<code>{new_token}</code>", parse_mode=ParseMode.HTML)

    elif query.data == 'get_hook':
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT secret_token FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone()
        conn.close()
        token = res[0] if res else "لم يتم التوليد"
        # يتم سحب رابط التطبيق آلياً من Render أو وضعه يدوياً
        app_url = os.getenv('RENDER_EXTERNAL_URL', 'https://your-app.onrender.com')
        url = f"{app_url}/webhook/{user_id}?secret={token}"
        query.edit_message_text(f"🌐 <b>رابط الويبهوك الخاص بك:</b>\n<code>{url}</code>", parse_mode=ParseMode.HTML)

    elif query.data == 'tog_algo':
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT is_algo_active FROM users WHERE user_id = ?", (user_id,))
        status = c.fetchone()
        new_val = 1 if not status or status[0] == 0 else 0
        c.execute("UPDATE users SET is_algo_active = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        conn.close()
        state = "✅ مفعل" if new_val == 1 else "❌ معطل"
        query.edit_message_text(f"🚀 التداول الآلي الآن: {state}")

def handle_msg(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    txt = update.message.text
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if txt.startswith("key:"):
        val = encrypt_data(txt.split(":")[1].strip())
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        c.execute("UPDATE users SET alpaca_key = ? WHERE user_id = ?", (val, user_id))
        update.message.reply_text("✅ تم حفظ API Key بنجاح (مشفر).")
    
    elif txt.startswith("secret:"):
        val = encrypt_data(txt.split(":")[1].strip())
        c.execute("UPDATE users SET alpaca_secret = ? WHERE user_id = ?", (val, user_id))
        update.message.reply_text("✅ تم حفظ Secret Key بنجاح (مشفر).")
    
    conn.commit()
    conn.close()

# --- 📈 محرك التداول والويبهوك (Alpaca Engine) ---
def alpaca_trade(user_id, ticker, side):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT alpaca_key, alpaca_secret, is_algo_active FROM users WHERE user_id = ?", (user_id,))
    u = c.fetchone()
    conn.close()

    if u and u[2] == 1 and u[0] and u[1]:
        try:
            a_key = decrypt_data(u[0])
            a_sec = decrypt_data(u[1])
            url = "https://paper-api.alpaca.markets/v2/orders"
            h = {"APCA-API-KEY-ID": a_key, "APCA-API-SECRET-KEY": a_sec}
            d = {"symbol": ticker, "qty": 1, "side": "buy" if "buy" in side.lower() else "sell", "type": "market", "time_in_force": "gtc"}
            res = requests.post(url, json=d, headers=h)
            return res.status_code == 200
        except: return False
    return False

@app.route('/webhook/<int:uid>', methods=['POST'])
def hook_in(uid):
    sec = request.args.get('secret')
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT secret_token FROM users WHERE user_id = ?", (uid,))
    res = c.fetchone()
    conn.close()

    if not res or res[0] != sec: return "Unauthorized", 403

    data = request.json
    ticker = data.get('ticker', 'N/A')
    action = data.get('action', 'info')
    
    traded = alpaca_trade(uid, ticker, action)
    status = "⚡ تم التداول" if traded else "📢 تنبيه فقط"
    
    msg = f"🔔 <b>إشارة Elias-Hook</b>\n━━━━━━━━━━━━\n📈 السهم: {ticker}\n↕️ النوع: {action}\n🛡 الحالة: {status}"
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": uid, "text": msg, "parse_mode": "HTML"})
    return "OK", 200

# --- 🚀 التشغيل ---
def start_flask():
    # بورت 8080 هو البورت الافتراضي الذي يستخدمه Render
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

if __name__ == '__main__':
    init_db()
    threading.Thread(target=start_flask, daemon=True).start()
    up = Updater(BOT_TOKEN)
    dp = up.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_msg))
    print("🚀 Elias-Hook System is Online...")
    up.start_polling()
    up.idle()
