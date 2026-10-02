"""提醒還沒完成的學生：還沒註冊（選學校＋暱稱）、還沒填前測、還沒答最新推送的那一題。

只發給 students 表裡有紀錄、且至少缺一項的人；不在資料庫裡的好友（換資料庫後從沒跟
機器人互動過的人）找不到，要另外從 LINE 官方帳號後台群發。

每位學生缺的項目合併成一次 push（最多 4 則訊息物件），LINE 額度按「收到的人數」計，
所以一個人不管缺幾項都只算 1 則。

作答按鈕用 Buttons 範本而不是 Quick Reply：Quick Reply 只會出現在聊天室最後一則訊息，
而註冊用的選學校按鈕也是 Quick Reply、要放在最後，兩個不能同時出現；Buttons 範本的按鈕
會一直留在訊息上。選項固定 4 個，剛好是 Buttons 範本的上限。
"""

import logging
from dataclasses import dataclass

from linebot.v3.messaging import (
    ButtonsTemplate,
    PushMessageRequest,
    TemplateMessage,
    TextMessage,
)
from sqlalchemy.orm import Session

from app import assessment_questions, crud, models
from app.assessment import build_assessment_url
from app.daily_push import answer_actions, option_label
from app.line_client import get_messaging_api
from app.routers.webhook import _school_selection_message

logger = logging.getLogger("reminders")

REMINDER_ASSESSMENT_ROUND = "baseline"


@dataclass
class ReminderPlan:
    student: models.Student
    needs_school: bool
    needs_nickname: bool
    needs_assessment: bool
    needs_quiz: bool

    @property
    def needs_registration(self) -> bool:
        return self.needs_school or self.needs_nickname

    @property
    def item_labels(self) -> list[str]:
        labels = []
        if self.needs_registration:
            labels.append("註冊（選學校）" if self.needs_school else "註冊（暱稱）")
        if self.needs_assessment:
            labels.append(f"{assessment_questions.ROUND_LABELS[REMINDER_ASSESSMENT_ROUND]}問卷")
        if self.needs_quiz:
            labels.append("小測驗")
        return labels


def latest_pushed_question(db: Session) -> models.Question | None:
    latest_push = crud.get_latest_daily_push(db)
    return crud.get_question_by_id(db, latest_push.question_id) if latest_push else None


def build_reminder_plans(db: Session, question: models.Question | None) -> list[ReminderPlan]:
    assessed = {r.student_id for r in crud.list_assessment_responses(db, REMINDER_ASSESSMENT_ROUND)}
    answered = (
        {log.student_id for log in crud.list_answer_logs_for_question(db, question.question_id)}
        if question
        else set()
    )
    plans = []
    for student in crud.list_students(db):
        plan = ReminderPlan(
            student=student,
            needs_school=student.school_id is None,
            needs_nickname=student.nickname is None,
            needs_assessment=student.student_id not in assessed,
            needs_quiz=question is not None and student.student_id not in answered,
        )
        if plan.item_labels:
            plans.append(plan)
    return plans


def _build_reminder_messages(db: Session, plan: ReminderPlan, question: models.Question | None) -> list:
    lines = ["🌱 比歐小助教提醒你，以下還沒完成喔："]
    if plan.needs_registration:
        step = "選學校＋取暱稱" if plan.needs_school else "取暱稱"
        lines.append(f"📌 完成註冊（{step}），才能累積能量、登上排行榜")
    if plan.needs_assessment:
        round_label = assessment_questions.ROUND_LABELS[REMINDER_ASSESSMENT_ROUND]
        lines.append(
            f"📋 填寫{round_label}問卷（3~5 分鐘，不用填名字，回答只用於研究分析，不會公開，也不會影響成績）\n"
            f"{build_assessment_url(REMINDER_ASSESSMENT_ROUND)}"
        )
    if plan.needs_quiz:
        lines.append("❓ 回答小測驗（題目在下面）")
    messages = [TextMessage(text="\n\n".join(lines))]

    if plan.needs_quiz:
        options = question.options[:13]
        option_lines = "\n".join(option_label(options, option) for option in options)
        date_label = f"{question.scheduled_date.month}/{question.scheduled_date.day} " if question.scheduled_date else ""
        messages.append(TextMessage(text=f"❓ {date_label}小測驗\n\n{question.question_text}\n\n{option_lines}"))
        messages.append(
            TemplateMessage(
                alt_text="小測驗作答按鈕",
                template=ButtonsTemplate(text="👇 點選你的答案", actions=answer_actions(question)[:4]),
            )
        )

    # 選學校按鈕是 Quick Reply，只會出現在最後一則訊息，所以註冊一定要放最後
    if plan.needs_school:
        messages.append(
            _school_selection_message(
                db,
                text=(
                    "📌 完成註冊只要 2 步驟\n\n"
                    "1️⃣ 點選下方按鈕，選擇你的學校\n"
                    "2️⃣ 輸入你的暱稱（會顯示在排行榜上）"
                ),
            )
        )
    elif plan.needs_nickname:
        messages.append(TextMessage(text="📛 最後一步：幫自己取一個暱稱（會顯示在排行榜上），直接打字傳給我就可以了 😊"))
    return messages


def send_reminders(db: Session) -> tuple[int, int]:
    """發送提醒，回傳 (成功人數, 失敗人數)。失敗通常是學生封鎖了官方帳號，或本月額度用完。"""
    question = latest_pushed_question(db)
    api = get_messaging_api()
    sent, failed = 0, 0
    for plan in build_reminder_plans(db, question):
        try:
            api.push_message(
                PushMessageRequest(
                    to=plan.student.line_user_id,
                    messages=_build_reminder_messages(db, plan, question),
                )
            )
            sent += 1
        except Exception:
            logger.exception("提醒發送失敗 student_id=%s", plan.student.student_id)
            failed += 1
    logger.info("提醒發送完成：成功 %s 人，失敗 %s 人", sent, failed)
    return sent, failed


def message_quota() -> dict | None:
    """本月 LINE 訊息額度：{"limit": 上限（None 代表無上限）, "used": 已用}；查不到回傳 None。"""
    try:
        api = get_messaging_api()
        quota = api.get_message_quota()
        usage = api.get_message_quota_consumption()
    except Exception:
        logger.exception("查詢 LINE 訊息額度失敗")
        return None
    limit = quota.value if quota.type == "limited" else None
    return {"limit": limit, "used": usage.total_usage}
