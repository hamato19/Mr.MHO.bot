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

# --- الدوال المساعدة ---
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

# --- Handlers ---
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
            await update.message.reply_text("✅ تم الحفظ بنجاح!", reply_markup=await get_main_menu((await get_user_data(uid))['language']))
    finally: release_db_conn(conn)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    try:
        await query.answer() 
    except:
        logging.warning("⚠️ Callback answer timeout")

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
            txt = "📺 <b>قنواتك:</b>\n" if lang == 'العربية' else "📺 <b>Your Channels:</b>\n"
            for e in ents:
                txt += f"🔗 <code>{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}</code>\n\n"
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

    elif query.data == 'gen_token':
        new_t = secrets.token_hex(8)
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_t, uid))
            conn.commit()
        release_db_conn(conn)
        await query.edit_message_text(f"✅ New Token: <code>{new_t}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))

# --- تشغيل البوت ---
async def main():
    global main_loop
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
