import logging
import asyncio
import secrets
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد الملفات المحلية المترابطة
import config
import database
import services
import keyboards  # التأكد من استيراد ملف الكيبورد المحدث
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

# --- 2. معالج الأزرار التفاعلية (Callbacks) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    
    await query.answer()

    # --- القائمة الرئيسية (home) ---
    if data == 'home':
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", parse_mode='HTML', reply_markup=markup)

    # --- روابط الويب هوك (wh) ---
    elif data == 'wh':
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    # --- تحديث الرمز (tok) ---
    elif data == 'tok':
        new_token = secrets.token_hex(8)
        services.update_user_token(uid, new_token)
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(
            f"✅ <b>تم تحديث رمز الأمان بنجاح!</b>\n\n{msg_text}",
            parse_mode='HTML',
            reply_markup=keyboards.get_back_home()
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
                f"⏳ المتبقي: {expiry}"
            )
            await query.edit_message_text(acc_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    # --- قنواتي (chs) ---
    elif data == 'chs':
        entities = services.get_user_entities(uid)
        markup = keyboards.get_entities_keyboard(entities)
        await query.edit_message_text("📺 <b>قنواتك المرتبطة:</b>\n(اضغط على اسم القناة لحذف الربط)", parse_mode='HTML', reply_markup=markup)

    # --- تجديد الاشتراك / إدخال كود (ren) ---
    elif data == 'ren':
        await query.edit_message_text(
            "📩 من فضلك أرسل كود التفعيل الآن في رسالة نصية:",
            reply_markup=keyboards.get_back_home()
        )
        context.user_data['awaiting_code'] = True

    # --- لوحة التحكم للأدمن (adm) ---
    elif data == 'adm':
        if int(uid) == config.ADMIN_ID:
            await query.edit_message_text("👮 <b>لوحة تحكم الأدمن</b>", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        else:
            await query.answer("⚠️ عذراً، هذه الصلاحية للمالك فقط.", show_alert=True)

    # --- حذف القنوات (البادئة d_ متوافقة مع نظام الفهرسة في keyboards.py) ---
    elif data.startswith('d_'):
        try:
            index = int(data.replace('d_', ''))
            entities = services.get_user_entities(uid)
            
            if 0 <= index < len(entities):
                target_entity = entities[index]
                target_id = target_entity[0] # المعرف الحقيقي
                
                # استدعاء دالة الحذف الفعلية
                services.delete_entity(uid, target_id) 
                
                await query.answer(f"✅ تم حذف: {target_entity[1]}", show_alert=True)
            else:
                await query.answer("⚠️ القناة غير موجودة")
        except Exception as e:
            logger.error(f"Error in delete: {e}")
            await query.answer("⚠️ حدث خطأ أثناء الحذف")
            
        # تحديث القائمة فوراً بعد الحذف
        new_entities = services.get_user_entities(uid)
        await query.edit_message_reply_markup(reply_markup=keyboards.get_entities_keyboard(new_entities))

# --- 3. معالج الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if context.user_data.get('awaiting_code'):
        success, message = services.redeem_code(uid, update.message.text)
        context.user_data['awaiting_code'] = False
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await update.message.reply_text(message, reply_markup=markup)

# --- 4. الدالة الرئيسية لتشغيل المنظومة ---
async def main():
    database.init_db()
    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

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
