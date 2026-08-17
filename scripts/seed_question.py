"""建立一筆測試題目，方便測試每日推送＋答題流程。

用法：
    python -m scripts.seed_question
"""

import sys

sys.path.append(".")

from app.database import Base, SessionLocal, engine
from app import models


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        question = models.Question(
            knowledge_card_text="全球暖化每上升 1°C，大氣就能多容納約 7% 的水氣，這也是極端暴雨愈來愈常見的原因之一。",
            question_text="下列何者是造成極端暴雨事件增加的原因之一？",
            options=["大氣中水氣含量增加", "海平面上升", "臭氧層破洞", "地震頻率增加"],
            correct_option="大氣中水氣含量增加",
            topic_tag="極端氣候",
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        print(f"已建立題目：question_id={question.question_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
