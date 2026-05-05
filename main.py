import os, secrets, asyncio, threading, logging, datetime, requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from psycopg2.extras import RealDictCursor

# استيراد الدوال من الملفات المساعدة (تأكد من سلامة ملف auth.py و database.py)
from database import get_db
from auth import activate_with_code

# الإعدادات الأساسية
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
application = None

# --- دوال مساعدة لحساب الوقت ---
def get_time_remaining(expiry_date):
    """تحسب الوقت المتبقي وتنسقه بشكل مقروء."""
    if not expiry_date:
        return "غير محدد"
    
    now = datetime.datetime.now()
    if now > expiry_date:
        return "منتهٍ 🛑"
    
    diff = expiry_date - now
    days = diff.days
    hours = diff.seconds // 3600
    
    if days > 0:
        return f"{days} يوم و {hours} ساعة"
    return f"{hours} ساعة"

# --- القوائم والأزرار ---
async def get_main_menu(uid):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 توليد رمز جديد", callback_data='gen_token')],
        [InlineKeyboardButton("📺 قنواتي", callback_data='view_chs')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{application.bot.username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=f"tg://user?id={ADMIN_ID}")]
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم", callback_data='admin_panel')])
    return InlineKeyboardMarkup(kb)

# --- Handlers الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    
    # 1. جلب بيانات المستخدم أو تسجيله (افتراضياً غير مفعل وبدون تاريخ)
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            
            if not user:
                cur.execute(
                    "INSERT INTO users (user_id, secret_token, is_activated, expiry_date) VALUES (%s, %s, %s, %s)",
                    (str(uid), secrets.token_hex(8), False, None)
                )
                conn.commit()
                # جلب البيانات بعد الإنشاء
                cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()

    # 2. منطق التأمين والتحقق من العداد (اغلاق البوت)
    is_admin = (uid == ADMIN_ID)
    is_expired = False
    
    # فحص تاريخ الانتهاء (Counter check)
    if user['expiry_date']:
        is_expired = datetime.datetime.now() > user['expiry_date']

    # إذا كان المستخدم ليس الأدمن (وإما غير مفعل أو عداده وصل للصفر)
    if not is_admin and (not user['is_activated'] or is_expired):
        context.user_data['state'] = 'WAIT_CODE'
        kb = [[InlineKeyboardButton("💳 اشترك الآن (تواصل مع المطور)", url=f"tg://user?id={ADMIN_ID}")]]
        
        # رسالة قفل البوت
        msg = "👋 أهلاً بك في نظام Mr.MOH\n\n🔒 النظام مغلق حالياً. يرجى إدخال كود التفعيل المكون من 10 أرقام للاستمرار:"
        if is_expired:
            msg = "👋 مرحباً بك مجدداً..\n\n❌ <b>انتهت فترة اشتراكك/التجربة (وصل العداد لـ 0).</b>\nيرجى إرسال كود تفعيل جديد للتجديد:"
            
        return await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML
        )

    # 3. عرض القائمة الرئيسية إذا كان الاشتراك سارياً (العداد > 0)
    await update.message.reply_text(
        "🏠 <b>القائمة الرئيسية للنظام:</b>", 
        reply_markup=await get_main_menu(uid), 
        parse_mode=ParseMode.HTML
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    data = query.data
    await query.answer()

    if data == 'home':
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)

    elif data == 'acc':
        # تفعيل العداد التنازلي في "حسابي"
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token, expiry_date, is_activated FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                ch_count = cur.fetchone()['count']
        
        # حساب الوقت المتبقي بدقة (العداد التنازلي)
        time_left = get_time_remaining(user['expiry_date'])
        status = "فعال ✅" if user['is_activated'] and time_left != "غير محدد" and "منتهٍ" not in time_left else "متوقف ❌"
        
        txt = (
            f"👤 <b>بيانات حسابك (نظام محمد للتحليل):</b>\n\n"
            f"- معرف المستخدم: <code>{uid}</code>\n"
            f"- حالة الحساب: <b>{status}</b>\n"
            f"- متبقي على الانتهاء: <b>{time_left}</b>\n"
            f"- القنوات المرتبطة: <code>{ch_count}</code>\n"
            f"- الرمز السري: <code>{user['secret_token']}</code>"
        )
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'add_ch':
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📂 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="📢 اختر القناة ليقوم البوت بسحب الـ ID وحفظه فوراً:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    elif data == 'view_chs':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text("❌ لا توجد قنوات مرتبطة.", reply_markup=await get_main_menu(uid))
        else:
            kb = [[InlineKeyboardButton(f"🗑️ حذف {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
            kb.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
            await query.edit_message_text("📺 <b>قنواتك المسجلة:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith('del_'):
        ch_id = data.replace('del_', '')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), ch_id))
                conn.commit()
        await query.edit_message_text(f"✅ تم حذف القناة بنجاح.", reply_markup=await get_main_menu(uid))

    elif data == 'view_wh':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                token = cur.fetchone()['secret_token']
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text("⚠️ أضف قناة أولاً لتوليد الروابط.", reply_markup=await get_main_menu(uid))
        else:
            txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n"
            for e in ents:
                txt += f"\n📍 القناة: <code>{e['entity_id']}</code>\n🔗 <code>{DOMAIN}/webhook/{token}/{e['entity_id']}</code>\n"
            await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
        await query.edit_message_text(f"✅ تم تحديث التوكن السري:\n<code>{new_token}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(uid))

    # --- لوحة التحكم (تم تحسينها وإضافة خيارات 60 و 90 يوم) ---
    elif data == 'admin_panel' and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("🎫 توليد كود اشتراك", callback_data='admin_durations')],
            [InlineKeyboardButton("👥 المستخدمين (الأحدث)", callback_data='admin_users')],
            [InlineKeyboardButton("🏠 عودة", callback_data='home')]
        ]
        await query.edit_message_text("👮 <b>لوحة تحكم المالك:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'admin_durations' and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("⏱️ 10 أيام", callback_data='gen_10'), InlineKeyboardButton("⏱️ 30 يوم", callback_data='gen_30')],
            [InlineKeyboardButton("⏱️ 60 يوم", callback_data='gen_60'), InlineKeyboardButton("⏱️ 90 يوم", callback_data='gen_90')],
            [InlineKeyboardButton("⏱️ 365 يوم", callback_data='gen_365')],
            [InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]
        ]
        await query.edit_message_text("💎 اختر مدة الاشتراك للكود الجديد ليتم تسجيله في قاعدة البيانات:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'admin_users' and uid == ADMIN_ID:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # جلب آخر 15 مستخدم حسب تاريخ الانتهاء
                cur.execute("SELECT user_id, expiry_date, is_activated FROM users ORDER BY expiry_date DESC NULLS LAST LIMIT 15")
                users = cur.fetchall()
        txt = "👥 <b>قائمة آخر 15 مستخدم (قاعدة البيانات):</b>\n\n"
        for u in users:
            status = "✅" if u['is_activated'] else "❌"
            exp = u['expiry_date'].strftime('%Y-%m-%d') if u['expiry_date'] else "غير محدد"
            txt += f"{status} <code>{u['user_id']}</code> | ينتهي: <code>{exp}</code>\n"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]))

    elif data.startswith('gen_') and uid == ADMIN_ID:
        days = int(data.replace('gen_', ''))
        # إنشاء كود فريد يبدأ بـ MOH
        code = f"MOH-{secrets.token_hex(3).upper()}"
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO activation_codes (code, duration_days) VALUES (%s, %s)", (code, days))
                conn.commit()
        await query.edit_message_text(f"✅ تم إنشاء كود جديد بنجاح:\n<code>{code}</code>\n⏳ الصلاحية: {days} يوماً", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]))

# --- معالجة الرسائل وسحب الـ ID ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')

    # 1. تفعيل الكود وربطه بقاعدة البيانات (نظام محمد)
    if state == 'WAIT_CODE' and update.message.text:
        text = update.message.text.strip()
        success, days = await activate_with_code(uid, text)
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ مبروك يا محمد! تم تفعيل اشتراكك لمدة {days} يوماً بنجاح.")
            # العودة للقائمة الرئيسية لتحديث العداد
            return await start(update, context)
        return await update.message.reply_text("❌ الكود خاطئ أو منتهي الصلاحية.")

    # 2. سحب الـ ID المباشر وحفظه في جدول entities
    if state == 'wait_ch' and update.message.chat_shared:
        target_id = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                # ON CONFLICT لضمان عدم تكرار القناة لنفس المستخدم
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), target_id))
                conn.commit()
                await update.message.reply_text(f"✅ تم ربط القناة <code>{target_id}</code> بنجاح يا محمد!", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
                context.user_data['state'] = None
                return await start(update, context)

# --- نظام الويب هوك المؤمن (الإرسال الخام) ---

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    # استقبال النص الخام تماماً من TradingView
    raw_data = request.get_data(as_text=True)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # التحقق المشترك: هل التوكن والآيدي صحيحان؟ هل المستخدم مفعل؟
            cur.execute("""
                SELECT u.user_id, u.is_activated, u.expiry_date FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s
            """, (token, target_id))
            user = cur.fetchone()
            
            if not user: return jsonify({"status": "unauthorized", "details": "Token/Chat ID not found in DB"}), 403
            
            # فحص العداد في الويب هوك (تأمين إضافي عالي)
            is_expired = user[2] and datetime.datetime.now() > user[2]
            if int(user[0]) != ADMIN_ID and (not user[1] or is_expired):
                # إذا منتهي (العداد=0)، لا نرسل الإشارة
                return jsonify({"status": "subscription_expired", "details": "Counter reached 0"}), 403
    
    # الإرسال الخام لملجرام لضمانTxt نظيف
    try:
        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": target_id,
            "text": raw_data, # النص الخام القادم من TradingView
            "parse_mode": "HTML" # للحفاظ على أي تنسيق بسيط في الـ JSON
        }
        r = requests.post(tg_url, json=payload)
        if r.status_code == 200:
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "error", "tg_response": r.text}), 500
    except Exception as e:
        return jsonify({"status": "exception", "error": str(e)}), 500

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    # تهيئة البوت
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات (Handlers)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    # فلتر شامل لاستقبال كافة أحداث المشاركة والنصوص
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    # تشغيل Flask في Thread منفصل لضمان الاستقرار
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🚀 نظام محمد للتحليل مفعل بالكامل (عداد تنازلي + تأمين عالي + إرسال خام)")
    application.run_polling()
