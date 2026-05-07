import logging
import asyncio
import secrets
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد ملفات المنظومة
import config
import database
import services
import keyboards 
import web_server
import privacy_policy
import security  

# ضبط السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- وظيفة موحدة للعودة للقائمة الرئيسية لضمان السرعة والترتيب ---
async def back_to_main_menu(update_or_query, context, uid):
    bot_info = await context.bot.get_me()
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    text = "🏠 <b>القائمة الرئيسية للمنظومة:</b>"
    
    if isinstance(update_or_query, Update): # إذا كان الاستدعاء من رسالة
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else: # إذا كان الاستدعاء من زر (CallbackQuery)
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)

# --- 1. الدالة الرئيسية /start ---
@security.rate_limit(seconds=1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # 🛡️ التحقق من الحظر (security.py)
    blocked, hours_left, level = security.is_user_blocked(uid)
    if blocked:
        msg = f"🔒 حسابك محظور مؤقتاً. المتبقي: {hours_left} ساعة." if level < 3 else "🚫 تم حظرك نهائياً لمخالفة الأنظمة."
        await update.message.reply_text(msg)
        return

    user = database.get_user_profile(uid)
    
    # فحص سياسة الخصوصية
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        return

    # فحص التفعيل (المالك مستثنى)
    if not (int(uid) == int(config.ADMIN_ID)) and not user.get('is_activated'):
        await update.message.reply_text("⚠️ <b>الحساب غير نشط</b>\nيرجى إرسال كود التفعيل للوصول للخدمات:", parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
        context.user_data['awaiting_code'] = True
        return

    await back_to_main_menu(update, context, uid)

# --- 2. معالج الأزرار الشامل (تفعيل كافة أزرار keyboards.py) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (int(uid) == int(config.ADMIN_ID))
    
    try: await query.answer()
    except: pass

    # 🛡️ حماية فورية للأزرار
    blocked, _, _ = security.is_user_blocked(uid)
    if blocked: return

    # 🔓 معالجة أزرار التأسيس (الخصوصية والقبول)
    if data in ['view_priv', 'back_tos', 'accept_tos', 'reject_tos']:
        if data == 'view_priv':
            await query.edit_message_text(privacy_policy.PRIVACY_TEXT, parse_mode='HTML', reply_markup=keyboards.get_back_to_tos())
        elif data == 'back_tos':
            await query.edit_message_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        elif data == 'accept_tos':
            database.register_user_if_not_exists(uid)
            await query.edit_message_text("✅ تم قبول الشروط. أرسل كود التفعيل الآن:", reply_markup=keyboards.get_subscription_options())
            context.user_data['awaiting_code'] = True
        elif data == 'reject_tos':
            await query.edit_message_text("❌ نأسف، لا يمكن استخدام المنظومة دون الموافقة على السياسة.")
        return

    # جلب بيانات المستخدم للفحص
    user = database.get_user_profile(uid)
    is_activated = user.get('is_activated') if user else False

    # منع الدخول إذا لم يكن مفعلاً أو مالكاً
    if not is_owner and not is_activated:
        await query.answer("⚠️ الاشتراك غير نشط!", show_alert=True)
        return

    # --- تنفيذ أوامر الأزرار المقترنة بالقائمة ---
    if data == 'home':
        await back_to_main_menu(query, context, uid)

    elif data == 'acc': # زر حسابي
        status = "✅ مفعل" if is_activated else "❌ غير مفعل (أدمن)"
        expiry = services.get_time_remaining(user.get('expiry_date')) if user else "غير محدود"
        await query.edit_message_text(f"👤 <b>بيانات الحساب:</b>\n\n🆔 معرفك: <code>{uid}</code>\n🚦 الحالة: {status}\n⏳ المتبقي: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'ren': # تجديد الاشتراك
        await query.edit_message_text("🎫 يرجى إرسال كود التفعيل الجديد:", reply_markup=keyboards.get_back_home())
        context.user_data['awaiting_code'] = True

    elif data == 'wh': # روابط الويب هوك
        await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'tok': # تحديث رمز الأمان
        new_tok = secrets.token_hex(16)
        if database.update_user_token(uid, new_tok):
            await query.answer("✅ تم تحديث رمز الأمان بنجاح", show_alert=True)
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'add_channel': # زر إضافة قناة
        await query.message.reply_text("📢 قم باختيار القناة المراد ربطها:", reply_markup=keyboards.get_request_channel_keyboard())

    elif data == 'chs': # عرض القنوات للحذف
        ents = database.get_user_entities(uid)
        await query.edit_message_text("📋 <b>إدارة القنوات المرتبطة:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))

    elif data.startswith('d_'): # حذف قناة معينة
        if database.delete_entity(uid, data.split('_')[1]):
            await query.answer("✅ تم حذف القناة")
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 القنوات المتبقية:", reply_markup=keyboards.get_entities_keyboard(ents))

    #     # --- لوحة التحكم للمالك (تفعيل كامل لجميع الأزرار) ---
    elif is_owner:
        # 1. القائمة الرئيسية للوحة التحكم
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(
                f"👮 <b>لوحة التحكم للمالك</b>\n\n"
                f"👥 إجمالي المستخدمين: {t}\n"
                f"✅ المشتركين النشطين: {a}\n"
                f"🎫 أكواد لم تُفعل: {c}", 
                parse_mode='HTML', 
                reply_markup=keyboards.get_admin_keyboard()
            )
        
        # 2. زر إدارة المستخدمين (تمت إضافته)
   elif data == 'adm_u':
            users = database.get_all_users() # جلب القائمة من قاعدة البيانات
            if not users:
                await query.answer("📋 لا يوجد مستخدمين مسجلين حالياً.", show_alert=True)
            else:
                await query.edit_message_text(
                    "👥 <b>إدارة المستخدمين:</b>\nاختر مستخدماً لعرض بياناته أو إدارته:",
                    parse_mode='HTML',
                    reply_markup=keyboards.get_users_management_keyboard(users)
                )

        # 3. زر الإحصائيات التفصيلية (تمت إضافته)
     elif data == 'adm_s':
            t, a, c = database.get_admin_dashboard_stats()
            # يمكنك هنا عرض تفاصيل أكثر مثل (المحظورين، اشتراكات منتهية، إلخ)
            stats_text = (
                "📊 <b>إحصائيات المنظومة الشاملة:</b>\n\n"
                f"• عدد المستخدمين: {t}\n"
                f"• الاشتراكات النشطة: {a}\n"
                f"• الأكواد المتوفرة: {c}\n"
                f"• حالة الخادم: متصل ✅"
            )
            await query.edit_message_text(stats_text, parse_mode='HTML', reply_markup=keyboards.get_back_to_admin())

        # 4. قائمة توليد الأكواد
        elif data == 'adm_gen_menu':
            await query.edit_message_text(
                "🗓️ <b>توليد كود اشتراك جديد:</b>\nاختر المدة المطلوبة:", 
                parse_mode='HTML', 
                reply_markup=keyboards.get_generation_menu()
            )
            
        # 5. معالج توليد الكود التلقائي (عند اختيار المدة)
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            new_code = f"SMO-{secrets.token_hex(4).upper()}"
            if database.add_subscription_code(new_code, days):
                # إرسال الكود للمالك في رسالة مستقلة ليسهل نسخها ونشرها
                await query.message.reply_text(
                    f"🎫 <b>تم إنشاء كود جديد بنجاح:</b>\n\n"
                    f"<code>{new_code}</code>\n"
                    f"📅 الصلاحية: {days} يوم", 
                    parse_mode='HTML'
                )
                # تحديث لوحة الأدمن لتعكس التغيير في عدد الأكواد
                t, a, c = database.get_admin_dashboard_stats()
                await query.edit_message_text(
                    f"👮 <b>لوحة المالك</b>\n✅ تم التوليد بنجاح.\n🎫 الأكواد المتوفرة حالياً: {c}", 
                    parse_mode='HTML',
                    reply_markup=keyboards.get_admin_keyboard()
                )

    

# --- 3. معالجة الرسائل وربط نظام الحماية (Security) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    uid = update.effective_user.id
    text = update.message.text

    if text == "🔙 إلغاء":
        context.user_data['awaiting_code'] = False
        await back_to_main_menu(update, context, uid)
        return
        
    # 🛡️ إرسال الكود للفحص الأمني الصارم
    if context.user_data.get('awaiting_code'):
        # دالة الفحص في security.py تتولى التفعيل أو الحظر تلقائياً
        is_success = await security.process_security_check(update, context, uid, text)
        if is_success:
            context.user_data['awaiting_code'] = False
            # عند النجاح، يظهر المنيو الرئيسي تلقائياً
            await asyncio.sleep(1) # تأخير بسيط لجمالية الظهور
            await back_to_main_menu(update, context, uid)
        return

# --- 4. معالجة ربط القنوات ---
async def handle_chat_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_shared:
        uid = update.effective_user.id
        cid = update.message.chat_shared.chat_id
        try:
            chat = await context.bot.get_chat(cid)
            if database.add_entity(uid, str(cid), chat.title):
                await update.message.reply_text(f"✅ تم ربط القناة: <b>{chat.title}</b>", parse_mode='HTML', reply_markup=ReplyKeyboardRemove())
                await back_to_main_menu(update, context, uid)
        except Exception as e:
            logger.error(f"Error in chat_shared: {e}")
            await update.message.reply_text("❌ خطأ: تأكد أن البوت مشرف في القناة وبكامل الصلاحيات.")

# --- 5. الإقلاع والتشغيل المستقر ---
async def main():
    database.init_db()
    # استخدام معالجة متوازية لضمان عدم تأخر الأزرار
    app = Application.builder().token(config.BOT_TOKEN).concurrent_updates(True).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_chat_shared))
    
    # تشغيل المهام الجانبية (سيرفر الويب والبقاء حياً)
    asyncio.create_task(web_server.start_server())
    asyncio.create_task(services.keep_alive())
    
    logger.info("🚀 المنظومة انطلقت بكامل طاقتها...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
