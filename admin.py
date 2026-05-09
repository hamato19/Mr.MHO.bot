import logging, asyncio, secrets, os, re
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy
import activation_handler

# إعدادات المراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. نظام التنظيف الصارم ---
async def clear_temp_messages(context, uid):
    """حذف كافة الرسائل المسجلة في ذاكرة الجلسة فوراً لتنظيف الشاشة"""
    if 'temp_msg_ids' in context.user_data:
        temp_ids = context.user_data['temp_msg_ids']
        if temp_ids:
            ids_to_delete = list(temp_ids)
            context.user_data['temp_msg_ids'] = []
            for msg_id in ids_to_delete:
                try:
                    await context.bot.delete_message(chat_id=uid, message_id=msg_id)
                except Exception:
                    pass

async def clean_and_show_menu(update_or_query, context, uid):
    """تنظيف النصوص الزائدة ثم عرض القائمة المناسبة لحالة المستخدم"""
    await clear_temp_messages(context, uid)
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    # 1. نظام الخصوصية للمستخدم الجديد تماماً
    if not user:
        text = privacy_policy.DISCLAIMER_TEXT
        markup = keyboards.get_disclaimer_keyboard()
    else:
        # 2. التحقق من حالة التفعيل للمستخدم العادي
        if not is_owner and not user.get('is_activated'):
            text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إدخال كود التفعيل للوصول للخدمات:"
            markup = keyboards.get_subscription_options()
        else:
            # 3. القائمة الرئيسية للمفعلين والأدمن
            text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
            markup = await keyboards.get_main_menu(uid, bot_info.username)

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
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
    # إضافة رسالة الـ /start للتنظيف لاحقاً
    context.user_data['temp_msg_ids'].append(update.message.message_id)
    await clean_and_show_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    try: await query.answer()
    except: pass

    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []

    # --- أزرار الخصوصية والتنقل الأساسي ---
    if data == 'accept_tos':
        database.register_user(uid, update.effective_user.full_name)
        await clean_and_show_menu(query, context, uid)
        return
    elif data == 'home':
        await clean_and_show_menu(query, context, uid)
        return
    elif data == 'ren': # زر "ادخل كود التفعيل"
        await clear_temp_messages(context, uid)
        context.user_data['awaiting_code'] = True 
        await query.edit_message_text("🔄 <b>نظام التفعيل:</b>\nيرجى إرسال كود التفعيل (SMO-xxxx) الآن.", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        return

    # --- خدمات المشتركين (محمية بالشرط) ---
    if is_owner or (user and user.get('is_activated')):
        if data == 'wh': # روابط الويب هوك
            webhook_text = services.format_webhook_links(uid)
            msg = await context.bot.send_message(chat_id=uid, text=f"🌐 <b>روابط الويب هوك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return
            
        elif data == 'tok': # تحديث رمز الأمان
            new_token = secrets.token_hex(8).upper()
            database.update_user_secret_token(uid, new_token)
            webhook_text = services.format_webhook_links(uid)
            msg = await context.bot.send_message(chat_id=uid, text=f"🔐 <b>تم تحديث الرمز بنجاح!</b>\nالروابط الجديدة:\n<code>{webhook_text}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return

        elif data == 'chs': # عرض القنوات
            await clear_temp_messages(context, uid)
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>قنواتك المرتبطة:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
            return

        elif data == 'add_channel': # زر إضافة قناة
             msg = await query.message.reply_text("📢 اضغط الزر بالأسفل لاختيار القناة المراد ربطها:", reply_markup=keyboards.get_request_channel_keyboard())
             context.user_data['temp_msg_ids'].append(msg.message_id)
             return
             
        elif data == 'acc': # حسابي
            await clear_temp_messages(context, uid)
            exp = services.get_time_remaining(user.get('expiry_date')) if user and not is_owner else "دائم"
            await query.edit_message_text(f"👤 <b>بيانات الحساب:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الصلاحية: {exp}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            return

    # --- لوحة الأدمن ---
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة الإدارة:</b>\n👤 المستخدمين: {t}\n✅ المشتركين: {a}\n🎫 الأكواد: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            return
        elif data == 'adm_u':
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
            return
        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد أكواد جديدة:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
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
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
    
    if update.message:
        context.user_data['temp_msg_ids'].append(update.message.message_id)

    # معالجة الأزرار النصية (ReplyKeyboard)
    if update.message.text == "🔙 إلغاء والعودة للقائمة":
        await clean_and_show_menu(update, context, uid)
        return

    # استلام القناة بعد اختيارها
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        m = await update.message.reply_text("✅ تم الربط بنجاح!", reply_markup=ReplyKeyboardRemove())
        context.user_data['temp_msg_ids'].append(m.message_id)
        await asyncio.sleep(1)
        await clean_and_show_menu(update, context, uid)
        return

    # معالجة أكواد التفعيل SMO-
    if update.message.text:
        text = update.message.text.strip()
        if text.upper().startswith("SMO-") or context.user_data.get('awaiting_code'):
            context.user_data['awaiting_code'] = False
            s_msg = await update.message.reply_text("⏳ جاري التفعيل...")
            context.user_data['temp_msg_ids'].append(s_msg.message_id)
            
            success, res = activation_handler.process_activation(uid, text.upper())
            await s_msg.edit_text(f"{'🎉' if success else '❌'} {res}", parse_mode='HTML')
            if success:
                await asyncio.sleep(2)
                await clean_and_show_menu(update, context, uid)

async def main():
    database.init_db()
    await web_server.start_server()
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    logger.info("🚀 سمو الأرقام انطلق بنجاح...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): pass
