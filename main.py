import os
import logging
import secrets
import asyncio
import threading
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- الإعدادات الأساسية ---
DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382 
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
main_loop = None
application = None 

# --- إدارة قاعدة البيانات المحسنة ---
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)

@contextmanager
def get_db():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

# --- نصوص البوت ---
STRINGS = {
    'العربية': {
        'intro': "🤖 <b>مرحباً بك في Profit Hook!</b>\nنظام ربط TradingView بتلجرام المتطور.",
        'welcome': "🏠 <b>القائمة الرئيسية:</b>",
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>\nيمكنك الاشتراك عبر الموقع أو إرسال كود التفعيل بشكل آمن.",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المربوطة: <code>{ch_count}</code>",
        'no_ch': "❌ لا يوجد قنوات مرتبطة حالياً.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 التفعيل", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'token': "🔄 توليد رمز جديد", 'wh': "🌐 الويب هوك", 
            'tv': "📊 TradingView", 'back': "🏠 القائمة الرئيسية", 
            'send_code': "🎟️ إرسال كود التفعيل", 'sub_link': "🔗 رابط الاشتراك",
            'how': "▶️ طريقة الاستخدام", 'support': "☎️ الدعم الفني",
            'admin_btn': "👮 إضافة البوت كمشرف"
        }
    }
}

async def get_main_menu():
    B = STRINGS['العربية']['btns']
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['buy'], callback_data='buy_menu')],
        [InlineKeyboardButton(B['add_ch'], callback_data='add_channel'), InlineKeyboardButton(B['my_ch'], callback_data='view_channels')],
        [InlineKeyboardButton(B['wh'], callback_data='view_webhooks'), InlineKeyboardButton(B['token'], callback_data='gen_token')],
        [InlineKeyboardButton(B['tv'], web_app=WebAppInfo(url="https://www.tradingview.com/chart/"))],
        [InlineKeyboardButton(B['admin_btn'], url=f"https://t.me/{application.bot.username}?startchannel=true&admin=post_messages+edit_messages+delete_messages")],
        [InlineKeyboardButton(B['how'], url="https://servernet.ct.ws"), InlineKeyboardButton(B['support'], url=f"tg://user?id={ADMIN_ID}")],
        [InlineKeyboardButton(B['back'], callback_data='home')]
    ])

# --- الـ Handlers الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id = %s", (str(uid),))
            if not cur.fetchone():
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s)", (str(uid), secrets.token_hex(8), 'العربية'))
                conn.commit()
    await update.message.reply_text(STRINGS['العربية']['intro'], parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    B = STRINGS['العربية']['btns']
    await query.answer()

    # --- الحالة 1: القائمة الرئيسية ---
    if query.data == 'home':
        await query.edit_message_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
    
    # --- الحالة 2: حسابي ---
    elif query.data == 'acc':
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                count = cur.fetchone()[0]
        txt = STRINGS['العربية']['acc_info'].format(uid=uid, ch_count=count)
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

    # --- الحالة 3: قائمة الشراء ---
    elif query.data == 'buy_menu':
        kb = [[InlineKeyboardButton(B['sub_link'], url="https://servernet.ct.ws")],
              [InlineKeyboardButton(B['send_code'], web_app=WebAppInfo(url=f"{DOMAIN}/activation_page"))],
              [InlineKeyboardButton(B['back'], callback_data='home')]]
        await query.edit_message_text(STRINGS['العربية']['buy_menu'], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    # --- الحالة 4: إضافة قناة ---
    elif query.data == 'add_channel':
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📂 اختر قناة من حسابك", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="📢 يرجى الضغط على الزر ومشاركة القناة المطلوب ربطها:", 
                                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    # --- الحالة 5: عرض القنوات ---
    elif query.data == 'view_channels':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text(STRINGS['العربية']['no_ch'], reply_markup=await get_main_menu())
        else:
            txt = "📺 <b>قنواتك المرتبطة:</b>\n"
            kb = [[InlineKeyboardButton(f"🗑️ حذف {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
            kb.append([InlineKeyboardButton(B['back'], callback_data='home')])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    # --- الحالة 6: عرض الويب هوك ---
    elif query.data == 'view_webhooks':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                token = cur.fetchone()['secret_token']
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text(STRINGS['العربية']['no_ch'], reply_markup=await get_main_menu())
        else:
            txt = "🌐 <b>روابط الويب هوك:</b>\n"
            for e in ents:
                wh = f"{DOMAIN}/webhook/{token}/{e['entity_id']}"
                txt += f"\n📍 القناة: <code>{e['entity_id']}</code>\n🔗 <code>{wh}</code>\n"
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

    # --- الحالة 7: توليد رمز جديد ---
    elif query.data == 'gen_token':
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (secrets.token_hex(8), str(uid)))
                conn.commit()
        await query.answer("✅ تم تحديث الرمز!", show_alert=True)
        query.data = 'view_webhooks'
        await button_callback(update, context)

    # --- الحالة 8: حذف قناة ---
    elif query.data.startswith('del_'):
        target = query.data.split('_')[1]
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), target))
                conn.commit()
        await query.answer(f"🗑️ تم حذف {target}")
        query.data = 'view_channels'
        await button_callback(update, context)



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if context.user_data.get('state') == 'wait_ch' and update.message.chat_shared:
        target_id = str(update.message.chat_shared.chat_id)
        if not target_id.startswith('-100'): target_id = f"-100{target_id}"
        with get_db() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), target_id))
                    conn.commit()
                await update.message.reply_text(f"✅ تم ربط القناة بنجاح!\nID: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
                await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=await get_main_menu())
            except:
                await update.message.reply_text("❌ هذه القناة مضافة مسبقاً.")
        context.user_data['state'] = None

# --- مسارات الويب (Flask) ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    try:
        data = request.get_json(force=True)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token = %s AND e.entity_id = %s", (token, str(target_id)))
                if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403
        msg = (f"🔔 <b>تنبيه تداول!</b>\n\n📈 الأداة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ العملية: <b>{data.get('action', 'N/A')}</b>\n💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML), main_loop)
        return jsonify({"status": "success"}), 200
    except: return jsonify({"status": "error"}), 500

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    update_data = request.get_json(force=True)
    if main_loop and application:
        update = Update.de_json(update_data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
    return 'OK', 200

async def main():
    global main_loop, application
    main_loop = asyncio.get_running_loop()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"{DOMAIN}/telegram")
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
