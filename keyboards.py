from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# 1. واجهة الخصوصية (تظهر للمستخدم الجديد)
def get_disclaimer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ موافق وأرغب بالتفعيل", callback_data='accept_tos')],
        [InlineKeyboardButton("❌ رفض", callback_data='reject_tos')]
    ])

# 2. واجهة التفعيل والتجديد (موحدة لضمان تجربة مستخدم سلسة)
def get_subscription_options():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 اشتراك الآن", url="https://sumoualarqam.com/"),
            InlineKeyboardButton("🎫 ادخل كود التفعيل", callback_data='ren')
        ]
    ])

# 3. القائمة الرئيسية (تظهر للمفعلين والأدمن فقط)
async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📋 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز الأمان", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت مشرف", url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    # التحقق من صلاحيات الأدمن لعرض لوحة التحكم
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

# 4. لوحة الأدمن الأساسية
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]
    ])

# 5. قائمة خيارات توليد الأكواد
def get_generation_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30'), InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90')],
        [InlineKeyboardButton("🗓️ سنة كاملة", callback_data='gen_365')],
        [InlineKeyboardButton("🔙 عودة للأدمن", callback_data='adm')]
    ])

# 6. واجهة اختيار القناة (تعتمد ميزة التليجرام الرسمية للاختيار)
def get_request_channel_keyboard():
    keyboard = [
        [KeyboardButton(
            text="📢 اضغط هنا لاختيار القناة", 
            request_chat=KeyboardButtonRequestChat(
                request_id=1, 
                chat_is_channel=True,
                user_administrator_rights={"can_post_messages": True},
                bot_administrator_rights={"can_post_messages": True}
            )
        )],
        [KeyboardButton(text="🔙 إلغاء")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# 7. قائمة إدارة القنوات المرتبطة
def get_entities_keyboard(entities):
    """توليد أزرار القنوات المرتبطة مع خيار الحذف السريع"""
    kb = []
    if not entities:
        kb.append([InlineKeyboardButton("❌ لا توجد قنوات مرتبطة حالياً", callback_data='none')])
    else:
        for ent in entities:
            # ent[0]: ID القناة في الداتا بيز | ent[1]: اسم القناة
            kb.append([
                InlineKeyboardButton(f"📺 {ent[1]}", callback_data=f"view_ch_{ent[0]}"),
                InlineKeyboardButton("🗑️ حذف", callback_data=f"del_ch_{ent[0]}")
            ])
    
    kb.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data='add_channel')])
    kb.append([InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')])
    return InlineKeyboardMarkup(kb)

# 8. زر العودة الموحد (لتنظيف الواجهة وتسهيل التنقل)
def get_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])
