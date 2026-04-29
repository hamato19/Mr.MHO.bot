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
ADMIN_ID = 8711658382 # معرف الآدمن الخاص بك
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
        'intro': "🤖 <b>مرحباً بك في بوت Profit Hook!</b>\n\nنظامنا المتطور يربط إشارات TradingView مباشرة بقنواتك ومجموعاتك في تلجرام عبر الويب هوك بسرعة فائقة.",
        'welcome': "🏠 <b>القائمة الرئيسية:</b>\nيرجى اختيار أحد الخيارات أدناه للتنقل:",
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>\nيمكنك الاشتراك الآن للحصول على كامل المميزات.",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{token}</code>",
        'no_ch_token': "⚠️ <b>تنبيه:</b> لا يمكنك توليد رمز أمان جديد قبل إضافة قناة واحدة على الأقل!",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'add_gr': "💬 إضافة مجموعة", 'del_ent': "❌ إزالة قناة/مجموعة",
            'token': "🔄 توليد رمز أمان", 'wh': "🌐 رابط الويب هوك", 'how': "▶️ طريقة الاستخدام",
            'lang': "🌍 تغيير اللغة", 'trading': "🤖🚀 التداول الآلي 🚀🤖", 'support': "☎️ الدعم", 
            'live_signals': "📊 إشارات مباشرة (Mini App)", 'back': "🏠 القائمة الرئيسية",
            'sub_link': "🔗 اضغط هنا للاشتراك", 'send_code': "🎟️ إرسال كود التفعيل"
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

async def get_main_menu(lang='العربية'):
    B = STRINGS[lang]['btns']
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['buy'], callback_data='buy_menu')],
        [InlineKeyboardButton(B['add_ch'], callback_data='add_channel'), InlineKeyboardButton(B['my_ch'], callback_data='my_channels')],
        [InlineKeyboardButton(B['add_gr'], callback_data='add_group')],
        [InlineKeyboardButton(B['del_ent'], callback_data='del_menu')],
        [InlineKeyboardButton(B['wh'], callback_data='url'), InlineKeyboardButton(B['token'], callback_data='gen_token')],
        [InlineKeyboardButton(B['lang'], callback_data='change_lang'), InlineKeyboardButton(B['how'], url="https://servernet.ct.ws")],
        [InlineKeyboardButton(B['trading'], callback_data='alpaca')],
        [InlineKeyboardButton(B['support'], url=f'tg://user?id={ADMIN_ID}')],
        [InlineKeyboardButton(B['live_signals'], web_app=WebAppInfo(url="https://servernet.ct.ws"))] # مثال للـ Mini App
    ])

# --- الـ Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_data(update.effective_user.id)
    await update.message.reply_text(STRINGS['العربية']['intro'])
    await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    try: await query.answer()
    except: pass

    user = await get_user_data(uid)
    lang = user['language']
    T = STRINGS[lang]
    B = T['btns']

    try:
        if query.data == 'home':
            await query.edit_message_text(T['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)
        
        elif query.data == 'buy_menu':
            kb = [
                [InlineKeyboardButton(B['sub_link'], url="https://servernet.ct.ws")],
                [InlineKeyboardButton(B['send_code'], callback_data='ask_code')],
                [InlineKeyboardButton(B['back'], callback_data='home')]
            ]
            await query.edit_message_text(T['buy_menu'], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

        elif query.data == 'ask_code':
            context.user_data['state'] = 'wait_code'
            await query.edit_message_text("🎟️ <b>يرجى إرسال كود التفعيل الآن:</b>", parse_mode=ParseMode.HTML)

        elif query.data == 'gen_token':
            conn = get_db_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM entities WHERE user_id = %s", (str(uid),))
                if not cur.fetchone():
                    await query.edit_message_text(T['no_ch_token'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)
                    return
                
                new_t = secrets.token_hex(8)
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_t, str(uid)))
                conn.commit()
            release_db_conn(conn)
            await query.edit_message_text(f"✅ تم تحديث رمز الأمان لروابطك:\n<code>{new_t}</code>", 
                                          parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))

        elif query.data in ['my_channels', 'url']:
            conn = get_db_conn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                    ents = cur.fetchall()
                if not ents:
                    await query.edit_message_text(T['no_ch'], reply_markup=await get_main_menu(lang))
                else:
                    txt = "📺 <b>قنواتك وروابط الويب هوك:</b>\n\n"
                    for e in ents:
                        wh = f"{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}"
                        txt += f"📍 ID: <code>{e['entity_id']}</code>\n🔗 Link: <code>{wh}</code>\n\n"
                    await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))
            finally: release_db_conn(conn)

        elif query.data == 'acc':
            txt = T['acc_info'].format(uid=uid, token=user['secret_token'])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

    except Exception as e:
        logging.error(f"Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')
    
    if state == 'wait_code':
        code = update.message.text
        # إرسال الكود للآدمن
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎟️ طلب تفعيل جديد:\nالاسم: {update.effective_user.first_name}\nID: {uid}\nالكود المرسل: {code}")
        context.user_data['state'] = None
        await update.message.reply_text("✅ تم إرسال الكود للآدمن، سيتم التفعيل قريباً.", reply_markup=await get_main_menu())
    
    elif state == 'wait_ch':
        # (منطق إضافة القناة القديم يوضع هنا)
        pass

# --- Flask & Servernet logic ---
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
