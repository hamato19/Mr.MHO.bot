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

# --- الإعدادات ---
DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382 
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
main_loop = None
application = None 

# إعداد قاعدة البيانات
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- القاموس الموحد المحدث ---
STRINGS = {
    'العربية': {
        'intro': "🤖 <b>مرحباً بك في Profit Hook!</b>\nنظام ربط TradingView بتلجرام عبر الويب هوك.",
        'welcome': "🏠 <b>القائمة الرئيسية:</b>",
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{token}</code>",
        'add_ch_msg': "📢 <b>أرسل الآن معرف القناة أو المجموعة:</b>\nمثال: <code>-100123456789</code>",
        'lang_select': "🌍 <b>اختر اللغة / Select Language:</b>",
        'no_ch': "❌ لا يوجد لديك قنوات مرتبطة.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'add_gr': "💬 إضافة مجموعة", 'del_ent': "❌ إزالة قناة",
            'token': "🔄 توليد رمز أمان", 'wh': "🌐 رابط الويب هوك", 'how': "▶️ طريقة الاستخدام",
            'lang': "🌍 اللغة / Language", 'trading': "🤖🚀 التداول الآلي", 'support': "☎️ الدعم", 
            'tv': "📊 TradingView", 'back': "🏠 القائمة الرئيسية", 'send_code': "🎟️ إرسال كود التفعيل"
        }
    },
    'English': {
        'intro': "🤖 <b>Welcome to Profit Hook!</b>",
        'welcome': "🏠 <b>Main Menu:</b>",
        'buy_menu': "🛒 <b>Subscription:</b>",
        'acc_info': "👤 <b>Your Account:</b>\n🆔 ID: <code>{uid}</code>\n🔑 Token: <code>{token}</code>",
        'add_ch_msg': "📢 <b>Send Channel or Group ID:</b>",
        'lang_select': "🌍 <b>Select Language:</b>",
        'no_ch': "❌ No linked channels.",
        'btns': {
            'acc': "👤 My Account", 'buy': "🛒 Activation", 'my_ch': "📺 My Channels",
            'add_ch': "📢 Add Channel", 'add_gr': "💬 Add Group", 'del_ent': "❌ Remove Channel",
            'token': "🔄 Refresh Token", 'wh': "🌐 Webhook Link", 'how': "▶️ How to use",
            'lang': "🌍 Language", 'trading': "🤖🚀 Auto Trading", 'support': "☎️ Support", 
            'tv': "📊 TradingView", 'back': "🏠 Main Menu", 'send_code': "🎟️ Send Activation Code"
        }
    }
}

# --- الدوال المساعدة ---
async def get_user_data(uid):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s) RETURNING *", (str(uid), token, 'العربية'))
                conn.commit()
                user = cur.fetchone()
        return user
    finally: release_db_conn(conn)

async def get_main_menu(lang):
    B = STRINGS[lang]['btns']
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['buy'], callback_data='buy_menu')],
        [InlineKeyboardButton(B['add_ch'], callback_data='add_channel'), InlineKeyboardButton(B['my_ch'], callback_data='my_channels')],
        [InlineKeyboardButton(B['wh'], callback_data='url'), InlineKeyboardButton(B['token'], callback_data='gen_token')],
        [InlineKeyboardButton(B['lang'], callback_data='change_lang'), InlineKeyboardButton(B['how'], url="https://servernet.ct.ws")],
        [InlineKeyboardButton(B['tv'], web_app=WebAppInfo(url="https://www.tradingview.com"))],
        [InlineKeyboardButton(B['support'], url=f'tg://user?id={ADMIN_ID}')]
    ])

# --- الـ Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_data(update.effective_user.id)
    lang = user['language']
    await update.message.reply_text(STRINGS[lang]['intro'], parse_mode=ParseMode.HTML)
    await update.message.reply_text(STRINGS[lang]['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    # استجابة سريعة للمس
    await query.answer()

    user = await get_user_data(uid)
    lang = user['language']
    T = STRINGS[lang]

    if query.data == 'home':
        await query.edit_message_text(T['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)
    
    elif query.data == 'change_lang':
        kb = [[InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_العربية')],
              [InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_English')],
              [InlineKeyboardButton(T['btns']['back'], callback_data='home')]]
        await query.edit_message_text(T['lang_select'], reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('set_lang_'):
        new_lang = query.data.split('_')[2]
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_lang, str(uid)))
            conn.commit()
        release_db_conn(conn)
        await query.edit_message_text(STRINGS[new_lang]['welcome'], reply_markup=await get_main_menu(new_lang), parse_mode=ParseMode.HTML)

    elif query.data == 'add_channel':
        context.user_data['state'] = 'wait_ch'
        await query.edit_message_text(T['add_ch_msg'], parse_mode=ParseMode.HTML, 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(T['btns']['back'], callback_data='home')]]))

    elif query.data in ['my_channels', 'url']:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
            ents = cur.fetchall()
        release_db_conn(conn)
        if not ents:
            await query.edit_message_text(T['no_ch'], reply_markup=await get_main_menu(lang))
        else:
            txt = "📺 <b>Channels:</b>\n"
            for e in ents:
                txt += f"🔗 <code>{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}</code>\n\n"
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')
    user = await get_user_data(uid)
    lang = user['language']

    if state == 'wait_ch':
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), update.message.text))
                conn.commit()
            context.user_data['state'] = None
            await update.message.reply_text("✅ تم ربط القناة بنجاح!", reply_markup=await get_main_menu(lang))
        except:
            await update.message.reply_text("❌ خطأ: المعرف موجود مسبقاً أو غير صحيح.")
        finally: release_db_conn(conn)

# --- مسارات الويب هوك (Webhook) ---
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    global main_loop, application
    update_data = request.get_json(force=True)
    if main_loop and application:
        update = Update.de_json(update_data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
        return 'OK', 200
    return 'Error', 500

async def main():
    global main_loop, application
    main_loop = asyncio.get_running_loop()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"{DOMAIN}/telegram")
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
