import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
import requests
from flask import Flask, request, render_template_string
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, Bot, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters, ChatMemberHandler

# --- ⚙️ الإعدادات (Environment) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
ALPACA_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET_KEY')

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# --- 🛠 قاعدة البيانات ---
def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 10, total_paid REAL DEFAULT 0.0,
                  expiry_days INTEGER DEFAULT 0, state TEXT DEFAULT 'IDLE')''')
    c.execute('''CREATE TABLE IF NOT EXISTS entities 
                 (id SERIAL PRIMARY KEY, user_id BIGINT, 
                  entity_id TEXT UNIQUE, entity_name TEXT)''')
    conn.commit(); c.close(); conn.close()

def get_user_data(uid):
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res:
        token = secrets.token_urlsafe(16).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    res['chans'] = c.fetchall()
    c.close(); conn.close()
    return res

# --- 🌍 نظام اللغات ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH Engine</b>\nالنظام جاهز للتحليل والأتمتة.",
        'acc': "👤 <b>حسابي</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: {chans}\n- أيام الاشتراك: {days}\n- إشارات متبقية: {sigs}\n- إجمالي المدفوع: ${paid}",
        'no_chan': "⚠️ لا توجد قنوات مرتبطة. يرجى إضافة البوت لقناتك كمشرف أولاً.",
        'hook_sent': "✅ تم توليد رابط ويب هوك جديد وإرساله لك.",
        'alpaca_req': "📈 أرسل رمز السهم للتحليل (مثال: AAPL):",
        'lang_switch': "🇺🇸 Switch to English"
    },
    'en': {
        'start': "👋 Welcome to <b>MOH Engine</b>\nSystem ready for analysis and automation.",
        'acc': "👤 <b>Account</b>\n\n- User ID: <code>{uid}</code>\n- Active Channels: {chans}\n- Sub Days: {days}\n- Signals Left: {sigs}\n- Total Paid: ${paid}",
        'no_chan': "⚠️ No channels linked. Add the bot as admin to your channel first.",
        'hook_sent': "✅ New Webhook URL generated and sent to you.",
        'alpaca_req': "📈 Send stock symbol to analyze (e.g., TSLA):",
        'lang_switch': "🇸🇦 التحويل للعربية"
    }
}

# --- ⌨️ لوحة التحكم ---
def get_main_keyboard(u):
    lang = u['lang']
    kb = [
        [InlineKeyboardButton("👤 " + ("حسابي" if lang=='ar' else "Account"), callback_data='acc'),
         InlineKeyboardButton("📊 " + ("عرض الشارات" if lang=='ar' else "Live Charts"), web_app=WebAppInfo(url=f"{RENDER_URL}/chart"))],
        [InlineKeyboardButton("➕ " + ("إضافة قناة" if lang=='ar' else "Add Channel"), url=f"https://t.me/{bot.get_me().username}?startchannel=true"),
         InlineKeyboardButton("🗑 " + ("حذف قناة" if lang=='ar' else "Delete Channel"), callback_data='list_to_del')],
        [InlineKeyboardButton("📈 " + ("تحليل الأسهم" if lang=='ar' else "AI Analysis"), callback_data='alpaca_analyze'),
         InlineKeyboardButton("🎫 " + ("تفعيل الاشتراك" if lang=='ar' else "Activate Sub"), web_app=WebAppInfo(url=f"{RENDER_URL}/sub"))],
        [InlineKeyboardButton("🔄 " + ("تجديد رابط ويب هوك" if lang=='ar' else "Renew Webhook"), callback_data='gen_token')],
        [InlineKeyboardButton("🌐 " + ("الويب هوك" if lang=='ar' else "Webhook"), callback_data='get_hook')],
        [InlineKeyboardButton(STRINGS[lang]['lang_switch'], callback_data='switch_lang')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 🤖 معالجات البوت ---

def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user_data(uid)
    lang = u['lang']
    query.answer()

    if query.data == 'acc':
        txt = STRINGS[lang]['acc'].format(uid=uid, chans=len(u['chans']), days=u['expiry_days'], sigs=u['signals_left'], paid=f"{u['total_paid']:.2f}")
        query.edit_message_text(txt, reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

    elif query.data == 'switch_lang':
        new_lang = 'en' if lang == 'ar' else 'ar'
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (new_lang, uid)); conn.commit(); c.close(); conn.close()
        u['lang'] = new_lang
        query.edit_message_text(STRINGS[new_lang]['start'], reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

    elif query.data == 'get_hook':
        if not u['chans']:
            query.edit_message_text(STRINGS[lang]['no_chan'], reply_markup=get_main_keyboard(u))
        else:
            url = f"{RENDER_URL}/webhook/{u['secret_token']}"
            bot.send_message(uid, f"🌐 <b>الويب هوك الخاص بك:</b>\n<code>{url}</code>", parse_mode=ParseMode.HTML)

    elif query.data == 'gen_token':
        new_token = secrets.token_urlsafe(16).upper()
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET secret_token=%s WHERE user_id=%s", (new_token, uid)); conn.commit(); c.close(); conn.close()
        url = f"{RENDER_URL}/webhook/{new_token}"
        bot.send_message(uid, f"🔄 <b>تم تجديد الرابط بنجاح:</b>\n<code>{url}</code>", parse_mode=ParseMode.HTML)

    elif query.data == 'alpaca_analyze':
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET state='AWAIT_STOCK' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['alpaca_req'], reply_markup=get_main_keyboard(u))

def handle_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user_data(uid)
    if u['state'] == 'AWAIT_STOCK':
        symbol = update.message.text.upper()
        # Alpaca API Call (Analysis Only)
        headers = {'APCA-API-KEY-ID': ALPACA_KEY, 'APCA-API-SECRET-KEY': ALPACA_SECRET}
        resp = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest", headers=headers)
        if resp.status_code == 200:
            price = resp.json()['quote']['ap']
            update.message.reply_text(f"📊 <b>تحليل Alpaca لـ {symbol}:</b>\nالسعر الحالي: ${price}\nالحالة: متصل ✅", parse_mode=ParseMode.HTML)
        else:
            update.message.reply_text("❌ لم يتم العثور على السهم.")
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET state='IDLE' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()

def track_new_channel(update: Update, context: CallbackContext):
    if update.my_chat_member and update.my_chat_member.new_chat_member.status == 'administrator':
        chat = update.my_chat_member.chat
        user_id = update.my_chat_member.from_user.id
        conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (user_id, str(chat.id), chat.title))
        conn.commit(); c.close(); conn.close()
        u = get_user_data(user_id)
        bot.send_message(user_id, f"🔗 <b>تم ربط القناة بنجاح!</b>\nالرابط الخاص بك:\n<code>{RENDER_URL}/webhook/{u['secret_token']}</code>", parse_mode=ParseMode.HTML)

# --- 🕸 Flask Routes ---

@app.route('/chart')
def chart():
    return render_template_string('''
        <body style="margin:0; background:#131722;">
            <div id="tv" style="height:100vh;"></div>
            <script src="https://s3.tradingview.com/tv.js"></script>
            <script>new TradingView.widget({"autosize": true, "symbol": "BINANCE:BTCUSDT", "theme": "dark", "container_id": "tv"});</script>
        </body>''')

@app.route('/sub')
def sub_page():
    return render_template_string('''
        <body style="font-family:sans-serif; padding:20px; text-align:center; background:#f4f4f4;">
            <h3>تفعيل الاشتراك / Activation</h3>
            <input type="text" placeholder="الكود أو رقم الطلب" style="padding:10px; width:80%; margin:10px 0;"><br>
            <button onclick="alert('تم الإرسال!')" style="padding:10px 20px; background:blue; color:white; border:none;">إرسال الطلب</button>
        </body>''')

@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token=%s", (token,))
    u = c.fetchone()
    if u:
        c.execute("SELECT entity_id FROM entities WHERE user_id=%s", (u['user_id'],))
        for row in c.fetchall():
            bot.send_message(row['entity_id'], request.json.get('message', 'Signal!'), parse_mode=ParseMode.HTML)
    c.close(); conn.close()
    return {"ok": True}

# --- 🚀 تشغيل ---
if __name__ == '__main__':
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(ChatMemberHandler(track_new_channel, ChatMemberHandler.MY_CHAT_MEMBER))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
    updater.start_polling()
    updater.idle()
