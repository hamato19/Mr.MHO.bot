import logging
import asyncio
import secrets
import telegram
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد الملفات المحلية
import config
import database
import services
import keyboards 
import web_server
import privacy_policy
import security  

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. الدالة الرئيسية /start ---
@security.rate_limit(seconds=2)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = database.get_user_profile(uid)
    
    # التحقق من الحظر أولاً (قبل أي إجراء)
    blocked, hours_left, level = security.is_user_blocked(uid)
    if blocked:
        msg = f"🚫 حسابك موقف حالياً. يرجى الانتظار <code>{hours_left}</code> ساعة."
        if level >= 3: msg = f"🔒 حسابك محظور بشكل نهائي.\nتواصل مع الإدارة لفك الحظر."
        await update.message.reply_text(msg, parse_mode='HTML')
        return

    # 1️⃣ فحص الموافقة على الخصوصية
    if not user:
        await update.message.reply_text(
            privacy_policy.DISCLAIMER_TEXT, 
            parse_mode='HTML', 
            reply_markup=keyboards.get_disclaimer_keyboard()
        )
        return

    is_admin = (int(uid) == int(config.ADMIN_ID))

    # 2️⃣ فحص التفعيل الإجباري
    if not user.get('is_activated') and not is_admin:
        await update.message.reply_text(
            "⚠️ <b>تنبيه: الحساب غير مفعل</b>\n\nيرجى إرسال كود التفعيل (مثال: <code>SMO-366EDDDC</code>):",
            parse_mode='HTML',
            reply_markup=keyboards.get_subscription_options()
        )
        context.user_data['awaiting_code'] = True
        return

    # 3️⃣ الدخول للقائمة الرئيسية
    bot_info = await context.bot.get_me()
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    welcome_text = (
        "👋 <b>منظومة سمو الأرقام (Mr. MOH)</b>\n\n"
        "حسابك نشط وجاهز للعمل. استخدم القائمة أدناه:"
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=markup)

# --- 2. معالج الأزرار الشامل ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    
    try: await query.answer()
    except: pass

    # منع المحظورين من استخدام الأزرار
    blocked, _, _ = security.is_user_blocked(uid)
    if blocked: return

    # أزرار الخصوصية (متاحة للجميع)
    if data == 'view_priv':
        await query.edit_message_text(privacy_policy.PRIVACY_TEXT, parse_mode='HTML', reply_markup=keyboards.get_back_to_tos())
        return
    elif data == 'back_tos':
        await query.edit_message_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        return
    elif data == 'accept_tos':
        database.register_user_if_not_exists(uid)
        # بعد القبول، نوجهه لصفحة التفعيل
        user = database.get_user_profile(uid)
        await query.edit_message_text("✅ تمت الموافقة. يرجى إرسال كود التفعيل الآن:", parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
        context.user_data['awaiting_code'] = True
        return

    # فحص التفعيل للأزرار الأخرى
    user = database.get_user_profile(uid)
    is_admin = (int(uid) == int(config.ADMIN_ID))
    if not is_admin and (not user or not user.get('is_activated')):
        await query.answer("⚠️ عذراً، هذا القسم للمشتركين فقط!", show_alert=True)
        return

    # الأزرار الوظيفية
    if data == 'home':
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", parse_mode='HTML', reply_markup=markup)

    elif data == 'wh':
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'acc':
        status = "✅ مفعل" if user.get('is_activated') else "❌ غير مفعل"
        expiry = services.get_time_remaining(user.get('expiry_date'))
        acc_text = f"👤 <b>بيانات حسابك:</b>\n\n🆔 معرفك: <code>{uid}</code>\n🚦 الحالة: {status}\n⏳ المتبقي: {expiry}"
        await query.edit_message_text(acc_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    # لوحة التحكم (أدمن فقط)
    elif data == 'adm' and is_admin:
        total_u, active_u, codes = database.get_admin_dashboard_stats()
        admin_text = f"👮 <b>لوحة التحكم</b>\n\n👥 المستخدمين: {total_u}\n✅ النشطين: {active_u}\n🎫 الأكواد المتوفرة: {codes}"
        await query.edit_message_text(admin_text, parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())

    elif data == 'adm_gen_menu' and is_admin:
        await query.edit_message_text("🗓️ <b>توليد كود اشتراك جديد:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())

    elif data.startswith('gen_') and is_admin:
        days = int(data.split('_')[1])
        new_code = f"SMO-{secrets.token_hex(4).upper()}"
        if database.add_subscription_code(new_code, days):
            await query.message.reply_text(f"🎫 <b>تم التوليد بنجاح:</b>\n<code>{new_code}</code>\nالصلاحية: {days} يوم", parse_mode='HTML')

# --- 3. معالج الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    uid = update.effective_user.id
    raw_text = update.message.text

    # نظام الحماية والتفعيل
    if context.user_data.get('awaiting_code'):
        # دالة process_security_check تتولى (الفحص، الحظر، التفعيل، وتنبيه الأدمن)
        await security.process_security_check(update, context, uid, raw_text)
        return

    # أي رسائل أخرى بعد التفعيل يمكن معالجتها هنا

# --- 4. معالج ربط القنوات (Chat Shared) ---
async def handle_chat_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.chat_shared:
        channel_id = update.message.chat_shared.chat_id
        try:
            chat_info = await context.bot.get_chat(channel_id)
            if database.add_entity(uid, str(channel_id), chat_info.title):
                await update.message.reply_text(f"✅ تم ربط القناة بنجاح: <b>{chat_info.title}</b>", parse_mode='HTML', reply_markup=ReplyKeyboardRemove())
        except:
            await update.message.reply_text("❌ فشل الربط. تأكد أن البوت "أدمن" في القناة.", reply_markup=ReplyKeyboardRemove())

# --- 5. الإقلاع ---
async def main():
    database.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_chat_shared))
    
    # تشغيل الخدمات الخلفية
    asyncio.create_task(web_server.start_server())
    asyncio.create_task(services.keep_alive())
    
    logger.info("🚀 نظام سمو الأرقام (النسخة الاحترافية) انطلق...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
