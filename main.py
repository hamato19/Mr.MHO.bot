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

# --- القاموس الموحد ---
STRINGS = {
    'العربية': {
        'intro': "🤖 <b>مرحباً بك في Profit Hook!</b>\nنظام ربط TradingView بتلجرام.",
        'welcome': "🏠 <b>القائمة الرئيسية:</b>",
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>\nيمكنك الاشتراك عبر الرابط أو إرسال الكود للدعم.",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: <code>{ch_count}</code>\n- أيام الاشتراك: <code>0</code>\n- إشارات متبقية مجانية: <code>100</code>",
        'add_ch_msg': "📢 <b>أرسل معرف القناة:</b>\nأرسل أرقاماً فقط (بدون رموز أو شرطة).\nمثال: <code>123456789</code>",
        'no_ch': "❌ لا يوجد قنوات مرتبطة حالياً.",
        'no_ch_gen': "⚠️ يجب إضافة قناة أولاً قبل توليد رمز أمان جديد.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'token': "🔄 توليد رمز أمان جديد", 'wh': "🌐 روابط الويب هوك", 
            'how': "▶️ طريقة الاستخدام", 'lang': "🌍 English", 'support': "☎️ الدعم", 
            'tv': "📊 الشارت (TradingView)", 'back': "🏠 القائمة الرئيسية", 
            'send_code': "🎟️ إرسال كود التفعيل", 'sub_link': "🔗 رابط الاشتراك"
        }
    },
    'English': {
        'intro': "🤖 <b>Welcome to Profit Hook!</b>",
        'welcome': "🏠 <b>Main Menu:</b>",
        'buy_menu': "🛒 <b>Activation:</b>",
        'acc_info': "👤 <b>Account Info:</b>\n\n- User ID: <code>{uid}</code>\n- Active Channels: <code>{ch_count}</code>\n- Subscription Days: <code>0</code>\n- Remaining Free Signals: <code>100</code>",
        'add_ch_msg': "📢 <b>Send Channel ID:</b>\nNumbers only.\nExample: <code>123456789</code>",
        'no_ch': "❌ No linked channels.",
        'no_ch_gen': "⚠️ Add a channel first before generating a token.",
        'btns': {
            'acc': "👤 My Account", 'buy': "🛒 Activation", 'my_ch': "📺 My Channels",
            'add_ch': "📢 Add Channel", 'token': "🔄 New Token", 'wh': "🌐 Webhook Links", 
            'how': "▶️ Tutorial", 'lang': "🌍 العربية", 'support': "☎️ Support", 
            'tv': "📊 Chart (TradingView)", 'back': "🏠 Main Menu",
            'send_code': "🎟️ Send Code", 'sub_link': "🔗 Subscription Link"
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
        [InlineKeyboardButton(B['tv'], web_app=WebAppInfo(url="https://www.tradingview.com/chart/"))],
        [InlineKeyboardButton(B['lang'], callback_data='change_lang'), InlineKeyboardButton(B['how'], url="https://servernet.ct.ws")],
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
    await query.answer()
    user = await get_user_data(uid)
    lang = user['language']
    B = STRINGS[lang]['btns']

    if query.data == 'home':
        await query.edit_message_text(STRINGS[lang]['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)
    
    elif query.data == 'acc':
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                ch_count = cur.fetchone()[0]
            txt = STRINGS[lang]['acc_info'].format(uid=uid, ch_count=ch_count)
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))
        finally: release_db_conn(conn)

    elif query.data == 'buy_menu':
        kb = [[InlineKeyboardButton(B['sub_link'], url="https://servernet.ct.ws")],
              [InlineKeyboardButton(B['send_code'], callback_data='ask_code')],
              [InlineKeyboardButton(B['back'], callback_data='home')]]
        await query.edit_message_text(STRINGS[lang]['buy_menu'], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data == 'ask_code':
        context.user_data['state'] = 'wait_code'
        await query.edit_message_text("🎟️ <b>يرجى إرسال كود التفعيل الآن:</b>", parse_mode=ParseMode.HTML)

    elif query.data == 'add_channel':
        context.user_data['state'] = 'wait_ch'
        await query.edit_message_text(STRINGS[lang]['add_ch_msg'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

    elif query.data in ['my_channels', 'url']:
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
            if not ents:
                await query.edit_message_text(STRINGS[lang]['no_ch'], reply_markup=await get_main_menu(lang))
            else:
                txt = "📺 <b>قنواتك وروابط الويب هوك الخاصة بها:</b>\n"
                kb = []
                for e in ents:
                    eid = e['entity_id']
                    wh = f"{DOMAIN}/webhook/{user['secret_token']}/{eid}"
                    txt += f"\n📍 ID: <code>{eid}</code>\n🔗 <code>{wh}</code>\n"
                    kb.append([InlineKeyboardButton(f"🗑️ حذف {eid}", callback_data=f"del_{eid}")])
                kb.append([InlineKeyboardButton(B['back'], callback_data='home')])
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        finally: release_db_conn(conn)

    elif query.data.startswith('del_'):
        target = query.data.split('_')[1]
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), target))
            conn.commit()
        release_db_conn(conn)
        await query.edit_message_text(f"✅ تم حذف القناة {target} بنجاح.", reply_markup=await get_main_menu(lang))

    elif query.data == 'gen_token':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
                if not ents:
                    await query.answer("⚠️ لا توجد قنوات مضافة!", show_alert=True)
                    msg = STRINGS[lang].get('no_ch_gen', "⚠️ أضف قناة أولاً.")
                    await query.edit_message_text(msg, reply_markup=await get_main_menu(lang))
                else:
                    new_t = secrets.token_hex(8)
                    cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_t, str(uid)))
                    conn.commit()
                    txt = f"✅ <b>تم تحديث رمز الأمان بنجاح!</b>\n🔑 الرمز الجديد: <code>{new_t}</code>\n\n⚠️ يرجى تحديث الروابط في TradingView فوراً:\n"
                    for e in ents:
                        new_wh = f"{DOMAIN}/webhook/{new_t}/{e['entity_id']}"
                        txt += f"\n📍 القناة: <code>{e['entity_id']}</code>\n🔗 <code>{new_wh}</code>\n"
                    await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))
                    await query.answer("✅ تم التحديث")
        finally: release_db_conn(conn)

    elif query.data == 'change_lang':
        new_lang = 'English' if lang == 'العربية' else 'العربية'
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_lang, str(uid)))
            conn.commit()
        release_db_conn(conn)
        await query.edit_message_text(STRINGS[new_lang]['welcome'], reply_markup=await get_main_menu(new_lang), parse_mode=ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')
    user = await get_user_data(uid)
    lang = user['language']

    if state == 'wait_ch':
        raw = update.message.text.strip()
        if not raw.isdigit():
            await update.message.reply_text("❌ خطأ: يرجى إرسال أرقام فقط.")
            return
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), raw))
                conn.commit()
            context.user_data['state'] = None
            await update.message.reply_text("✅ تم ربط القناة بنجاح!", reply_markup=await get_main_menu(lang))
        except: await update.message.reply_text("❌ هذا المعرف مسجل مسبقاً.")
        finally: release_db_conn(conn)

    elif state == 'wait_code':
        code = update.message.text
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎟️ <b>طلب تفعيل جديد:</b>\n👤 {update.effective_user.first_name}\n🆔 {uid}\n🎫 الكود: <code>{code}</code>", parse_mode=ParseMode.HTML)
        context.user_data['state'] = None
        await update.message.reply_text("✅ تم إرسال طلبك للدعم الفني بنجاح.", reply_markup=await get_main_menu(lang))

# --- Flask Webhooks ---
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    update_data = request.get_json(force=True)
    if main_loop and application:
        update = Update.de_json(update_data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
    return 'OK', 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    conn = get_db_conn()
    try:
        data = request.get_json(force=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token = %s AND e.entity_id = %s", (token, str(target_id)))
            if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403

        real_chat_id = f"-100{target_id}" if not str(target_id).startswith('-') else target_id
        msg = (f"🔔 <b>تنبيه تداول جديد!</b>\n\n"
               f"📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n"
               f"💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        
        asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id=real_chat_id, text=msg, parse_mode=ParseMode.HTML), main_loop)
        return jsonify({"status": "success"}), 200
    except: return jsonify({"status": "error"}), 500
    finally: release_db_conn(conn)

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
