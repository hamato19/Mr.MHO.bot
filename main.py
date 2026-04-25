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

# --- 🛠 إدارة قاعدة البيانات ---
def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 100, total_paid REAL DEFAULT 0.0,
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

# --- 🌍 اللغات ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH Engine</b>\nالنظام جاهز للتحليل والأتمتة.",
        'acc': "👤 <b>حسابي</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: {chans}\n- أيام الاشتراك: {days}\n- إشارات متبقية: {sigs}\n- إجمالي المدفوع: ${paid}",
        'no_chan': "⚠️ لا توجد قنوات مرتبطة. يرجى إضافة البوت لقناتك كمشرف أولاً لتوليد الرابط.",
        'analyze_req': "مساعدك الذكي للتداول في السوق الأمريكي 🇺🇸\n🔍 تحليل | 📈 فني | 📊 مالي\n\n✍️ اكتب رمز السهم مثال AAPL او الصندوق مثال SMH ويظهر لك التقرير فورًا!",
        'webhook_info': "🌐 <b>رابط الويب هوك الخاص بك:</b>\n<code>{url}/webhook/{token}</code>",
        'token_info': "🔐 <b>رمز أمان الويب هوك الخاص بك:</b>\n<code>{token}</code>"
    },
    'en': {
        'start': "👋 Welcome to <b>MOH Engine</b>\nSystem ready for analysis.",
        'acc': "👤 <b>Account</b>\n\n- User ID: <code>{uid}</code>\n- Active Channels: {chans}\n- Sub Days: {days}\n- Signals Left: {sigs}\n- Total Paid: ${paid}",
        'no_chan': "⚠️ No channels linked. Add bot as admin to your channel first.",
        'analyze_req': "Your AI Trading Assistant 🇺🇸\n🔍 Analysis | 📈 Technical | 📊 Financial\n\n✍️ Enter stock symbol (e.g. TSLA) for an instant report!",
        'webhook_info': "🌐 <b>Your Webhook URL:</b>\n<code>{url}/webhook/{token}</code>",
        'token_info': "🔐 <b>Your Webhook Security Token:</b>\n<code>{token}</code>"
    }
}

# --- ⌨️ لوحة التحكم المحدثة ---
def get_main_keyboard(u):
    lang = u.get('lang', 'ar')
    kb = [
        [InlineKeyboardButton("👤 " + ("حسابي" if lang=='ar' else "Account"), callback_data='acc'),
         InlineKeyboardButton("📊 " + ("عرض الشارات" if lang=='ar' else "Live Charts"), web_app=WebAppInfo(url=f"{RENDER_URL}/chart"))],
        [InlineKeyboardButton("➕ " + ("إضافة قناة" if lang=='ar' else "Add Channel"), url=f"https://t.me/{bot.get_me().username}?startchannel=true"),
         InlineKeyboardButton("🗑 " + ("حذف قناة" if lang=='ar' else "Delete Channel"), callback_data='list_to_del')],
        [InlineKeyboardButton("📈 " + ("تحليل الأسهم" if lang=='ar' else "AI Analysis"), callback_data='alpaca_analyze'),
         InlineKeyboardButton("🎫 " + ("تفعيل الاشتراك" if lang=='ar' else "Activate Sub"), web_app=WebAppInfo(url=f"{RENDER_URL}/sub"))],
        [InlineKeyboardButton("🔐 " + ("رمز أمان ويب هوك" if lang=='ar' else "Webhook Token"), callback_data='gen_token')],
        [InlineKeyboardButton("🌐 " + ("رابط ويب هوك" if lang=='ar' else "Webhook URL"), callback_data='get_hook')],
        [InlineKeyboardButton("🇺🇸 English" if lang=='ar' else "🇸🇦 العربية", callback_data='switch_lang')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 🤖 المعالجات ---

def start(update: Update, context: CallbackContext):
    u = get_user_data(update.effective_user.id)
    update.message.reply_text(STRINGS[u['lang']]['start'], reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

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
            txt = STRINGS[lang]['webhook_info'].format(url=RENDER_URL, token=u['secret_token'])
            query.edit_message_text(txt, reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

    elif query.data == 'gen_token':
        if not u['chans']:
            query.edit_message_text(STRINGS[lang]['no_chan'], reply_markup=get_main_keyboard(u))
        else:
            txt = STRINGS[lang]['token_info'].format(token=u['secret_token'])
            query.edit_message_text(txt, reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

    elif query.data == 'alpaca_analyze':
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET state='AWAIT_STOCK' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['analyze_req'], reply_markup=get_main_keyboard(u))

def handle_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user_data(uid)
    if u.get('state') == 'AWAIT_STOCK':
        symbol = update.message.text.upper()
        # Alpaca Analysis Logic
        headers = {'APCA-API-KEY-ID': ALPACA_KEY, 'APCA-API-SECRET-KEY': ALPACA_SECRET}
        resp = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest", headers=headers)
        if resp.status_code == 200:
            price = resp.json().get('quote', {}).get('ap', 'N/A')
            update.message.reply_text(f"📊 <b>تقرير التحليل الذكي ({symbol}):</b>\n\n💰 السعر الحالي: <code>${price}</code>\n⚡️ الحالة: نشط\n🛡 المصدر: Alpaca Markets\n\n<i>هذا التحليل تم توليده آلياً بناءً على بيانات السوق الحالية.</i>", parse_mode=ParseMode.HTML)
        else:
            update.message.reply_text("❌ لم يتم العثور على الرمز، تأكد من كتابة الرمز بشكل صحيح (مثل AAPL).")
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET state='IDLE' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()

def track_new_channel(update: Update, context: CallbackContext):
    result = update.my_chat_member
    if result.new_chat_member.status == 'administrator':
        chat = result.chat
        user_id = result.from_user.id
        conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO UPDATE SET entity_name=%s", (user_id, str(chat.id), chat.title, chat.title))
        conn.commit(); c.close(); conn.close()
        u = get_user_data(user_id)
        context.bot.send_message(user_id, f"✅ <b>تم ربط القناة بنجاح!</b>\nالآن يمكنك استخدام الويب هوك لنشر الإشارات هنا.\n\nرابطك: <code>{RENDER_URL}/webhook/{u['secret_token']}</code>", parse_mode=ParseMode.HTML)

# --- 🕸 Flask Routes ---
@app.route('/chart')
def chart_page():
    return render_template_string('''<body style="margin:0; background:#131722;"><div id="tv" style="height:100vh;"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "NASDAQ:AAPL", "theme": "dark", "container_id": "tv"});</script></body>''')

@app.route('/webhook/<token>', methods=['POST'])
def webhook_handler(token):
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token=%s", (token,))
    u = c.fetchone()
    if u:
        c.execute("SELECT entity_id FROM entities WHERE user_id=%s", (u['user_id'],))
        for row in c.fetchall():
            msg = request.json.get('message', '🚀 إشارة تداول جديدة!')
            try: bot.send_message(row['entity_id'], msg, parse_mode=ParseMode.HTML)
            except: pass
    c.close(); conn.close()
    return {"ok": True}

@app.route('/')
def home(): return "MOH Engine Active"

# --- 🚀 تشغيل ---
if __name__ == '__main__':
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(ChatMemberHandler(track_new_channel, ChatMemberHandler.MY_CHAT_MEMBER))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
