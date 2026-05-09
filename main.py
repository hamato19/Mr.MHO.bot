import logging, asyncio, secrets, os, re
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy
import activation_handler
# إعدادات المراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. الدالة المساعدة للتنظيف الذكي ---
async def clear_temp_messages(context, uid):
    """حذف كافة الرسائل والملفات المؤقتة المخزنة في ذاكرة الجلسة"""
    if 'temp_msg_ids' in context.user_data:
        for msg_id in context.user_data['temp_msg_ids']:
            try:
                await context.bot.delete_message(chat_id=uid, message_id=msg_id)
            except Exception:
                pass
        context.user_data['temp_msg_ids'] = []

async def clean_and_show_menu(update_or_query, context, uid):
    """عرض القائمة الرئيسية مع تنظيف شامل"""
    await clear_temp_messages(context, uid)
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

# --- 2. المعالجات (Handlers) ---
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
    
    # 🛑 التنظيف الذكي لكل الأزرار
    await clear_temp_messages(context, uid)
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []

    try: await query.answer()
    except: pass

    # 1. التنقل الأساسي
    if data == 'home':
        context.user_data.clear()
        await clean_and_show_menu(query, context, uid)
        return

    # 2. إدارة الاشتراك
    if data == 'ren':
        context.user_data['awaiting_code'] = True 
        sub_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 اشتراك الآن", url="https://sumoualarqam.com/")],
            [InlineKeyboardButton("🎫 ادخل كود التفعيل", callback_data='await_msg')],
            [InlineKeyboardButton("⬅️ رجوع", callback_data='home')]
        ])
        await query.edit_message_text("🔄 <b>تفعيل الاشتراك:</b>\nأرسل كود التفعيل هنا مباشرة.", parse_mode='HTML', reply_markup=sub_markup)
        return

    # 3. وظائف المشتركين (كاملة الأزرار)
    if is_owner or (user and user.get('is_activated')):
        if data == 'acc': # حسابي
            expiry = services.get_time_remaining(user.get('expiry_date')) if user else "دائم"
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الانتهاء: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            return

        elif data == 'wh': # الويب هوك (عرض الروابط)
            webhook_text = services.format_webhook_links(uid)
            msg = await context.bot.send_message(chat_id=uid, text=f"🌐 <b>روابط الويب هوك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return
            
        elif data == 'tok': # توليد رمز جديد
            # 1. فك تعليق الزر فوراً (ضروري جداً للاستجابة)
            await query.answer()
            
            # 2. العمليات البرمجية
            new_token = secrets.token_hex(8).upper()
            
            # ملاحظة: إذا كانت الدالة في database.py معرفة بـ async def أضف await هنا
            database.update_user_secret_token(uid, new_token)
            
            webhook_text = services.format_webhook_links(uid)
            
            # 3. إرسال الرسالة الجديدة
            msg = await context.bot.send_message(
                chat_id=uid, 
                text=f"🔐 <b>تم تحديث رمز الأمان!</b>\n\nالروابط الجديدة:\n<code>{webhook_text}</code>", 
                parse_mode='HTML'
            )
            
            # 4. إضافة المعرف للمصفوفة (تأكد من تعريفها أولاً)
            if 'temp_msg_ids' not in context.user_data:
                context.user_data['temp_msg_ids'] = []
            context.user_data['temp_msg_ids'].append(msg.message_id)
            
            return

        elif data == 'chs': # قنواتي
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>قنواتك المرتبطة:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
            return

        elif data == 'add_channel': # إضافة قناة
             await query.message.reply_text("📢 اضغط الزر أدناه لاختيار القناة:", reply_markup=keyboards.get_request_channel_keyboard())
             return

    # --- 4. لوحة الأدمن ---
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة الأدمن</b>\n\n👤 المستخدمين: {t}\n✅ المشتركين: {a}\n🎫 الأكواد: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            return

        elif data == 'adm_u':
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
            return

        # 👇 تضاف الإضافة المطورة هنا مباشرة 👇
     elif data.startswith('view_u_'):
            target_uid = int(data.split('_')[2]) 
            target_user = database.get_user_profile(target_uid) 
            
            if target_user:
                await clear_temp_messages(context, uid)
                status = "✅ مفعل" if target_user.get('is_activated') else "❌ غير مفعل"
                exp = services.get_time_remaining(target_user.get('expiry_date'))
                
                user_entities = database.get_user_entities(target_uid)
                channels_text = "\n".join([f"🔹 <code>{e['entity_id']}</code>" for e in user_entities]) if user_entities else "لا توجد قنوات."
                webhook_links = services.format_webhook_links(target_uid)

                text = (
                    f"👤 <b>تفاصيل المستخدم:</b>\n"
                    f"🆔 ID: <code>{target_uid}</code>\n"
                    f"👤 الاسم: {target_user.get('full_name')}\n"
                    f"📊 الحالة: {status}\n"
                    f"⏳ الصلاحية: {exp}\n\n"
                    f"📢 <b>القنوات:</b>\n{channels_text}\n\n"
                    f"🌐 <b>الويب هوك:</b>\n<code>{webhook_links}</code>"
                )
                await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboards.get_user_control_keyboard(target_uid))
            return

        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد أكواد:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
            return
            
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            code = f"SMO-{secrets.token_hex(4).upper()}"
            database.add_subscription_code(code, days)
            msg = await query.message.reply_text(f"✅ كود جديد ({days} يوم):\n<code>{code}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message and update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        await update.message.reply_text("✅ تم ربط القناة بنجاح!")
        await clean_and_show_menu(update, context, uid)
    elif update.message and update.message.text:
        text = update.message.text.strip()
        if text.upper().startswith("SMO-") or context.user_data.get('awaiting_code'):
            context.user_data['awaiting_code'] = False
            msg = await update.message.reply_text("⏳ جاري التفعيل...")
            success, res = activation_handler.process_activation(uid, text.upper())
            await msg.edit_text(f"{'🎉' if success else '❌'} {res}", parse_mode='HTML')
            if success: await clean_and_show_menu(update, context, uid)

# --- 3. تشغيل التطبيق (Render Fix) ---
async def main():
    database.init_db()
    await web_server.start_server()
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    
    logger.info("🚀 سمو الأرقام بدأ العمل بنجاح...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
