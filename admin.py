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
    # حذف القوائم والرسائل السابقة قبل عرض القائمة الجديدة لمنع التكرار
    await clear_temp_messages(context, uid)
    
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    if not user:
        text = privacy_policy.DISCLAIMER_TEXT
        markup = keyboards.get_disclaimer_keyboard()
    else:
        if not is_owner and not user.get('is_activated'):
            text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إدخال كود التفعيل للوصول للخدمات:"
            markup = keyboards.get_subscription_options()
        else:
            text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
            markup = await keyboards.get_main_menu(uid, bot_info.username)

    if isinstance(update_or_query, Update):
        # إرسال القائمة وتسجيل الـ ID للحذف لاحقاً
        sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
        context.user_data['temp_msg_ids'].append(sent_msg.message_id)
    else:
        try:
            # محاولة التعديل لسرعة الاستجابة، إذا فشل (رسالة محذوفة) يرسل جديدة
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except:
            sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
            context.user_data['temp_msg_ids'].append(sent_msg.message_id)

# --- 2. المعالجات (Handlers) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
    
    # تنظيف شامل عند كل /start لمنع تكرار القوائم
    await clear_temp_messages(context, uid)
    context.user_data['temp_msg_ids'].append(update.message.message_id)
    await clean_and_show_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    # استجابة فورية للزر لسرعة فائقة (UI Speed)
    try: await query.answer()
    except: pass

    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []

    # --- إدارة التنقل والخصوصية ---
    if data == 'accept_tos':
        database.register_user(uid, update.effective_user.full_name)
        await clean_and_show_menu(query, context, uid)
        return
    elif data == 'home':
        await clean_and_show_menu(query, context, uid)
        return
    elif data == 'ren': # نظام التفعيل
        await clear_temp_messages(context, uid)
        context.user_data['awaiting_code'] = True 
        await query.edit_message_text("🔄 <b>نظام التفعيل:</b>\nيرجى إرسال كود التفعيل (SMO-xxxx) الآن.", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        return

    # --- خدمات المشتركين والأدمن (محمية) ---
    if is_owner or (user and user.get('is_activated')):
        if data == 'wh': # رابط الويب هوك
            webhook_text = services.format_webhook_links(uid)
            msg = await context.bot.send_message(chat_id=uid, text=f"🌐 <b>روابط الويب هوك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            return
            
        elif data == 'tok': # تحديث رمز الأمان
            new_token = secrets.token_hex(8).upper()
            database.update_user_secret_token(uid, new_token)
            webhook_text = services.format_webhook_links(uid)
            msg = await context.bot.send_message(chat_id=uid, text=f"🔐 <b>تم تحديث الرمز بنجاح!</b>\n\nالروابط الجديدة:\n<code>{webhook_text}</code>", parse_mode='HTML')
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
             
        elif data == 'acc': # حسابي
            await clear_temp_messages(context, uid)
            exp = services.get_time_remaining(user.get('expiry_date')) if user and not is_owner else "دائم"
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ ينتهي في: {exp}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            return

    # --- لوحة التحكم للإدارة ---
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة الإدارة</b>\n\n👤 المستخدمين: {t}\n✅ المشتركين: {a}\n🎫 الأكواد: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            return
        elif data == 'adm_u':
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>قائمة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
            return
            
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
        # 👆 نهاية الكود الجديد 👆

        elif data.startswith('gen_'): # توليد الأكواد
            # ... كود توليد الأكواد ...
            return
        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد أكواد تفعيل:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
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
    
    # تسجيل أي رسالة واردة من المستخدم ليتم تنظيفها لاحقاً
    if update.message:
        context.user_data['temp_msg_ids'].append(update.message.message_id)

    # معالجة الأزرار النصية
    if update.message.text == "🔙 إلغاء والعودة للقائمة":
        await clean_and_show_menu(update, context, uid)
        return

    # استقبال القناة المشتركة (Request Chat)
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        m = await update.message.reply_text("✅ تم ربط القناة بنجاح!", reply_markup=ReplyKeyboardRemove())
        context.user_data['temp_msg_ids'].append(m.message_id)
        await asyncio.sleep(1)
        await clean_and_show_menu(update, context, uid)
        return

    # معالجة نصوص الأكواد
    if update.message.text:
        text = update.message.text.strip()
        if text.upper().startswith("SMO-") or context.user_data.get('awaiting_code'):
            context.user_data['awaiting_code'] = False
            s_msg = await update.message.reply_text("⏳ جاري التحقق من صلاحية الكود...")
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
    
    # الهاندلرز
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    logger.info("🚀 سمو الأرقام يعمل بكامل طاقته...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try: asyncio.run(main())
    except: pass
