from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# --- دالة مساعدة لزر العودة الموحد ---
def back_home_button():
    return [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='home')]

# 1. واجهة الخصوصية
def get_disclaimer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ موافق وأرغب بالتفعيل", callback_data='accept_tos')],
        [InlineKeyboardButton("❌ رفض", callback_data='reject_tos')]
    ])

# 2. واجهة التفعيل والتجديد
def get_subscription_options():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 اشتراك الآن", url="https://sumoualarqam.com/"),
            InlineKeyboardButton("🎫 ادخل كود التفعيل", callback_data='ren')
        ],
        back_home_button()
    ])

# 3. القائمة الرئيسية
async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📋 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز الأمان", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت مشرف", url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

# 4. لوحة الأدمن
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='adm_gen_menu')],
        back_home_button()
    ])

# 5. قائمة خيارات مدة الكود (للأدمن) - تم إضافة الـ 5 أيام والـ 60 يوم
def get_generation_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎁 تجريبي (5 أيام)", callback_data='gen_5'),
            InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30')
        ],
        [
            InlineKeyboardButton("🗓️ 60 يوم", callback_data='gen_60'),
            InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90')
        ],
        [InlineKeyboardButton("🗓️ سنة كاملة (365 يوم)", callback_data='gen_365')],
        [InlineKeyboardButton("🔙 عودة للأدمن", callback_data='adm')],
        back_home_button()
    ])

# 6. إدارة المستخدمين
def get_users_management_keyboard(users):
    kb = []
    for user in users:
        status = "✅" if user.get('is_activated') else "❌"
        kb.append([InlineKeyboardButton(f"👤 {user['user_id']} | {status}", callback_data=f"view_u_{user['user_id']}")])
    kb.append([InlineKeyboardButton("🔙 عودة للأدمن", callback_data='adm')])
    kb.append(back_home_button())
    return InlineKeyboardMarkup(kb)

# 7. التحكم بالمستخدم (من قبل الأدمن)
def get_user_control_keyboard(target_id, is_active):
    # زر التفعيل سيوجه الأدمن أو يفتح حالة التفعيل للمستخدم
    # سنستخدم اختصارات: 'act_' للتفعيل و 'del_u_' للحذف
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تفعيل (إدخال كود)", callback_data=f"act_{target_id}")],
        [InlineKeyboardButton("🗑️ حذف المستخدم", callback_data=f"del_u_{target_id}")],
        [InlineKeyboardButton("🔙 عودة للقائمة", callback_data='adm_u')]
    ])


# 8. إدارة القنوات (عرض وحذف) - نسخة محسنة لمنع الأخطاء
def get_entities_keyboard(entities):
    kb = []
    if not entities:
        kb.append([InlineKeyboardButton("❌ لا توجد قنوات مرتبطة", callback_data='none')])
    else:
        for ent in entities:
            try:
                # 1. استخراج الـ ID والتأكد من أنه نص نظيف وقصير
                if isinstance(ent, dict):
                    raw_id = str(ent.get('entity_id', '0'))
                else:
                    raw_id = str(ent[0])
                
                # تنظيف الـ ID من أي مسافات أو رموز غريبة قد تزيد الحجم
                clean_id = raw_id.strip()

                # 2. نص الزر (يظهر للمستخدم) - نعرض الـ ID كاملاً هنا لأنه لا يسبب خطأ
                button_text = f"🆔 {clean_id}"
                
                # 3. البيانات الخلفية (المشكلة هنا) - سنقتصر على أول 20 حرف فقط كإجراء احترازي
                # تذكر: الحرف 'd_' يأخذ 2 بايت، والـ ID يأخذ الباقي
                safe_callback_v = f"v_{clean_id}"[:60] 
                safe_callback_d = f"d_{clean_id}"[:60]

                kb.append([
                    InlineKeyboardButton(button_text, callback_data=safe_callback_v),
                    InlineKeyboardButton("🗑️ حذف", callback_data=safe_callback_d)
                ])
            except Exception as e:
                logging.error(f"Error rendering button: {e}")
                continue

    kb.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data='add_channel')])
    kb.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='home')])
    return InlineKeyboardMarkup(kb)



# 9. زر اختيار القناة
def get_request_channel_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📢 اختر القناة  ", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))],
        [KeyboardButton("🔙 إلغاء والعودة للقائمة")]
    ], resize_keyboard=True, one_time_keyboard=True)

# 10. العودة السريعة
def get_back_home():
    return InlineKeyboardMarkup([back_home_button()])
