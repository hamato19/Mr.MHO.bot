import logging, asyncio, secrets, os, re
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy
import activation_handler

# إعدادات المراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. نظام التنظيف الذكي وحماية الواجهة ---
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
    """عرض القائمة الرئيسية مع تنظيف شامل لضمان ثبات الواجهة"""
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
        sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
        if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
        context.user_data['temp_msg_ids'].append(sent_msg.message_id)
    else:
        try:
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except:
            sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
            if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
            context.user_data['temp_msg_ids'].append(sent_msg.message_id)

# --- 2. معالج الرسائل والـ Web App (نظام التفعيل الصامت) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
    
    # استقبال بيانات التفعيل من الـ Web App (Iframe)
    if update.message.web_app_data:
        code = update.message.web_app_data.data.strip().upper()
        success, res = activation_handler.process_activation(uid, code)
        msg = await update.message.reply_text(f"{'🎉' if success else '❌'} {res}", parse_mode='HTML')
        await asyncio.sleep(2)
        try: await update.message.delete()
        except: pass
        await clean_and_show_menu(update, context, uid)
        return

    # استقبال الرسائل النصية العادية (تنظيف تلقائي)
    if update.message:
        context.user_data['temp_msg_ids'].append(update.message.message_id)
        
        # التعامل مع ربط القنوات
        if update.message.chat_shared:
            database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
            await clean_and_show_menu(update, context, uid)
            return

        # معالجة يدوية للأكواد
        text = update.message.text.strip().upper() if update.message.text else ""
        if text.startswith("SMO-"):
            success, res = activation_handler.process_activation(uid, text)
            msg = await update.message.reply_text(f"{'🎉' if success else '❌'} {res}", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            await asyncio.sleep(2)
            await clean_and_show_menu(update, context, uid)

# --- 3. معالج الأزرار التفاعلية (Callbacks) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []

    try: await query.answer()
    except: pass

    # القائمة الرئيسية
    if data == 'home':
        await clean_and_show_menu(query, context, uid)
        return

    # تجديد الاشتراك
    if data == 'ren':
        await query.edit_message_text("🔄 <b>تفعيل الاشتراك:</b>\nاختر وسيلة التفعيل أدناه:", parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
        return

    # نظام الحماية: التحقق من الاشتراك قبل تنفيذ الوظائف
    if is_owner or (user and user.get('is_activated')):
        if data == 'acc': # حسابي
            expiry = services.get_time_remaining(user.get('expiry_date')) if user and not is_owner else "دائم"
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ الانتهاء: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        
        elif data == 'wh': # الويب هوك
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            
        elif data == 'tok': # توليد رمز جديد
            new_token = secrets.token_hex(8).upper()
            database.update_user_secret_token(uid, new_token)
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🔐 <b>تم تحديث الرمز بنجاح!</b>\n\nروابطك الجديدة:\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())

        elif data == 'chs': # القنوات
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>قنواتك المرتبطة:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))

        elif data == 'add_channel': # إضافة قناة
             await query.edit_message_text("📢 اضغط الزر أدناه لاختيار القناة المراد ربطها:", reply_markup=keyboards.get_request_channel_keyboard())

    # --- لوحة الأدمن (إصلاح زر توليد الأكواد) ---
    if is_owner:
        if data == 'adm': # المنيو الرئيسي للأدمن
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة التحكم:</b>\n👤 المستخدمين: {t}\n✅ المشتركين: {a}\n🎫 الأكواد: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        
        elif data == 'adm_gen_menu': # منيو توليد الأكواد
            await query.edit_message_text("🔑 <b>توليد أكواد اشتراك:</b>\nاختر المدة المطلوبة:", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
            
        elif data.startswith('gen_'): # تنفيذ التوليد
            days = int(data.split('_')[1])
            code = f"SMO-{secrets.token_hex(4).upper()}"
            database.add_subscription_code(code, days)
            await query.edit_message_text(f"✅ <b>تم إنشاء كود بنجاح:</b>\n\nالمدة: {days} يوم\nالكود: <code>{code}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())

# --- 4. تشغيل النظام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await clear_temp_messages(context, uid)
    user = database.get_user_profile(uid)
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
    else:
        await clean_and_show_menu(update, context, uid)

async def main():
    database.init_db() # قاعدة البيانات
    await web_server.start_server() # نظام الويب هوك
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    logger.info("🚀 سمو الأرقام يعمل بكامل طاقته ونظام الحماية مفعل.")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try: asyncio.run(main())
    except: pass
