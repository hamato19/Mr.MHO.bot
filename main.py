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
    conn = get_db_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 10, total_paid REAL DEFAULT 0.0,
                  alpaca_key TEXT, alpaca_secret TEXT, state TEXT DEFAULT 'IDLE')''')
    c.execute('''CREATE TABLE IF NOT EXISTS entities 
                 (id SERIAL PRIMARY KEY, user_id BIGINT, 
                  entity_id TEXT, entity_name TEXT, entity_type TEXT)''')
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

# --- 🌍 قاموس النصوص الموحد ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>MOH Engine</b>\nالنظام السحابي مفعل وجاهز للأتمتة والتحليل.",
        'acc': "👤 <b>حسابي:</b>\n- المعرف: <code>{uid}</code>\n- القنوات/المجموعات: {chans_count}\n- الإشارات: {sigs}\n- التوكن: <code>{token}</code>",
        'hook_info': "🌐 <b>رابط الويب هوك:</b>\n<code>{url}/webhook/{token}</code>",
        'no_chans': "⚠️ يجب إضافة البوت لمجموعة أو قناة أولاً لتفعيل الويب هوك.",
        'analyze_req': "📈 أرسل <b>اسم السهم</b> أو <b>الرمز</b> للتحليل:",
        'wait_analyze': "⏳ جاري تحليل السهم عبر الذكاء الاصطناعي... انتظر قليلاً.",
        'deleted': "✅ تم الحذف بنجاح.",
        'alp_info': "🔑 أرسل مفتاح Alpaca API الخاص بك الآن لحفظه:",
        'lang_confirm': "✅ تم تغيير اللغة إلى العربية."
    },
    'en': {
        'start': "👋 Welcome to <b>MOH Engine</b>\nCloud system active for Automation & Analysis.",
        'acc': "👤 <b>Account:</b>\n- ID: <code>{uid}</code>\n- Entities: {chans_count}\n- Signals: {sigs}\n- Token: <code>{token}</code>",
        'hook_info': "🌐 <b>Your Webhook:</b>\n<code>{url}/webhook/{token}</code>",
        'no_chans': "⚠️ Add bot to a channel/group first to enable Webhook.",
        'analyze_req': "📈 Send <b>Stock Name/Symbol</b> for analysis:",
        'wait_analyze': "⏳ Analyzing stock via AI... Please wait.",
        'deleted': "✅ Removed successfully.",
        'alp_info': "🔑 Send your Alpaca API Key now to save it:",
        'lang_confirm': "✅ Language switched to English."
    }
}

def get_main_keyboard(lang):
    kb = [
        [InlineKeyboardButton("👤 حسابي | Account" if lang=='ar' else "👤 Account", callback_data='acc'),
         InlineKeyboardButton("📈 تحليل الأسهم | AI" if lang=='ar' else "📈 AI Analysis", callback_data='analyze')],
        [InlineKeyboardButton("📊 الشارت | Chart", web_app=WebAppInfo(url=f"{RENDER_URL}/chart"))],
        [InlineKeyboardButton("🖥 قنواتي ومجموعاتي" if lang=='ar' else "🖥 My Entities", callback_data='list_chans')],
        [InlineKeyboardButton("🔑 Alpaca" if lang=='ar' else "🔑 Alpaca", callback_data='alp_set'),
         InlineKeyboardButton("🌐 الويب هوك" if lang=='ar' else "🌐 Webhook", callback_data='get_hook')],
        [InlineKeyboardButton("🇺🇸 English", callback_data='lang_en'), InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 🤖 المعالجات ---
def start(update: Update, context: CallbackContext):
    u = get_user_data(update.effective_user.id)
    update.message.reply_text(STRINGS[u['lang']]['start'], reply_markup=get_main_keyboard(u['lang']), parse_mode=ParseMode.HTML)

def handle_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user_data(uid)
    text = update.message.text

    if u['state'] == 'AWAIT_STOCK':
        update.message.reply_text(STRINGS[u['lang']]['wait_analyze'])
        # محاكاة تحليل احترافي
        analysis = f"📊 <b>تحليل الذكاء الاصطناعي لـ ({text}):</b>\n\n" \
                   f"🏷 <b>الحالة العامة:</b> مستقر مع ميل للصعود.\n" \
                   f"🎯 <b>أهداف متوقعة:</b> اختراق المقاومة الأولى قريباً.\n" \
                   f"💡 <b>نصيحة:</b> يفضل الانتظار حتى تأكيد إشارة السيولة."
        update.message.reply_text(analysis, reply_markup=get_main_keyboard(u['lang']), parse_mode=ParseMode.HTML)
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET state='IDLE' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
    
    elif u['state'] == 'AWAIT_ALPACA':
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET alpaca_key=%s, state='IDLE' WHERE user_id=%s", (text, uid)); conn.commit(); c.close(); conn.close()
        update.message.reply_text("✅ Saved / تم الحفظ", reply_markup=get_main_keyboard(u['lang']))

def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user_data(uid)
    lang = u['lang']
    query.answer()

    if query.data.startswith('lang_'):
        new_lang = query.data.split('_')[1]
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET lang=%s WHERE user_id=%s", (new_lang, uid)); conn.commit(); c.close(); conn.close()
        # إرسال رسالة تأكيد وحذف القديمة لضمان نظافة المحادثة
        query.edit_message_text(STRINGS[new_lang]['lang_confirm'], reply_markup=get_main_keyboard(new_lang))

    elif query.data == 'acc':
        txt = STRINGS[lang]['acc'].format(uid=uid, chans_count=len(u['chans']), sigs=u['signals_left'], token=u['secret_token'])
        query.edit_message_text(txt, reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)
    
    elif query.data == 'analyze':
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET state='AWAIT_STOCK' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['analyze_req'], reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)

    elif query.data == 'list_chans':
        if not u['chans']:
            query.edit_message_text(STRINGS[lang]['no_chans'], reply_markup=get_main_keyboard(lang))
        else:
            kb = [[InlineKeyboardButton(f"❌ {c['entity_name']}", callback_data=f"del_{c['id']}")] for c in u['chans']]
            kb.append([InlineKeyboardButton("🔙 Back", callback_data='acc')])
            query.edit_message_text("🖥 قنواتك ومجموعاتك:", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('del_'):
        c_id = query.data.split('_')[1]
        conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM entities WHERE id=%s", (c_id,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['deleted'], reply_markup=get_main_keyboard(lang))

    elif query.data == 'get_hook':
        if not u['chans']:
            query.edit_message_text(STRINGS[lang]['no_chans'], reply_markup=get_main_keyboard(lang))
        else:
            query.edit_message_text(STRINGS[lang]['hook_info'].format(url=RENDER_URL, token=u['secret_token']), reply_markup=get_main_keyboard(lang), parse_mode=ParseMode.HTML)

    elif query.data == 'alp_set':
        conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE users SET state='AWAIT_ALPACA' WHERE user_id=%s", (uid,)); conn.commit(); c.close(); conn.close()
        query.edit_message_text(STRINGS[lang]['alp_info'], reply_markup=get_main_keyboard(lang))

# --- 🚀 التشغيل ---
if __name__ == '__main__':
    init_db()
    up = Updater(BOT_TOKEN, use_context=True)
    dp = up.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    # Flask يعمل في Thread منفصل
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    up.start_polling(drop_pending_updates=True)
    up.idle()
