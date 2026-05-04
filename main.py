import os, secrets, asyncio, threading, logging, datetime
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
main_loop = None

# --- القوائم والأزرار ---
async def get_main_menu(uid):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 إضافة قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐  رابط الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 توليد رمز جديد", callback_data='gen_token')],
        [InlineKeyboardButton("📺 حذف/قنواتي", callback_data='view_chs')],
        [InlineKeyboardButton("📊 TradingView", web_app=WebAppInfo(url="https://www.tradingview.com/chart/"))],
        [InlineKeyboardButton("☎️ الدعم الفني", url=f"tg://user?id={ADMIN_ID}")]
    ]
    # لوحة الأدمن المتطورة
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (توليد رموز)", callback_data='admin_durations')])
    return InlineKeyboardMarkup(kb)

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    
    # فحص الاشتراك واستثناء الأدمن
    allowed, msg = await check_user_access(uid)
    if uid == ADMIN_ID: allowed = True

    if not allowed:
        context.user_data['state'] = 'WAIT_CODE'
        kb = [[InlineKeyboardButton("💳 اشترك الآن (تواصل مع الإدارة)", url=f"tg://user?id={ADMIN_ID}")]]
        return await update.message.reply_text(
            f"👋 مرحباً بك في بوت Mr.MOH\n\n{msg}\n\nأرسل رمز التفعيل هنا، أو اضغط للاشتراك عبر الإدارة:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # تسجيل المستخدم إذا لم يكن موجوداً
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
        txt = f"👤 <b>بيانات حسابك:</b>\n\n🆔 الآيدي: <code>{uid}</code>\n📅 انتهاء الاشتراك: <code>{expiry_txt}</code>\n📺 القنوات المرتبطة: <code>{count}</code>\n🔑 التوكن الحالي: <code>{user['secret_token']}</code>"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'add_ch':
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📂 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="📢 قم باختيار القناة المراد ربطها بالبوت من القائمة:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    elif data == 'view_chs':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text("❌ لا توجد قنوات مرتبطة حالياً.", reply_markup=await get_main_menu(uid))
        else:
            kb = [[InlineKeyboardButton(f"🗑️ حذف القناة {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
            kb.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
            await query.edit_message_text("📺 <b>إدارة قنواتك:</b>\nاضغط على القناة لحذف الربط عنها.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith('del_'):
        ch_id = data.replace('del_', '')
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), ch_id))
                conn.commit()
        await query.edit_message_text(f"✅ تم حذف القناة {ch_id} بنجاح.", reply_markup=await get_main_menu(uid))

    elif data == 'view_wh':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                token = cur.fetchone()['secret_token']
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents:
            await query.edit_message_text("⚠️ يرجى إضافة قناة أولاً لتوليد روابط الويب هوك.", reply_markup=await get_main_menu(uid))
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
        await query.edit_message_text(f"✅ تم تحديث التوكن السري!\nالتوكن الجديد: <code>{new_token}</code>\n\n⚠️ لا تنسَ تحديث الروابط في TradingView.", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(uid))

    # --- إدارة الأدمن ومدد الاشتراك ---
    elif data == 'admin_durations' and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("⏱️ 7 أيام", callback_data='gen_7'), InlineKeyboardButton("⏱️ 15 يوم", callback_data='gen_15')],
            [InlineKeyboardButton("⏱️ 30 يوم", callback_data='gen_30'), InlineKeyboardButton("⏱️ 90 يوم", callback_data='gen_90')],
            [InlineKeyboardButton("🏠 عودة", callback_data='home')]
        ]
        await query.edit_message_text("💎 <b>لوحة توليد الأكواد:</b>\nاختر مدة الاشتراك المطلوبة للرمز الجديد:", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith('gen_') and uid == ADMIN_ID:
        days = int(data.replace('gen_', ''))
        code = f"MOH-{secrets.token_hex(3).upper()}"
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO activation_codes (code, duration_days) VALUES (%s, %s)", (code, days))
                conn.commit()
        await query.edit_message_text(
            f"✅ <b>تم إنشاء الرمز بنجاح!</b>\n\n🎟️ الرمز: <code>{code}</code>\n⏳ المدة: <code>{days}</code> يوماً\n\nأرسله الآن للمشترك.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للقائمة", callback_data='home')]])
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get('state') == 'WAIT_CODE':
        success, days = await activate_with_code(uid, text)
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم تفعيل حسابك بنجاح لمدة {days} يوماً!")
            return await start(update, context)
        return await update.message.reply_text("❌ رمز غير صحيح. تأكد من الكود أو تواصل مع الإدارة.")

    if context.user_data.get('state') == 'wait_ch' and update.message.chat_shared:
        target_id = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), target_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ تم ربط القناة {target_id} بنجاح!", reply_markup=ReplyKeyboardRemove())
                    await start(update, context)
                except: 
                    await update.message.reply_text("⚠️ هذه القناة مسجلة مسبقاً.", reply_markup=ReplyKeyboardRemove())
        context.user_data['state'] = None

# --- Webhook (TradingView) ---

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE
            """, (token, target_id))
            if not cur.fetchone():
                return jsonify({"status": "unauthorized"}), 403
    
    asyncio.run_coroutine_threadsafe(
        application.bot.send_message(chat_id=target_id, text=f"📊 <b>إشارة TradingView جديدة:</b>\n\n<code>{raw_data}</code>", parse_mode=ParseMode.HTML), 
        main_loop
    )
    return jsonify({"status": "success"}), 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    main_loop = asyncio.new_event_loop()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🚀 Mr.MOH Bot is fully operational!")
    application.run_polling()
