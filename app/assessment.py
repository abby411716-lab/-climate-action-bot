"""成效評估問卷的 LINE 推播：手動由老師/管理員觸發，把 LIFF 表單連結廣播給所有好友。

不像每日測驗有精確的 scheduled_date，前測/中測/後測只知道「哪一週」要發，
所以做成跟 /admin/push-daily 一樣的手動觸發端點（見 app/routers/admin.py），
由管理員自己挑那一週裡的哪一天發送，而不是自動排程。
"""

from linebot.v3.messaging import BroadcastRequest, TextMessage

from app import assessment_questions
from app.config import settings
from app.line_client import get_messaging_api

LIFF_BASE_URL = "https://liff.line.me"


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

    api = get_messaging_api()
    api.broadcast(BroadcastRequest(messages=[TextMessage(text=text)]))
