from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
# Neon 免費方案閒置約 5 分鐘會暫停資料庫並切斷連線，但服務被 /health 叫醒時一直開著，
# 連線池裡會留著已被切斷的舊連線，下一個查詢就噴「SSL connection has been closed unexpectedly」。
# pool_pre_ping 會在每次取用連線前先確認還活著，斷了就自動重連。
engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
