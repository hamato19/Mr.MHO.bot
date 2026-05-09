import logging, asyncio, secrets, os
from telegram import Update, ReplyKeyboardRemove, ChatAdministratorRights, KeyboardButtonRequestChat
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy
import activation_handler

# إعدادات المراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def clean_and_show_menu(update_or_query, context, uid):
    """دالة التنظيف الذكي: تحديث القائمة الرئيسية (Inline) دون مسح أزرار الكيبورد السفلي"""
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    
    # التحقق من حالة التفعيل
    if not is_owner and (not user or not user.get('is_activated')):
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إدخال كود التفعيل:"
        markup = keyboards.get_subscription_options()

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else:
        try:
            # نستخدم التعديل (Edit) للقائمة لتظل الواجهة سلسة
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except:
            await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = database.get_user_profile(uid)
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
    else:
        await clean_and_show_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    try: await query.answer()
    except: pass

    # --- التنقل للرئيسية ---
    if data == 'home':
        context.user_data.clear()
        await clean_and_show_menu(query, context, uid)
        return

    # --- إدارة زر إضافة قناة (التعديل المطلوب) ---
    if data == 'add_channel':
        context.user_data['awaiting_code'] = False 
        # نرسل رسالة جديدة بطلب القناة (Reply Keyboard) مع إبقاء القائمة (Inline) بالأعلى
        await query.message.reply_text(
            "📢 <b>تم فتح خيار اختيار القناة في الأسفل 👇</b>\nيرجى الضغط على زر 'اختر القناة' وربطها بالبوت.", 
            parse_mode='HTML',
            reply_markup=keyboards.get_request_channel_keyboard()
        )
        # لا نستخدم delete_message هنا لتبقى القائمة الرئيسية موجودة للسلسلة
        return

    # --- بقية العمليات ---
    if is_owner or (user and user.get('is_activated')):
        if data == 'chs':
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>قنواتك المرتبطة (ID):</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
        elif data == 'wh':
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🌐 <b>روابط الويب هوك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date')) if user else "غير محدد"
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الصلاحية: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message: return
    text = update.message.text.strip() if update.message.text else ""

    # عند استلام القناة بنجاح
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        # نخفي كيبورد "اختيار القناة" فقط الآن لنعود للواجهة العادية
        await update.message.reply_text("✅ تم ربط القناة بنجاح!", reply_markup=ReplyKeyboardRemove())
        await clean_and_show_menu(update, context, uid)
        return

    # تفعيل الكود عبر ملف activation_handler
    if text.upper().startswith("SMO-"):
        status_msg = await update.message.reply_text("⏳ جاري التحقق...")
        success, response_text = activation_handler.process_activation(uid, text.upper())
        if success:
            context.user_data.clear()
            await status_msg.edit_text(f"🎊 {response_text}", parse_mode='HTML')
            await clean_and_show_menu(update, context, uid)
        else:
            await status_msg.edit_text(f"❌ {response_text}", parse_mode='HTML')
        return

async def main():
    database.init_db()
    asyncio.create_task(web_server.start_server())
    
    # تحسين وقت الاستجابة والاتصال
    app = Application.builder().token(config.BOT_TOKEN).read_timeout(30).connect_timeout(30).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    
    logger.info("🚀 البوت يعمل بكفاءة...")
    await app.initialize(); await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
