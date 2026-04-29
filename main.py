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

# --- قاموس النصوص الكامل (عربي/إنجليزي) ---
STRINGS = {
    'العربية': {
        'welcome': "👋 أهلاً بك! يرجى اختيار أحد الخيارات...",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{token}</code>",
        'add_ch_msg': "📢 <b>أرسل الآن معرف القناة:</b>\nمثال: -100123456789",
        'add_gr_msg': "💬 <b>أرسل الآن معرف المجموعة:</b>",
        'lang_select': "🌍 <b>اختر اللغة / Select Language:</b>",
        'btns': {
            'acc': "👤 حسابي",
            'buy': "🛒 تفعيل الاشتراك",
            'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة",
            'add_gr': "💬 إضافة مجموعة",
            'del_ent': "❌ إزالة قناة/مجموعة",
            'token': "🔄 توليد رمز أمان",
            'wh': "🌐 رابط الويب هوك",
            'how': "▶️ طريقة الاستخدام",
            'lang': "🌍 تغيير اللغة",
            'trading': "🤖🚀 التداول الآلي 🚀🤖",
            'support': "☎️ الدعم",
            'back': "🏠 عودة"
        }
    },
    'English': {
        'welcome': "👋 Welcome! Please choose an option...",
        'acc_info': "👤 <b>Your Info:</b>\n🆔 ID: <code>{uid}</code>\n🔑 Token: <code>{token}</code>",
        'add_ch_msg': "📢 <b>Send Channel ID:</b>\nEx: -100123456789",
        'add_gr_msg': "💬 <b>Send Group ID:</b>",
        'lang_select': "🌍 <b>Select Language:</b>",
        'btns': {
            'acc': "👤 My Account",
            'buy': "🛒 Subscription",
            'my_ch': "📺 My Channels",
            'add_ch': "📢 Add Channel",
            'add_gr': "💬 Add Group",
            'del_ent': "❌ Remove Entitiy",
            'token': "🔄 Gen Security Token",
            'wh': "🌐 Webhook Link",
            'how': "▶️ How to use",
            'lang': "🌍 Language",
            'trading': "🤖🚀 Auto Trading 🚀🤖",
            'support': "☎️ Support",
            'back': "🏠 Back"
        }
    }
}

# إعداد قاعدة البيانات
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- بناء القائمة بنفس ترتيب الصورة تماماً ---
async def get_main_menu(lang):
    B = STRINGS[lang]['btns']
    keyboard = [
        [InlineKeyboardButton(B['buy'], callback_data='buy'), InlineKeyboardButton(B['acc'], callback_data='acc')],
        [InlineKeyboardButton(B['my_ch'], callback_data='my_channels'), InlineKeyboardButton(B['add_ch'], callback_data='add_channel')],
        [InlineKeyboardButton(B['add_gr'], callback_data='add_group')],
        [InlineKeyboardButton(B['del_ent'], callback_data='del_menu')],
        [InlineKeyboardButton(B['token'], callback_data='gen_token'), InlineKeyboardButton(B['wh'], callback_data='url')],
        [InlineKeyboardButton(B['how'], url="https://servernet.ct.ws"), InlineKeyboardButton(B['lang'], callback_data='change_lang')],
        [InlineKeyboardButton(B['trading'], callback_data='alpaca')],
        [InlineKeyboardButton(B['support'], url=f'tg://user?id={ADMIN_ID}')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- معالج الضغط على الأزرار ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()
    
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            lang = user['language'] if user else 'العربية'
            T = STRINGS[lang]

            if query.data == 'home':
                await query.edit_message_text(T['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)

            elif query.data == 'acc':
                txt = T['acc_info'].format(uid=uid, token=user['secret_token'])
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, 
                                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(T['btns']['back'], callback_data='home')]]))

            elif query.data == 'change_lang':
                kb = [[InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_العربية')],
                      [InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_English')],
                      [InlineKeyboardButton(T['btns']['back'], callback_data='home')]]
                await query.edit_message_text(T['lang_select'], reply_markup=InlineKeyboardMarkup(kb))

            elif query.data.startswith('set_lang_'):
                new_l = query.data.split('_')[2]
                cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_l, uid))
                conn.commit()
                await query.edit_message_text(STRINGS[new_l]['welcome'], reply_markup=await get_main_menu(new_l), parse_mode=ParseMode.HTML)

            elif query.data == 'add_channel':
                context.user_data['state'] = 'wait_ch'
                await query.edit_message_text(T['add_ch_msg'], parse_mode=ParseMode.HTML)

            elif query.data == 'add_group':
                context.user_data['state'] = 'wait_ch'
                await query.edit_message_text(T['add_gr_msg'], parse_mode=ParseMode.HTML)

            elif query.data in ['my_channels', 'url']:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
                if not ents:
                    await query.edit_message_text(STRINGS[lang]['no_ch'] if 'no_ch' in STRINGS[lang] else "❌ لا يوجد قنوات", 
                                                  reply_markup=await get_main_menu(lang))
                else:
                    txt = STRINGS[lang]['my_ch_title']
                    for e in ents:
                        wh_link = f"{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}"
                        txt += f"📍 <code>{e['entity_id']}</code>\n🔗 <code>{wh_link}</code>\n\n"
                    await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))

    finally: release_db_conn(conn)

# --- إطلاق البوت ---
async def run_bot():
    global main_loop
    main_loop = asyncio.get_running_loop()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # الروابط والمعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"{DOMAIN}/telegram")
    
    # تشغيل Flask في Thread
    def start_flask():
        server = make_server('0.0.0.0', int(os.environ.get('PORT', 10000)), app)
        server.serve_forever()
    
    threading.Thread(target=start_flask, daemon=True).start()
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(run_bot())
