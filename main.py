import os
import logging
import secrets
import psycopg2
import asyncio
import threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from werkzeug.serving import make_server

# --- الإعدادات ---
DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com") 

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- نظام النصوص ---
STRINGS = {
    'العربية': {
        'start_msg': "👋 أهلاً بك في بوت <b>Mr.MHO</b>",
        'main_menu': "🏠 القائمة الرئيسية لبوت <b>Mr.MHO</b>",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{token}</code>",
        'lang_success': "✅ تم تغيير اللغة إلى: <b>العربية</b>",
        'set_lang_prompt': "🌍 اختر اللغة / Choose Language",
        'no_channels': "❌ لم تضف قنوات بعد.",
        'webhooks_title': "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n",
        'buy_msg': "💎 <b>تفعيل الاشتراك المميز</b>\nأرسل رقم الطلب بعد الشراء من الموقع.",
        'alpaca_msg': "🚀 <b>إعدادات Alpaca:</b>\nيرجى ضبط مفاتيح التداول الآلي.",
        'wait_ch': "📢 أرسل ID القناة أو المجموعة (مثال: -100xxx):",
        'wait_order': "📝 أرسل رقم الطلب الآن:",
        'wait_key': "📝 أرسل Key ID الخاص بـ Alpaca:",
        'wait_sec': "📝 أرسل Secret Key الخاص بـ Alpaca:",
        'sent_to_admin': "✅ تم إرسال الطلب للمراجعة.",
        'gen_token_msg': "🔄 تم تحديث الرمز: <code>{token}</code>",
        'del_prompt': "❌ اختر القناة المراد إزالتها:",
        'del_success': "✅ تم حذف القناة <code>{target}</code>.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'add': "📢 إضافة قناة",
            'my_ch': "📺 قنواتي", 'group': "💬 إضافة مجموعة", 'del': "❌ إزالة قناة",
            'url': "🌐 رابط الويب هوك", 'token': "🔄 توليد رمز أمان", 'lang': "🌍 تغيير اللغة",
            'how': "▶️ طريقة الاستخدام", 'alpaca': "🚀 التداول الآلي 🤖🚀", 'support': "☎️ الدعم",
            'home': "🏠 الرئيسية", 'send_id': "🔑 إرسال كود التفعيل", 'buy_link': "🌐 للاشتراك اضغط هنا"
        }
    },
    'English': {
        'start_msg': "👋 Welcome to <b>Mr.MHO</b> Bot",
        'main_menu': "🏠 <b>Mr.MHO</b> Main Menu",
        'acc_info': "👤 <b>Account Details:</b>\n🆔 ID: <code>{uid}</code>\n🔑 Token: <code>{token}</code>",
        'lang_success': "✅ Language changed to: <b>English</b>",
        'set_lang_prompt': "🌍 Choose Language / اختر اللغة",
        'no_channels': "❌ No channels added yet.",
        'webhooks_title': "🌐 <b>Your Webhook URLs:</b>\n\n",
        'buy_msg': "💎 <b>Premium Subscription</b>\nPlease send your Order ID.",
        'alpaca_msg': "🚀 <b>Alpaca Settings:</b>\nPlease configure your trading keys.",
        'wait_ch': "📢 Send Channel/Group ID (e.g., -100xxx):",
        'wait_order': "📝 Send your Order ID now:",
        'wait_key': "📝 Send your Alpaca Key ID:",
        'wait_sec': "📝 Send your Alpaca Secret Key:",
        'sent_to_admin': "✅ Request sent for review.",
        'gen_token_msg': "🔄 Token updated: <code>{token}</code>",
        'del_prompt': "❌ Select channel to remove:",
        'del_success': "✅ Channel <code>{target}</code> removed.",
        'btns': {
            'acc': "👤 Account", 'buy': "🛒 Activate", 'add': "📢 Add Channel",
            'my_ch': "📺 My Channels", 'group': "💬 Add Group", 'del': "❌ Remove Channel",
            'url': "🌐 Webhook URL", 'token': "🔄 New Token", 'lang': "🌍 Language",
            'how': "▶️ How to use", 'alpaca': "🚀 Auto Trading 🤖🚀", 'support': "☎️ Support",
            'home': "🏠 Home", 'send_id': "🔑 Send Order ID", 'buy_link': "🌐 Buy Subscription"
        }
    }
}

# --- قاعدة البيانات ---
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

async def get_user_data(uid):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s) RETURNING *", (uid, token, 'العربية'))
                conn.commit()
                user = cur.fetchone()
        return user
    finally: release_db_conn(conn)

async def get_main_menu(lang='العربية'):
    B = STRINGS[lang]['btns']
    keyboard = [
        [InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['buy'], callback_data='buy')],
        [InlineKeyboardButton(B['add'], callback_data='add_channel'), InlineKeyboardButton(B['my_ch'], callback_data='url')],
        [InlineKeyboardButton(B['group'], callback_data='add_group')],
        [InlineKeyboardButton(B['del'], callback_data='del_menu')],
        [InlineKeyboardButton(B['url'], callback_data='url'), InlineKeyboardButton(B['token'], callback_data='gen_token')],
        [InlineKeyboardButton(B['lang'], callback_data='change_lang'), InlineKeyboardButton(B['how'], url='https://servernet.ct.ws')],
        [InlineKeyboardButton(B['alpaca'], callback_data='alpaca')],
        [InlineKeyboardButton(B['support'], url=f'tg://user?id={ADMIN_ID}')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- تطبيق التلجرام ---
application = ApplicationBuilder().token(BOT_TOKEN).build()

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    try:
        update_data = request.get_json(force=True)
        loop = getattr(application, 'loop', None)
        if loop and loop.is_running():
            update = Update.de_json(update_data, application.bot)
            asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
            return 'OK', 200
        return 'Loop not ready', 503
    except Exception as e:
        logging.error(f"❌ Error in webhook: {e}")
        return 'Error', 500

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
async def trading_webhook(token, target_id):
    conn = get_db_conn()
    try:
        data = request.get_json()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT u.user_id FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token = %s AND e.entity_id = %s", (token, str(target_id)))
            if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403
        msg = (f"🔔 <b>تنبيه تداول جديد!</b>\n📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        await application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally: release_db_conn(conn)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_data(update.effective_user.id)
    lang = user.get('language', 'العربية')
    await update.message.reply_text(STRINGS[lang]['start_msg'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, text = update.effective_user.id, update.message.text
    state = context.user_data.get('state')
    if not state: return
    user = await get_user_data(uid)
    lang = user.get('language', 'العربية')
    T = STRINGS[lang]
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            if state == 'wait_ch':
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (uid, text))
                conn.commit()
                await update.message.reply_text(T['del_success'].format(target=text), parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))
            elif state == 'wait_order':
                await context.bot.send_message(ADMIN_ID, f"🔔 Order ID: {text} from {uid}")
                await update.message.reply_text(T['sent_to_admin'], reply_markup=await get_main_menu(lang))
    finally:
        release_db_conn(conn)
        context.user_data['state'] = None

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()
    user = await get_user_data(uid)
    lang = user.get('language', 'العربية')
    T = STRINGS[lang]
    if query.data == 'home':
        await query.edit_message_text(T['main_menu'], parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))
    elif query.data == 'acc':
        await query.edit_message_text(T['acc_info'].format(uid=uid, token=user['secret_token']), parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))
    elif query.data == 'url':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
            if not ents:
                await query.edit_message_text(T['no_channels'], reply_markup=await get_main_menu(lang))
            else:
                txt = T['webhooks_title']
                for e in ents:
                    txt += f"📢: <code>{e['entity_id']}</code>\n🔗: <code>{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}</code>\n\n"
                await context.bot.send_message(chat_id=uid, text=txt, parse_mode=ParseMode.HTML)
                await query.edit_message_text("✅ تم إرسال الروابط لخاصك.", reply_markup=await get_main_menu(lang))
        finally: release_db_conn(conn)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(button_callback))

# --- تشغيل موحد ---
async def run_bot():
    await application.initialize()
    application.loop = asyncio.get_running_loop()
    await application.bot.set_webhook(url=f"{DOMAIN}/telegram")
    await application.start()
    logging.info("✅ Bot initialized and Webhook set.")
    
    # تشغيل Flask في Thread منفصل
    port = int(os.environ.get('PORT', 10000))
    server = make_server('0.0.0.0', port, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(run_bot())
