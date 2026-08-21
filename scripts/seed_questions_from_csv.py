"""從 CSV 檔案批次匯入正式題庫。

CSV 欄位（第一列為表頭）：
    knowledge_card_text, question_text, option_a, option_b, option_c, option_d,
    correct_option, topic_tag, scheduled_date

- correct_option 欄位填的是「選項文字本身」（要跟 option_a~d 其中一個完全一致），不是 A/B/C/D 字母
- scheduled_date 格式為 YYYY-MM-DD，可留空
- 已存在相同 question_text 的題目會被跳過，避免重複匯入

用法：
    python -m scripts.seed_questions_from_csv "C:\\path\\to\\questions.csv"
"""

import csv
import sys
from datetime import date, datetime

sys.path.append(".")

from app.database import SessionLocal
from app import models


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def main():
    if len(sys.argv) < 2:
        print("用法：python -m scripts.seed_questions_from_csv <csv路徑>")
        sys.exit(1)

    csv_path = sys.argv[1]

    db = SessionLocal()
    try:
        existing_texts = {q.question_text for q in db.query(models.Question).all()}

        created = 0
        skipped = 0
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                question_text = row["question_text"].strip()
                if question_text in existing_texts:
                    print(f"第 {row_num} 列：題目已存在，跳過 -> {question_text[:20]}...")
                    skipped += 1
                    continue

                options = [
                    row["option_a"].strip(),
                    row["option_b"].strip(),
                    row["option_c"].strip(),
                    row["option_d"].strip(),
                ]
                correct_option = row["correct_option"].strip()
                if correct_option not in options:
                    raise ValueError(
                        f"第 {row_num} 列：correct_option「{correct_option}」不在四個選項裡 -> {options}"
                    )

                question = models.Question(
                    knowledge_card_text=row["knowledge_card_text"].strip(),
                    question_text=question_text,
                    options=options,
                    correct_option=correct_option,
                    topic_tag=(row.get("topic_tag") or "").strip() or None,
                    scheduled_date=parse_date(row.get("scheduled_date", "")),
                )
                db.add(question)
                existing_texts.add(question_text)
                created += 1

        db.commit()
        print(f"完成：新增 {created} 筆，跳過 {skipped} 筆（已存在）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
