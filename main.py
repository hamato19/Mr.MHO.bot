import logging
import asyncio
import secrets
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد الملفات المحلية المترابطة
import config
import database
import services
import keyboards
import web_server

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. الدالة الرئيسية عند بدء البوت /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    services.initialize_user(uid)
    
    # جلب يوزر البوت تلقائياً لرابط إضافة المشرف
    bot_info = await context.bot.get_me()
    
    # استخدام الدالة async من ملف keyboards.py الجديد
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    
    welcome_text = (
        "👋 <b>مرحباً بك في منظومة سمو الأرقام (Mr. MOH)</b>\n\n"
        "هذا البوت يربط إشارات <b>TradingView</b> مباشرة بقنواتك.\n\n"
        "استخدم القائمة أدناه لإدارة حسابك وروابط الويب هوك."
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=markup
    )

# --- 2. معالج الأزرار التفاعلية (تم تحديث الـ Callback لتطابق الكيبورد الجديد) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    
    await query.answer()

    # --- روابط الويب هوك (view_wh) ---
    if data == 'view_wh':
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_back_to_home())

    # --- تحديث الرمز (gen_token) ---
    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        services.update_user_token(uid, new_token)
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(
            f"✅ <b>تم تحديث رمز الأمان بنجاح!</b>\n\n{msg_text}",
            parse_mode='HTML',
            reply_markup=keyboards.get_back_to_home()
        )

    # --- حسابي (acc) ---
    elif data == 'acc':
        user = services.get_user_data(uid)
        if user:
            status = "✅ مفعل" if services.is_user_active(user) else "❌ غير مفعل"
            expiry = services.get_time_remaining(user.get('expiry_date'))
            acc_text = (
                f"👤 <b>بيانات حسابك:</b>\n\n"
                f"🆔 معرفك: <code>{uid}</code>\n"
                f"🚦 الحالة: {status}\n"
                f"⏳ المتبقي: {expiry}\n"
                f"🔑 الرمز الحالي: <code>{user.get('secret_token')}</code>"
            )
            await query.edit_message_text(acc_text, parse_mode='HTML', reply_markup=keyboards.get_back_to_home())

    # --- قنواتي (view_chs) ---
    elif data == 'view_chs':
        entities = services.get_user_entities(uid)
        markup = keyboards.get_entities_keyboard(entities)
        await query.edit_message_text("📺 <b>قنواتك المرتبطة:</b>\n(اضغط على اسم القناة لحذف الربط)", parse_mode='HTML', reply_markup=markup)

    # --- تجديد الاشتراك / إدخال كود (renew_sub) ---
    elif data == 'renew_sub':
        await query.edit_message_text(
            "📩 من فضلك أرسل كود التفعيل الآن في رسالة نصية:",
            reply_markup=keyboards.get_back_to_home()
        )
        context.user_data['awaiting_code'] = True

    # --- لوحة التحكم للأدمن (admin_panel) ---
    elif data == 'admin_panel':
        if int(uid) == config.ADMIN_ID:
            await query.edit_message_text("👮 <b>لوحة تحكم الأدمن</b>", parse_mode='HTML', reply_markup=keyboards.get_admin_main_keyboard())
        else:
            await query.answer("⚠️ عذراً، هذه الصلاحية للمالك فقط.", show_alert=True)

    # --- العودة للقائمة الرئيسية (home) ---
    elif data == 'home':
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", parse_mode='HTML', reply_markup=markup)

# --- 3. معالج الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if context.user_data.get('awaiting_code'):
        success, message = services.redeem_code(uid, update.message.text)
        context.user_data['awaiting_code'] = False
        # جلب بيانات المستخدم المحدثة لعرض المنيو
        user = services.get_user_data(uid)
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await update.message.reply_text(message, reply_markup=markup)

# --- 4. تشغيل المنظومة ---
async def main():
    database.init_db()
    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    asyncio.create_task(web_server.start_server())
    asyncio.create_task(services.keep_alive())

    logger.info("🚀 النظام يعمل الآن بكامل خصائصه...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 تم إيقاف النظام.")
