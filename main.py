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

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. الدالة الرئيسية /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    database.register_user_if_not_exists(uid)
    
    bot_info = await context.bot.get_me()
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

# --- 2. معالج الأزرار المصلح (Callbacks) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    
    # محاولة إجابة التنبيه لتجنب تعليق الزر
    try:
        await query.answer()
    except:
        pass

    if data == 'home':
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", parse_mode='HTML', reply_markup=markup)

    elif data == 'wh':
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'tok':
        new_token = database.update_user_secret_token(uid)
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(
            f"✅ <b>تم تحديث رمز الأمان بنجاح!</b>\n\n{msg_text}",
            parse_mode='HTML',
            reply_markup=keyboards.get_back_home()
        )

    elif data == 'acc':
        user = database.get_user_profile(uid)
        if user:
            status = "✅ مفعل" if user.get('is_activated') else "❌ غير مفعل"
            expiry = services.get_time_remaining(user.get('expiry_date'))
            acc_text = (
                f"👤 <b>بيانات حسابك:</b>\n\n"
                f"🆔 معرفك: <code>{uid}</code>\n"
                f"🚦 الحالة: {status}\n"
                f"⏳ المتبقي: {expiry}"
            )
            await query.edit_message_text(acc_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'chs':
        entities = database.get_user_entities(uid)
        markup = keyboards.get_entities_keyboard(entities)
        try:
            await query.edit_message_text("📺 <b>قنواتك المرتبطة:</b>\n\nاضغط على اسم القناة لحذفها، أو استخدم زر الإضافة بالأسفل.", parse_mode='HTML', reply_markup=markup)
        except telegram.error.BadRequest:
            pass

    elif data == 'add_channel': # تأكد أن هذا الاسم مطابق للزر في keyboards.py
        # نقوم بإرسال رسالة جديدة لأن ReplyKeyboardMarkup لا يظهر مع تعديل الرسالة
        await context.bot.send_message(
            chat_id=uid,
            text="👇 اضغط على الزر بالأسفل لاختيار القناة من حسابك مباشرة:",
            reply_markup=keyboards.get_request_channel_keyboard()
        )

    elif data == 'ren':
        await query.edit_message_text(
            "📩 من فضلك أرسل كود التفعيل الآن في رسالة نصية:",
            reply_markup=keyboards.get_back_home()
        )
        context.user_data['awaiting_code'] = True

    elif data == 'adm':
        # الإصلاح الحاسم: تحويل الطرفين لـ int لضمان نجاح المقارنة
        if int(uid) == int(config.ADMIN_ID):
            total_u, active_u, codes = database.get_admin_dashboard_stats()
            admin_text = (
                "👮 <b>لوحة تحكم الأدمن</b>\n\n"
                f"👥 المستخدمين: {total_u}\n"
                f"✅ النشطين: {active_u}\n"
                f"🎫 الأكواد المتاحة: {codes}"
            )
            await query.edit_message_text(admin_text, parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        else:
            await query.answer("⚠️ عذراً، هذه الصلاحية للمالك فقط.", show_alert=True)

    elif data.startswith('d_'):
        try:
            target_id = data.replace('d_', '')
            database.delete_entity(uid, target_id)
            await query.answer("✅ تم حذف القناة بنجاح", show_alert=True)
            new_entities = database.get_user_entities(uid)
            await query.edit_message_reply_markup(reply_markup=keyboards.get_entities_keyboard(new_entities))
        except Exception as e:
            logger.error(f"Error in delete: {e}")

# --- 3. معالج الرسائل المصلح ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # 1. معالجة اختيار القناة المباشر (Chat Shared)
    if update.message.chat_shared:
        channel_id = update.message.chat_shared.chat_id
        try:
            chat_info = await context.bot.get_chat(channel_id)
            channel_name = chat_info.title
            success = database.add_entity(uid, str(channel_id), channel_name)
            
            if success:
                await update.message.reply_text(
                    f"✅ تم ربط القناة بنجاح:\n<b>{channel_name}</b>",
                    parse_mode='HTML',
                    reply_markup=ReplyKeyboardRemove() # إخفاء الكيبورد السفلي بعد النجاح
                )
            else:
                await update.message.reply_text("⚠️ هذه القناة مرتبطة مسبقاً.")
        except Exception as e:
            await update.message.reply_text("❌ حدث خطأ، تأكد أن البوت مشرف في القناة.", reply_markup=ReplyKeyboardRemove())
        return

    # 2. معالجة كود التفعيل
    if context.user_data.get('awaiting_code'):
        code = update.message.text.strip()
        success, message = database.activate_user_with_code(uid, code)
        context.user_data['awaiting_code'] = False
        
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await update.message.reply_text(message, reply_markup=markup)
        return

# --- 4. تشغيل المنظومة ---
async def main():
    database.init_db()
    # زيادة وقت الاتصال لتجنب أخطاء Render المتكررة
    application = Application.builder().token(config.BOT_TOKEN).connect_timeout(30).read_timeout(30).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    asyncio.create_task(web_server.start_server())
    asyncio.create_task(services.keep_alive())

    logger.info("🚀 نظام سمو الأرقام يعمل الآن بكامل خصائصه...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 تم إيقاف النظام.")
