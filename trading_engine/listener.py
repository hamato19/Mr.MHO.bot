import re
import logging
from telethon import TelegramClient, events
from .executor import run_mass_execution
from trading_api.database import SessionLocal

# إعداد السجلات لمراقبة وصول الإشارات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SignalListener")

# إعدادات التليجرام (تُجلب من .env)
API_ID = 'YOUR_API_ID'
API_HASH = 'YOUR_API_HASH'
SIGNAL_SOURCE = 'MOH_SignalsBot' # اسم البوت أو معرف القناة

client = TelegramClient('moh_listener_session', API_ID, API_HASH)

def parse_signal(text):
    """
    دالة تحليل النص (Parsing) لاستخراج بيانات الصفقة.
    تعتمد على النمط المعتاد في بوت @MOH_SignalsBot
    """
    try:
        # البحث عن الزوج (مثال: #BTCUSDT)
        symbol_match = re.search(r'#(\w+)', text)
        # البحث عن سعر الدخول (Entry)
        entry_match = re.search(r'(?:Entry|Dentry|دخول):\s*([\d.]+)', text, re.IGNORECASE)
        # البحث عن وقف الخسارة (SL)
        sl_match = re.search(r'(?:SL|Stop|وقف):\s*([\d.]+)', text, re.IGNORECASE)
        
        if symbol_match and entry_match and sl_match:
            return {
                "symbol": f"{symbol_match.group(1).upper()}",
                "side": "buy" if "long" in text.lower() or "شراء" in text else "sell",
                "entry": float(entry_match.group(1)),
                "sl": float(sl_match.group(1))
            }
    except Exception as e:
        logger.error(f"Error parsing text: {e}")
    return None

@client.on(events.NewMessage(chats=SIGNAL_SOURCE))
async def my_event_handler(event):
    """الاستماع للرسائل الجديدة فور صدورها"""
    raw_text = event.raw_text
    logger.info(f"New Signal Received: {raw_text[:50]}...")

    # 1. تحليل النص وتحويله لبيانات رقمية
    signal_data = parse_signal(raw_text)

    if signal_data:
        logger.info(f"Parsed Data: {signal_data}")
        
        # 2. فتح جلسة قاعدة البيانات وتمرير الإشارة لمحرك التنفيذ
        db = SessionLocal()
        try:
            # استدعاء دالة التنفيذ الجماعي التي بنيناها في executor.py
            run_mass_execution(signal_data, db)
            logger.info("Signal dispatched to all active users.")
        finally:
            db.close()
    else:
        logger.warning("Message received but could not be parsed as a valid signal.")

if __name__ == "__main__":
    print("Connecting to Telegram and listening for signals...")
    client.start()
    client.run_until_disconnected()
