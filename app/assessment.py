"""成效評估問卷的 LINE 推播：把 LIFF 表單連結廣播給所有好友。

有兩種觸發方式：
- 自動：ASSESSMENT_SCHEDULE 列出的日期，會跟每日測驗一起在 Asia/Taipei 08:00 自動推送
  （app/scheduler.py 內建排程＋GitHub Actions 呼叫 /admin/push-daily 雙保險）
- 手動：/admin/push-assessment（廣播給所有好友），或教師後台「成效總覽」頁的按鈕
  （只 push 給 students 表裡還沒填這一輪的學生）
前測（baseline）會在問卷連結後面附上選學校的按鈕，讓還沒建檔的好友一次點選完成註冊
（例如 2026/10 換資料庫後、舊資料遺失的那批好友），同一次 broadcast 不會多耗訊息則數。
兩種方式送出都會寫一筆 assessment_pushes 紀錄；自動推送前會先檢查這一輪是否已經推過，
所以就算老師已經先手動按過、或兩個排程都觸發到，也不會重複推送。
"""

import logging
from datetime import date, datetime

from linebot.v3.messaging import BroadcastRequest, PushMessageRequest, TextMessage
from sqlalchemy.orm import Session

from app import assessment_questions, crud, models
from app.config import settings
from app.database import SessionLocal
from app.game_rules import TAIPEI
from app.line_client import get_messaging_api
from app.routers.webhook import _school_selection_message

logger = logging.getLogger("assessment")

LIFF_BASE_URL = "https://liff.line.me"

# 自動推送問卷的日期（Asia/Taipei）→ 輪次；要改日期或加輪次改這裡即可
ASSESSMENT_SCHEDULE: dict[date, str] = {
    date(2026, 10, 1): "baseline",
    date(2026, 10, 16): "midterm",
    date(2026, 11, 1): "posttest",
}


def build_assessment_url(assessment_round: str) -> str:
    return f"{LIFF_BASE_URL}/{settings.liff_id}?round={assessment_round}"


def _invite_text(assessment_round: str) -> str:
    round_label = assessment_questions.ROUND_LABELS[assessment_round]
    return (
        f"📋 {round_label}問卷來囉！\n\n"
        f"幫我們花 3~5 分鐘填一下這份問卷，讓我們了解大家在氣候行動上的變化 🌱\n"
        f"問卷不用填名字，你的回答只用於研究分析，不會公開，也不會影響成績。\n\n"
        f"{build_assessment_url(assessment_round)}"
    )


def _registration_message(db: Session):
    return _school_selection_message(
        db,
        text=(
            "📌 請完成註冊（只要 2 步驟）\n\n"
            "1️⃣ 點選下方按鈕，選擇你的學校\n"
            "2️⃣ 輸入你的暱稱（會顯示在排行榜上）\n\n"
            "完成後就能開始每天答題、累積能量囉 🌱（已經註冊過的同學不用再點）"
        ),
    )


def broadcast_assessment_invite(assessment_round: str) -> None:
    if assessment_round not in assessment_questions.ROUNDS:
        raise ValueError(f"未知的 assessment_round: {assessment_round}")

    db = SessionLocal()
    try:
        messages = [TextMessage(text=_invite_text(assessment_round))]
        if assessment_round == "baseline":
            messages.append(_registration_message(db))

        api = get_messaging_api()
        api.broadcast(BroadcastRequest(messages=messages))
        crud.record_assessment_push(db, assessment_round)
    finally:
        db.close()


def list_incomplete_students(db: Session, assessment_round: str) -> list[models.Student]:
    """students 表裡還沒交這一輪問卷的人（不在資料庫裡的好友找不到，不會列入）。"""
    done = {r.student_id for r in crud.list_assessment_responses(db, assessment_round)}
    return [s for s in crud.list_students(db) if s.student_id not in done]


def push_assessment_to_incomplete(db: Session, assessment_round: str) -> tuple[int, int]:
    """只推問卷連結給還沒填這一輪的學生，回傳 (成功人數, 失敗人數)。

    用 push 一個一個發，LINE 額度按收到的人數計；前測若學生還沒選學校，順便附上註冊按鈕。
    """
    if assessment_round not in assessment_questions.ROUNDS:
        raise ValueError(f"未知的 assessment_round: {assessment_round}")

    api = get_messaging_api()
    sent, failed = 0, 0
    for student in list_incomplete_students(db, assessment_round):
        messages = [TextMessage(text=_invite_text(assessment_round))]
        if assessment_round == "baseline" and student.school_id is None:
            messages.append(_registration_message(db))
        try:
            api.push_message(PushMessageRequest(to=student.line_user_id, messages=messages))
            sent += 1
        except Exception:
            logger.exception("問卷推送失敗 student_id=%s", student.student_id)
            failed += 1
    if sent:
        crud.record_assessment_push(db, assessment_round)
    logger.info("%s 問卷推送給未完成者：成功 %s 人，失敗 %s 人", assessment_round, sent, failed)
    return sent, failed


def push_scheduled_assessment() -> None:
    """今天（Asia/Taipei）若是 ASSESSMENT_SCHEDULE 排定的日期、且該輪還沒推過，就推送問卷。"""
    today = datetime.now(TAIPEI).date()
    assessment_round = ASSESSMENT_SCHEDULE.get(today)
    if assessment_round is None:
        return

    db = SessionLocal()
    try:
        if crud.has_assessment_push(db, assessment_round):
            logger.info("%s 問卷已經推送過，略過。", assessment_round)
            return
    finally:
        db.close()

    broadcast_assessment_invite(assessment_round)
    logger.info("已自動推送 %s 問卷", assessment_round)
