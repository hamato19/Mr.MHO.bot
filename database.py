import os
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")

# إنشاء حوض اتصالات لضمان السرعة في الويب هوك
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)

@contextmanager
def get_db():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)
