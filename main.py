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

# --- ⚙️ الإعدادات الأساسية ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = "5674313264" 
DB_NAME = "moh_signals.db"

# إعداد التشفير
env_key = os.getenv('ELIAS_SECRET_KEY')
if not env_key:
    env_key = Fernet.generate_key().decode()
cipher_suite = Fernet(env_key.encode())

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

# --- 🌍 القائمة الدائمة واللغات ---
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
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH_SignalsBot</b>. المنصة المتكاملة للتداول والتحليل جاهزة:",
        'acc': "👤 <b>حسابي:</b>\n- المعرف: <code>{uid}</code>\n- القنوات: {chans}\n- الإشارات: {sigs}\n- المدفوع: ${paid}",
        'hook_fail': "⚠️ يرجى إضافة قناة/مجموعة وتعيين البوت مشرفاً أولاً.",
        'hook_success': "✅ <b>تم التحقق!</b> رابط الويب هوك الخاص بك:\n<code>{url}</code>",
        'order_req': "الرجاء إرسال رقم الطلب الخاص بك للتفعيل.",
        'sub_info': "للاشتراك، يرجى زيارة موقعنا أو إرسال كود التفعيل:"
    },
    'en': {
        'start': "👋 Welcome to <b>MOH_SignalsBot</b>. All-in-one Trading & Analysis platform is ready:",
        'acc': "👤 <b>Account:</b>\n- ID: <code>{uid}</code>\n- Channels: {chans}\n- Signals: {sigs}\n- Paid: ${paid}",
        'hook_fail': "⚠️ Please add a channel/group and promote bot to admin first.",
        'hook_success': "✅ <b>Verified!</b> Your Webhook URL:\n<code>{url}</code>",
        'order_req': "Please send your order number to activate.",
        'sub_info': "To subscribe, visit our website or send activation code:"
    }
}

# --- 🛠 وظائف الأمان ومنع النوم ---
def encrypt_data(data): return cipher_suite.encrypt(data.encode()).decode() if data else None
def decrypt_data(data):
    try: return cipher_suite.decrypt(data.encode()).decode() if data else None
    except: return None

def keep_alive():
    while True:
        try:
            app_url = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
            requests.get(app_url, timeout=10)
            logging.info("Keep-alive ping sent...")
        except: pass
        time.sleep(600)

def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT lang, signals_left, total_paid, secret_token, is_algo_active, alpaca_key, alpaca_secret FROM users WHERE user_id = ?", (uid,))
    res = c.fetchone()
    if not res:
        c.execute("INSERT INTO users (user_id, signals_left) VALUES (?, 10)", (uid,))
        conn.commit()
        res = ('ar', 10, 0.0, None, 0, None, None)
    c.execute("SELECT COUNT(*) FROM entities WHERE user_id = ?", (uid,))
    chans = c.fetchone()[0]
    conn.close()
    return {'lang': res[0], 'sigs': res[1], 'paid': res[2], 'token': res[3], 'algo': res[4], 'key': res[5], 'sec': res[6], 'chans': chans}

# --- 🌐 مسارات تطبيق TradingView المصغر ---
@app.route('/chart')
def show_chart():
    return """
    <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0;"><div id="tv_chart" style="height:100vh;"></div>
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>new TradingView.widget({"autosize":true,"symbol":"NASDAQ:AAPL","interval":"D","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"en","allow_symbol_change":true,"container_id":"tv_chart"});</script>
    </body></html>
    """

@app.route('/')
def home(): return "MOH_SignalsBot is Live"

# --- 🤖 الأوامر واللوحة ---
def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user(uid)
    update.message.reply_text(STRINGS[u['lang']]['start'], reply_markup=get_main_keyboard(u['lang']), parse_mode=ParseMode.HTML)

def handle_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user(uid)
    lang = u['lang']
    query.answer()
    kb = get_main_keyboard(lang)

    if query.data == 'acc':
        query.edit_message_text(STRINGS[lang]['acc'].format(uid=uid, chans=u['chans'], sigs=u['sigs'], paid=u['paid']), reply_markup=kb, parse_mode=ParseMode.HTML)

    elif query.data == 'get_hook':
        if u['chans'] == 0:
            query.edit_message_text(STRINGS[lang]['hook_fail'], reply_markup=kb)
        else:
            token = u['token'] if u['token'] else "----"
            app_url = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
            url = f"{app_url}/webhook/{uid}?secret={token}"
            query.edit_message_text(STRINGS[lang]['hook_success'].format(url=url), reply_markup=kb, parse_mode=ParseMode.HTML)

    elif query.data == 'sub':
        btns = [[InlineKeyboardButton("الاشتراك الآن" if lang=='ar' else "Subscribe Now", url="https://your-site.com")],
                [InlineKeyboardButton("إرسال كود التفعيل" if lang=='ar' else "Send Activation Code", callback_data='ask_code')]]
        query.edit_message_text(STRINGS[lang]['sub_info'], reply_markup=InlineKeyboardMarkup(btns + kb.inline_keyboard))

    elif query.data == 'ask_code':
        context.user_data['waiting_for_code'] = True
        query.edit_message_text(STRINGS[lang]['order_req'], reply_markup=kb)

    elif query.data.startswith('set_'):
        new_l = query.data.split('_')[1]
        sqlite3.connect(DB_NAME).execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_l, uid)).connection.commit()
        query.edit_message_text("✅ Language Updated", reply_markup=get_main_keyboard(new_l))

# --- 📈 محرك الويبهوك (Alpaca) ---
@app.route('/webhook/<int:uid>', methods=['POST'])
def hook_in(uid):
    sec = request.args.get('secret')
    u = get_user(uid)
    if not u['token'] or u['token'] != sec: return "Unauthorized", 403
    # ... منطق تنفيذ التداول المشفر هنا ...
    return "OK", 200

# --- 🚀 التشغيل ---
if __name__ == '__main__':
    init_db()
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    
    up = Updater(BOT_TOKEN)
    dp = up.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, lambda u, c: None)) # وظيفة معالجة الرسائل
    
    up.start_polling()
    up.idle()
