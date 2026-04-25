import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
import requests
from flask import Flask, request, render_template_string
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, Bot, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

# --- ⚙️ الإعدادات ---
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
    c.execute("SELECT user_id, secret_token, lang, COALESCE(signals_left, 100) as signals_left, COALESCE(total_paid, 0.0) as total_paid, COALESCE(expiry_days, 0) as expiry_days, state FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res:
        token = secrets.token_urlsafe(16).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        return get_user_data(uid)
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    res['chans'] = c.fetchall()
    c.close(); conn.close()
    return res

# --- 🌍 النصوص ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH Engine</b>\nالنظام السحابي جاهز للعمل.",
        'acc': "👤 <b>حسابي</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: {chans}\n- أيام الاشتراك: {days}\n- إشارات متبقية: {sigs}\n- إجمالي المدفوع: ${paid}",
        'analyze_req': "مساعدك الذكي للتداول في السوق الأمريكي 🇺🇸\n🔍 تحليل | 📈 فني | 📊 مالي\n\n✍️ اكتب رمز السهم (مثال: AAPL) الآن:",
        'no_chan': "⚠️ لم يتم ربط قنوات. أضف البوت للقناة وأرسل أي رسالة هناك للربط التلقائي.",
        'hook_info': "🌐 <b>رابط الويب هوك:</b>\n<code>{url}/webhook/{token}</code>",
        'token_info': "🔐 <b>رمز الأمان:</b>\n<code>{token}</code>"
    },
    'en': {
        'start': "👋 Welcome to <b>MOH Engine</b>\nSystem is online.",
        'acc': "👤 <b>Account</b>\n\n- ID: <code>{uid}</code>\n- Channels: {chans}\n- Days: {days}\n- Signals: {sigs}\n- Total Paid: ${paid}",
        'analyze_req': "Your AI Trading Assistant 🇺🇸\n\n✍️ Enter stock symbol (e.g. TSLA):",
        'no_chan': "⚠️ No channels. Add bot to channel and send a message there to link.",
        'hook_info': "🌐 <b>Webhook URL:</b>\n<code>{url}/webhook/{token}</code>",
        'token_info': "🔐 <b>Security Token:</b>\n<code>{token}</code>"
    }
}

def get_main_keyboard(u):
    lang = u.get('lang', 'ar')
    kb = [
        [InlineKeyboardButton("👤 " + ("حسابي" if lang=='ar' else "Account"), callback_data='acc'),
         InlineKeyboardButton("📊 " + ("عرض الشارات" if lang=='ar' else "Charts"), web_app=WebAppInfo(url=f"{RENDER_URL}/chart"))],
        [InlineKeyboardButton("➕ " + ("إضافة قناة" if lang=='ar' else "Add Channel"), url=f"https://t.me/{(bot.get_me().username)}?startchannel=true")],
        [InlineKeyboardButton("📈 " + ("تحليل الأسهم" if lang=='ar' else "AI Analysis"), callback_data='alpaca_analyze'),
         InlineKeyboardButton("🎫 " + ("تفعيل الاشتراك" if lang=='ar' else "Sub"), web_app=WebAppInfo(url=f"{RENDER_URL}/sub"))],
        [InlineKeyboardButton("🔐 " + ("رمز أمان ويب هوك" if lang=='ar' else "Token"), callback_data='gen_token')],
        [InlineKeyboardButton("🌐 " + ("رابط ويب هوك" if lang=='ar' else "URL"), callback_data='get_hook')],
        [InlineKeyboardButton("🇺🇸 English" if lang=='ar' else "🇸🇦 العربية", callback_data='switch_lang')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 🤖 المعالجات ---

def start_cmd(update: Update, context: CallbackContext):
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
    
    elif query.data == 'alpaca_analyze':
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET state='AWAIT_STOCK' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['analyze_req'], reply_markup=get_main_keyboard(u))

    elif query.data == 'get_hook':
        if not u['chans']: query.edit_message_text(STRINGS[lang]['no_chan'], reply_markup=get_main_keyboard(u))
        else: query.edit_message_text(STRINGS[lang]['hook_info'].format(url=RENDER_URL, token=u['secret_token']), reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

    elif query.data == 'gen_token':
        query.edit_message_text(STRINGS[lang]['token_info'].format(token=u['secret_token']), reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

    elif query.data == 'switch_lang':
        new_lang = 'en' if lang == 'ar' else 'ar'
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (new_lang, uid)); conn.commit(); c.close(); conn.close()
        u['lang'] = new_lang
        query.edit_message_text(STRINGS[new_lang]['start'], reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

def handle_all_messages(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    uid = user.id
    
    # 1. منطق الربط التلقائي (إذا أرسل المستخدم رسالة في قناة أو مجموعة البوت فيها مشرف)
    if chat.type in ['channel', 'group', 'supergroup']:
        conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO NOTHING", (uid, str(chat.id), chat.title))
        conn.commit(); c.close(); conn.close()
        return

    # 2. منطق التحليل في الخاص
    u = get_user_data(uid)
    if u['state'] == 'AWAIT_STOCK':
        symbol = update.message.text.upper()
        headers = {'APCA-API-KEY-ID': ALPACA_KEY, 'APCA-API-SECRET-KEY': ALPACA_SECRET}
        try:
            r = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest", headers=headers)
            if r.status_code == 200:
                price = r.json().get('quote', {}).get('ap', 'N/A')
                update.message.reply_text(f"📊 <b>تحليل {symbol}:</b>\nالسعر الحالي: <code>${price}</code>\nالمصدر: Alpaca", parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(u))
            else: update.message.reply_text("❌ لم يتم العثور على الرمز.")
        except: update.message.reply_text("⚠️ خطأ في الاتصال بـ Alpaca.")
        
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET state='IDLE' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()

# --- 🕸 Flask Webhook ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook_handler(token):
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token=%s", (token,))
    u = c.fetchone()
    if u:
        c.execute("SELECT entity_id FROM entities WHERE user_id=%s", (u['user_id'],))
        for row in c.fetchall():
            msg = request.json.get('message', '🚀 Signal!')
            try: bot.send_message(row['entity_id'], msg, parse_mode=ParseMode.HTML)
            except: pass
    c.close(); conn.close()
    return {"ok": True}

@app.route('/chart')
def chart(): return render_template_string('<body style="margin:0;"><iframe src="https://www.tradingview.com/chart/" style="width:100%;height:100vh;border:none;"></iframe></body>')

@app.route('/')
def home(): return "MOH Engine Running"

# --- 🚀 التشغيل ---
if __name__ == '__main__':
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    # هذا الهاندلر الآن يراقب كل شيء لضمان الربط والتحليل
    dp.add_handler(MessageHandler(Filters.all, handle_all_messages))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
