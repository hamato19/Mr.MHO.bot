import logging, asyncio, secrets, os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy

# --- 1. إعداد الـ Logging (حل مشكلة NameError) ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. الدوال المساعدة ---
async def back_to_main_menu(update_or_query, context, uid):
    """العودة للقائمة الرئيسية مع فحص حالة الاشتراك"""
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    # إذا لم يكن مفعل (وليس الأدمن) يوجه للتفعيل
    if not is_owner and (not user or not user.get('is_activated')):
        text = "⚠️ يجب تفعيل الحساب أولاً للوصول للخدمات:"
        markup = keyboards.get_subscription_options()
    else:
        text = "🏠 <b>القائمة الرئيسية لسمو الأرقام:</b>"
        markup = await keyboards.get_main_menu(uid, bot_info.username)

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else:
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)

# --- 3. معالجات الأوامر ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = database.get_user_profile(uid)
    
    # فحص الخصوصية أولاً
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
    else:
        await back_to_main_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    try: await query.answer()
    except: pass

    # مسار الخصوصية والتفعيل
    if data == 'accept_tos':
        database.register_user_if_not_exists(uid)
        await query.edit_message_text("✅ تم قبول الشروط. يرجى التفعيل الآن:", reply_markup=keyboards.get_subscription_options())
    elif data == 'reject_tos':
        await query.edit_message_text("⚠️ نعتذر، لا يمكنك استخدام المنظومة دون الموافقة على السياسة.")
    elif data == 'view_priv':
        await query.edit_message_text(privacy_policy.PRIVACY_TEXT, parse_mode='HTML', reply_markup=keyboards.get_back_home())
    
    # مسار التفعيل
    elif data == 'ren':
        await query.edit_message_text("🎫 يرجى إرسال كود التفعيل المكون من 10 أرقام:", reply_markup=keyboards.get_back_home())
        context.user_data['awaiting_code'] = True

    # مسارات المستخدم (تعمل فقط للمفعلين أو الأدمن)
    elif is_owner or (user and user.get('is_activated')):
        if data == 'home': await back_to_main_menu(query, context, uid)
        elif data == 'add_channel':
            await query.message.reply_text("📢 اختر القناة التي تريد ربطها:", reply_markup=keyboards.get_request_channel_keyboard())
        elif data == 'chs':
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 قنواتك المرتبطة:", reply_markup=keyboards.get_entities_keyboard(ents))
        elif data.startswith('del_ch_'):
            database.delete_user_entity(uid, data.replace('del_ch_', ''))
            await query.edit_message_text("✅ تم الحذف.", reply_markup=keyboards.get_entities_keyboard(database.get_user_entities(uid)))
        elif data == 'wh':
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'tok':
            database.update_user_secret_token(uid)
            await query.edit_message_text("✅ تم تحديث رمز الأمان.", reply_markup=keyboards.get_back_home())
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date'))
            await query.edit_message_text(f"👤 بياناتك:\n🆔 ID: <code>{uid}</code>\n⏳ الانتهاء: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())

    # مسار الأدمن
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 لوحة التحكم\n👥 المستخدمين: {t}\n🎫 الأكواد: {c}", reply_markup=keyboards.get_admin_keyboard())
        elif data == 'adm_u':
            await query.edit_message_text("👥 إدارة المستخدمين:", reply_markup=keyboards.get_users_management_keyboard(database.get_all_users()))
        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 اختر مدة الكود:", reply_markup=keyboards.get_generation_menu())
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            code = f"SMO-{secrets.token_hex(3).upper()}"
            database.add_subscription_code(code, days)
            await query.message.reply_text(f"✅ كود جديد ({days} يوم):\n<code>{code}</code>", parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # استلام القناة المختارة
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "قناة جديدة")
        await update.message.reply_text("✅ تم الربط بنجاح!", reply_markup=ReplyKeyboardRemove())
        await back_to_main_menu(update, context, uid)
        return

    # استلام كود التفعيل
    if context.user_data.get('awaiting_code'):
        days = database.check_and_use_code(update.message.text.strip())
        if days:
            database.activate_user_subscription(uid, days)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(f"🎉 تم التفعيل لـ {days} يوم!")
            await back_to_main_menu(update, context, uid)
        else:
            await update.message.reply_text("❌ الكود خاطئ.")

# --- 4. دالة التشغيل الرئيسية ---
async def main():
    database.init_db()
    # تشغيل سيرفر استقبال الإشارات
    asyncio.create_task(web_server.start_server())
    
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    
    logger.info("🚀 المنظومة تعمل الآن على Render...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
