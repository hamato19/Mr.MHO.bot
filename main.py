import logging, asyncio, secrets, os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy, security

# إعداد الحماية والسجلات
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def back_to_main_menu(update_or_query, context, uid):
    """دالة العودة للرئيسية مع فحص الاشتراك"""
    user = database.get_user_profile(uid)
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    # حماية صارمة: إذا لم يكن أدمن وغير مفعل، لا تفتح له القائمة أبداً
    if not is_owner and (not user or not user.get('is_activated')):
        text = "⚠️ <b>عذراً، يجب تفعيل الاشتراك أولاً للوصول للمنظومة.</b>"
        markup = keyboards.get_subscription_options()
    else:
        bot_info = await context.bot.get_me()
        text = "🏠 <b>القائمة الرئيسية لمنظومة سمو الأرقام:</b>"
        markup = await keyboards.get_main_menu(uid, bot_info.username)

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else:
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)

@security.rate_limit(seconds=1) # حماية من السبام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = database.get_user_profile(uid)
    
    # 1. فحص الخصوصية أولاً
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        return

    # 2. فحص التفعيل
    is_owner = (str(uid) == str(config.ADMIN_ID))
    if not is_owner and not user.get('is_activated'):
        await update.message.reply_text("⚠️ حسابك مسجل ولكن غير نشط. يرجى التفعيل:", reply_markup=keyboards.get_subscription_options())
        return

    await back_to_main_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    try: await query.answer()
    except: pass

    user = database.get_user_profile(uid)

    # بوابات الحماية (Callbacks)
    try:
        # أزرار مسموحة للجميع (الخصوصية والتفعيل)
        if data == 'view_priv':
            await query.edit_message_text(privacy_policy.PRIVACY_TEXT, parse_mode='HTML', reply_markup=keyboards.get_back_home())
            return
        elif data == 'accept_tos':
            database.register_user_if_not_exists(uid)
            await query.edit_message_text("✅ تم قبول الشروط. يرجى اختيار وسيلة التفعيل:", reply_markup=keyboards.get_subscription_options())
            return
        elif data == 'ren':
            await query.edit_message_text("🎫 أرسل كود التفعيل المكون من 10 أرقام الآن:", reply_markup=keyboards.get_back_home())
            context.user_data['awaiting_code'] = True
            return

        # حماية صارمة: منع أي Callback آخر إذا لم يكن مفعل (باستثناء الأدمن)
        if not is_owner and (not user or not user.get('is_activated')):
            await query.edit_message_text("🚫 <b>يجب التفعيل أولاً!</b>", parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
            return

        # --- منطقة العمليات (متاحة للمفعلين فقط) ---
        if data == 'home': await back_to_main_menu(query, context, uid)
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date'))
            await query.edit_message_text(f"👤 <b>بيانات الحساب:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الانتهاء: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'wh': # نظام الويب هوك الصارم
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'chs':
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 قنواتك المرتبطة:", reply_markup=keyboards.get_entities_keyboard(ents))
        elif data.startswith('del_ch_'):
            database.delete_user_entity(uid, data.replace('del_ch_', ''))
            await query.edit_message_text("✅ تم حذف القناة.", reply_markup=keyboards.get_entities_keyboard(database.get_user_entities(uid)))

        # لوحة الأدمن
        elif is_owner and data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 لوحة التحكم\n👥 الكل: {t} | ✅ نشط: {a}\n🎫 أكواد: {c}", reply_markup=keyboards.get_admin_keyboard())

    except Exception as e: logger.error(f"Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""

    # معالجة كود التفعيل
    if context.user_data.get('awaiting_code'):
        days = database.check_and_use_code(text)
        if days:
            database.activate_user_subscription(uid, days)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(f"🎉 تم تفعيل حسابك بنجاح لمدة {days} يوم!")
            await back_to_main_menu(update, context, uid)
        else:
            await update.message.reply_text("❌ الكود غير صحيح. تأكد منه أو تواصل مع الدعم.")
        return

async def main():
    database.init_db()
    asyncio.create_task(web_server.start_server()) # تشغيل نظام استقبال إشارات TradingView
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    logger.info("🚀 المنظومة تعمل بنظام الحماية القصوى...")
    await app.initialize(); await app.start(); await app.updater.start_polling(); await asyncio.Event().wait()

if __name__ == '__main__': asyncio.run(main())
