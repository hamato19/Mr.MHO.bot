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

# --- 1. نظام التنظيف والعرض الموحد ---
async def clean_and_show_menu(update_or_query, context, uid):
    """عرض القائمة الرئيسية مع تنظيف شامل لضمان ثبات الواجهة"""
    await clear_temp_messages(context, uid)
    
    # جلب البيانات والتأكد من الهوية
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    is_active = user.get('is_activated') if user else False
    
    # تحديد النص والأزرار بناءً على الحالة
    if is_owner or is_active:
        text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
        markup = await keyboards.get_main_menu(uid, bot_info.username)
    else:
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إرسال كود التفعيل في الشات:"
        markup = keyboards.get_subscription_options()

    # معالجة الإرسال الذكية
    sent_msg = None
    if hasattr(update_or_query, 'edit_message_text'):  # حالة الضغط على زر
        try:
            sent_msg = await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except Exception:
            sent_msg = await context.bot.send_message(chat_id=uid, text=text, parse_mode='HTML', reply_markup=markup)
    else:  # حالة أمر نصي مثل /start
        sent_msg = await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)

    # حفظ معرف الرسالة للمسح لاحقاً
    if sent_msg:
        if 'temp_msg_ids' not in context.user_data: 
            context.user_data['temp_msg_ids'] = []
        context.user_data['temp_msg_ids'].append(sent_msg.message_id)

# --- 2. معالج الرسائل الموحد (نظام التفعيل المباشر والربط) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
    
    # تسجيل رسالة المستخدم للتنظيف
    context.user_data['temp_msg_ids'].append(update.message.message_id)
    
    if update.message.text:
        raw_text = update.message.text.strip()

        # 1. فحص زر الإلغاء
        if raw_text == "🔙 إلغاء والعودة للقائمة":
            await update.message.reply_text("🔄 جاري العودة للقائمة الرئيسية...", reply_markup=ReplyKeyboardRemove())
            await clean_and_show_menu(update, context, uid)
            return
            
        # 2. معالجة إرسال البث للأدمن
        if context.user_data.get('waiting_for_broadcast') and str(uid) == str(config.ADMIN_ID):
            all_users = database.get_all_user_ids()
            sent, failed = 0, 0
            
            progress = await update.message.reply_text(f"⏳ جاري الإرسال إلى {len(all_users)} مستخدم...")
            
            for user_id in all_users:
                try:
                    await context.bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=update.message.chat_id,
                        message_id=update.message.message_id
                    )
                    sent += 1
                except:
                    failed += 1
            
            await progress.edit_text(f"✅ تم الانتهاء!\n\n🟢 نجح: {sent}\n🔴 فشل: {failed}")
            context.user_data['waiting_for_broadcast'] = False
            return 

        # أ: التعامل مع أكواد التفعيل (SMO-)
        text = raw_text.upper()
        if text.startswith("SMO-"):
            checking_msg = await update.message.reply_text("⏳ جاري التحقق من الكود...")
            success, res = activation_handler.process_activation(uid, text)
            await checking_msg.delete()
            
            msg = await update.message.reply_text(f"{'🎉' if success else '❌'} {res}", parse_mode='HTML')
            context.user_data['temp_msg_ids'].append(msg.message_id)
            
            if success:
                await asyncio.sleep(1.5)
                await clean_and_show_menu(update, context, uid)
            return

    # ب: التعامل مع ربط القنوات (Request Chat)
    # ب: التعامل مع ربط القنوات (Request Chat)
    if update.message.chat_shared:
        # 🚀 الفحص: إذا لم يكن أدمن، نتحقق من شرط القناة الواحدة
        if str(uid) != str(config.ADMIN_ID):
            existing_channels = database.get_user_entities(uid)
            if existing_channels:
                current_ch_name = "قناة مضافة"
                if isinstance(existing_channels[0], dict):
                    current_ch_name = existing_channels[0].get('entity_name', 'قناة مضافة')
                elif len(existing_channels[0]) > 2:
                    current_ch_name = existing_channels[0][2]

                # إرسال رسالة التنبيه للمشترك
                await update.message.reply_text(
                    f"⚠️ <b>عذراً، يمكنك إضافة قناة واحدة فقط كحد أقصى!</b>\n\n"
                    f"حسابك مرتبط حالياً بـ: (<code>{current_ch_name}</code>).\n"
                    f"يرجى الانتقال إلى قسم '📋 إدارة القنوات' وحذفها أولاً لتتمكن من التغيير.\n\n"
                    f"🔄 <i>جاري تحويلك الآن إلى القائمة الرئيسية...</i>",
                    parse_mode='HTML'
                )
                
                # 🔄 ربط فوري: الانتظار ثانيتين ثم مسح الرسائل المؤقتة وإعادة عرض القائمة الرئيسية تلقائياً
                await asyncio.sleep(2)
                await clean_and_show_menu(update, context, uid)
                return # الخروج الآمن والعودة للقائمة دون تجميد الواجهة

        # ✅ للأدمن (أو المشترك العادي إذا لم يملك قناة مسبقاً): يتم الحفظ بشكل طبيعي
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        await update.message.reply_text("✅ تم ربط القناة بنجاح!")
        await asyncio.sleep(1.5)
        await clean_and_show_menu(update, context, uid)
        return

# --- 3. معالج الأزرار التفاعلية (Callbacks) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []

    try: 
        await query.answer()
    except: 
        pass

    # ================= [ الفئة 1: أزرار عامة ومستقلة تماماً ] =================
    
    if data == 'add_channel':
        await keyboards.process_add_channel_logic(query, context, uid, is_owner, user, database)
        return

    if data == 'home':
        await clean_and_show_menu(query, context, uid)
        return

    if data == 'ren':
        await query.edit_message_text("🔄 <b>تفعيل الاشتراك:</b>\nأرسل الكود في الشات مباشرة (مثال: SMO-XXXX)", parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
        return

    if data == 'how_to_act':
        await query.message.reply_text(
            "🎫 <b>طريقة تفعيل الاشتراك:</b>\n\n"
            "من فضلك قم بكتابة كود التفعيل الخاص بك هنا في الشات مباشرة.\n"
            "مثال: <code>SMO-XXXX-XXXX</code>\n\n"
            "⏳ سيقوم النظام بالتحقق من الكود تلقائياً.", 
            parse_mode='HTML'
        )
        return

    if data == 'accept_tos':
        database.add_new_user(uid) 
        if is_owner:
            await query.message.reply_text(f"👑 <b>أهلاً بك يا مدير (ID: {uid})</b>", parse_mode='HTML')
            await clean_and_show_menu(query, context, uid)
            return

        user = database.get_user_profile(uid)
        if user is None:
            is_active = False
            expiry_date = None
        else:
            is_active = user.get('is_activated', False)
            expiry_date = user.get('expiry_date')

        from datetime import datetime
        now = datetime.now()

        if is_active and expiry_date and expiry_date > now:
            await query.message.reply_text(f"✅ تم التحقق من الحساب (ID: <code>{uid}</code>)", parse_mode='HTML')
            await clean_and_show_menu(query, context, uid)
        else:
            await query.message.reply_text("⚠️ حسابك غير مفعل حالياً، يرجى إرسال كود التفعيل.", parse_mode='HTML')
        return

    if data == 'reject_tos':
        await query.edit_message_text(
            "⚠️ <b>تنبيه!</b>\n\nعذراً، لا يمكنك استخدام خدمات <b>سمو الأرقام</b> دون الموافقة على سياسة الخصوصية.\n\n"
            "إذا غيرت رأيك، أرسل /start مجدداً للموافقة.",
            parse_mode='HTML'
        )
        return     

    # ================= [ الفئة 2: الأزرار المحمية للمشتركين والأدمن ] =================
    if is_owner or (user and user.get('is_activated')):
        if data == 'acc': 
            user = database.get_user_profile(uid)
            user_entities = database.get_user_entities(uid)
            channels_count = len(user_entities) if user_entities else 0
            raw_date = user.get('expiry_date')
            
            if is_owner:
                time_left = "وصول كامل (الادمن)"
            elif raw_date:
                if "2099" in str(raw_date):
                    time_left = "إشتراك دائم ♾️"
                else:
                    time_left = services.get_time_remaining(raw_date)
            else:
                time_left = "غير محدد (يرجى التواصل مع الدعم)"

            await query.edit_message_text(
                f"👤 <b>بيانات حسابك:</b>\n\n"
                f"🆔 معرفك: <code>{uid}</code>\n"
                f"⏳ حالة الاشتراك: {'نشط ✅' if is_owner or user.get('is_activated') else 'غير مفعل ❌'}\n"
                f"📅 ينتهي في: <code>{time_left}</code>\n"
                f"📢 القنوات المضافة: <b>{channels_count}</b>", 
                parse_mode='HTML', 
                reply_markup=keyboards.get_back_home()
            )
            return
        
        elif data == 'wh': 
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            return
            
        elif data == 'tok': 
            new_token = secrets.token_hex(8).upper()
            database.update_user_secret_token(uid, new_token)
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🔐 <b>تم تحديث الرمز بنجاح!</b>\n\nروابطك الجديدة:\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            return
        
        elif data == 'chs': 
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>قنواتك المرتبطة حالياً:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
            return 

        elif data.startswith('del_ent_'): 
            try:
                ent_id = data.replace('del_ent_', '')
                database.delete_user_entity(uid, ent_id)
                await query.answer("✅ تم حذف القناة بنجاح")
                ents = database.get_user_entities(uid)
                await query.edit_message_text("📋 <b>قنواتك المرتبطة حالياً:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
            except Exception as e:
                logging.error(f"Error deleting entity: {e}")
            return  

    # ================= [ الفئة 3: لوحة تحكم الإدارة الفائقة (الأدمن فقط) ] =================
    if is_owner:
        if data == 'adm': 
            stats = database.get_admin_dashboard_stats()
            t = stats.get('total', 0)
            a = stats.get('active', 0)
            c = stats.get('codes', 0)
            
            await query.edit_message_text(
                f"👮 <b>لوحة التحكم:</b>\n\n"
                f"👤 إجمالي المستخدمين: {t}\n"
                f"✅ المشتركين النشطين: {a}\n"
                f"🎫 الأكواد غير المستخدمة: {c}", 
                parse_mode='HTML', 
                reply_markup=keyboards.get_admin_keyboard()
            )
            return

        elif data == 'adm_u': 
            try:
                users = database.get_all_users()
                if not users:
                    await query.answer("ℹ️ لا يوجد مستخدمون حالياً", show_alert=True)
                    return
                await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>\nاختر مستخدماً:", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
            except Exception as e:
                logging.error(f"Error in adm_u: {e}")
            return

        elif data.startswith('user_info_'): 
            try:
                target_uid = data.replace('user_info_', '')
                u_profile = database.get_user_profile(target_uid)
                u_channels = database.get_user_entities(target_uid)
                if u_profile:
                    ch_text = "\n".join([f"🔹 <code>{ch['entity_id']}</code>" for ch in u_channels]) if u_channels else "❌ لا توجد قنوات"
                    text = (f"👤 <b>تفاصيل المستخدم:</b> <code>{target_uid}</code>\n"
                            f"📊 الحالة: {'✅ نشط' if u_profile.get('is_activated') else '❌ غير نشط'}\n"
                            f"📅 الانتهاء: <code>{u_profile.get('expiry_date', 'غير محدد')}</code>\n\n"
                            f"📢 القنوات:\n{ch_text}")
                    await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboards.get_user_control_keyboard(target_uid, u_profile.get('is_activated')))
            except Exception as e:
                logging.error(f"Error in user_info: {e}")
            return

        elif data.startswith('del_u_'):
            u_id = data.replace('del_u_', '')
            try:
                if database.delete_user(u_id):
                    await query.answer(f"🗑️ تم حذف المستخدم بنجاح", show_alert=True)
                    await clean_and_show_menu(query, context, uid)
                else:
                    await query.answer("❌ فشل الحذف: المعرف غير موجود", show_alert=True)
            except Exception as e:
                logging.error(f"Error in delete: {e}")
                await query.answer("🚨 خطأ تقني في الحذف")
            return

        elif data.startswith('act_'):
            parts = data.split('_')
            try:
                if len(parts) == 3:
                    days = int(parts[1])
                    target_id = parts[2]
                    success, date_str = database.admin_activate_user(target_id, days)
                    
                    if success:
                        await query.answer(f"✅ تم التفعيل بنجاح لمدة {days} يوم", show_alert=False)
                        await query.edit_message_text(
                            f"🎉 <b>تم تفعيل المستخدم بنجاح!</b>\n\n"
                            f"👤 معرف المستخدم: <code>{target_id}</code>\n"
                            f"📅 مدة الاشتراك: <b>{days} يوم</b>\n"
                            f"⏳ تاريخ الانتهاء الجديد: <code>{date_str}</code>\n\n"
                            f"✨ تم تحديث صلاحيات الوصول للمستخدم الآن.",
                            parse_mode='HTML',
                            reply_markup=keyboards.get_back_home()
                        )
                    else:
                        await query.answer("❌ فشل التفعيل in قاعدة البيانات", show_alert=True)
                else:
                    await query.answer("⚠️ عذراً، حدث خطأ في تنسيق البيانات")
            except Exception as e:
                logging.error(f"Error in activation success message: {e}")
                await query.answer("⚠️ حدث خطأ تقني أثناء محاولة تحديث الرسالة")
            return

        elif data.startswith('ask_act_'):
            target_id = data.replace('ask_act_', '')
            await query.edit_message_reply_markup(reply_markup=keyboards.get_activation_periods_keyboard(target_id))
            return
            
        elif data == 'adm_gen_menu': 
            await query.edit_message_text("🔑 <b>توليد الأكواد:</b>\nاختر المدة:", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
            return

        elif data.startswith('gen_'): 
            try:
                days = int(data.split('_')[1])
                new_code = f"SMO-{secrets.token_hex(4).upper()}"
                database.add_subscription_code(new_code, days)
                await query.edit_message_text(f"✅ <b>تم التوليد!</b>\nالكود: <code>{new_code}</code>\nالمدة: {days} يوم", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            except Exception as e:
                logging.error(f"Error generating code: {e}")
            return

        if data == 'broadcast_prompt':
           await query.message.reply_text("📝 يرجى إرسال الرسالة التي تريد تعميمها على جميع المشتركين الآن:")
           context.user_data['waiting_for_broadcast'] = True
           return

# --- 4. نقطة الانطلاق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await clear_temp_messages(context, uid)
    
    database.add_new_user(uid) 
    
    if str(uid) == str(config.ADMIN_ID):
        await clean_and_show_menu(update, context, uid)
        return

    user = database.get_user_profile(uid)
    if not user:
        await update.message.reply_text(
            privacy_policy.DISCLAIMER_TEXT, 
            parse_mode='HTML', 
            reply_markup=keyboards.get_disclaimer_keyboard()
        )
    else:
        await clean_and_show_menu(update, context, uid)

async def main():
    database.init_db() 
    await web_server.start_server() 
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    logger.info("🚀 سمو الأرقام يعمل الآن بكامل طاقته (نظام التفعيل المباشر).")
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
        pass
