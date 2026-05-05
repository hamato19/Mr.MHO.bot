import os, secrets, asyncio, threading, logging, datetime, requests, time
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from psycopg2.extras import RealDictCursor

# استيراد الدوال من الملفات المساعدة
from database import get_db
from auth import activate_with_code

# الإعدادات الأساسية
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# متطلب عالمي للوصول للبوت داخل الدوال
application = None

# --- دوال مساعدة ---

def get_time_remaining(expiry_date):
    if not expiry_date: return "غير مفعل 🔓"
    now = datetime.datetime.now()
    if now > expiry_date: return "منتهٍ 🛑"
    diff = expiry_date - now
    days = diff.days
    hours = diff.seconds // 3600
    return f"{days} يوم و {hours} ساعة"

async def get_main_menu(uid):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 تحديث الرمز", callback_data='gen_token')],
        [InlineKeyboardButton("📺 قنواتي المرتبطة", callback_data='view_chs')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{(await application.bot.get_me()).username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=f"tg://user?id={ADMIN_ID}")]
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (الأدمن)", callback_data='admin_panel')])
    return InlineKeyboardMarkup(kb)

# --- Handlers الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            if not user:
                cur.execute("INSERT INTO users (user_id, secret_token, is_activated, expiry_date, created_at) VALUES (%s, %s, %s, %s, NOW())",
                            (str(uid), secrets.token_hex(8), False, None))
                conn.commit()
                cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()

    is_admin = (uid == ADMIN_ID)
    is_expired = user['expiry_date'] and datetime.datetime.now() > user['expiry_date']

    if not is_admin and (not user['is_activated'] or is_expired):
        context.user_data['state'] = 'WAIT_CODE'
        welcome_msg = (
            "🚀 <b>مرحباً بك في نظام SUMOU-AL-ARQAM</b>\n\n"
            "⚠️ <b>الحالة:</b> الوصول مقيد.\n"
            "يرجى إرسال <b>كود التفعيل</b> المكون من 8 أرقام لبدء الخدمة:"
        )
        if is_expired:
            welcome_msg = "❌ <b>انتهى اشتراكك!</b>\nيرجى إرسال كود تفعيل جديد للتجديد:"
            
        return await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 شراء كود تفعيل", url=f"tg://user?id={ADMIN_ID}")]]) , parse_mode=ParseMode.HTML)

    await update.message.reply_text(
        f"🌟 <b>لوحة تحكم Mr.MOH</b>\n\nنظامك يعمل بكفاءة، استخدم الأزرار أدناه للإدارة:",
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
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token, expiry_date, is_activated FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                ch_count = cur.fetchone()['count']
        
        time_left = get_time_remaining(user['expiry_date'])
        status = "فعال ✅" if user['is_activated'] and "منتهٍ" not in time_left else "متوقف ❌"
        txt = (f"👤 <b>بيانات حسابك:</b>\n\n• الحالة: {status}\n• المتبقي: {time_left}\n• القنوات: {ch_count}\n• الرمز الخاص: <code>{user['secret_token']}</code>")
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'add_ch':
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📢 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="يرجى النقر على الزر لاختيار القناة المراد ربطها بالويب هوك:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

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
            await query.edit_message_text("📺 <b>قنواتك المرتبطة:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith('del_'):
        ch_id = data.replace('del_', '')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), ch_id))
                conn.commit()
        await query.edit_message_text(f"✅ تم حذف القناة {ch_id} بنجاح.", reply_markup=await get_main_menu(uid))

    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
        await query.edit_message_text(f"✅ تم تحديث الرمز السري بنجاح.\n⚠️ يجب تحديث روابط الويب هوك في TradingView فوراً.", reply_markup=await get_main_menu(uid))

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

    # --- إدارة الأدمن ---
    elif data == 'admin_panel' and uid == ADMIN_ID:
        kb = [[InlineKeyboardButton("🎫 توليد كود تفعيل", callback_data='admin_durations')],
              [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='admin_users')],
              [InlineKeyboardButton("🏠 عودة", callback_data='home')]]
        await query.edit_message_text("👮 <b>لوحة تحكم الأدمن</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'admin_durations' and uid == ADMIN_ID:
        kb = [[InlineKeyboardButton("10 أيام", callback_data='gen_10'), InlineKeyboardButton("30 يوم", callback_data='gen_30')],
              [InlineKeyboardButton("60 يوم", callback_data='gen_60'), InlineKeyboardButton("90 يوم", callback_data='gen_90')],
              [InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]
        await query.edit_message_text("اختر مدة الكود المراد إنشاؤه:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('gen_') and uid == ADMIN_ID:
        days = int(data.replace('gen_', ''))
        code = f"MOH-{secrets.token_hex(3).upper()}"
        with get_db() as conn:
            with conn.cursor() as cur:
                # التأكد من عدم تكرار الكود (Unique Code)
                cur.execute("INSERT INTO activation_codes (code, duration_days, is_used) VALUES (%s, %s, FALSE)", (code, days))
                conn.commit()
        await query.edit_message_text(f"✅ تم إنشاء كود جديد:\n<code>{code}</code>\nالمدة: {days} يوم", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]))

    elif data == 'admin_users' and uid == ADMIN_ID:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id, is_activated, expiry_date FROM users ORDER BY created_at DESC LIMIT 10")
                users = cur.fetchall()
        txt = "👥 <b>آخر المستخدمين:</b>\n\n"
        kb = []
        for u in users:
            status = "✅" if u['is_activated'] else "❌"
            txt += f"{status} <code>{u['user_id']}</code> | {u['expiry_date'].strftime('%Y-%m-%d') if u['expiry_date'] else 'N/A'}\n"
            kb.append([InlineKeyboardButton(f"⚙️ إدارة {u['user_id']}", callback_data=f"manage_u_{u['user_id']}")])
        kb.append([InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')])
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

# --- الرسائل والمدخلات ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')

    if state == 'WAIT_CODE' and update.message.text:
        success, days = await activate_with_code(uid, update.message.text.strip())
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم تفعيل الاشتراك بنجاح لمدة {days} يوماً!")
            return await start(update, context)
        await update.message.reply_text("❌ الكود خاطئ أو تم استخدامه مسبقاً.")

    if state == 'wait_ch' and update.message.chat_shared:
        target_id = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), target_id))
                conn.commit()
        await update.message.reply_text(f"✅ تم ربط القناة <code>{target_id}</code> بنجاح!", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
        context.user_data['state'] = None
        return await start(update, context)

# --- نظام الويب هوك (إرسال خام) ---

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_text = request.get_data(as_text=True) # استقبال النص خام بدون أي تعديل
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""SELECT u.user_id, u.is_activated, u.expiry_date FROM users u 
                           JOIN entities e ON u.user_id = e.user_id 
                           WHERE u.secret_token=%s AND e.entity_id=%s""", (token, target_id))
            user = cur.fetchone()
            if not user: return jsonify({"error": "Unauthorized"}), 403
            
            is_expired = user['expiry_date'] and datetime.datetime.now() > user['expiry_date']
            if int(user['user_id']) != ADMIN_ID and (not user['is_activated'] or is_expired):
                return jsonify({"error": "Subscription Expired"}), 403
    
    try:
        # إرسال الإشارة بشكل خام تماماً لقناة تليجرام
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      json={"chat_id": target_id, "text": raw_text, "parse_mode": "HTML"})
        return jsonify({"status": "sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- الاستيقاظ والتشغيل ---

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

def keep_alive():
    while True:
        try: requests.get(DOMAIN, timeout=10)
        except: pass
        time.sleep(5) # استيقاظ كل 5 ثوانٍ

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    print("🚀 نظام Mr.MOH مفعل وشغال...")
    application.run_polling()
