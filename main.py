import os, secrets, asyncio, threading, logging, datetime, requests, time
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from psycopg2.extras import RealDictCursor

# استيراد الملفات المساعدة
from database import get_db
from auth import activate_with_code
import admin  
import terms
import i18n
import errors

# الإعدادات الأساسية
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

application = None

# --- الدوال المساعدة ---

def keep_alive():
    """الحفاظ على استمرارية تشغيل السيرفر في Render"""
    while True:
        try: 
            requests.get(DOMAIN, timeout=10)
        except: 
            pass
        time.sleep(20)

def get_time_remaining(expiry_date):
    """حساب الوقت المتبقي للاشتراك"""
    if not expiry_date: return "غير مفعل 🔓"
    now = datetime.datetime.now()
    if now > expiry_date: return "منتهٍ 🛑"
    diff = expiry_date - now
    return f"{diff.days} يوم و {diff.seconds // 3600} ساعة"

async def get_main_menu(uid):
    """إنشاء القائمة الرئيسية مع التحقق من صلاحيات الأدمن"""
    try:
        bot_me = await application.bot.get_me()
        bot_username = bot_me.username
    except:
        bot_username = "bot"

    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 تحديث الرمز", callback_data='gen_token')],
        [InlineKeyboardButton("📺 قنواتي المرتبطة", callback_data='view_chs')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=f"tg://user?id={ADMIN_ID}")]
    ]
    
    if int(uid) == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (الأدمن)", callback_data='admin_panel')])
        
    return InlineKeyboardMarkup(kb)

# --- المعالجات الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نقطة البداية للمستخدم"""
    if not update.effective_user: return
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_ar'), 
            InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_en')
        ]
    ]
    welcome_msg = "👋 مرحباً بك في نظام سمو الأرقام\nالرجاء اختيار اللغة:\n\nWelcome! Please choose your language:"
    await update.effective_chat.send_message(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع ضغطات الأزرار (Inline Buttons)"""
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    await query.answer()

    # اختيار اللغة وشروط الخدمة
    if data.startswith('set_lang_'):
        selected_lang = data.split('_')[2]
        context.user_data['selected_lang'] = selected_lang
        await terms.send_terms(update, context, user_lang=selected_lang)

    # العودة للقائمة الرئيسية
    elif data == 'home':
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)
    
    # عرض بيانات الحساب
    elif data == 'acc':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token, expiry_date, is_activated FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()
        
        txt = (f"👤 <b>بيانات الحساب:</b>\n\n"
               f"• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n"
               f"• المتبقي: {get_time_remaining(user['expiry_date'])}\n"
               f"• الرمز: <code>{user['secret_token']}</code>")
        
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    # تحديث الرمز السري
    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
        await query.edit_message_text(f"✅ تم تحديث الرمز بنجاح: <code>{new_token}</code>", 
                                     parse_mode=ParseMode.HTML, 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    # طلب ربط قناة (إرسال زر طلب القناة)
    elif data == 'add_ch':
        kb = [[KeyboardButton("📢 اختر القناة التي تريد ربطها", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, 
                                     text="يرجى الضغط على الزر أدناه لاختيار القناة وتزويد البوت بصلاحيات الربط:", 
                                     reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    # عرض القنوات المرتبطة
    elif data == 'view_chs':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        
        if not ents: 
            return await query.edit_message_text("❌ ليس لديك قنوات مرتبطة حالياً.", reply_markup=await get_main_menu(uid))
        
        kb = [[InlineKeyboardButton(f"🗑️ حذف {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
        kb.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
        await query.edit_message_text("📺 قنواتك المرتبطة حالياً:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    # عرض روابط الويب هوك للمشترك
    elif data == 'view_wh':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                token = cur.fetchone()['secret_token']
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        
        if not ents: 
            return await query.edit_message_text("⚠️ يرجى ربط قناة واحدة على الأقل أولاً.", reply_markup=await get_main_menu(uid))
        
        txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n"
        for e in ents: 
            txt += f"• <code>{DOMAIN}/webhook/{token}/{e['entity_id']}</code>\n"
        
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    # لوحة تحكم الإدارة
    elif data == 'admin_panel' and int(uid) == ADMIN_ID:
        await admin.show_admin_panel(update, context)

    # توجيه طلبات الإدارة الأخرى لملف admin
    elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) == ADMIN_ID:
            if data == 'admin_users': await admin.list_users(update)
            elif data == 'admin_stats': await admin.show_admin_stats(update)
            elif data == 'admin_broadcast': await admin.start_broadcast(update, context)
            elif data == 'admin_generate_code': await admin.show_generate_code_menu(update)
            elif data.startswith('gen_days_'): await admin.process_generate_code(update, int(data.split('_')[2]))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع الرسائل النصية والكيانات المشتركة"""
    if not update.message: return
    uid = update.effective_user.id
    
    # معالجة استقبال "معرف القناة" بعد اختيارها من قبل المستخدم
    if update.message.chat_shared:
        tid = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), tid))
                conn.commit()
        await update.message.reply_text(f"✅ تم ربط القناة بنجاح!\nالمعرف: <code>{tid}</code>", 
                                       parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
        return await check_activation_logic(update, context)

    # معالجة الرسائل النصية (أكواد التفعيل أو الإذاعة)
    if update.message.text:
        text = update.message.text.strip()
        state = context.user_data.get('state')

        # منطق إدخال كود التفعيل
        if state == 'WAIT_CODE':
            success, days = await activate_with_code(uid, text)
            if success:
                context.user_data['state'] = None
                await update.message.reply_text(
                    f"✅ <b>تم التفعيل بنجاح!</b>\n⏳ مدة الاشتراك: {days} يوم.", 
                    parse_mode=ParseMode.HTML
                )
                return await check_activation_logic(update, context)
            else:
                await update.message.reply_text("❌ <b>عذراً، هذا الكود غير صالح أو منتهي.</b>", parse_mode=ParseMode.HTML)
        
        # معالجة رسالة الإذاعة من الأدمن
        elif state == 'WAIT_BROADCAST_MSG' and uid == ADMIN_ID:
            await admin.exec_broadcast(update, context)

async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من صحة الاشتراك وتوجيه المستخدم"""
    uid = update.effective_user.id
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT is_activated FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
    
    if not user or not user['is_activated']:
        context.user_data['state'] = 'WAIT_CODE'
        await update.effective_chat.send_message("⚠️ <b>اشتراكك غير نشط حالياً.</b>\nالرجاء إرسال كود التفعيل الخاص بك:", parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message("🌟 <b>مرحباً بك في لوحة التحكم:</b>", 
                                       reply_markup=await get_main_menu(uid), 
                                       parse_mode=ParseMode.HTML)

# --- Flask Server (Webhooks & Keep-Alive) ---
@app.route('/')
def index(): 
    return "🚀 Sumou Al-Arqam System is Online", 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    """استقبال الإشارات من TradingView وإرسالها للتليجرام"""
    raw_data = request.get_data(as_text=True)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # التحقق من صحة التوكن والربط
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE
            """, (token, target_id))
            
            if not cur.fetchone(): 
                return jsonify({"error": "Unauthorized or Inactive"}), 403
    
    # إرسال الرسالة للقناة المستهدفة
    msg_text = f"🔔 <b>تنبيه إشارة جديدة:</b>\n\n<code>{raw_data}</code>"
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": target_id, 
        "text": msg_text, 
        "parse_mode": "HTML"
    })
    return jsonify({"status": "signal_forwarded"}), 200

# --- انطلاق النظام ---
if __name__ == "__main__":
    # إعداد تطبيق التليجرام
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    # تشغيل Flask في Thread منفصل
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    
    # تشغيل خدمة البقاء نشطاً
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # بدء عمل البوت
    print("🤖 Bot is starting...")
    application.run_polling(drop_pending_updates=True)
