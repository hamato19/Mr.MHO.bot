import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

# --- ⚙️ الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')

app = Flask(__name__)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 🛠 إدارة قاعدة البيانات ---
def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 10, total_paid REAL DEFAULT 0.0,
                  alpaca_key TEXT, alpaca_secret TEXT, is_algo_active INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS entities 
                 (id SERIAL PRIMARY KEY, user_id BIGINT, 
                  entity_id TEXT, entity_name TEXT)''')
    conn.commit()
    c.close()
    conn.close()

def get_user_data(uid):
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res:
        token = secrets.token_hex(4).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
    c.execute("SELECT id, entity_id, entity_name FROM entities WHERE user_id = %s", (uid,))
    res['chans'] = c.fetchall()
    c.close(); conn.close()
    return res

# --- 🌍 النصوص ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH_SignalsBot</b>.\nالنظام متصل بالسحاب ومستعد للعمل 🚀",
        'acc': "👤 <b>حسابي:</b>\n- المعرف: <code>{uid}</code>\n- القنوات: {chans_count}\n- الإشارات: {sigs}\n- الرصيد: ${paid}",
        'hook_info': "🌐 <b>رابط الويب هوك الخاص بك:</b>\n<code>{url}/webhook/{token}</code>\n\nاستخدمه في TradingView Alerts.",
        'sub_info': "🛒 <b>تفعيل الاشتراك:</b>\nتواصل مع المطور @MOH_Admin لتفعيل الباقات الاحترافية.",
        'alp_info': "🔑 <b>إعدادات Alpaca:</b>\nأرسل مفتاحك (API Key) في رسالة نصية لحفظه.",
        'deleted': "✅ تم الحذف.",
        'no_chans': "⚠️ لم تقم بإضافة قنوات بعد."
    },
    'en': {
        'start': "👋 Welcome to <b>MOH_SignalsBot</b>.\nCloud System is Ready 🚀",
        'acc': "👤 <b>Account:</b>\n- ID: <code>{uid}</code>\n- Channels: {chans_count}\n- Signals: {sigs}\n- Paid: ${paid}",
        'hook_info': "🌐 <b>Your Webhook URL:</b>\n<code>{url}/webhook/{token}</code>\n\nUse it in TradingView Alerts.",
        'sub_info': "🛒 <b>Subscription:</b>\nContact @MOH_Admin for premium plans.",
        'alp_info': "🔑 <b>Alpaca Settings:</b>\nSend your API Key as a text message to save it.",
        'deleted': "✅ Removed.",
        'no_chans': "⚠️ No channels added yet."
    }
}

def get_main_keyboard(lang):
    kb = [
        [InlineKeyboardButton("👤 حسابي" if lang=='ar' else "👤 Account", callback_data='acc'),
         InlineKeyboardButton("🛒 تفعيل الاشتراك" if lang=='ar' else "🛒 Subscribe", callback_data='sub')],
        [InlineKeyboardButton("📊 فتح الشارت (Mini App)" if lang=='ar' else "📊 Chart App", web_app=WebAppInfo(url=f"{RENDER_URL}/chart"))],
        [InlineKeyboardButton("🖥 قنواتي" if lang=='ar' else "🖥 My Channels", callback_data='list_chans')],
        [InlineKeyboardButton("🔑 Alpaca" if lang=='ar' else "🔑 Alpaca", callback_data='alp_set')],
        [InlineKeyboardButton("🌐 رابط ويب هوك" if lang=='ar' else "🌐 Webhook", callback_data='get_hook')],
        [InlineKeyboardButton("🇺🇸 English", callback_data='lang_en'), InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 🤖 معالجة الأوامر والرسائل ---
def start(update: Update, context: CallbackContext):
    u = get_user_data(update.effective_user.id)
    update.message.reply_text(STRINGS[u['lang']]['start'], reply_markup=get_main_keyboard(u['lang']), parse_mode=ParseMode.HTML)

def handle_text(update: Update, context: CallbackContext):
    # حفظ مفاتيح Alpaca إذا أرسلها المستخدم
    uid = update.effective_user.id
    text = update.message.text
    if len(text) > 15: # تحقق بسيط أنها ليست رسالة عادية
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET alpaca_key = %s WHERE user_id = %s", (text, uid))
        conn.commit(); c.close(); conn.close()
        update.message.reply_text("✅ تم حفظ مفتاح Alpaca بنجاح.")

def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user_data(uid)
    lang = u['lang']
    query.answer()

    if query.data == 'acc':
        query.edit_message_text(STRINGS[lang]['acc'].format(uid=uid, chans_count=len(u['chans']), sigs=u['signals_left'], paid=u['total_paid']), 
                                reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)
    elif query.data == 'sub':
        query.edit_message_text(STRINGS[lang]['sub_info'], reply_markup=get_main_keyboard(lang))
    elif query.data == 'alp_set':
        query.edit_message_text(STRINGS[lang]['alp_info'], reply_markup=get_main_keyboard(lang))
    elif query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1]
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (new_lang, uid)); conn.commit(); c.close(); conn.close()
        query.edit_message_text("✅ Done", reply_markup=get_main_keyboard(new_lang))
    elif query.data == 'get_hook':
        query.edit_message_text(STRINGS[lang]['hook_info'].format(url=RENDER_URL, token=u['secret_token']), reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)
    elif query.data == 'list_chans':
        if not u['chans']:
            query.edit_message_text(STRINGS[lang]['no_chans'], reply_markup=get_main_keyboard(lang))
        else:
            kb = [[InlineKeyboardButton(f"❌ {c['entity_name']}", callback_data=f"del_{c['id']}")] for c in u['chans']]
            kb.append([InlineKeyboardButton("🔙 Back", callback_data='acc')])
            query.edit_message_text("قنواتك:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data.startswith('del_'):
        c_id = query.data.split('_')[1]
        conn = get_db_connection(); c = conn.cursor()
        c.execute("DELETE FROM entities WHERE id=%s", (c_id,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['deleted'], reply_markup=get_main_keyboard(lang))

# --- 🌐 Flask & Webhook Receiver ---
@app.route('/')
def home(): return "MOH Signals Engine is Running ✅"

@app.route('/chart')
def chart(): return '<html><body style="margin:0;"><iframe src="https://www.tradingview.com/chart/" style="width:100%;height:100vh;border:none;"></iframe></body></html>'

@app.route('/webhook/<token>', methods=['POST'])
def webhook_receiver(token):
    data = request.json
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token = %s", (token,))
    user = c.fetchone()
    if user:
        c.execute("SELECT entity_id FROM entities WHERE user_id = %s", (user['user_id'],))
        channels = c.fetchall()
        # إرسال التنبيه لكل القنوات المرتبطة
        for chan in channels:
            msg = f"🚀 <b>تنبيه إشارة جديد!</b>\n\n{data.get('message', 'No Message Content')}"
            requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={chan['entity_id']}&text={msg}&parse_mode=HTML")
    c.close(); conn.close()
    return {"status": "success"}, 200

# --- 🚀 التشغيل ---
if __name__ == '__main__':
    init_db()
    up = Updater(BOT_TOKEN, use_context=True)
    dp = up.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    up.start_polling(drop_pending_updates=True)
    up.idle()
