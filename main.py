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

# --- ⚙️ الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
ALPACA_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET_KEY')

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 🛠 قاعدة البيانات (معالجة الأخطاء) ---
def get_db_connection():
    try:
        return psycopg2.connect(DB_URL, sslmode='require')
    except Exception as e:
        logging.error(f"DB Connection Error: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                      signals_left INTEGER DEFAULT 100, total_paid REAL DEFAULT 0.0,
                      expiry_days INTEGER DEFAULT 0, state TEXT DEFAULT 'IDLE')''')
        c.execute('''CREATE TABLE IF NOT EXISTS entities 
                     (id SERIAL PRIMARY KEY, user_id BIGINT, 
                      entity_id TEXT UNIQUE, entity_name TEXT)''')
        conn.commit(); c.close(); conn.close()

def get_user_data(uid):
    conn = get_db_connection()
    if not conn: return None
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res:
        token = secrets.token_urlsafe(16).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    res['chans'] = c.fetchall() or []
    c.close(); conn.close()
    return res

# --- 🌍 النصوص ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH Engine</b>\nالنظام السحابي مفعل وجاهز.",
        'acc': "👤 <b>حسابي</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: {chans}\n- أيام الاشتراك: {days}\n- إشارات متبقية: {sigs}\n- إجمالي المدفوع: ${paid}",
        'analyze_req': "مساعدك الذكي للتداول في السوق الأمريكي 🇺🇸\n🔍 تحليل | 📈 فني | 📊 مالي\n\n✍️ اكتب رمز السهم (مثال: AAPL) الآن:",
        'no_chan': "⚠️ لم تقم بإضافة أي قناة بعد. أضف البوت كمشرف في قناتك أولاً.",
        'hook_info': "🌐 <b>رابط الويب هوك الخاص بك:</b>\n<code>{url}/webhook/{token}</code>",
        'token_info': "🔐 <b>رمز الأمان:</b>\n<code>{token}</code>"
    },
    'en': {
        'start': "👋 Welcome to <b>MOH Engine</b>\nCloud system active.",
        'acc': "👤 <b>Account</b>\n\n- User ID: <code>{uid}</code>\n- Active Channels: {chans}\n- Sub Days: {days}\n- Signals Left: {sigs}\n- Total Paid: ${paid}",
        'analyze_req': "Your AI Trading Assistant 🇺🇸\n\n✍️ Enter stock symbol (e.g. TSLA) now:",
        'no_chan': "⚠️ No channels found. Add bot as admin to your channel.",
        'hook_info': "🌐 <b>Your Webhook URL:</b>\n<code>{url}/webhook/{token}</code>",
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
    if u: update.message.reply_text(STRINGS[u['lang']]['start'], reply_markup=get_main_keyboard(u), parse_mode=ParseMode.HTML)

def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user_data(uid)
    if not u: return
    lang = u['lang']
    query.answer()

    if query.data == 'acc':
        txt = STRINGS[lang]['acc'].format(uid=uid, chans=len(u['chans']), days=u['expiry_days'], sigs=u['signals_left'], paid=u['total_paid'])
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

def handle_messages(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user_data(uid)
    if not u: return
    
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

def on_add_bot(update: Update, context: CallbackContext):
    # مراقبة إضافة البوت للقنوات والمجموعات
    if update.my_chat_member:
        chat = update.my_chat_member.chat
        user_id = update.my_chat_member.from_user.id
        status = update.my_chat_member.new_chat_member.status
        
        if status in ['administrator', 'member']:
            conn = get_db_connection(); c = conn.cursor()
            c.execute("INSERT INTO entities (user_id, entity_id, entity_name) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO NOTHING", (user_id, str(chat.id), chat.title))
            conn.commit(); c.close(); conn.close()
            context.bot.send_message(user_id, f"✅ تم ربط <b>{chat.title}</b> بنجاح!", parse_mode=ParseMode.HTML)

# --- 🚀 التشغيل ---
if __name__ == '__main__':
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_messages))
    dp.add_handler(ChatMemberHandler(on_add_bot, ChatMemberHandler.MY_CHAT_MEMBER))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
