from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

def get_back_home():
    """زر العودة الموحد"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])

async def get_main_menu(uid, bot_username="bot"):
    """القائمة الرئيسية"""
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد", callback_data='ren')],
        [InlineKeyboardButton("📢 ربط قناة", callback_data='add'), InlineKeyboardButton("📺 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 تحديث الرمز", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    if int(uid) == config.ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

def get_entities_keyboard(entities):
    """
    حل مشكلة الـ 64 بايت (Button_data_invalid) نهائياً.
    بدلاً من إرسال المعرف الطويل، نرسل رقم الترتيب (index).
    """
    keyboard = []
    
    for index, ent in enumerate(entities):
        try:
            # استخراج اسم القناة
            name = str(ent[1]) if isinstance(ent, (tuple, list)) else "قناة"
            
            # نرسل d_ متبوعة برقم الترتيب (مثل d_0, d_1)
            # هذا يضمن أن حجم البيانات دائماً أقل من 5 بايت
            keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"d_{index}")])
        except:
            continue
            
    keyboard.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    """لوحة تحكم الأدمن"""
    kb = [
        [InlineKeyboardButton("👥 المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='adm_s')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='adm_g')],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)
