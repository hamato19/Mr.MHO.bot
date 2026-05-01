import os
import logging
import secrets
import asyncio
import threading
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, render_template_string
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, 
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButtonRequestChat
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

# --- الإعدادات الأساسية ---
DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# --- النصوص والأزرار ---
STRINGS = {
    'العربية': {
        'intro': "🤖 <b>مرحباً بك في @MOH_SignalsBot!</b>\nنظام ربط TradingView بتلجرام المتطور والآمن.",
        'welcome': "🏠 <b>القائمة الرئيسية:</b>\nاختر من الأزرار أدناه لإدارة حسابك وقنواتك.",
        'btns': {
            'acc': "👤 حسابي", 
            'buy': "🛒 تفعيل الاشتراك", 
            'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 
            'token': "🔄 توليد رمز جديد", 
            'wh': "🌐 الويب هوك", 
            'tv': "📊 TradingView", 
            'back': "🏠 العودة للقائمة", 
            'how': "▶️ طريقة الاستخدام", 
            'support': "☎️ الدعم الفني",
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
    if not update.effective_user: return
    uid = update.effective_user.id
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id = %s", (str(uid),))
            if not cur.fetchone():
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s)", 
                           (str(uid), secrets.token_hex(8), 'العربية'))
                conn.commit()
    await update.message.reply_text(STRINGS['العربية']['intro'], parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    B = STRINGS['العربية']['btns']
    data = query.data

    try:
        if data == 'home':
            await query.answer()
            await query.edit_message_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
        
        elif data == 'buy_menu':
            await query.answer()
            kb_reply = [
                [KeyboardButton("🎟️ إرسال كود التفعيل", web_app=WebAppInfo(url=f"{DOMAIN}/activation_page"))],
                [KeyboardButton("🏠 العودة للقائمة الرئيسية")]
            ]
            await query.delete_message()
            await context.bot.send_message(
                chat_id=uid,
                text="🛒 <b>تفعيل الاشتراك</b>\n\n🔗 أدخل كود التفعيل الذي حصلت عليه عبر الموقع بالضغط أدناه:",
                reply_markup=ReplyKeyboardMarkup(kb_reply, resize_keyboard=True, one_time_keyboard=True),
                parse_mode=ParseMode.HTML
            )

        elif data == 'acc':
            await query.answer()
            with get_db() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                    user = cur.fetchone()
                    cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                    count = cur.fetchone()['count']
            txt = f"👤 <b>بيانات حسابك:</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المربوطة: <code>{count}</code>\n- الرمز السري الحالي: <code>{user['secret_token']}</code>"
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

        elif data == 'gen_token':
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM entities WHERE user_id = %s", (str(uid),))
                    if not cur.fetchone():
                        await query.answer("⚠️ لا يمكن توليد رمز! يرجى ربط قناة أولاً.", show_alert=True)
                        return
                    new_token = secrets.token_hex(8)
                    cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                    conn.commit()
            await query.answer("✅ تم تحديث الرمز!")
            txt = f"🔄 <b>تم توليد رمز جديد!</b>\n\n🔑 رمزك الجديد: <code>{new_token}</code>\n\n⚠️ قم بتحديث الروابط في TradingView فوراً."
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

        elif data == 'add_channel':
            await query.answer()
            context.user_data['state'] = 'wait_ch'
            kb = [[KeyboardButton("📂 اختر قناة من القائمة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
            await context.bot.send_message(chat_id=uid, text="📢 اضغط أدناه لاختيار القناة المراد ربطها:", 
                                        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

        elif data == 'view_channels':
            await query.answer()
            with get_db() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                    ents = cur.fetchall()
            if not ents:
                await query.edit_message_text("❌ لا توجد قنوات مرتبطة حالياً.", reply_markup=await get_main_menu())
            else:
                kb = [[InlineKeyboardButton(f"🗑️ حذف القناة {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
                kb.append([InlineKeyboardButton(B['back'], callback_data='home')])
                await query.edit_message_text("📺 <b>قنواتك المرتبطة:</b>\nاضغط على الزر لحذف الربط.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith('del_'):
            target_del = data.replace('del_', '')
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), target_del))
                    conn.commit()
            await query.answer(f"✅ تم حذف {target_del}")
            # إعادة عرض القائمة المحدثة فوراً
            with get_db() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                    ents = cur.fetchall()
            if not ents:
                await query.edit_message_text("❌ لا توجد قنوات الآن.", reply_markup=await get_main_menu())
            else:
                kb = [[InlineKeyboardButton(f"🗑️ حذف القناة {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
                kb.append([InlineKeyboardButton(B['back'], callback_data='home')])
                await query.edit_message_text("📺 قنواتك المتبقية:", reply_markup=InlineKeyboardMarkup(kb))

        elif data == 'view_webhooks':
            await query.answer()
            with get_db() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                    res = cur.fetchone()
                    token = res['secret_token'] if res else "None"
                    cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                    ents = cur.fetchall()
            if not ents:
                await query.edit_message_text("❌ اربط قناة أولاً للحصول على الروابط.", reply_markup=await get_main_menu())
            else:
                txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n"
                for e in ents:
                    txt += f"\n📍 القناة: <code>{e['entity_id']}</code>\n🔗 <code>{DOMAIN}/webhook/{token}/{e['entity_id']}</code>\n"
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))
                
    except BadRequest as e:
        if "Message is not modified" in str(e): await query.answer()
        else: raise e

# --- مسارات الويب (Flask) ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    try:
        # 1. سحب البيانات الخام كـ Text بدلاً من JSON لتجنب مشاكل التنسيق
        raw_data = request.get_data(as_text=True)
        
        # 2. التحقق من الصلاحية (نحتاج الـ JSON هنا فقط للتحقق من قاعدة البيانات)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM users u 
                    JOIN entities e ON u.user_id = e.user_id 
                    WHERE u.secret_token = %s AND e.entity_id = %s
                """, (token, str(target_id)))
                if not cur.fetchone():
                    return jsonify({"status": "unauthorized"}), 403

        # 3. إرسال التنبيه كما هو تماماً
        # سيتم إرساله داخل وسم <code> ليكون سهل النسخ وبنفس شكل التنسيق الأصلي
        msg = f"📩 <b>تنبيه مباشر من TradingView:</b>\n\n<code>{raw_data}</code>"

        if main_loop and application:
            asyncio.run_coroutine_threadsafe(
                application.bot.send_message(
                    chat_id=target_id, 
                    text=msg, 
                    parse_mode=ParseMode.HTML
                ), 
                main_loop
            )
            return jsonify({"status": "success"}), 200
        
        return jsonify({"status": "error"}), 500

    except Exception as e:
        logging.error(f"Webhook Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/activation_page')
def activation_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: sans-serif; background: #1c1c1c; color: white; text-align: center; padding: 20px; }
        input { width: 90%; padding: 15px; margin: 20px 0; border-radius: 10px; border: 1px solid #444; background: #2b2b2b; color: white; font-size: 16px; }
        button { background: #248bfe; color: white; border: none; padding: 15px; border-radius: 10px; width: 95%; font-weight: bold; cursor: pointer; }
    </style></head>
    <body><h3>🎟️ تفعيل الاشتراك</h3><input type="text" id="code" placeholder="أدخل الكود هنا..."><button id="sendBtn">تفعيل الآن</button>
    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        document.getElementById('sendBtn').onclick = function() {
            let val = document.getElementById('code').value;
            if(val.trim() !== "") { tg.sendData(val); tg.close(); }
        };
    </script></body></html>
    """)

@app.route('/')
def index(): return "Bot is Running", 200

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    if main_loop and application:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
    return 'OK', 200

# --- معالجة الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id

    if update.message and update.message.text == "🏠 العودة للقائمة الرئيسية":
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
        return

    if update.message and update.message.web_app_data:
        code = update.message.web_app_data.data
        if ADMIN_ID != 0:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 <b>طلب تفعيل!</b>\n👤 مستخدم: <code>{uid}</code>\n🎟️ كود: <code>{code}</code>", parse_mode=ParseMode.HTML)
        await update.message.reply_text("✅ تم إرسال كود التفعيل بنجاح، سيتم الرد عليك قريباً.", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
        return

    if context.user_data.get('state') == 'wait_ch' and update.message.chat_shared:
        target_id = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), target_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ تم ربط القناة: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
                    await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
                except: 
                    await update.message.reply_text("❌ القناة مرتبطة مسبقاً بهذا الحساب.", reply_markup=ReplyKeyboardRemove())
                    await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
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
    
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
