import os, secrets, asyncio, threading, logging, datetime, requests, time
from flask import Flask, request, jsonify
# بقية الاستيرادات...
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from psycopg2.extras import RealDictCursor

# استيراد الدوال من الملفات المساعدة
from database
import get_db
from auth 
import activate_with_code
import terms  
import i18n

# الإعدادات الأساسية
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

application = None

# --- دوال مساعدة ---

def keep_alive():
    while True:
        try: requests.get(DOMAIN, timeout=10)
        except: pass
        time.sleep(20)

def get_time_remaining(expiry_date):
    if not expiry_date: return "غير مفعل 🔓"
    now = datetime.datetime.now()
    if now > expiry_date: return "منتهٍ 🛑"
    diff = expiry_date - now
    return f"{diff.days} يوم و {diff.seconds // 3600} ساعة"

async def get_main_menu(uid):
    bot_me = await application.bot.get_me()
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 تحديث الرمز", callback_data='gen_token')],
        [InlineKeyboardButton("📺 قنواتي المرتبطة", callback_data='view_chs')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_me.username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=f"tg://user?id={ADMIN_ID}")]
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (الأدمن)", callback_data='admin_panel')])
    return InlineKeyboardMarkup(kb)

# --- المعالجات المعدلة ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    keyboard = [[InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_ar'), InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_en')]]
    welcome_msg = "👋 مرحباً بك في نظام سمو الأرقام\nالرجاء اختيار اللغة:\n\nWelcome! Please choose your language:"
    await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith('set_lang_'):
        selected_lang = query.data.split('_')[2]
        # حفظ اللغة في ذاكرة المستخدم
        context.user_data['selected_lang'] = selected_lang
        await terms.send_terms(update, context, user_lang=selected_lang)

# تصحيح دالة التحقق (إضافة user_lang ودعم استدعاء المنيو)
async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang=None):
    uid = update.effective_user.id
    chat = update.effective_chat
    
    # تحديد اللغة
    lang = user_lang or context.user_data.get('selected_lang', 'ar')
    
    # 1. المالك (الأدمن) يتخطى الفحص دائماً
    if uid == ADMIN_ID:
        msg = "👑 <b>أهلاً بك يا مطور النظام:</b>" if lang == 'ar' else "👑 <b>Welcome, Developer:</b>"
        return await chat.send_message(msg, reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)

    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()
                
                # إنشاء مستخدم جديد إذا لم يوجد
                if not user:
                    new_token = secrets.token_hex(8)
                    cur.execute("INSERT INTO users (user_id, secret_token, is_activated, expiry_date, created_at) VALUES (%s, %s, %s, %s, NOW())", 
                                (str(uid), new_token, False, None))
                    conn.commit()
                    cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
                    user = cur.fetchone()

        # 2. فحص صلاحية الاشتراك
        now = datetime.datetime.now()
        is_expired = user['expiry_date'] and now > user['expiry_date']
        
        if not user['is_activated'] or is_expired:
            context.user_data['state'] = 'WAIT_CODE'
            if lang == 'ar':
                msg = "⚠️ <b>الوصول مقيد.</b>\nالرجاء إرسال كود التفعيل:"
                btn_txt = "💳 شراء كود"
            else:
                msg = "⚠️ <b>Access Restricted.</b>\nPlease send activation code:"
                btn_txt = "💳 Buy Code"
            
            kb = [[InlineKeyboardButton(btn_txt, url=f"tg://user?id={ADMIN_ID}")]]
            return await chat.send_message(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

        # 3. إذا كان مفعل تظهر القائمة
        success_msg = "🌟 <b>لوحة التحكم تعمل:</b>" if lang == 'ar' else "🌟 <b>Dashboard is Active:</b>"
        await chat.send_message(success_msg, reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)

    except Exception as e:
        logging.error(f"DB Error: {e}")
        await chat.send_message(f"❌ خطأ فني: {e}")

# --- دالة معالجة الأزرار ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query.data: return
    uid = update.effective_user.id
    data = query.data
    await query.answer()

    if data == 'home':
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)
    
    elif data == 'acc':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token, expiry_date, is_activated FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()
        txt = f"👤 <b>بيانات الحساب:</b>\n\n• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n• المتبقي: {get_time_remaining(user['expiry_date'])}\n• الرمز: <code>{user['secret_token']}</code>"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
        await query.edit_message_text(f"✅ تم تحديث الرمز: <code>{new_token}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'add_ch':
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📢 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="اختر القناة:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    elif data == 'view_chs':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents: 
            return await query.edit_message_text("❌ لا قنوات مرتبطة.", reply_markup=await get_main_menu(uid))
        kb = [[InlineKeyboardButton(f"🗑️ {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
        kb.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
        await query.edit_message_text("📺 قنواتك المرتبطة:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'view_wh':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                user_res = cur.fetchone()
                token = user_res['secret_token']
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents: 
            return await query.edit_message_text("⚠️ يرجى إضافة قناة أولاً.", reply_markup=await get_main_menu(uid))
        txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n"
        for e in ents: txt += f"• <code>{DOMAIN}/webhook/{token}/{e['entity_id']}</code>\n"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'admin_panel' and uid == ADMIN_ID:
        kb = [[InlineKeyboardButton("🎫 إدارة الأكواد", callback_data='admin_durations'), InlineKeyboardButton("👥 المستخدمين", callback_data='admin_users')], [InlineKeyboardButton("🏠", callback_data='home')]]
        await query.edit_message_text("👮 لوحة تحكم الإدارة", reply_markup=InlineKeyboardMarkup(kb))

# --- معالجة الرسائل النصية ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: 
        # معالجة مشاركة القناة (Chat Shared)
        if update.message and update.message.chat_shared:
            uid = update.effective_user.id
            tid = str(update.message.chat_shared.chat_id)
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), tid))
                    conn.commit()
            await update.message.reply_text(f"✅ تم ربط القناة بنجاح: {tid}", reply_markup=ReplyKeyboardRemove())
            context.user_data['state'] = None
            return await check_activation_logic(update, context)
        return

    uid = update.effective_user.id
    text = update.message.text.strip()
    
    # حالة انتظار كود التفعيل
    if context.user_data.get('state') == 'WAIT_CODE':
        success, days = await activate_with_code(uid, text)
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم تفعيل الاشتراك بنجاح لمدة {days} يوم!")
            return await check_activation_logic(update, context)
        else:
            await update.message.reply_text("❌ الكود غير صحيح أو مستخدم مسبقاً.")

# --- Flask Webhook System ---
@app.route('/')
def index(): return "Bot is Running", 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT u.user_id FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token=%s AND e.entity_id=%s", (token, target_id))
            user = cur.fetchone()
            if not user: return jsonify({"error": "Unauthorized"}), 403
    
    # إرسال التنبيه للقناة
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": target_id, 
        "text": f"🔔 <b>تنبيه إشارة جديدة:</b>\n\n{raw_data}", 
        "parse_mode": "HTML"
    })
    return jsonify({"status": "success"}), 200

# --- تشغيل البوت ---
if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback, pattern='^set_lang_'))
    application.add_handler(CallbackQueryHandler(terms.handle_terms_callback, pattern='^(accept_terms|decline_terms)$'))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    # تشغيل Flask في خيط منفصل
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    # تشغيل نظام البقاء حياً
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # بدء استقبال الرسائل
    application.run_polling()
