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
    temp_ids = context.user_data.get('temp_msg_ids', [])
    if temp_ids:
        context.user_data['temp_msg_ids'] = []
        for msg_id in temp_ids:
            try:
                await context.bot.delete_message(chat_id=uid, message_id=msg_id)
            except Exception:
                pass

async def clean_and_show_menu(update_or_query, context, uid):
    """عرض القائمة الرئيسية مع تنظيف شامل لرسائل الـ txt"""
    await clear_temp_messages(context, uid)
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    # التحقق من وجود المستخدم (نظام الخصوصية)
    if not user:
        text = privacy_policy.DISCLAIMER_TEXT
        markup = keyboards.get_disclaimer_keyboard()
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
        else:
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        return

    # إعداد القائمة بناءً على حالة التفعيل
    text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    
    # إذا لم يكن أدمن وغير مفعل، تظهر خيارات الاشتراك فقط
    if not is_owner and not user.get('is_activated'):
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إدخال كود التفعيل للوصول للخدمات:"
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
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
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

    # 1. نظام الخصوصية (الموافقة) - متوافق مع accept_tos في ملف الكيبورد
    if data == 'accept_tos':
        database.register_user(uid, update.effective_user.full_name)
        await clean_and_show_menu(query, context, uid)
        return
    elif data == 'reject_tos':
        await query.edit_message_text("❌ يجب الموافقة على الشروط لاستخدام البوت. أرسل /start مجدداً للموافقة.")
        return

    # 2. التنقل والعودة
    if data == 'home':
        await clean_and_show_menu(query, context, uid)
        return

    # 3. إدارة الاشتراك (متوافق مع ren في ملف الكيبورد)
    if data == 'ren':
        await clear_temp_messages(context, uid)
        context.user_data['awaiting_code'] = True 
        await query.edit_message_text("🔄 <b>نظام التفعيل:</b>\nيرجى إرسال كود التفعيل (SMO-xxxx) الآن.", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        return

    # 🔒 حماية الخدمات: لا تعمل إلا للمفعلين أو الأدمن
    if is_owner or (user and user.get('is_activated')):
        if data == 'acc': # حسابي
            await clear_temp_messages(context, uid)
            expiry = services.get_time_remaining(user.get('expiry_date')) if user and not is_owner else "دائم"
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الانتهاء: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            return

        elif data == 'wh': # الويب هوك
            webhook_text = services.format_webhook_links(uid)
            msg = await context.bot.send_message(chat_id=uid, text=f"🌐 <b>روابط الويب هوك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return
            
        elif data == 'tok': # توليد رمز جديد
            new_token = secrets.token_hex(8).upper()
            database.update_user_secret_token(uid, new_token)
            webhook_text = services.format_webhook_links(uid)
            msg = await context.bot.send_message(chat_id=uid, text=f"🔐 <b>تم تحديث رمز الأمان!</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return

        elif data == 'chs': # قنواتي
            await clear_temp_messages(context, uid)
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>قنواتك المرتبطة:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
            return

        elif data == 'add_channel': # إضافة قناة
             msg = await query.message.reply_text("📢 اضغط الزر أدناه لاختيار القناة:", reply_markup=keyboards.get_request_channel_keyboard())
             context.user_data['temp_msg_ids'].append(msg.message_id)
             return

    # 4. لوحة الأدمن (متوافقة مع adm و adm_u و gen_ في ملف الكيبورد)
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة الأدمن</b>\n👤 المستخدمين: {t} | ✅ المشتركين: {a}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            return
        
        elif data == 'adm_u':
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
            return

        elif data.startswith('view_u_'):
            t_uid = data.split('_')[2]
            u = database.get_user_profile(t_uid)
            if u:
                status = "✅ مفعل" if u.get('is_activated') else "❌ غير مفعل"
                await query.edit_message_text(f"👤 مستخدم: <code>{t_uid}</code>\nالحالة: {status}", parse_mode='HTML', reply_markup=keyboards.get_user_control_keyboard(t_uid, u.get('is_activated')))
            return

        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد أكواد جديدة:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
            return

        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            code = f"SMO-{secrets.token_hex(4).upper()}"
            database.add_subscription_code(code, days)
            msg = await query.message.reply_text(f"✅ كود {days} يوم:\n<code>{code}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
    
    # زر إلغاء العودة للقائمة (من الكيبورد الريبلاي)
    if update.message.text == "🔙 إلغاء والعودة للقائمة":
        await clean_and_show_menu(update, context, uid)
        return

    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        m = await update.message.reply_text("✅ تم ربط القناة بنجاح!", reply_markup=ReplyKeyboardRemove())
        await asyncio.sleep(2)
        await clean_and_show_menu(update, context, uid)

    elif update.message.text:
        text = update.message.text.strip()
        context.user_data['temp_msg_ids'].append(update.message.message_id)
        if text.upper().startswith("SMO-") or context.user_data.get('awaiting_code'):
            context.user_data['awaiting_code'] = False
            s_msg = await update.message.reply_text("⏳ جاري التحقق...")
            success, res = activation_handler.process_activation(uid, text.upper())
            await s_msg.edit_text(f"{'🎉' if success else '❌'} {res}", parse_mode='HTML')
            if success:
                await asyncio.sleep(2)
                await clean_and_show_menu(update, context, uid)
            else:
                context.user_data['temp_msg_ids'].append(s_msg.message_id)

async def main():
    database.init_db()
    await web_server.start_server()
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try: asyncio.run(main())
    except: pass
