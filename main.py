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

# إعداد السجلات لمراقبة أداء السيرفر في Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. الدالة الرئيسية عند بدء البوت /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    # إنشاء ملف للمستخدم في قاعدة البيانات إن لم يوجد
    services.initialize_user(uid)
    
    user = services.get_user_data(uid)
    
    welcome_text = (
        "👋 <b>مرحباً بك في منظومة سمو الأرقام (Mr. MOH)</b>\n\n"
        "هذا البوت هو جسرك لربط إشارات <b>TradingView</b> مباشرة بقنواتك.\n\n"
        "🚀 <b>كيف تبدأ؟</b>\n"
        "1. أضف البوت مشرفاً في قناتك.\n"
        "2. اربط القناة من قسم 'قنواتي'.\n"
        "3. انسخ رابط الويب هوك وضعه في تنبيهات المنصة."
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=keyboards.get_main_keyboard(user)
    )

# --- 2. معالج الأزرار التفاعلية (Callback Queries) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    
    await query.answer()

    # --- قسم الويب هوك وتوليد الإشارات ---
    if data == 'view_webhooks':
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_webhook_keyboard())

    elif data == 'gen_new_token':
        # توليد رمز أمان جديد وتحديث روابط الإشارة فوراً
        new_token = secrets.token_hex(8)
        services.update_user_token(uid, new_token)
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(
            f"✅ <b>تم تحديث رمز الأمان بنجاح!</b>\n\n{msg_text}",
            parse_mode='HTML',
            reply_markup=keyboards.get_webhook_keyboard()
        )

    # --- قسم قنواتي وإدارة الربط ---
    elif data == 'my_channels':
        msg_text = services.format_my_entities(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_channels_management_keyboard())

    # --- لوحة تحكم المالك (خاصة بـ فهد بن محمد) ---
    elif data == 'admin_panel':
        if uid == config.ADMIN_ID:
            u_count, c_count = services.get_admin_stats()
            admin_msg = (
                f"🛡️ <b>لوحة تحكم المالك</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"👥 المستخدمين: {u_count}\n"
                f"🎫 أكواد التفعيل: {c_count}\n"
                f"⚙️ الحالة: متصل (Online)"
            )
            await query.edit_message_text(admin_msg, parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        else:
            await query.answer("⚠️ صلاحية المالك مطلوبة.", show_alert=True)

    # --- العودة للوحة التحكم الرئيسية ---
    elif data == 'back_to_home':
        user = services.get_user_data(uid)
        expiry_info = services.get_time_remaining(user['expiry_date'])
        status = "✅ مفعل" if services.is_user_active(user) else "❌ غير مفعل"
        
        home_text = (
            f"🏠 <b>لوحة التحكم | سمو الأرقام</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 المعرف: <code>{uid}</code>\n"
            f"🚦 الاشتراك: {status}\n"
            f"⏳ المتبقي: {expiry_info}\n"
            f"🔑 الرمز: <code>{user['secret_token']}</code>"
        )
        await query.edit_message_text(home_text, parse_mode='HTML', reply_markup=keyboards.get_main_keyboard(user))

# --- 3. معالج الرسائل (لتفعيل الأكواد) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # إذا كان المستخدم في حالة انتظار لإدخال كود
    if context.user_data.get('awaiting_code'):
        success, message = services.redeem_code(uid, text)
        context.user_data['awaiting_code'] = False
        await update.message.reply_text(message, reply_markup=keyboards.get_main_keyboard(services.get_user_data(uid)))

# --- 4. الدالة الرئيسية لتشغيل المنظومة ---
async def main():
    # أ. تهيئة قاعدة البيانات
    database.init_db()

    # ب. بناء تطبيق التلجرام
    application = Application.builder().token(config.BOT_TOKEN).build()

    # ج. تسجيل المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # د. تشغيل سيرفر استقبال إشارات TradingView (الويب هوك)
    asyncio.create_task(web_server.start_server())

    # هـ. تشغيل خاصية Keep Alive لمنع خمول السيرفر
    asyncio.create_task(services.keep_alive())

    # و. إطلاق البوت
    logger.info("🚀 النظام يعمل الآن بكامل خصائصه...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # ضمان بقاء السيرفر يعمل بشكل مستمر
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 تم إيقاف النظام.")
