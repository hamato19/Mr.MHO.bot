import os
import logging
import secrets
import asyncio
import threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
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
main_loop = None
application = None # تعريف عالمي للوصول إليه من Flask

# إعداد قاعدة البيانات
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- القاموس الموحد ---
STRINGS = {
    'العربية': {
        'welcome': "👋 أهلاً بك! يرجى اختيار أحد الخيارات...",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{token}</code>",
        'add_ch_msg': "📢 <b>أرسل الآن معرف القناة:</b>\nمثال: -100123456789",
        'add_gr_msg': "💬 <b>أرسل الآن معرف المجموعة:</b>",
        'lang_select': "🌍 <b>اختر اللغة / Select Language:</b>",
        'no_ch': "❌ لا يوجد لديك قنوات مرتبطة.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'add_gr': "💬 إضافة مجموعة", 'del_ent': "❌ إزالة قناة/مجموعة",
            'token': "🔄 توليد رمز أمان", 'wh': "🌐 رابط الويب هوك", 'how': "▶️ طريقة الاستخدام",
            'lang': "🌍 تغيير اللغة", 'trading': "🤖🚀 التداول الآلي 🚀🤖", 'support': "☎️ الدعم", 'back': "🏠 عودة"
        }
    },
    'English': {
        'welcome': "👋 Welcome! Please choose an option...",
        'acc_info': "👤 <b>Your Info:</b>\n🆔 ID: <code>{uid}</code>\n🔑 Token: <code>{token}</code>",
        'add_ch_msg': "📢 <b>Send Channel ID:</b>",
        'add_gr_msg': "💬 <b>Send Group ID:</b>",
        'lang_select': "🌍 <b>Select Language:</b>",
        'no_ch': "❌ No channels linked.",
        'btns': {
            'acc': "👤 My Account", 'buy': "🛒 Subscription", 'my_ch': "📺 My Channels",
            'add_ch': "📢 Add Channel", 'add_gr': "💬 Add Group", 'del_ent': "❌ Remove Entity",
            'token': "🔄 Refresh Token", 'wh': "🌐 Webhook Link", 'how': "▶️ How to use",
            'lang': "🌍 Language", 'trading': "🤖🚀 Auto Trading 🚀🤖", 'support': "☎️ Support", 'back': "🏠 Back"
        }
    }
}

# --- مسارات FLASK (هذا ما كان ينقصك وحل مشكلة 404) ---

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    """استقبال رسائل تلجرام وتحويلها للبوت"""
    global main_loop, application
    update_data = request.get_json(force=True)
    if main_loop and application:
        update = Update.de_json(update_data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
        return 'OK', 200
    return 'Error', 500

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
async def trading_webhook(token, target_id):
    """استقبال تنبيهات TradingView وإرسالها للقناة"""
    conn = get_db_conn()
    try:
        data = request.get_json()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token = %s AND e.entity_id = %s
            """, (token, str(target_id)))
            if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403

        msg = (f"🔔 <b>تنبيه تداول جديد!</b>\n"
               f"📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n"
               f"💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        
        await application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML)
        return jsonify({"status": "success"}), 200
    finally:
        release_db_conn(conn)

# --- الدوال المساعدة للبوت ---

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

async def get_main_menu(lang):
    B = STRINGS[lang]['btns']
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['buy'], callback_data='buy')],
        [InlineKeyboardButton(B['add_ch'], callback_data='add_channel'), InlineKeyboardButton(B['my_ch'], callback_data='my_channels')],
        [InlineKeyboardButton(B['add_gr'], callback_data='add_group')],
        [InlineKeyboardButton(B['del_ent'], callback_data='del_menu')],
        [InlineKeyboardButton(B['wh'], callback_data='url'), InlineKeyboardButton(B['token'], callback_data='gen_token')],
        [InlineKeyboardButton(B['lang'], callback_data='change_lang'), InlineKeyboardButton(B['how'], url="https://servernet.ct.ws")],
        [InlineKeyboardButton(B['trading'], callback_data='alpaca')],
        [InlineKeyboardButton(B['support'], url=f'tg://user?id={ADMIN_ID}')]
    ])

# --- الـ Handlers الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_data(update.effective_user.id)
    await update.message.reply_text(STRINGS[user['language']]['welcome'], reply_markup=await get_main_menu(user['language']), parse_mode=ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')
    if not state: return

    conn = get_db_conn()
    try:
        if state == 'wait_ch':
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (uid, update.message.text))
                conn.commit()
            context.user_data['state'] = None
            user = await get_user_data(uid)
            await update.message.reply_text("✅ تم الحفظ بنجاح!", reply_markup=await get_main_menu(user['language']))
    except:
        await update.message.reply_text("❌ خطأ في الحفظ، تأكد من المعرف.")
    finally: release_db_conn(conn)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    try: await query.answer()
    except: pass

    user = await get_user_data(uid)
    lang = user['language']
    T = STRINGS[lang]

    if query.data == 'home':
        await query.edit_message_text(T['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)
    
    elif query.data == 'acc':
        txt = T['acc_info'].format(uid=uid, token=user['secret_token'])
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(T['btns']['back'], callback_data='home')]]))

    elif query.data == 'add_channel' or query.data == 'add_group':
        context.user_data['state'] = 'wait_ch'
        msg = T['add_ch_msg'] if query.data == 'add_channel' else T['add_gr_msg']
        await query.edit_message_text(msg, parse_mode=ParseMode.HTML)

    elif query.data in ['my_channels', 'url']:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
            ents = cur.fetchall()
        release_db_conn(conn)
        
        if not ents:
            await query.edit_message_text(T['no_ch'], reply_markup=await get_main_menu(lang))
        else:
            txt = "📺 <b>قنواتك وروابط الويب هوك:</b>\n\n"
            for e in ents:
                txt += f"📍 <code>{e['entity_id']}</code>\n🔗 <code>{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}</code>\n\n"
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))

    elif query.data == 'change_lang':
        kb = [[InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_العربية')],
              [InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_English')],
              [InlineKeyboardButton(T['btns']['back'], callback_data='home')]]
        await query.edit_message_text(T['lang_select'], reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('set_lang_'):
        new_l = query.data.split('_')[2]
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_l, uid))
            conn.commit()
        release_db_conn(conn)
        await query.edit_message_text(STRINGS[new_l]['welcome'], reply_markup=await get_main_menu(new_l), parse_mode=ParseMode.HTML)

# --- تشغيل البوت ---

async def main():
    global main_loop, application
    main_loop = asyncio.get_running_loop()
    
    # بناء تطبيق التلجرام
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await application.initialize()
    await application.start()
    
    # ضبط الويب هوك
    webhook_url = f"{DOMAIN}/telegram"
    await application.bot.set_webhook(url=webhook_url)
    logging.info(f"✅ Webhook set to: {webhook_url}")
    
    # تشغيل Flask في خلفية منفصلة
    def run_flask():
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
    
    threading.Thread(target=run_flask, daemon=True).start()

    # إبقاء الـ Loop يعمل
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
