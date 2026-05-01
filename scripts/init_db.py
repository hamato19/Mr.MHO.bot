import sys
import os
# لإضافة المسار الرئيسي للـ Python Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading_api.database import engine
from trading_api.models import Base

def create_tables():
    print("جاري إنشاء جداول التداول الجديدة...")
    Base.metadata.create_all(bind=engine)
    print("تم إنشاء الجداول بنجاح!")

if __name__ == "__main__":
    create_tables()
