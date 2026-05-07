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
    
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=markup)

# --- 2. معالج الأزرار الشامل (Callbacks) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    
    try:
        await query.answer()
    except:
        pass

    # --- التنقل والقائمة الرئيسية ---
    if data == 'home':
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", parse_mode='HTML', reply_markup=markup)

    elif data == 'wh':
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'tok':
        database.update_user_secret_token(uid)
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(f"✅ <b>تم تحديث رمز الأمان بنجاح!</b>\n\n{msg_text}", parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'acc':
        user = database.get_user_profile(uid)
        if user:
            status = "✅ مفعل" if user.get('is_activated') else "❌ غير مفعل"
            expiry = services.get_time_remaining(user.get('expiry_date'))
            acc_text = f"👤 <b>بيانات حسابك:</b>\n\n🆔 معرفك: <code>{uid}</code>\n🚦 الحالة: {status}\n⏳ المتبقي: {expiry}"
            await query.edit_message_text(acc_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'chs':
        entities = database.get_user_entities(uid)
        markup = keyboards.get_entities_keyboard(entities)
        try:
            await query.edit_message_text("📺 <b>قنواتك المرتبطة:</b>\n\nاضغط على ❌ لحذف القناة، أو أضف قناة جديدة.", parse_mode='HTML', reply_markup=markup)
        except: pass

    elif data == 'add_channel':
        await context.bot.send_message(chat_id=uid, text="👇 اضغط على الزر بالأسفل لاختيار القناة:", reply_markup=keyboards.get_request_channel_keyboard())

    elif data == 'ren':
        await query.edit_message_text("📩 أرسل كود التفعيل الآن في رسالة نصية:", reply_markup=keyboards.get_back_home())
        context.user_data['awaiting_code'] = True

    # --- أزرار لوحة التحكم للأدمن ---
    elif data == 'adm':
        if int(uid) == int(config.ADMIN_ID):
            total_u, active_u, codes = database.get_admin_dashboard_stats()
            admin_text = f"👮 <b>لوحة التحكم</b>\n\n👥 المستخدمين: {total_u}\n✅ النشطين: {active_u}\n🎫 الأكواد: {codes}"
            await query.edit_message_text(admin_text, parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        else:
            await query.answer("⚠️ للمالك فقط", show_alert=True)

    elif data == 'adm_g': # توليد كود يبدأ بـ SMO-
        if int(uid) == int(config.ADMIN_ID):
            random_part = secrets.token_hex(4).upper()
            new_code = f"SMO-{random_part}"
            
            if database.add_subscription_code(new_code, 30):
                await query.message.reply_text(f"🎫 <b>تم توليد كود جديد:</b>\n<code>{new_code}</code>", parse_mode='HTML')
            else:
                await query.answer("❌ فشل حفظ الكود")

    elif data == 'adm_s': # إحصائيات مفصلة
        if int(uid) == int(config.ADMIN_ID):
            total_u, active_u, codes = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"📊 <b>الإحصائيات:</b>\n\nالمسجلين: {total_u}\nالمشتركين: {active_u}\nالأكواد: {codes}", parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data.startswith('d_'): # حذف قناة
        target_id = data.replace('d_', '')
        database.delete_entity(uid, target_id)
        await query.answer("✅ تم الحذف")
        new_entities = database.get_user_entities(uid)
        await query.edit_message_reply_markup(reply_markup=keyboards.get_entities_keyboard(new_entities))

# --- 3. معالج الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # معالجة القنوات المشتركة (Chat Shared)
    if update.message.chat_shared:
        channel_id = update.message.chat_shared.chat_id
        try:
            chat_info = await context.bot.get_chat(channel_id)
            if database.add_entity(uid, str(channel_id), chat_info.title):
                await update.message.reply_text(f"✅ تم ربط: <b>{chat_info.title}</b>", parse_mode='HTML', reply_markup=ReplyKeyboardRemove())
            else:
                await update.message.reply_text("⚠️ مرتبطة مسبقاً.")
        except:
            await update.message.reply_text("❌ خطأ، تأكد أن البوت مشرف في القناة.", reply_markup=ReplyKeyboardRemove())
        return

    # معالجة إدخال كود التفعيل
    if context.user_data.get('awaiting_code'):
        success, msg = database.activate_user_with_code(uid, update.message.text.strip())
        context.user_data['awaiting_code'] = False
        bot_info = await context.bot.get_me()
        await update.message.reply_text(msg, reply_markup=await keyboards.get_main_menu(uid, bot_info.username))

# --- 4. التشغيل ---
async def main():
    database.init_db()
    app = Application.builder().token(config.BOT_TOKEN).connect_timeout(30).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    # تشغيل المهام الجانبية
    asyncio.create_task(web_server.start_server())
    asyncio.create_task(services.keep_alive())
    
    logger.info("🚀 النظام يعمل بكامل طاقته...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
