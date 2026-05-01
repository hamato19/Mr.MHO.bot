from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# استخدام رابط قاعدة البيانات من البوت الأساسي
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") 

# تحسين الاتصال لخدمة عدد كبير من المستخدمين (Connection Pooling)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_size=20, 
    max_overflow=0
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
