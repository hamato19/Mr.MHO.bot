import os
import logging
import secrets
import asyncio
import threading
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, render_template_string
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

# --- إدارة قاعدة البيانات ---
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
    data = query.data

    if data == 'home':
        await query.answer()
        await query.edit_message_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
    
    elif data == 'buy_menu':
        await query.answer()
        kb = [[InlineKeyboardButton(B['sub_link'], url="https://servernet.ct.ws")],
              [InlineKeyboardButton(B['send_code'], web_app=WebAppInfo(url=f"{DOMAIN}/activation_page"))],
              [InlineKeyboardButton(B['back'], callback_data='home')]]
        await query.edit_message_text(STRINGS['العربية']['buy_menu'], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'acc':
        await query.answer()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                count = cur.fetchone()[0]
        txt = f"👤 <b>بيانات حسابك:</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المربوطة: <code>{count}</code>"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
        await query.answer("✅ تم تحديث رمز الويب هوك بنجاح!", show_alert=True)
        await query.edit_message_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

    elif data.startswith('del_'):
        target_del = data.replace('del_', '')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), target_del))
                conn.commit()
        await query.answer(f"🗑️ تم حذف القناة بنجاح", show_alert=True)
        await query.edit_message_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

    elif data == 'add_channel':
        await query.answer()
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📂 اختر قناة من حسابك", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="📢 يرجى الضغط على الزر أدناه لاختيار القناة:", 
                                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    elif data == 'view_channels':
        await query.answer()
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text("❌ لا يوجد قنوات مرتبطة.", reply_markup=await get_main_menu())
        else:
            txt = "📺 <b>قنواتك المرتبطة:</b>\nاضغط على الحذف لإزالة الارتباط."
            kb = [[InlineKeyboardButton(f"🗑️ حذف {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
            kb.append([InlineKeyboardButton(B['back'], callback_data='home')])
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data == 'view_webhooks':
        await query.answer()
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                user_res = cur.fetchone()
                token = user_res['secret_token'] if user_res else "None"
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text("❌ اربط قناة أولاً لتوليد الروابط.", reply_markup=await get_main_menu())
        else:
            txt = "🌐 <b>روابط الويب هوك (TradingView):</b>\n"
            for e in ents:
                txt += f"\n📍 القناة: <code>{e['entity_id']}</code>\n🔗 <code>{DOMAIN}/webhook/{token}/{e['entity_id']}</code>\n"
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

# --- مسارات الويب (Flask) ---

@app.route('/activation_page')
def activation_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: sans-serif; background: #1c1c1c; color: white; text-align: center; padding: 20px; }
            input { width: 90%; padding: 15px; margin: 20px 0; border-radius: 10px; border: 1px solid #444; background: #2b2b2b; color: white; font-size: 16px; }
            button { background: #248bfe; color: white; border: none; padding: 15px; border-radius: 10px; width: 95%; font-weight: bold; }
        </style>
    </head>
    <body>
        <h3>🎟️ كود التفعيل</h3>
        <input type="text" id="code" placeholder="أدخل الكود هنا..." autofocus>
        <button id="sendBtn">إرسال للأدمن</button>
        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            document.getElementById('sendBtn').onclick = function() {
                let val = document.getElementById('code').value;
                if(val.trim() !== "") { tg.sendData(val); }
            };
        </script>
    </body>
    </html>
    """)

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    try:
        data = request.get_json(force=True)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token = %s AND e.entity_id = %s", (token, str(target_id)))
                if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403

        # معالجة الإشارة المتقدمة
        sig = str(data.get('signal', '')).lower()
        icon = "🔴" if "sel" in sig else "🟢"
        act = "بيـع (SELL)" if "sel" in sig else "شـراء (BUY)"

        msg = (
            f"{icon} <b>تنبيه تداول جديد!</b>\n\n"
            f"📊 الأداة: <code>{data.get('ticker', 'N/A')}</code>\n"
            f"⚡ العملية: <b>{act}</b>\n"
            f"🏷️ النوع: <code>{data.get('type', 'N/A')}</code>\n"
            f"💰 السعر: <code>{data.get('price', 'N/A')}</code>\n"
            f"📦 الكمية: <code>{data.get('quantity', '100%')}</code>\n"
            f"📝 ملاحظة: <b>{data.get('msg', 'N/A')}</b>"
        )

        if main_loop:
            asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML), main_loop)
            return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    update_data = request.get_json(force=True)
    if main_loop and application:
        update = Update.de_json(update_data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
    return 'OK', 200

# --- معالجة الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id

    if update.message and update.message.web_app_data:
        code = update.message.web_app_data.data
        await update.message.reply_text(f"✅ تم إرسال الكود: <code>{code}</code>", parse_mode=ParseMode.HTML)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 <b>طلب تفعيل!</b>\nالمستخدم: {uid}\nالكود: <code>{code}</code>", parse_mode=ParseMode.HTML)
        return

    if context.user_data.get('state') == 'wait_ch' and update.message.chat_shared:
        target_id = f"-100{update.message.chat_shared.chat_id}"
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), target_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ تم ربط القناة: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
                except: await update.message.reply_text("❌ هذه القناة مرتبطة بالفعل.")
        context.user_data['state'] = None

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
