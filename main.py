import logging, asyncio, secrets, os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy

# إعدادات التسجيل والمراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def clean_and_show_menu(update_or_query, context, uid):
    """دالة تنظيف المحادثة وعرض القائمة الرئيسية بسلاسة"""
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    
    # حماية: إذا لم يكن مفعل أو أدمن يوجه للتفعيل
    if not is_owner and (not user or not user.get('is_activated')):
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إدخال كود التفعيل:"
        markup = keyboards.get_subscription_options()

    if isinstance(update_or_query, Update):
        # في حال كان أمراً نصياً مثل /start
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else:
        # في حال كان ضغط زر، نقوم بتعديل الرسالة نفسها لتوفير سرعة الاستجابة
        try:
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except:
            # في حال فشل التعديل (رسالة قديمة)، نرسل رسالة جديدة
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
    
    # استجابة سريعة للضغط
    try: await query.answer()
    except: pass

    # --- 1. بوابات الدخول والخصوصية ---
    if data == 'accept_tos':
        database.register_user_if_not_exists(uid)
        await query.edit_message_text("✅ تم قبول الشروط.\nيرجى اختيار وسيلة التفعيل المناسبة:", reply_markup=keyboards.get_subscription_options())
        return
    elif data == 'reject_tos':
        await query.edit_message_text("⚠️ نعتذر، لا يمكن الاستخدام دون موافقة. اضغط /start للمحاولة.")
        return
    elif data == 'view_priv':
        await query.edit_message_text(privacy_policy.PRIVACY_TEXT, parse_mode='HTML', reply_markup=keyboards.get_back_home())
        return

    # --- 2. إدارة التفعيل والعودة (التنظيف الشامل) ---
    if data == 'home':
        await clean_and_show_menu(query, context, uid)
        return
        
    if data == 'ren':
        await query.edit_message_text(
            "🔄 <b>تجديد أو تفعيل الاشتراك</b>\n\nيمكنك الاشتراك عبر الموقع أو إدخال الكود مباشرة:",
            parse_mode='HTML', reply_markup=keyboards.get_subscription_options()
        )
        context.user_data['awaiting_code'] = True 
        return

    # --- 3. لوحة الأدمن (تطابق كامل مع Keyboards.py) ---
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(
                f"👮 <b>لوحة التحكم بالإدارة</b>\n\n👤 المستخدمين: {t}\n✅ المشتركين: {a}\n🎫 الأكواد: {c}",
                parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        elif data == 'adm_u':
            # ميزة إدارة المستخدمين (اختياري: يمكنك ربطها بقائمة)
            await query.answer("جاري جلب القائمة...")
        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد أكود:</b>\nاختر مدة الصلاحية:", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            code = f"SMO-{secrets.token_hex(3).upper()}"
            database.add_subscription_code(code, days)
            await query.message.reply_text(f"✅ <b>تم توليد كود جديد:</b>\n\nالمدة: {days} يوم\nالكود: <code>{code}</code>", parse_mode='HTML')
        if data in ['adm', 'adm_u', 'adm_gen_menu'] or data.startswith('gen_'): return

    # --- 4. أوامر العمليات (للمفعلين والأدمن) ---
    if is_owner or (user and user.get('is_activated')):
        if data == 'add_channel':
            await query.message.reply_text("📢 اختر القناة لربطها فوراً:", reply_markup=keyboards.get_request_channel_keyboard())
        elif data == 'chs':
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 قنواتك المرتبطة بالمنظومة:", reply_markup=keyboards.get_entities_keyboard(ents))
        elif data == 'wh':
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'tok':
            database.update_user_secret_token(uid)
            await query.edit_message_text("🔄 تم تحديث رمز الأمان وإبطال الرموز السابقة.", reply_markup=keyboards.get_back_home())
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date'))
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الصلاحية: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # استلام القناة (تنظيف الكيبورد النصي بعد الاختيار)
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "قناة تداول")
        await update.message.reply_text("✅ تم ربط القناة بنجاح!", reply_markup=ReplyKeyboardRemove())
        await clean_and_show_menu(update, context, uid)
        return

    # استلام الكود
    if context.user_data.get('awaiting_code'):
        days = database.check_and_use_code(update.message.text.strip())
        if days:
            database.activate_user_subscription(uid, days)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(f"🎉 تم تفعيل الاشتراك لـ {days} يوم!")
            await clean_and_show_menu(update, context, uid)
        else:
            await update.message.reply_text("❌ الكود خاطئ. حاول مرة أخرى أو اضغط عودة.")

async def main():
    database.init_db()
    asyncio.create_task(web_server.start_server())
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    
    logger.info("🚀 المنظومة تعمل الآن بأقصى سرعة...")
    await app.initialize(); await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
