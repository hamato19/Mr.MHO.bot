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

# 2. واجهة التفعيل والتجديد (تعديل: زرين بجانب بعض)
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

# 5. قائمة خيارات مدة الكود (للأدمن)
def get_generation_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30'),
            InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90')
        ],
        [InlineKeyboardButton("🗓️ سنة كاملة (365 يوم)", callback_data='gen_365')],
        [InlineKeyboardButton("🔙 عودة للأدمن", callback_data='adm')],
        back_home_button()
    ])

# 6. إدارة المستخدمين (قائمة ديناميكية)
def get_users_management_keyboard(users):
    kb = []
    for user in users:
        status = "✅" if user.get('is_activated') else "❌"
        kb.append([InlineKeyboardButton(f"👤 {user['user_id']} | {status}", callback_data=f"view_u_{user['user_id']}")])
    kb.append([InlineKeyboardButton("🔙 عودة للأدمن", callback_data='adm')])
    kb.append(back_home_button())
    return InlineKeyboardMarkup(kb)

# 7. التحكم بالمستخدم
def get_user_control_keyboard(target_id, is_active):
    toggle_text = "🚫 تعطيل" if is_active else "✅ تفعيل"
    action = "deactivate" if is_active else "activate"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=f"toggle_u_{action}_{target_id}")],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_u_{target_id}")],
        [InlineKeyboardButton("🔙 عودة", callback_data='adm_u')]
    ])

# 8. إدارة القنوات (عرض وحذف)
def get_entities_keyboard(entities):
    kb = []
    if not entities:
        kb.append([InlineKeyboardButton("❌ لا توجد قنوات مرتبطة", callback_data='none')])
    else:
        for ent in entities:
            kb.append([
                InlineKeyboardButton(f"📺 {ent[1]}", callback_data=f"view_ch_{ent[0]}"),
                InlineKeyboardButton("🗑️ حذف", callback_data=f"del_ch_{ent[0]}")
            ])
    kb.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data='add_channel')])
    kb.append(back_home_button())
    return InlineKeyboardMarkup(kb)

# 9. العودة السريعة
def get_back_home():
    return InlineKeyboardMarkup([back_home_button()])
