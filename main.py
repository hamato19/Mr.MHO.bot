# --- معالجة الرسائل (نسخة محدثة لمنع تكرار معرف القناة) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id

    # 1. العودة للقائمة الرئيسية من الزر
    if update.message and update.message.text == "🏠 العودة للقائمة الرئيسية":
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text(STRINGS['العربية']['welcome'], reply_markup=await get_main_menu(), parse_mode=ParseMode.HTML)
        return

    # 2. استلام كود التفعيل من WebApp
    if update.message and update.message.web_app_data:
        code = update.message.web_app_data.data
        if ADMIN_ID != 0:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 <b>طلب تفعيل جديد!</b>\n\n👤 المستخدم: <code>{uid}</code>\n🎟️ الكود: <code>{code}</code>", parse_mode=ParseMode.HTML)
        await update.message.reply_text("✅ تم إرسال الكود بنجاح، سيتم التفعيل قريباً.", reply_markup=ReplyKeyboardRemove())
        return

    # 3. ربط القنوات (تم إزالة إضافة -100 اليدوية هنا)
    if context.user_data.get('state') == 'wait_ch' and update.message.chat_shared:
        # نحصل على المعرف كما هو من تليجرام
        raw_id = update.message.chat_shared.chat_id
        
        # تليجرام يرسل المعرف ببادئة -100 للقنوات بشكل تلقائي في الأنظمة الحديثة
        # لذا سنقوم بتحويله لنص وتخزينه مباشرة
        target_id = str(raw_id)

        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), target_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ تم ربط القناة بنجاح بالمعرف: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
                except Exception as e:
                    logging.error(f"Error inserting channel: {e}")
                    await update.message.reply_text("❌ القناة مرتبطة مسبقاً أو حدث خطأ في البيانات.")
        context.user_data['state'] = None
