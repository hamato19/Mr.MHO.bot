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
        'intro': "🤖 <b>مرحباً بك في Profit Hook!</b>\nنظام ربط TradingView بتلجرام عبر الويب هوك.",
        'welcome': "🏠 <b>القائمة الرئيسية:</b>",
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>\nيمكنك الاشتراك عبر الرابط أو إرسال كود التفعيل للآدمن.",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن الحالي: <code>{token}</code>",
        'add_ch_msg': "📢 <b>أرسل الآن معرف القناة أو المجموعة:</b>\nتأكد من إضافة البوت كمشرف أولاً.\nمثال: <code>-100123456789</code>",
        'lang_select': "🌍 <b>اختر اللغة / Select Language:</b>",
        'no_ch': "❌ لا يوجد لديك قنوات مرتبطة حالياً.",
        'no_ch_gen': "⚠️ يجب إضافة قناة أولاً قبل توليد رمز أمان جديد.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'token': "🔄 توليد رمز أمان", 'wh': "🌐 رابط الويب هوك", 
            'how': "▶️ طريقة الاستخدام", 'lang': "🌍 اللغة / Language", 'support': "☎️ الدعم", 
            'tv': "📊 TradingView", 'back': "🏠 القائمة الرئيسية", 'send_code': "🎟️ إرسال كود التفعيل",
            'sub_link': "🔗 رابط الاشتراك"
        }
    },
    'English': {
        'intro': "🤖 <b>Welcome to Profit Hook!</b>",
        'welcome': "🏠 <b>Main Menu:</b>",
        'buy_menu': "🛒 <b>Activation:</b>",
        'acc_info': "👤 <b>Your Account:</b>\n🆔 ID: <code>{uid}</code>\n🔑 Token: <code>{token}</code>",
        'add_ch_msg': "📢 <b>Send Channel/Group ID:</b>",
        'lang_select': "🌍 <b>Select Language:</b>",
        'no_ch': "❌ No linked channels.",
        'no_ch_gen': "⚠️ Add a channel first before generating a new token.",
        'btns': {
            'acc': "👤 My Account", 'buy': "🛒 Activation", 'my_ch': "📺 My Channels",
            'add_ch': "📢 Add Channel", 'token': "🔄 Refresh Token", 'wh': "🌐 Webhook Link", 
            'how': "▶️ How to use", 'lang': "🌍 Language", 'support': "☎️ Support", 
            'tv': "📊 TradingView", 'back': "🏠 Main Menu", 'send_code': "🎟️ Send Code",
            'sub_link': "🔗 Subscription Link"
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
    await query.answer()

    user = await get_user_data(uid)
    lang = user['language']
    T = STRINGS[lang]
    B = T['btns']

    if query.data == 'home':
        await query.edit_message_text(T['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)
    
    elif query.data == 'acc':
        txt = T['acc_info'].format(uid=uid, token=user['secret_token'])
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

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
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM entities WHERE user_id = %s", (str(uid),))
                if not cur.fetchone():
                    await query.edit_message_text(T['no_ch_gen'], reply_markup=await get_main_menu(lang))
                else:
                    new_token = secrets.token_hex(8)
                    cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                    conn.commit()
                    await query.edit_message_text(f"✅ تم تحديث الرمز بنجاح!\nالرمز الجديد: <code>{new_token}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))
        finally: release_db_conn(conn)

    elif query.data == 'change_lang':
        kb = [[InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_العربية')],
              [InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_English')],
              [InlineKeyboardButton(B['back'], callback_data='home')]]
        await query.edit_message_text(T['lang_select'], reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('set_lang_'):
        new_l = query.data.split('_')[2]
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_l, str(uid)))
            conn.commit()
        release_db_conn(conn)
        await query.edit_message_text(STRINGS[new_l]['welcome'], reply_markup=await get_main_menu(new_l), parse_mode=ParseMode.HTML)

    elif query.data == 'add_channel':
        context.user_data['state'] = 'wait_ch'
        await query.edit_message_text(T['add_ch_msg'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')
    user = await get_user_data(uid)
    lang = user['language']

    if state == 'wait_ch':
        raw_text = update.message.text.strip()
        
        # --- نظام التحقق الصارم ---
        #isdigit() تتأكد أن النص يحتوي على أرقام فقط (0-9) 
        # هذا سيرفض أي نص يحتوي على شرطة (-) أو حروف مثل (id)
        if not raw_text.isdigit():
            msg = "❌ <b>خطأ في التنسيق:</b> يرجى إرسال أرقام فقط بدون شرطة وبدون حروف.\nمثال: <code>123456789</code>" if lang == 'العربية' else "❌ <b>Format Error:</b> Send numbers only without dashes or letters."
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return # توقف هنا ولا تكمل الحفظ

        try:
            # هنا نقوم بتخزين الرقم الصافي
            clean_id = raw_text 
            conn = get_db_conn()
            try:
                with conn.cursor() as cur:
                    # نقوم بتخزين الرقم كما هو (بدون إضافة أي رموز برمجياً)
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), clean_id))
                    conn.commit()
                
                context.user_data['state'] = None
                success_msg = "✅ تم ربط القناة بنجاح!" if lang == 'العربية' else "✅ Channel linked successfully!"
                await update.message.reply_text(success_msg, reply_markup=await get_main_menu(lang))
            except:
                err_msg = "❌ هذا المعرف مسجل مسبقاً." if lang == 'العربية' else "❌ This ID is already registered."
                await update.message.reply_text(err_msg)
            finally: 
                release_db_conn(conn)
        except Exception as e:
            logging.error(f"DB Error: {e}")
            await update.message.reply_text("❌ حدث خطأ في قاعدة البيانات.")

    elif state == 'wait_code':
        code = update.message.text
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎟️ <b>طلب تفعيل جديد:</b>\nالمستخدم: {update.effective_user.first_name}\nID: <code>{uid}</code>\nالكود: <code>{code}</code>", parse_mode=ParseMode.HTML)
        context.user_data['state'] = None
        await update.message.reply_text("✅ تم إرسال طلبك للدعم الفني بنجاح، سيتم التفعيل قريباً.", reply_markup=await get_main_menu(lang))

# --- مسارات الويب هوك (Flask) ---
@app.route('/telegram', methods=['POST'])
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    global main_loop, application
    update_data = request.get_json(force=True)
    if main_loop and application:
        update = Update.de_json(update_data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
        return 'OK', 200
    return 'Error', 500

# 2. هذا هو المسار الجديد الذي كان ينقصك لاستقبال إشارات TradingView
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    conn = get_db_conn()
    try:
                data = request.get_json(force=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # التحقق من التوكن والمعرف في قاعدة البيانات
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token = %s AND e.entity_id = %s
            """, (token, str(target_id)))
            
            if not cur.fetchone():
                return jsonify({"status": "unauthorized"}), 403

        # 1. تصحيح معرف القناة (إضافة -100 إذا كان رقمياً صافياً)
        # هذا يضمن أن الإرسال سيعمل حتى لو خزن المستخدم أرقاماً فقط
        real_chat_id = f"-100{target_id}" if not str(target_id).startswith('-') else target_id

        # 2. تجهيز رسالة التداول المنسقة
        msg = (f"🔔 <b>تنبيه تداول جديد!</b>\n\n"
               f"📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n"
               f"💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        
        # 3. إرسال الرسالة إلى تلجرام (Thread Safe)
        asyncio.run_coroutine_threadsafe(
            application.bot.send_message(chat_id=real_chat_id, text=msg, parse_mode=ParseMode.HTML),
            main_loop
        )
        
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        release_db_conn(conn)

# --- نهاية ملف الكود الأساسية ---

async def main():
    global main_loop, application
    main_loop = asyncio.get_running_loop()
    
    # بناء تطبيق التلجرام
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات (Handlers)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل الويب هوك الخاص بتلجرام
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"{DOMAIN}/telegram")
    
    # تشغيل Flask في خيط منفصل (Thread)
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    # إبقاء البوت حياً
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
