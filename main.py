import logging, asyncio, secrets, os, re
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy
import activation_handler

# إعدادات المراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. نظام التنظيف ومنع تكرار القائمة ---
async def clear_temp_messages(context, uid):
    """حذف الرسائل المؤقتة لتنظيف المحادثة"""
    if 'temp_msg_ids' in context.user_data:
        for msg_id in context.user_data['temp_msg_ids']:
            try: await context.bot.delete_message(chat_id=uid, message_id=msg_id)
            except: pass
        context.user_data['temp_msg_ids'] = []

async def clean_and_show_menu(update_or_query, context, uid):
    """عرض القائمة الرئيسية بشكل ذكي يمنع التكرار"""
    await clear_temp_messages(context, uid)
    
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    is_active = user.get('is_activated') if user else False
    
    # تحديد النص بناءً على حالة الاشتراك
    if is_owner or is_active:
        text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
        markup = await keyboards.get_main_menu(uid, bot_info.username)
    else:
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إرسال كود التفعيل:"
        markup = keyboards.get_subscription_options()

    # التنفيذ: تعديل الرسالة إذا كان ضغط زر، وإرسال جديدة إذا كان أمر /start
    if isinstance(update_or_query, Update):
        sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
        context.user_data.setdefault('temp_msg_ids', []).append(sent_msg.message_id)
    else:
        try:
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except:
            sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
            context.user_data.setdefault('temp_msg_ids', []).append(sent_msg.message_id)

# --- 2. معالج الرسائل (تفعيل SMO، إذاعة، وربط قنوات) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    context.user_data.setdefault('temp_msg_ids', []).append(update.message.message_id)
    
    if update.message.text:
        text = update.message.text.strip()

        # زر الإلغاء
        if text == "🔙 إلغاء والعودة للقائمة":
            await update.message.reply_text("🔄 جاري العودة...", reply_markup=ReplyKeyboardRemove())
            await clean_and_show_menu(update, context, uid)
            return

        # نظام الإذاعة للأدمن
        if context.user_data.get('waiting_for_broadcast') and str(uid) == str(config.ADMIN_ID):
            all_users = database.get_all_user_ids()
            sent, failed = 0, 0
            progress = await update.message.reply_text(f"⏳ جاري الإرسال إلى {len(all_users)}...")
            for user_id in all_users:
                try:
                    await context.bot.copy_message(user_id, update.message.chat_id, update.message.message_id)
                    sent += 1
                except: failed += 1
            await progress.edit_text(f"✅ تم!\n🟢 نجح: {sent} | 🔴 فشل: {failed}")
            context.user_data['waiting_for_broadcast'] = False
            return

        # نظام تفعيل SMO
        if text.upper().startswith("SMO-"):
            checking = await update.message.reply_text("⏳ جاري التحقق...")
            success, res = activation_handler.process_activation(uid, text.upper())
            await checking.delete()
            msg = await update.message.reply_text(f"{'🎉' if success else '❌'} {res}", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            if success: 
                await asyncio.sleep(1.5)
                await clean_and_show_menu(update, context, uid)
            return

    # ربط القنوات
    if update.message.chat_shared:
        existing = database.get_user_entities(uid)
        if existing:
            await update.message.reply_text("⚠️ لديك قناة مرتبطة بالفعل. احذفها أولاً لتغييرها.")
            await clean_and_show_menu(update, context, uid)
        else:
            database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
            await update.message.reply_text("✅ تم ربط القناة بنجاح!")
            await clean_and_show_menu(update, context, uid)

# --- 3. معالج الأزرار (Callbacks) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    try: await query.answer()
    except: pass

    # الخصوصية والقبول
    if data == 'accept_tos':
        database.add_new_user(uid)
        if is_owner or (user and user.get('is_activated')):
            await clean_and_show_menu(query, context, uid)
        else:
            await query.message.reply_text("⚠️ حسابك غير مفعل، أرسل كود التفعيل.")
        return

    if data == 'home':
        await clean_and_show_menu(query, context, uid)
        return

    # إدارة الويب هوك والرموز
    if data == 'wh':
        webhook_text = services.format_webhook_links(uid)
        await query.edit_message_text(f"🌐 روابطك:\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())
    
    elif data == 'tok':
        new_token = secrets.token_hex(8).upper()
        database.update_user_secret_token(uid, new_token)
        await query.answer("🔐 تم تحديث الرمز!")
        await clean_and_show_menu(query, context, uid)

    # لوحة الإدارة
    if is_owner:
        if data == 'adm':
            stats = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 لوحة التحكم:\n👤 مستخدمين: {stats['total']}\n✅ نشطين: {stats['active']}", 
                                          parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        elif data == 'broadcast_prompt':
            await query.message.reply_text("📝 أرسل رسالة الإذاعة الآن:")
            context.user_data['waiting_for_broadcast'] = True

# --- 4. التشغيل الرئيسي ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    database.add_new_user(uid) # تسجيل تلقائي في القاعدة
    
    user = database.get_user_profile(uid)
    if not user: # لم يوافق على الخصوصية بعد
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
    else:
        await clean_and_show_menu(update, context, uid)

async def main():
    database.init_db()
    await web_server.start_server()
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    logger.info("🚀 سمو الأرقام يعمل الآن بنظام نظيف.")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try: asyncio.run(main())
    except: pass
