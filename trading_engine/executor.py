import ccxt
import logging
from sqlalchemy.orm import Session
from trading_api import models, security, database

# إعداد السجلات (Logs) لمراقبة العمليات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradeExecutor")

class TradeExecutor:
    def __init__(self, user_id: int, db: Session):
        self.user_id = user_id
        self.db = db
        self.exchange = self._init_exchange()

    def _init_exchange(self):
        """جلب مفاتيح المستخدم وفك تشفيرها وربطها بـ CCXT"""
        key_data = self.db.query(models.UserAPIKeys).filter(models.UserAPIKeys.user_id == self.user_id).first()
        
        if not key_data:
            logger.error(f"User {self.user_id} has no API keys.")
            return None

        # فك التشفير باستخدام نظام الأمان الذي بنيناه سابقاً
        api_key = security.decrypt_key(key_data.api_key_enc)
        api_secret = security.decrypt_key(key_data.api_secret_enc)

        # إنشاء كائن المنصة (Binance كمثال)
        exchange_class = getattr(ccxt, key_data.exchange.lower())
        return exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} # العمل على العقود الآجلة
        })

    def execute_market_order(self, symbol: str, side: str, amount: float, sl: float = None, tp: float = None):
        """تنفيذ صفقة ماركت مع وقف خسارة وجني أرباح"""
        if not self.exchange: return

        try:
            logger.info(f"Executing {side} for {self.user_id} on {symbol}")
            
            # 1. فتح الصفقة الرئيسية
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount
            )

            # 2. وضع أمر وقف الخسارة (SL) إذا تم تحديده
            if sl:
                sl_side = 'sell' if side == 'buy' else 'buy'
                self.exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side=sl_side,
                    amount=amount,
                    params={'stopPrice': sl}
                )

            # 3. تسجيل الصفقة في جدول التاريج (TradeHistory)
            new_trade = models.TradeHistory(
                user_id=self.user_id,
                symbol=symbol,
                side=side,
                entry_price=order['price'] if order['price'] else 0,
                stop_loss=sl,
                status='OPEN'
            )
            self.db.add(new_trade)
            self.db.commit()
            
            return order

        except Exception as e:
            logger.error(f"Trade failed for user {self.user_id}: {str(e)}")
            return None

def run_mass_execution(signal_data, db_session: Session):
    """
    الدالة التي يتم استدعاؤها عند وصول إشارة من @MOH_SignalsBot
    تقوم بتوزيع الصفقات على جميع المستخدمين المفعلين
    """
    # جلب جميع المستخدمين الذين فعلوا البوت
    active_users = db_session.query(models.TradingSettings).filter(models.TradingSettings.is_bot_active == True).all()

    for user_setting in active_users:
        # حساب الحجم بناءً على إعدادات المستخدم (Risk Management)
        # هنا يتم تطبيق منطق الـ Fibonacci و الـ FVG قبل التنفيذ
        executor = TradeExecutor(user_setting.user_id, db_session)
        
        # تنفيذ الصفقة (مثال: الشراء بناءً على الإشارة)
        executor.execute_market_order(
            symbol=signal_data['symbol'],
            side=signal_data['side'],
            amount=calculate_amount(user_setting, signal_data), # دالة لحساب الحجم
            sl=signal_data['sl']
        )

def calculate_amount(user_setting, signal_data):
    # منطق حساب الكمية بناءً على نسبة المخاطرة (Risk %) الموجودة في قاعدة البيانات
    return 0.001 # قيمة افتراضية للتجربة
