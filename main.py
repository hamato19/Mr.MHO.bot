import os
import logging
import secrets
import asyncio
import threading
import re
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
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>\nيمكنك الاشتراك عبر الرابط أو إرسال الكود للدعم.",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: <code>{ch_count}</code>\n- أيام الاشتراك: <code>0</code>\n- إشارات متبقية مجانية: <code>100</code>",
        'add_ch_msg': "📢 <b>إضافة قناة جديدة:</b>\n\nاضغط على الزر بالأسفل لاختيار قناة من حسابك ومشاركتها مع البوت ليتم ربطها تلقائياً.",

        'no_ch': "❌ لا يوجد قنوات مرتبطة حالياً.",
        'no_ch_gen': "⚠️ يجب إضافة قناة واحدة على الأقل قبل توليد رمز أمان جديد لضمان عمل روابط الويب هوك.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'token': "🔄 توليد رمز أمان جديد", 'wh': "🌐 روابط الويب هوك", 
            'how': "▶️ طريقة الاستخدام", 'lang': "🌍 English", 'support': "☎️ الدعم", 
            'tv': "📊 الشارت (TradingView)", 'back': "🏠 القائمة الرئيسية", 
            'send_code': "🎟️ إرسال كود التفعيل", 'sub_link': "🔗 رابط الاشتراك",
            'share_btn': "📂 اختر قناة من حسابك"
        }
    },
    'English': {
        'intro': "🤖 <b>Welcome to Profit Hook!</b>",
        'welcome': "🏠 <b>Main Menu:</b>",
        'buy_menu': "🛒 <b>Activation:</b>",
        'acc_info': "👤 <b>Account Info:</b>\n\n- User ID: <code>{uid}</code>\n- Active Channels: <code>{ch_count}</code>\n- Subscription Days: <code>0</code>\n- Free Signals: <code>100</code>",
        'add_ch_msg': "📢 <b>Choose how to add channel:</b>\n\n1️⃣ Click the button below to pick a channel.\n2️⃣ Or send channel link/username.\n3️⃣ Or forward a message from the channel.",
        'no_ch': "❌ No linked channels.",
        'no_ch_gen': "⚠️ You must add at least one channel before generating a new token.",
        'btns': {
            'acc': "👤 My Account", 'buy': "🛒 Activation", 'my_ch': "📺 My Channels",
            'add_ch': "📢 Add Channel", 'token': "🔄 New Token", 'wh': "🌐 Webhook Links", 
            'how': "▶️ Tutorial", 'lang': "🌍 العربية", 'support': "☎️ Support", 
            'tv': "📊 Chart (TradingView)", 'back': "🏠 Main Menu",
            'send_code': "🎟️ Send Code", 'sub_link': "🔗 Subscription",
            'share_btn': "📂 Select Channel from list"
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
    await update.message.reply_text(STRINGS[lang]['intro'], parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
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
        keyboard = [[KeyboardButton(B['share_btn'], request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await context.bot.send_message(chat_id=uid, text=STRINGS[lang]['add_ch_msg'], reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await query.edit_message_text("🔙 اضغط /start للعودة إذا أردت.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

    elif query.data in ['my_channels', 'url']:
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
            if not ents:
                await query.edit_message_text(STRINGS[lang]['no_ch'], reply_markup=await get_main_menu(lang))
            else:
                txt = "📺 <b>قنواتك وروابط الويب هوك:</b>\n"
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
        await query.answer("✅ تم الحذف")
        # العودة لقائمة القنوات لتحديث العرض
        query.data = 'my_channels'
        await button_callback(update, context)

    elif query.data == 'gen_token':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # التأكد أولاً من وجود قنوات مرتبطة (طلبك الأساسي)
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
                if not ents:
                    await query.edit_message_text(STRINGS[lang]['no_ch_gen'], reply_markup=await get_main_menu(lang))
                    return

                # إذا وجدت قنوات، ولد رمز جديد وحدث قاعدة البيانات
                new_token = secrets.token_hex(8)
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
                
                txt = "🔄 <b>تم توليد رمز أمان جديد بنجاح!</b>\n"
                txt += f"🔑 الرمز الحالي: <code>{new_token}</code>\n\n<b>الروابط المحدثة:</b>\n"
                for e in ents:
                    new_wh = f"{DOMAIN}/webhook/{new_token}/{e['entity_id']}"
                    txt += f"📍 <code>{e['entity_id']}</code>\n🔗 <code>{new_wh}</code>\n\n"
                
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))
        finally: release_db_conn(conn)

    elif query.data == 'change_lang':
        new_lang = 'English' if lang == 'العربية' else 'العربية'
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_lang, str(uid)))
            conn.commit()
        release_db_conn(conn)
        # إعادة تحميل القائمة باللغة الجديدة
        user['language'] = new_lang
        await query.edit_message_text(STRINGS[new_lang]['welcome'], reply_markup=await get_main_menu(new_lang), parse_mode=ParseMode.HTML)

# --- دالة handle_message (تصحيح الـ ID والـ Resolve Peer) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')
    user = await get_user_data(uid)
    lang = user['language']

    if state == 'wait_ch':
        target_id = None
        if update.message.chat_shared:
            target_id = str(update.message.chat_shared.chat_id)
        elif update.message.forward_from_chat:
            target_id = str(update.message.forward_from_chat.id)
        elif update.message.text:
            text = update.message.text.strip()
            if "t.me/c/" in text:
                match = re.search(r't\.me/c/(\d+)', text)
                if match: target_id = f"-100{match.group(1)}"
            elif "t.me/" in text or text.startswith('@'):
                username = text.split('/')[-1].replace('@', '')
                try:
                    chat = await context.bot.get_chat(username)
                    target_id = str(chat.id)
                except:
                    await update.message.reply_text("❌ لم يتم العثور على القناة. تأكد أن البوت Admin فيها.")
                    return
            elif text.lstrip('-').isdigit():
                target_id = text

        if target_id:
            if not target_id.startswith('-100') and not target_id.startswith('-'):
                target_id = f"-100{target_id}"
            
            conn = get_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), target_id))
                    conn.commit()
                context.user_data['state'] = None
                await update.message.reply_text(f"✅ تم الربط!\nID: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
                await update.message.reply_text(STRINGS[lang]['welcome'], reply_markup=await get_main_menu(lang))
            except:
                await update.message.reply_text("❌ القناة مضافة مسبقاً.")
            finally: release_db_conn(conn)

    elif state == 'wait_code':
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎟️ كود من {uid}: {update.message.text}")
        context.user_data['state'] = None
        await update.message.reply_text("✅ تم الإرسال.", reply_markup=await get_main_menu(lang))

# --- Webhook logic (TradingView) ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    conn = get_db_conn()
    try:
        data = request.get_json(force=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token = %s AND e.entity_id = %s", (token, str(target_id)))
            if not cur.fetchone(): return jsonify({"status": "unauthorized"}), 403
        
        msg = (f"🔔 <b>تنبيه تداول!</b>\n\n📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
               f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n💰 السعر: <code>{data.get('price', 'N/A')}</code>")
        asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id=target_id, text=msg, parse_mode=ParseMode.HTML), main_loop)
        return jsonify({"status": "success"}), 200
    except: return jsonify({"status": "error"}), 500
    finally: release_db_conn(conn)

@# --- مسارات الـ Web App (iFrame) لإرسال الكود بخصوصية ---

@app.route('/activation_page')
def activation_page():
    # هذه الصفحة تفتح كـ iFrame داخل تلجرام
    return '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                   padding: 20px; background-color: #f4f7f9; text-align: center; color: #222; }
            .container { background: white; padding: 25px; border-radius: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
            h3 { color: #0088cc; margin-bottom: 10px; }
            p { font-size: 14px; color: #555; line-height: 1.5; }
            input { width: 100%; padding: 14px; margin: 20px 0; border: 2px solid #e0e0e0; border-radius: 12px; 
                   font-size: 16px; box-sizing: border-box; outline: none; transition: 0.3s; text-align: center; }
            input:focus { border-color: #0088cc; box-shadow: 0 0 8px rgba(0,136,204,0.2); }
            button { background: #0088cc; color: white; border: none; padding: 15px; border-radius: 12px; 
                    cursor: pointer; font-size: 16px; width: 100%; font-weight: bold; transition: 0.3s; }
            button:active { transform: scale(0.98); background: #0077b5; }
            .footer { font-size: 11px; color: #aaa; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h3>🔒 تفعيل الاشتراك</h3>
            <p>يرجى إدخال كود التفعيل بالأسفل. سيتم إرساله مباشرة للإدارة بشكل آمن.</p>
            <input type="text" id="v_code" placeholder="أدخل الكود هنا" autocomplete="off">
            <button onclick="sendCode()">إرسال الطلب</button>
            <div class="footer">🔒 هذه النافذة مشفرة - لن يظهر الكود في سجل الدردشة.</div>
        </div>

        <script>
            const tg = window.Telegram.WebApp;
            tg.expand();
            tg.ready();

            function sendCode() {
                const codeVal = document.getElementById('v_code').value;
                if (!codeVal || codeVal.length < 3) {
                    tg.showAlert("يرجى إدخال كود صحيح");
                    return;
                }

                fetch('/submit_code', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: tg.initDataUnsafe.user.id,
                        code: codeVal
                    })
                }).then(res => {
                    if(res.ok) {
                        tg.close();
                    } else {
                        tg.showAlert("حدث خطأ في الإرسال، حاول لاحقاً");
                    }
                }).catch(err => tg.showAlert("فشل الاتصال بالسيرفر"));
            }
        </script>
    </body>
    </html>
    '''

@app.route('/submit_code', methods=['POST'])
def submit_code():
    try:
        data = request.get_json(force=True)
        uid = data.get('user_id')
        code = data.get('code')
        
        # إرسال الكود للأدمن (أنت)
        asyncio.run_coroutine_threadsafe(
            application.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🎟️ <b>طلب تفعيل جديد (عبر iFrame)</b>\n\n👤 المستخدم: <code>{uid}</code>\n🔑 الكود: <code>{code}</code>",
                parse_mode=ParseMode.HTML
            ), main_loop
        )
        
        # إرسال تأكيد للمستخدم في البوت
        asyncio.run_coroutine_threadsafe(
            application.bot.send_message(
                chat_id=uid,
                text="✅ <b>تم استلام طلبك!</b>\nجاري مراجعة الكود من قبل الإدارة لتفعيل اشتراكك.",
                parse_mode=ParseMode.HTML
            ), main_loop
        )
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logging.error(f"Error in submit_code: {e}")
        return jsonify({"status": "error"}), 500

# --- مسارات البوت الأساسية ---

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def trading_webhook(token, target_id):
    conn = get_db_conn()
    try:
        data = request.get_json(force=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
    
    # الـ Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    # تم تحديث الفلتر ليشمل مشاركة القنوات والنصوص المحولة
    application.add_handler(MessageHandler((filters.TEXT | filters.FORWARDED | filters.StatusUpdate.CHAT_SHARED) & ~filters.COMMAND, handle_message))
    
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"{DOMAIN}/telegram")
    
    # تشغيل Flask في Thread منفصل
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
))
