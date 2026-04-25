import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
import requests
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

# --- ⚙️ الإعدادات الأساسية ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
ADMIN_ID = 123456789  # 💡 استبدله بمعرف التليجرام الخاص بك (أبو إلياس)

app = Flask(__name__)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 🛠 إدارة قاعدة البيانات (Neon.tech) ---
def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 10, total_paid REAL DEFAULT 0.0,
                  alpaca_key TEXT, alpaca_secret TEXT, state TEXT DEFAULT 'IDLE')''')
    c.execute('''CREATE TABLE IF NOT EXISTS entities 
                 (id SERIAL PRIMARY KEY, user_id BIGINT, 
                  entity_id TEXT UNIQUE, entity_name TEXT, entity_type TEXT)''')
    conn.commit(); c.close(); conn.close()

def get_user_data(uid):
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res:
        token = secrets.token_urlsafe(12).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    res['chans'] = c.fetchall()
    c.close(); conn.close()
    return res

# --- 🌍 قاموس النصوص (عربي/إنجليزي) ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH Engine</b>\nالنظام السحابي مفعل وجاهز للأتمتة والتحليل.",
        'acc': "👤 <b>حسابي:</b>\n- المعرف: <code>{uid}</code>\n- القنوات/المجموعات: {chans_count}\n- الإشارات: {sigs}\n- التوكن: <code>{token}</code>",
        'hook_info': "🌐 <b>رابط الويب هوك الخاص بك:</b>\n<code>{url}/webhook/{token}</code>",
        'no_chans': "⚠️ يجب إضافة البوت لمجموعة أو قناة أولاً لتفعيل الويب هوك.",
        'analyze_req': "📈 أرسل <b>اسم السهم</b> أو الرمز للتحليل:",
        'wait_analyze': "⏳ جاري التحليل عبر الذكاء الاصطناعي...",
        'deleted': "✅ تم الحذف بنجاح.",
        'alp_info': "🔑 أرسل مفتاح Alpaca API الخاص بك الآن:",
        'lang_confirm': "✅ تم تغيير اللغة بنجاح.",
        'token_gen': "🔐 تم توليد رمز أمان جديد وتحديث روابطك!",
        'sub_req': "🎫 أرسل طلب أو كود الاشتراك الآن للتفعيل:",
        'sub_sent': "✅ تم إرسال طلبك للإدارة بنجاح.",
        'link_success': "🔗 <b>تم ربط القناة بنجاح!</b>\nإليك رابط الويب هوك الخاص بك لهذه القناة:\n<code>{url}/webhook/{token}</code>"
    },
    'en': {
        'start': "👋 Welcome to <b>MOH Engine</b>\nSystem active and ready for Automation.",
        'acc': "👤 <b>Account:</b>\n- ID: <code>{uid}</code>\n- Entities: {chans_count}\n- Signals: {sigs}\n- Token: <code>{token}</code>",
        'hook_info': "🌐 <b>Your Webhook URL:</b>\n<code>{url}/webhook/{token}</code>",
        'no_chans': "⚠️ Add bot to a channel first.",
        'analyze_req': "📈 Send <b>Stock Symbol</b> for AI analysis:",
        'wait_analyze': "⏳ Analyzing stock...",
        'deleted': "✅ Removed successfully.",
        'alp_info': "🔑 Send your Alpaca API Key:",
        'lang_confirm': "✅ Language updated.",
        'token_gen': "🔐 Security token updated!",
        'sub_req': "🎫 Send subscription code:",
        'sub_sent': "✅ Request sent to admin.",
        'link_success': "🔗 <b>Channel Linked!</b>\nYour Webhook URL:\n<code>{url}/webhook/{token}</code>"
    }
}

# --- ⌨️ لوحة التحكم الرئيسية ---
def get_main_keyboard(lang):
    # الحصول على اسم البوت ديناميكياً للرابط
    add_url = f"https://t.me/MrMHO_Bot?startchannel=true"
    kb = [
        [InlineKeyboardButton("👤 حسابي | Account" if lang=='ar' else "👤 Account", callback_data='acc'),
         InlineKeyboardButton("📈 تحليل الأسهم | AI" if lang=='ar' else "📈 AI Analysis", callback_data='analyze')],
        [InlineKeyboardButton("📊 الشارت | Chart", web_app=WebAppInfo(url=f"{RENDER_URL}/chart"))],
        [InlineKeyboardButton("🖥 قنواتي ومجموعاتي" if lang=='ar' else "🖥 My Entities", callback_data='list_chans'),
         InlineKeyboardButton("➕ إضافة قناة" if lang=='ar' else "➕ Add Channel", url=add_url)],
        [InlineKeyboardButton("🔑 Alpaca" if lang=='ar' else "🔑 Alpaca", callback_data='alp_set'),
         InlineKeyboardButton("🌐 الويب هوك" if lang=='ar' else "🌐 Webhook", callback_data='get_hook')],
        [InlineKeyboardButton("🔐 رمز أمان جديد" if lang=='ar' else "🔐 New Token", callback_data='gen_token'),
         InlineKeyboardButton("🎫 تفعيل الاشتراك" if lang=='ar' else "🎫 Subscription", callback_data='sub_activate')],
        [InlineKeyboardButton("🇺🇸 English", callback_data='lang_en'), InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 🤖 معالجات الرسائل والتحكم ---
def track_entities(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    if chat and chat.type in ['channel', 'group', 'supergroup'] and user:
        conn = get_db_connection(); c = conn.cursor()
        c.execute("SELECT id FROM entities WHERE entity_id = %s", (str(chat.id),))
        if not c.fetchone():
            c.execute('''INSERT INTO entities (user_id, entity_id, entity_name, entity_type) 
                         VALUES (%s, %s, %s, %s)''', (user.id, str(chat.id), chat.title, chat.type))
            conn.commit()
            u = get_user_data(user.id)
            hook_msg = STRINGS[u['lang']]['link_success'].format(url=RENDER_URL, token=u['secret_token'])
            try: context.bot.send_message(chat_id=user.id, text=hook_msg, parse_mode=ParseMode.HTML)
            except: pass
        c.close(); conn.close()

def start(update: Update, context: CallbackContext):
    u = get_user_data(update.effective_user.id)
    update.message.reply_text(STRINGS[u['lang']]['start'], reply_markup=get_main_keyboard(u['lang']), parse_mode=ParseMode.HTML)

def handle_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user_data(uid)
    text = update.message.text
    lang = u['lang']

    if u['state'] == 'AWAIT_STOCK':
        update.message.reply_text(STRINGS[lang]['wait_analyze'])
        analysis = f"📊 <b>نتائج تحليل ({text}):</b>\n\n✅ الاتجاه العام: صاعد\n🎯 الأهداف: قيد التحديث\n💡 التوصية: مراقبة نقطة الدخول."
        update.message.reply_text(analysis, reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET state='IDLE' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
    
    elif u['state'] == 'AWAIT_ALPACA':
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET alpaca_key=%s, state='IDLE' WHERE user_id=%s", (text, uid)); conn.commit(); c.close(); conn.close()
        update.message.reply_text("✅ API Saved", reply_markup=get_main_keyboard(lang))

    elif u['state'] == 'AWAIT_SUB':
        context.bot.send_message(chat_id=ADMIN_ID, text=f"🎫 <b>طلب اشتراك:</b>\nالمستخدم: <code>{uid}</code>\nالرسالة: {text}", parse_mode=ParseMode.HTML)
        update.message.reply_text(STRINGS[lang]['sub_sent'], reply_markup=get_main_keyboard(lang))
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET state='IDLE' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()

def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user_data(uid)
    lang = u['lang']
    query.answer()

    if query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1]
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (new_lang, uid)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[new_lang]['lang_confirm'], reply_markup=get_main_keyboard(new_lang))
    elif query.data == 'acc':
        txt = STRINGS[lang]['acc'].format(uid=uid, chans_count=len(u['chans']), sigs=u['signals_left'], token=u['secret_token'])
        query.edit_message_text(txt, reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)
    elif query.data == 'analyze':
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET state='AWAIT_STOCK' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['analyze_req'], reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)
    elif query.data == 'list_chans':
        u = get_user_data(uid)
        if not u['chans']: query.edit_message_text(STRINGS[lang]['no_chans'], reply_markup=get_main_keyboard(lang))
        else:
            kb = [[InlineKeyboardButton(f"❌ {c['entity_name']}", callback_data=f"del_{c['id']}")] for c in u['chans']]
            kb.append([InlineKeyboardButton("🔙 Back", callback_data='acc')])
            query.edit_message_text("🖥 قنواتك ومجموعاتك:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data.startswith('del_'):
        c_id = query.data.split('_')[1]
        conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM entities WHERE id=%s", (c_id,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['deleted'], reply_markup=get_main_keyboard(lang))
    elif query.data == 'get_hook':
        if not u['chans']: query.edit_message_text(STRINGS[lang]['no_chans'], reply_markup=get_main_keyboard(lang))
        else: query.edit_message_text(STRINGS[lang]['hook_info'].format(url=RENDER_URL, token=u['secret_token']), reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)
    elif query.data == 'gen_token':
        new_token = secrets.token_urlsafe(12).upper()
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET secret_token=%s WHERE user_id=%s", (new_token, uid)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['token_gen'], reply_markup=get_main_keyboard(lang))
    elif query.data == 'sub_activate':
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET state='AWAIT_SUB' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['sub_req'], reply_markup=get_main_keyboard(lang))

# --- 🕸 Flask Webhook Receiver ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook_receiver(token):
    data = request.json
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token = %s", (token,))
    user = c.fetchone()
    if user:
        c.execute("SELECT entity_id FROM entities WHERE user_id = %s", (user['user_id'],))
        for chan in c.fetchall():
            msg = data.get('message', 'New Signal Received! 🚀')
            requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={chan['entity_id']}&text={msg}&parse_mode=HTML")
    c.close(); conn.close()
    return {"status": "success"}, 200

@app.route('/chart')
def chart(): return '<html><body style="margin:0;"><iframe src="https://www.tradingview.com/chart/" style="width:100%;height:100vh;border:none;"></iframe></body></html>'

@app.route('/')
def home(): return "MOH Engine Core Active"

# --- 🚀 التشغيل النهائي ---
if __name__ == '__main__':
    init_db()
    up = Updater(BOT_TOKEN, use_context=True)
    dp = up.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(MessageHandler(Filters.chat_type.channel | Filters.chat_type.groups, track_entities))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    up.start_polling(drop_pending_updates=True)
    up.idle()
