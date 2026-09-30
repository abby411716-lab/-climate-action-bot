"""成效評估問卷的 LINE 推播：把 LIFF 表單連結廣播給所有好友。

有兩種觸發方式：
- 自動：ASSESSMENT_SCHEDULE 列出的日期，會跟每日測驗一起在 Asia/Taipei 08:00 自動推送
  （app/scheduler.py 內建排程＋GitHub Actions 呼叫 /admin/push-daily 雙保險）
- 手動：/admin/push-assessment 或教師後台「成效總覽」頁的按鈕，還沒排定日期的輪次用這個發
前測（baseline）會在問卷連結後面附上選學校的按鈕，讓還沒建檔的好友一次點選完成註冊
（例如 2026/10 換資料庫後、舊資料遺失的那批好友），同一次 broadcast 不會多耗訊息則數。
兩種方式送出都會寫一筆 assessment_pushes 紀錄；自動推送前會先檢查這一輪是否已經推過，
所以就算老師已經先手動按過、或兩個排程都觸發到，也不會重複推送。
"""

import logging
from datetime import date, datetime

from linebot.v3.messaging import BroadcastRequest, TextMessage

from app import assessment_questions, crud
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


def broadcast_assessment_invite(assessment_round: str) -> None:
    if assessment_round not in assessment_questions.ROUNDS:
        raise ValueError(f"未知的 assessment_round: {assessment_round}")

    round_label = assessment_questions.ROUND_LABELS[assessment_round]
    url = build_assessment_url(assessment_round)
    text = (
        f"📋 {round_label}問卷來囉！\n\n"
        f"幫我們花 3~5 分鐘填一下這份匿名問卷，讓我們了解大家在氣候行動上的變化 🌱\n\n"
        f"{url}"
    )

    db = SessionLocal()
    try:
        messages = [TextMessage(text=text)]
        if assessment_round == "baseline":
            messages.append(
                _school_selection_message(
                    db,
                    text=(
                        "📌 請完成註冊（只要 2 步驟）\n\n"
                        "1️⃣ 點選下方按鈕，選擇你的學校\n"
                        "2️⃣ 輸入你的暱稱（會顯示在排行榜上）\n\n"
                        "完成後就能開始每天答題、累積能量囉 🌱（已經註冊過的同學不用再點）"
                    ),
                )
            )

        api = get_messaging_api()
        api.broadcast(BroadcastRequest(messages=messages))
        crud.record_assessment_push(db, assessment_round)
    finally:
        db.close()


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
