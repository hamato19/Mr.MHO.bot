import logging, asyncio, secrets
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, privacy_policy

# ... (إعدادات الـ logging كما هي)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    try: await query.answer()
    except: pass

    # عند اختيار "إضافة قناة"
    if data == 'add_channel':
        # نرسل له كيبورد الأزرار الذي يحتوي على خاصية اختيار القناة
        await query.message.reply_text(
            "👇 اضغط على الزر أدناه ليفتح لك قائمة قنواتك، اختر القناة التي تريد ربطها بالمنظومة:",
            reply_markup=keyboards.get_request_channel_keyboard()
        )
        return

    # باقي الأزرار (أدمن، قنواتي، إلخ)
    elif data == 'adm':
        if is_owner:
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 لوحة التحكم\n👥 الكل: {t} | ✅ نشط: {a}\n🎫 أكواد: {c}", reply_markup=keyboards.get_admin_keyboard())
    
    elif data == 'chs':
        ents = database.get_user_entities(uid)
        await query.edit_message_text("📋 قنواتك المرتبطة بالمنظومة:", reply_markup=keyboards.get_entities_keyboard(ents))
    
    elif data == 'accept_tos':
        database.register_user_if_not_exists(uid)
        await query.edit_message_text("✅ تم قبول الشروط بنجاح. يرجى تفعيل اشتراكك الآن:", reply_markup=keyboards.get_subscription_options())

    elif data == 'reject_tos':
        await query.edit_message_text("⚠️ نعتذر، لا يمكنك استخدام البوت دون الموافقة على السياسة.")
        # هنا سيتوقف البوت حتى يعيد المستخدم ضغط /start

    # ... (بقية الـ callbacks كما هي)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # 1. فحص هل أرسل المستخدم قناة عبر خاصية "request_chat"
    if update.message.chat_shared:
        chat_id = update.message.chat_shared.chat_id
        # محاولة الحصول على اسم القناة (اختياري)
        try:
            chat_info = await context.bot.get_chat(chat_id)
            chat_name = chat_info.title
        except:
            chat_name = f"قناة ID: {chat_id}"
            
        # إضافة القناة لقاعدة البيانات
        if database.add_user_entity(uid, chat_id, chat_name):
            await update.message.reply_text(f"✅ تم ربط القناة <b>({chat_name})</b> بنجاح!", parse_mode='HTML', reply_markup=ReplyKeyboardRemove())
            # العودة للقائمة الرئيسية
            bot_info = await context.bot.get_me()
            await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=await keyboards.get_main_menu(uid, bot_info.username))
        return

    # 2. فحص كود التفعيل
    if context.user_data.get('awaiting_code'):
        code = update.message.text.strip()
        days = database.check_and_use_code(code)
        if days:
            database.activate_user_subscription(uid, days)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(f"🎉 مبارك! تم تفعيل اشتراكك لمدة {days} يوم.")
            bot_info = await context.bot.get_me()
            await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=await keyboards.get_main_menu(uid, bot_info.username))
        else:
            await update.message.reply_text("❌ الكود غير صحيح أو منتهي الصلاحية.")
        return

# ... (دالة main كما هي)
    # --- تابع handle_callback (تكملة معالجات الأدمن والمستخدم) ---
    elif data == 'acc':
        expiry = services.get_time_remaining(user.get('expiry_date'))
        await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ ينتهي في: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
    
    elif data == 'wh':
        await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
    
    elif data == 'tok':
        if database.update_user_secret_token(uid):
            await query.edit_message_text("✅ تم تحديث رمز الأمان بنجاح. تذكر تحديث الروابط في TradingView!", reply_markup=keyboards.get_back_home())
    
    elif data == 'home':
        await back_to_main_menu(query, context, uid)

    # --- معالجات لوحة الأدمن التفصيلية ---
    elif is_owner:
        if data == 'adm_u':
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>قائمة المستخدمين المسجلين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
        
        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد كود جديد - اختر المدة:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
        
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            new_code = f"SMO-{secrets.token_hex(3).upper()}"
            if database.add_subscription_code(new_code, days):
                await query.message.reply_text(f"✅ <b>تم توليد كود جديد:</b>\n\nالمدة: {days} يوم\nالكود: <code>{new_code}</code>", parse_mode='HTML')
        
        elif data.startswith('view_u_'):
            target_id = data.split('_')[2]
            u_details = database.get_user_details(target_id)
            await query.edit_message_text(f"👤 <b>إدارة المستخدم:</b> {target_id}\nالحالة: {'نشط ✅' if u_details['is_activated'] else 'غير نشط ❌'}", 
                                          reply_markup=keyboards.get_user_control_keyboard(target_id, u_details['is_activated']))
        
        elif data.startswith('toggle_u_'):
            parts = data.split('_')
            action, target_id = parts[2], parts[3]
            database.update_user_status(target_id, action == 'activate')
            await query.answer("✅ تم تحديث حالة المستخدم")
            users = database.get_all_users()
            await query.edit_message_text("👥 إدارة المستخدمين:", reply_markup=keyboards.get_users_management_keyboard(users))

# --- دالة البداية والتشغيل النهائي ---
async def main():
    # 1. تهيئة قاعدة البيانات عند الإقلاع
    database.init_db()
    logger.info("✅ تم فحص وتهيئة قاعدة البيانات.")

    # 2. تشغيل سيرفر الويب هوك (FastAPI/Flask) في الخلفية لاستقبال إشارات TradingView
    asyncio.create_task(web_server.start_server())
    logger.info("🌐 سيرفر الويب هوك يعمل الآن...")

    # 3. بناء تطبيق التليجرام
    app = Application.builder().token(config.BOT_TOKEN).build()

    # 4. إضافة المعالجات (Handlers)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # معالج الرسائل النصية + معالج استلام القنوات المشتركة
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))

    # 5. بدء العمل
    await app.initialize()
    await app.start()
    
    # حذف التحديثات المعلقة لتجنب تكرار الرسائل القديمة عند إعادة التشغيل
    await app.updater.start_polling(drop_pending_updates=True)
    
    logger.info("🚀 بوت سمو الأرقام يعمل بكامل طاقته...")
    
    # إبقاء البوت يعمل للأبد
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ تم إيقاف النظام.")
