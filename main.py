import os, secrets, asyncio, threading, logging, datetime, requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from psycopg2.extras import RealDictCursor

# استيراد الدوال من الملفات المساعدة
from database import get_db
from auth import check_user_access, activate_with_code

# الإعدادات الأساسية
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
application = None

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

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    
    allowed, msg = await check_user_access(uid)
    if uid == ADMIN_ID: allowed = True

    if not allowed:
        context.user_data['state'] = 'WAIT_CODE'
        kb = [[InlineKeyboardButton("💳 اشترك الآن (تواصل مع الإدارة)", url=f"tg://user?id={ADMIN_ID}")]]
        return await update.message.reply_text(
            f"👋 مرحباً بك في بوت Mr.MOH\n\n{msg}\n\nأرسل رمز التفعيل هنا:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), secrets.token_hex(8)))
            conn.commit()

    await update.message.reply_text("🏠 <b>القائمة الرئيسية:</b>", reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)

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
                cur.execute("SELECT secret_token, expiry_date FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (str(uid),))
                count = cur.fetchone()['count']
        
        expiry_txt = user['expiry_date'].strftime('%Y-%m-%d') if user['expiry_date'] else "غير محدد"
        txt = f"👤 <b>بيانات حسابك:</b>\n\n🆔 الآيدي: <code>{uid}</code>\n📅 الانتهاء: <code>{expiry_txt}</code>\n📺 القنوات المرتبطة: <code>{count}</code>\n🔑 التوكن: <code>{user['secret_token']}</code>"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'add_ch':
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📂 اختر القناة من هنا", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="📢 اختر القناة ليقوم البوت بسحب الـ ID وحفظه في قاعدة البيانات فوراً:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    elif data == 'view_chs':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text("❌ لا توجد قنوات مرتبطة في قاعدة البيانات.", reply_markup=await get_main_menu(uid))
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
        await query.edit_message_text(f"✅ تم حذف القناة من قاعدة البيانات.", reply_markup=await get_main_menu(uid))

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
        await query.edit_message_text(f"✅ تم تحديث التوكن السري بنجاح:\n<code>{new_token}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(uid))

    # --- إدارة الأدمن ---
    elif data == 'admin_panel' and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("🎫 توليد أكواد تفعيل", callback_data='admin_durations')],
            [InlineKeyboardButton("👥 سجل المستخدمين", callback_data='admin_users')],
            [InlineKeyboardButton("🏠 عودة", callback_data='home')]
        ]
        await query.edit_message_text("👮 <b>لوحة تحكم المالك:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'admin_durations' and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("⏱️ 7 أيام", callback_data='gen_7'), InlineKeyboardButton("⏱️ 30 يوم", callback_data='gen_30')],
            [InlineKeyboardButton("⏱️ 90 يوم", callback_data='gen_90'), InlineKeyboardButton("⏱️ 365 يوم", callback_data='gen_365')],
            [InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]
        ]
        await query.edit_message_text("💎 اختر مدة الكود المراد إنشاؤه في قاعدة البيانات:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data == 'admin_users' and uid == ADMIN_ID:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id, expiry_date, is_activated FROM users ORDER BY expiry_date DESC NULLS LAST LIMIT 20")
                users = cur.fetchall()
        
        txt = "👥 <b>سجل المشتركين (قاعدة البيانات):</b>\n\n"
        for u in users:
            status = "✅" if u['is_activated'] else "❌"
            exp = u['expiry_date'].strftime('%Y-%m-%d') if u['expiry_date'] else "لم يفعل"
            txt += f"{status} <code>{u['user_id']}</code> | ينتهي: <code>{exp}</code>\n"
        
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]))

    elif data.startswith('gen_') and uid == ADMIN_ID:
        days = int(data.replace('gen_', ''))
        code = f"MOH-{secrets.token_hex(3).upper()}"
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO activation_codes (code, duration_days) VALUES (%s, %s)", (code, days))
                conn.commit()
        await query.edit_message_text(f"✅ تم تسجيل الكود في قاعدة البيانات: <code>{code}</code>\n⏳ المدة: {days} يوماً", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')

    if state == 'WAIT_CODE' and update.message.text:
        text = update.message.text.strip()
        success, days = await activate_with_code(uid, text)
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم تحديث بياناتك وتفعيل الاشتراك لـ {days} يوماً!")
            return await start(update, context)
        return await update.message.reply_text("❌ الكود غير موجود أو مستخدم مسبقاً.")

    if state == 'wait_ch' and update.message.chat_shared:
        target_id = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), target_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ تم سحب ID القناة <code>{target_id}</code> بنجاح!", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
                    context.user_data['state'] = None
                    return await start(update, context)
                except Exception as e:
                    await update.message.reply_text(f"⚠️ خطأ في قاعدة البيانات: {str(e)}")
        context.user_data['state'] = None

# --- Webhook المصلح (إرسال الإشارة خام) ---

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    # استقبال النص الخام القادم من TradingView كما هو
    raw_data = request.get_data(as_text=True)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # التحقق من قاعدة البيانات (التوكن والآيدي)
            cur.execute("""
                SELECT u.user_id, u.is_activated FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s
            """, (token, target_id))
            user = cur.fetchone()
            
            if not user: return jsonify({"status": "unauthorized"}), 403
            # استثناء للأدمن أو التحقق من التفعيل
            if int(user[0]) != ADMIN_ID and not user[1]: return jsonify({"status": "unactivated"}), 403
    
    try:
        # إرسال الرسالة خام تماماً بدون أي تنسيق أو إضافات
        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": target_id,
            "text": raw_data  # النص القادم من TradingView مباشرة
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
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🚀 البوت يعمل الآن - نظام الإرسال الخام مفعل")
    application.run_polling()
