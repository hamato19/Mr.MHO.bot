import logging, asyncio, secrets, os, re
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy
import activation_handler

# إعدادات المراقبة المتقدمة لكشف التكرار
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. نظام التنظيف والتحكم الذكي ---
async def clear_temp_messages(context, uid):
    """حذف الرسائل المؤقتة لتنظيف المحادثة ومنع التراكم"""
    if 'temp_msg_ids' in context.user_data:
        ids = list(set(context.user_data['temp_msg_ids']))
        for msg_id in ids:
            try: await context.bot.delete_message(chat_id=uid, message_id=msg_id)
            except: pass
        context.user_data['temp_msg_ids'] = []

async def clean_and_show_menu(update_or_query, context, uid):
    """عرض القائمة الرئيسية مع استعادة كافة البيانات والتحققات"""
    # نظام منع التكرار الزمني (1 ثانية)
    now = datetime.now().timestamp()
    if now - context.user_data.get('last_menu_ts', 0) < 1.0:
        return
    context.user_data['last_menu_ts'] = now

    await clear_temp_messages(context, uid)
    
    # استرجاع التحقق من الملف الشخصي والحالة
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    is_active = user.get('is_activated') if user else False
    
    if is_owner or is_active:
        text = (
            f"🏠 <b>نظام سمو الأرقام - القائمة الرئيسية</b>\n\n"
            f"👤 <b>الحالة:</b> {'المدير العام 🛠️' if is_owner else 'مشترك نشط ✅'}\n"
            f"🔑 <b>الرمز السري:</b> <code>{user.get('secret_token', 'غير مولد')}</code>\n"
            f"📅 <b>انتهاء الاشتراك:</b> {user.get('expiry_date', 'دائم')}"
        )
        markup = await keyboards.get_main_menu(uid, bot_info.username)
    else:
        text = "⚠️ <b>حسابك غير مفعل.</b>\nيرجى إرسال كود التفعيل (SMO-xxxx) أو الاشتراك:"
        markup = keyboards.get_subscription_options()

    try:
        if hasattr(update_or_query, 'data'):
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        else:
            sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
            context.user_data.setdefault('temp_msg_ids', []).append(sent_msg.message_id)
    except Exception as e:
        logger.error(f"Error showing menu: {e}")
        sent_msg = await context.bot.send_message(chat_id=uid, text=text, parse_mode='HTML', reply_markup=markup)
        context.user_data.setdefault('temp_msg_ids', []).append(sent_msg.message_id)

# --- 2. معالج الرسائل (استعادة الإذاعة والتحقق التلقائي) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""

    context.user_data.setdefault('temp_msg_ids', []).append(update.message.message_id)

    if text == "🔙 إلغاء والعودة للقائمة":
        await update.message.reply_text("🔄 جاري العودة...", reply_markup=ReplyKeyboardRemove())
        await clean_and_show_menu(update, context, uid)
        return

    # استعادة نظام الإذاعة الشامل (نص، ميديا)
    if context.user_data.get('waiting_for_broadcast') and str(uid) == str(config.ADMIN_ID):
        all_users = database.get_all_user_ids()
        count = 0
        for user_id in all_users:
            try:
                await context.bot.copy_message(user_id, update.message.chat_id, update.message.message_id)
                count += 1
            except: pass
        await update.message.reply_text(f"✅ تم إرسال الإذاعة لـ {count} مستخدم.")
        context.user_data['waiting_for_broadcast'] = False
        return

    # نظام تفعيل SMO التلقائي
    if text.upper().startswith("SMO-"):
        success, res = activation_handler.process_activation(uid, text.upper())
        msg = await update.message.reply_text(f"{'✅' if success else '❌'} {res}", parse_mode='HTML')
        context.user_data['temp_msg_ids'].append(msg.message_id)
        if success:
            await asyncio.sleep(2)
            await clean_and_show_menu(update, context, uid)
        return

    # ربط القنوات (Chat Shared)
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        await update.message.reply_text("✅ تم ربط القناة بنجاح!")
        await clean_and_show_menu(update, context, uid)

# --- 3. معالج الأزرار (استعادة الرموز والويب هوك والإدارة) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    try: await query.answer()
    except: pass

    if data in ['home', 'accept_tos']:
        if data == 'accept_tos': database.add_new_user(uid)
        await clean_and_show_menu(query, context, uid)

    elif data == 'wh': # روابط الويب هوك
        links = services.format_webhook_links(uid)
        await query.edit_message_text(f"🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n<code>{links}</code>", 
                                      parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'tok': # توليد رمز جديد
        new_token = secrets.token_hex(8).upper()
        database.update_user_secret_token(uid, new_token)
        await query.answer("🔐 تم توليد رمز سري جديد بنجاح!")
        await clean_and_show_menu(query, context, uid)

    elif data == 'adm' and is_owner: # استعادة إحصائيات الإدارة الكاملة
        stats = database.get_admin_dashboard_stats()
        await query.edit_message_text(
            f"👮 <b>لوحة تحكم المدير:</b>\n\n"
            f"👥 إجمالي المستخدمين: {stats['total']}\n"
            f"✅ المشتركين النشطين: {stats['active']}\n"
            f"📈 طلبات اليوم: {stats.get('today_requests', 0)}",
            parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard()
        )

    elif data == 'broadcast_prompt' and is_owner:
        await query.message.reply_text("📝 أرسل الآن المحتوى المراد إذاعته:")
        context.user_data['waiting_for_broadcast'] = True

# --- 4. التشغيل الرئيسي وحماية الـ Webhook ---
async def main():
    database.init_db()
    await web_server.start_server()
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # حذف الويب هوك القديم لتجنب التكرار عند بدء التشغيل
    await app.bot.delete_webhook(drop_pending_updates=True)
    
    app.add_handler(CommandHandler("start", lambda u, c: clean_and_show_menu(u, c, u.effective_user.id)))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    logger.info("🚀 سمو الأرقام يعمل بكامل المحذوفات ونظام حماية التكرار.")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try: asyncio.run(main())
    except: pass
