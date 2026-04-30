import os
import logging
import secrets
import asyncio
import threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButtonRequestChat
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
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>\nيمكنك الاشتراك عبر الرابط أو إرسال الكود للدعم عبر النافذة الآمنة.",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: <code>{ch_count}</code>",
        'add_ch_msg': "📢 <b>إضافة قناة جديدة:</b>\nاضغط على الزر بالأسفل لاختيار قناة من حسابك.",
        'no_ch': "❌ لا يوجد قنوات مرتبطة حالياً.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'token': "🔄 توليد رمز جديد", 'wh': "🌐 روابط الويب هوك", 
            'how': "▶️ طريقة الاستخدام", 'lang': "🌍 English", 'support': "☎️ الدعم", 
            'tv': "📊 الشارت (TradingView)", 'back': "🏠 القائمة الرئيسية", 
            'send_code': "🎟️ إرسال كود التفعيل", 'sub_link': "🔗 رابط الاشتراك",
            'share_btn': "📂 اختر قناة من حسابك"
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

async def get_main_menu():
    B = STRINGS['العربية']['btns']
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['buy'], callback_data='buy_menu')],
        [InlineKeyboardButton(B['add_ch'], callback_data='add_channel'), InlineKeyboardButton(B['my_ch'], callback_data='url')],
        [InlineKeyboardButton(B['wh'], callback_data='url'), InlineKeyboardButton(B['token'], callback_data='gen_token')],
        [InlineKeyboardButton(B['tv'], web_app=WebAppInfo(url="https://www.tradingview.com/chart/"))],
        [InlineKeyboardButton(B['lang'], callback_data='change_lang'), InlineKeyboardButton(B['how'], url="https://servernet.ct.ws")],
        [InlineKeyboardButton(B['support'], url=f'tg://user?id={ADMIN_ID}')]
    ])

# --- الـ Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    await get_user_data(update.effective_user.id)
    await update.message.reply_text(STRINGS['العربية']['intro'], parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()
    user = await get_user_data(uid)
    B = STRINGS['العربية']['btns']

    if query.data == 'home':
        await query.edit_message_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
    
    elif query.data == 'acc':
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                count = cur.fetchone()[0]
            txt = STRINGS['العربية']['acc_info'].format(uid=uid, ch_count=count)
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))
        finally: release_db_conn(conn)

    elif query.data == 'buy_menu':
        kb = [[InlineKeyboardButton(B['sub_link'], url="https://servernet.ct.ws")],
              [InlineKeyboardButton(B['send_code'], web_app=WebAppInfo(url=f"{DOMAIN}/activation_page"))],
              [InlineKeyboardButton(B['back'], callback_data='home')]]
        await query.edit_message_text(STRINGS['العربية']['buy_menu'], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data == 'url':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
            if not ents:
                await query.edit_message_text(STRINGS['العربية']['no_ch'], reply_markup=await get_main_menu())
            else:
                txt = "🌐 <b>روابط الويب هوك المحدثة:</b>\n"
                kb = []
                for e in ents:
                    eid = e['entity_id']
                    webhook = f"{DOMAIN}/webhook/{user['secret_token']}/{eid}"
                    txt += f"\n📍 القناة: <code>{eid}</code>\n🔗 الرابط: <code>{webhook}</code>\n"
                    kb.append([InlineKeyboardButton(f"🗑️ حذف {eid}", callback_data=f"del_{eid}")])
                kb.append([InlineKeyboardButton(B['back'], callback_data='home')])
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        finally: release_db_conn(conn)

    elif query.data == 'gen_token':
        new_token = secrets.token_hex(8)
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
            await query.answer("🔄 تم توليد رمز جديد وتحديث الروابط")
            # تحديث العرض فوراً لعكس الروابط الجديدة
            query.data = 'url'
            await button_callback(update, context)
        finally: release_db_conn(conn)

    elif query.data.startswith('del_'):
        target = query.data.split('_')[1]
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), target))
                conn.commit()
            await query.answer("✅ تم الحذف")
            query.data = 'url'
            await button_callback(update, context)
        finally: release_db_conn(conn)

# --- دالة handle_message ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    uid = update.effective_user.id
    
    if context.user_data.get('state') == 'wait_ch' and update.message.chat_shared:
        target_id = str(update.message.chat_shared.chat_id)
        if not target_id.startswith('-100'): target_id = f"-100{target_id}"
        
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), target_id))
                conn.commit()
            await update.message.reply_text(f"✅ تم ربط القناة: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
            await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
            context.user_data['state'] = None
        except:
            await update.message.reply_text("❌ القناة مضافة مسبقاً.")
        finally: release_db_conn(conn)

# --- Flask & Web App ---
@app.route('/activation_page')
def activation_page():
    return '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: sans-serif; padding: 20px; text-align: center; background: #f4f7f9; }
            .card { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
            input { width: 100%; padding: 12px; margin: 15px 0; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; text-align:center; }
            button { background: #0088cc; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="card">
            <h3>🔓 تفعيل الاشتراك</h3>
            <input type="text" id="vcode" placeholder="أدخل كود التفعيل">
            <button onclick="send()">إرسال الطلب</button>
        </div>
        <script>
            const tg = window.Telegram.WebApp;
            function send() {
                const code = document.getElementById('vcode').value;
                if(!code) return alert("أدخل الكود أولاً");
                fetch('/submit_code', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: tg.initDataUnsafe.user.id, code: code })
                }).then(() => {
                    tg.close();
                });
            }
        </script>
    </body>
    </html>
    '''

@app.route('/submit_code', methods=['POST'])
def submit_code():
    data = request.get_json(force=True)
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🎟️ <b>طلب تفعيل</b>\n👤 المستخدم: <code>{data.get('user_id')}</code>\n🔑 الكود: <code>{data.get('code')}</code>",
            parse_mode=ParseMode.HTML
        ), main_loop
    )
    return jsonify({"status": "ok"}), 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    conn = get_db_conn()
    try:
        data = request.get_json(force=True)
        with conn.cursor() as cur:
            # التحقق من الـ Token والارتباط بالقناة
            cur.execute("SELECT 1 FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token = %s AND e.entity_id = %s", (token, str(target_id)))
            if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403
        
        msg = (f"🔔 <b>تنبيه تداول!</b>\n\n📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML), main_loop)
        return jsonify({"status": "success"}), 200
    except: return jsonify({"status": "error"}), 500
    finally: release_db_conn(conn)

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
