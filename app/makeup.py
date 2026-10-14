"""補做題目：學生漏答的舊題目，可以自己從選單「補做題目」（或打字「補做」）一題一題補答。

「補做」的定義是：作答日期（Asia/Taipei）晚於這題的推送日期。補做能量減半
（`game_rules.MAKEUP_CORRECT_POINTS`／`MAKEUP_INCORRECT_POINTS`），鼓勵學生當天就作答。
提醒訊息裡重新附上的舊題目，隔天以後才答一樣算補做。

補做題目用 Reply Message 回覆學生，不耗 LINE 訊息額度。
"""

from datetime import date

from linebot.v3.messaging import TextMessage
from sqlalchemy.orm import Session

from app import crud, game_rules, models
from app.daily_push import quiz_with_buttons_messages
from app.game_rules import TAIPEI

MAKEUP_MENU_ACTION = "makeup"
MAKEUP_KEYWORDS = {"補做", "補做題目"}


def _push_date(push: models.DailyPush) -> date:
    return push.pushed_at.astimezone(TAIPEI).date()


def is_makeup(db: Session, question_id: int, today: date) -> bool:
    push = crud.get_daily_push_for_question(db, question_id)
    return push is not None and _push_date(push) < today


def missed_question_ids_by_student(db: Session, today: date) -> dict[int, list[int]]:
    """每位學生「今天以前推送過、但還沒答」的題目，由舊到新排列；沒漏答的學生不會出現。"""
    past_ids = [p.question_id for p in crud.list_daily_pushes(db) if _push_date(p) < today]
    answered = crud.list_answered_question_ids(db)
    missed = {}
    for student in crud.list_students(db):
        ids = [qid for qid in past_ids if (student.student_id, qid) not in answered]
        if ids:
            missed[student.student_id] = ids
    return missed


def missed_question_ids(db: Session, student_id: int, today: date) -> list[int]:
    answered = {log.question_id for log in crud.list_answer_logs_for_student(db, student_id)}
    return [
        p.question_id
        for p in crud.list_daily_pushes(db)
        if _push_date(p) < today and p.question_id not in answered
    ]


def makeup_reply_messages(db: Session, student: models.Student, today: date) -> list:
    """選單「補做題目」的回覆：送出最舊的一題漏答題目；沒有漏答就看今天的題目答了沒。"""
    missed = missed_question_ids(db, student.student_id, today)
    if missed:
        question = crud.get_question_by_id(db, missed[0])
        date_label = f"{question.scheduled_date.month}/{question.scheduled_date.day} " if question.scheduled_date else ""
        heading = (
            f"📝 補做 {date_label}小測驗（還有 {len(missed)} 題沒補）\n"
            f"補做能量減半：答對 +{game_rules.MAKEUP_CORRECT_POINTS}、答錯 +{game_rules.MAKEUP_INCORRECT_POINTS}"
        )
        return quiz_with_buttons_messages(question, heading)

    latest_push = crud.get_latest_daily_push(db)
    if (
        latest_push
        and _push_date(latest_push) == today
        and crud.get_answer_log(db, student.student_id, latest_push.question_id) is None
    ):
        question = crud.get_question_by_id(db, latest_push.question_id)
        return [TextMessage(text="🎉 舊題目都答完了！不過今天的題目還沒作答喔 👇")] + quiz_with_buttons_messages(
            question, "❓ 今日小測驗"
        )
    return [TextMessage(text="🎉 目前沒有需要補做的題目，你每一題都答了，太厲害了！")]
