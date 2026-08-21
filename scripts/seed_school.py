"""建立新學校並印出加好友連結。

用法：
    python -m scripts.seed_school "南投高中" nantou_high
"""

import sys

sys.path.append(".")

from app.database import SessionLocal
from app import crud, models

LINE_BOT_BASIC_ID = "@071qusgf"


def main():
    if len(sys.argv) != 3:
        print("用法：python -m scripts.seed_school <學校名稱> <join_link_code>")
        sys.exit(1)

    school_name, join_link_code = sys.argv[1], sys.argv[2]

    db = SessionLocal()
    try:
        existing = crud.get_school_by_join_code(db, join_link_code)
        if existing:
            print(f"already exists: school_id={existing.school_id}")
            return

        school = models.School(school_name=school_name, join_link_code=join_link_code)
        db.add(school)
        db.commit()
        db.refresh(school)

        print(f"已建立學校：{school.school_name}（school_id={school.school_id}）")
        print(f"加好友連結：https://line.me/R/ti/p/{LINE_BOT_BASIC_ID}?school={join_link_code}")
        print("（若加好友連結無法自動帶入學校，學生仍可透過加好友後的按鈕選單手動選擇）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
