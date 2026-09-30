"""把本機 SQLite（climate_action.db）裡的題庫複製到 DATABASE_URL 指向的資料庫。

用在換資料庫時（例如 Render 免費 Postgres 過期後改用 Neon）：先對新資料庫跑
alembic upgrade head 建好表，再用這支把題目（含 scheduled_date）搬過去。
question_id 會照原本的值寫入，已存在相同 question_text 的題目會跳過，可重複執行。

用法（DATABASE_URL 設成新資料庫的連線網址）：
    python -m scripts.copy_questions_from_sqlite
"""

import sys

sys.path.append(".")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import SessionLocal

SOURCE_URL = "sqlite:///./climate_action.db"


def main():
    source = sessionmaker(bind=create_engine(SOURCE_URL))()
    target = SessionLocal()
    try:
        existing_texts = {q.question_text for q in target.query(models.Question).all()}
        created = 0
        for q in source.query(models.Question).order_by(models.Question.question_id).all():
            if q.question_text in existing_texts:
                continue
            target.add(
                models.Question(
                    question_id=q.question_id,
                    knowledge_card_text=q.knowledge_card_text,
                    knowledge_card_image_url=q.knowledge_card_image_url,
                    question_text=q.question_text,
                    options=q.options,
                    correct_option=q.correct_option,
                    topic_tag=q.topic_tag,
                    scheduled_date=q.scheduled_date,
                )
            )
            created += 1
        target.commit()

        # 手動指定了 question_id，Postgres 的自動編號要跟著往後調，之後新增題目才不會撞號
        if target.bind.dialect.name == "postgresql":
            target.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('questions', 'question_id'), "
                    "(SELECT MAX(question_id) FROM questions))"
                )
            )
            target.commit()

        total = target.query(models.Question).filter(models.Question.scheduled_date.isnot(None)).count()
        print(f"完成：新增 {created} 題，目前有排程日期的題目共 {total} 題")
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
