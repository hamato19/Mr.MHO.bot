import logging, asyncio, secrets, os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy

# إعدادات المراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def clean_and_show_menu(update_or_query, context, uid):
    """دالة التنظيف الذكي: تحديث الرسالة الحالية وحذف أي كيبورد سفلي"""
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    
    if not is_owner and (not user or not user.get('is_activated')):
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إدخال كود التفعيل:"
        markup = keyboards.get_subscription_options()

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else:
        try:
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

    # --- إدارة التنقل ---
    if data == 'home':
        context.user_data['awaiting_code'] = False
        await clean_and_show_menu(query, context, uid)
        return

    # --- الخصوصية والتفعيل ---
    if data == 'accept_tos':
        database.register_user_if_not_exists(uid)
        await query.edit_message_text("✅ تم قبول الشروط.\nيرجى اختيار وسيلة التفعيل:", reply_markup=keyboards.get_subscription_options())
        return
    
    if data == 'ren':
        await query.edit_message_text("🔄 <b>تجديد أو تفعيل الاشتراك:</b>\n\nاختر الاشتراك عبر الموقع أو أدخل الكود مباشرة:", 
                                      parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
        context.user_data['awaiting_code'] = True 
        return

    # --- لوحة الأدمن ---
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة الأدمن</b>\n\n👤 المستخدمين: {t}\n✅ المشتركين: {a}\n🎫 الأكواد: {c}", 
                                          parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        elif data == 'adm_u':
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد أكواد:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            code = f"SMO-{secrets.token_hex(3).upper()}"
            database.add_subscription_code(code, days)
            await query.edit_message_text(f"✅ <b>تم توليد كود جديد:</b>\n\nالمدة: {days} يوم\nالكود: <code>{code}</code>", 
                                          parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        elif data.startswith('view_u_'):
            target_id = data.replace('view_u_', '')
            u_details = database.get_user_profile(target_id)
            await query.edit_message_text(f"👤 <b>إدارة المستخدم:</b> <code>{target_id}</code>\nالحالة: {'نشط ✅' if u_details['is_activated'] else 'معطل ❌'}", 
                                          parse_mode='HTML', reply_markup=keyboards.get_user_control_keyboard(target_id, u_details['is_activated']))
        if data in ['adm', 'adm_u', 'adm_gen_menu'] or data.startswith(('gen_', 'view_u_', 'toggle_u_')): return

    # --- العمليات الأساسية للمشتركين ---
    if is_owner or (user and user.get('is_activated')):
        # 1. إضافة قناة (رسالة جديدة لطلب الكيبورد)
        if data == 'add_channel':
            await query.message.reply_text("📢 اضغط على الزر أدناه لاختيار القناة لربطها  عبر الـ ID:", 
                                           reply_markup=keyboards.get_request_channel_keyboard())
            try: await query.delete_message()
            except: pass

        # 2. عرض قنواتي (تعديل الرسالة الحالية)
        elif data == 'chs':
            ents = database.get_user_entities(uid)
            await query.edit_message_text(
                "📋 <b>قنواتك المرتبطة (ID):</b>\n\nيتم الربط بالمعرف الرقمي لثبات الخدمة.",
                parse_mode='HTML', 
                reply_markup=keyboards.get_entities_keyboard(ents)
            )

        # 3. بقية الأزرار (ويب هوك، توكن، حسابي)
        elif data == 'wh':
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n<code>{webhook_text}</code>", 
                                          parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'tok':
            database.update_user_secret_token(uid)
            await query.edit_message_text("🔄 <b>تم تحديث رمز الأمان بنجاح!</b>", 
                                          parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date'))
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الصلاحية: {expiry}", 
                                          parse_mode='HTML', reply_markup=keyboards.get_back_home())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        await update.message.reply_text("✅ تم ربط القناة بنجاح!", reply_markup=ReplyKeyboardRemove())
        await clean_and_show_menu(update, context, uid)
        return
    if context.user_data.get('awaiting_code'):
        days = database.check_and_use_code(update.message.text.strip())
        if days:
            database.activate_user_subscription(uid, days)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(f"🎉 تم التفعيل لـ {days} يوم!")
            await clean_and_show_menu(update, context, uid)
        else:
            await update.message.reply_text("❌ كود خاطئ. حاول مرة أخرى.")

async def main():
    database.init_db()
    asyncio.create_task(web_server.start_server())
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    logger.info("🚀 سمو الأرقام تعمل الآن...")
    await app.initialize(); await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
