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
    
    # حماية: إذا لم يكن أدمن وغير مفعل، تظهر قائمة الاشتراك فقط
    if not is_owner and (not user or not user.get('is_activated')):
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إرسال كود التفعيل في الشات:"
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

# --- 2. معالج الرسائل الموحد (نظام التفعيل المباشر والربط) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    if 'temp_msg_ids' not in context.user_data: context.user_data['temp_msg_ids'] = []
    
    # تسجيل رسالة المستخدم للتنظيف
    context.user_data['temp_msg_ids'].append(update.message.message_id)
    if update.message.text:
        raw_text = update.message.text.strip()

        # 1. فحص زر الإلغاء (يجب أن يكون قبل تحويل النص لـ UPPER)
        if raw_text == "🔙 إلغاء والعودة للقائمة":
            from telegram import ReplyKeyboardRemove
            await update.message.reply_text("🔄 جاري العودة للقائمة الرئيسية...", reply_markup=ReplyKeyboardRemove())
            await clean_and_show_menu(update, context, uid)
            return
    
    # أ: التعامل مع أكواد التفعيل (SMO-)
    if update.message.text:
        text = update.message.text.strip().upper()
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
    if update.message.chat_shared:
        # 1. 🚀 الفحص: هل المستخدم لديه قناة مضافة مسبقاً؟
        existing_channels = database.get_user_entities(uid)
        
        if existing_channels:
            # إذا وجدنا قناة، نرسل رسالة التنبيه ونوقف العملية فوراً
            # (نأخذ أول قناة لأن نظامك يضمن وجود واحدة فقط)
            current_ch_name = "قناة مضافة"
            if isinstance(existing_channels[0], dict):
                current_ch_name = existing_channels[0].get('entity_name', 'قناة مضافة')
            elif len(existing_channels[0]) > 2:
                current_ch_name = existing_channels[0][2]

            await update.message.reply_text(
                f"⚠️ <b>تنبيه:</b>\nهذا الحساب مرتبط بالفعل بقناة: (<code>{current_ch_name}</code>).\n\n"
                f"عليك حذف القناة المضافة أولاً لتتمكن من تغيير القناة.",
                parse_mode='HTML'
            )
            await asyncio.sleep(1)
            await clean_and_show_menu(update, context, uid)
            return # الخروج من الدالة دون إضافة القناة الجديدة

        # 2. ✅ إذا لم توجد قناة، يتم الحفظ بشكل طبيعي
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        await update.message.reply_text("✅ تم ربط القناة بنجاح!")
        await asyncio.sleep(1)
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

    try: await query.answer()
    except: pass
    if data == 'accept_tos':
        # 1. تسجيل المستخدم في قاعدة البيانات (أو التأكد من وجوده)
        database.add_new_user(uid) 
        
        # 2. جلب بيانات المستخدم للتحقق من حالة الاشتراك والـ ID
        user = database.get_user_profile(uid)
        from datetime import datetime
        now = datetime.now()

        is_active = user.get('is_activated') if user else False
        expiry_date = user.get('expiry_date') if user else None
        
        # شرط التجاوز: حساب مفعل + تاريخ انتهاء لم يأتِ بعد
        if is_active and expiry_date and expiry_date > now:
            await query.message.reply_text(f"✅ تم التحقق من الحساب (ID: <code>{uid}</code>)\nأهلاً بك مجدداً في سمو الأرقام.", parse_mode='HTML')
            await clean_and_show_menu(query, context, uid)
        else:
            # رسالة المنع إذا كان جديداً أو منتهياً
            status_text = "حسابك منتهي الاشتراك" if is_active else "الحساب غير مفعل حالياً"
            await query.message.reply_text(
                f"✅ <b>تم قبول السياسة بنجاح.</b>\n\n"
                f"⚠️ {status_text}.\n"
                f"لا يمكنك تجاوز هذه المرحلة والوصول للقائمة الرئيسية إلا بعد التفعيل.\n\n"
                f"يرجى إرسال <b>كود التفعيل</b> الخاص بك الآن في الشات\n"
                f"(مثال: <code>SMO-XXXX</code>):",
                parse_mode='HTML',
                reply_markup=keyboards.get_subscription_options() # أزرار الدعم والاشتراك فقط
            )
        return

    elif data == 'reject_tos':
        # معالجة حالة رفض السياسة
        try: await query.answer("تم تسجيل الرفض")
        except: pass
        
        await query.edit_message_text(
            "⚠️ <b>تنبيه!</b>\n\nعذراً، لا يمكنك استخدام خدمات <b>سمو الأرقام</b> دون الموافقة على سياسة الخصوصية.\n\n"
            "إذا غيرت رأيك، أرسل /start مجدداً للموافقة.",
            parse_mode='HTML'
        )
        return     
    # القائمة الرئيسية والعودة
    if data == 'home':
        await clean_and_show_menu(query, context, uid)
        return

    # تجديد الاشتراك
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
    # --- القسم المحمي (للمشتركين والأدمن فقط) ---
    if is_owner or (user and user.get('is_activated')):
        if data == 'acc': # زر حسابي
            # 1. جلب بيانات المستخدم كاملة من قاعدة البيانات
            user = database.get_user_profile(uid)
            
            # 2. جلب عدد القنوات المرتبطة
            user_entities = database.get_user_entities(uid)
            channels_count = len(user_entities) if user_entities else 0
            
            # 3. معالجة التاريخ وحالة NULL الظاهرة في قاعدة بياناتك
            raw_date = user.get('expiry_date')
            
            if is_owner:
                time_left = "وصول كامل (الادمن)"
            elif raw_date:
                # إذا كان التاريخ 2099 كما في الصورة فهو اشتراك دائم
                if "2099" in str(raw_date):
                    time_left = "إشتراك دائم ♾️"
                else:
                    time_left = services.get_time_remaining(raw_date)
            else:
                # هذا الحل إذا كانت القيمة NULL كما في الصورة
                time_left = "غير محدد (يرجى التواصل مع الدعم)"

            # 4. الرسالة النهائية
            await query.edit_message_text(
                f"👤 <b>بيانات حسابك:</b>\n\n"
                f"🆔 معرفك: <code>{uid}</code>\n"
                f"⏳ حالة الاشتراك: {'نشط ✅' if is_owner or user.get('is_activated') else 'غير مفعل ❌'}\n"
                f"📅 ينتهي في: <code>{time_left}</code>\n"
                f"📢 القنوات المضافة: <b>{channels_count}</b>", 
                parse_mode='HTML', 
                reply_markup=keyboards.get_back_home()
            )
        
        elif data == 'wh': # الويب هوك
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            
        elif data == 'tok': # توليد رمز سري جديد
            new_token = secrets.token_hex(8).upper()
            database.update_user_secret_token(uid, new_token)
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🔐 <b>تم تحديث الرمز بنجاح!</b>\n\nروابطك الجديدة:\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())

        
        elif data == 'chs': # إدارة القنوات
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>قنواتك المرتبطة حالياً:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
            return # تأكد أن المسافة هنا 12 مسطرة (أو 3 Tab)

        elif data.startswith('del_ent_'): # معالج الحذف
            try:
                ent_id = data.replace('del_ent_', '')
                database.delete_user_entity(uid, ent_id)
                await query.answer("✅ تم حذف القناة بنجاح")
                # إعادة عرض القائمة المحدثة
                ents = database.get_user_entities(uid)
                await query.edit_message_text("📋 <b>قنواتك المرتبطة حالياً:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
            except Exception as e:
                logging.error(f"Error deleting entity: {e}")
            return

        
        elif data == 'add_channel':
            if is_owner or (user and user.get('is_activated')):
                # 1. حذف الرسالة القديمة لتنظيف الشاشة
                try: await query.message.delete()
                except: pass

                # 2. إرسال رسالة جديدة تماماً تطلب القناة
                await context.bot.send_message(
                    chat_id=uid,
                    text="📢 <b>ربط قناة جديدة:</b>\n\nاضغط على الزر الكبير بالأسفل لاختيار القناة وتفويض البوت.",
                    parse_mode='HTML',
                    reply_markup=keyboards.get_request_channel_keyboard()
                )
            else:
                await query.answer("⚠️ عذراً، هذه الميزة للمشتركين فقط.", show_alert=True)
            re    # --- لوحة الأدمن (التحكم الكامل) ---
    if is_owner:
        if data == 'adm': # الإحصائيات
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة التحكم:</b>\n\n👤 إجمالي المستخدمين: {t}\n✅ المشتركين النشطين: {a}\n🎫 الأكواد غير المستخدمة: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            return

        elif data == 'adm_u': # قائمة المستخدمين
            try:
                users = database.get_all_users()
                if not users:
                    await query.answer("ℹ️ لا يوجد مستخدمون حالياً", show_alert=True)
                    return
                await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>\nاختر مستخدماً:", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
            except Exception as e:
                logging.error(f"Error in adm_u: {e}")
            return

        elif data.startswith('user_info_'): # تفاصيل مستخدم محدد
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

        elif data == 'adm_gen_menu': # قائمة التوليد
            await query.edit_message_text("🔑 <b>توليد الأكواد:</b>\nاختر المدة:", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
            return

        elif data.startswith('gen_'): # تنفيذ التوليد
            try:
                days = int(data.split('_')[1])
                new_code = f"SMO-{secrets.token_hex(4).upper()}"
                database.add_subscription_code(new_code, days)
                await query.edit_message_text(f"✅ <b>تم التوليد!</b>\nالكود: <code>{new_code}</code>\nالمدة: {days} يوم", parse_mode='HTML', reply_markup=keyboards.get_back_home())
            except Exception as e:
                logging.error(f"Error generating code: {e}")
            return

# --- 4. نقطة الانطلاق (خارج الدالة السابقة) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await clear_temp_messages(context, uid)
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
        # drop_pending_updates=True ضرورية لمنع تراكم الرسائل القديمة
        await app.updater.start_polling(drop_pending_updates=True)
        while True: 
            await asyncio.sleep(3600)

if __name__ == '__main__':
    try: 
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): 
        pass
