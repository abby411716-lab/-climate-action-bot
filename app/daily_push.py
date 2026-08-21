"""每日推送：找出下一題、廣播知識卡＋測驗給所有已加好友的學生。"""

import logging
from datetime import datetime

from linebot.v3.messaging import (
    BroadcastRequest,
    ImageMessage,
    PostbackAction,
    QuickReply,
    QuickReplyItem,
    TextMessage,
)

from app import crud, models
from app.database import SessionLocal
from app.game_rules import TAIPEI
from app.line_client import get_messaging_api

logger = logging.getLogger("daily_push")

ANSWER_POSTBACK_PREFIX = "answer|"


def _build_quiz_messages(question: models.Question) -> list:
    messages = []
    if question.knowledge_card_image_url:
        messages.append(
            ImageMessage(
                original_content_url=question.knowledge_card_image_url,
                preview_image_url=question.knowledge_card_image_url,
            )
        )
    messages.append(TextMessage(text=f"📘 今日氣候知識卡\n\n{question.knowledge_card_text}"))

    items = [
        QuickReplyItem(
            action=PostbackAction(
                label=option[:20],
                data=f"{ANSWER_POSTBACK_PREFIX}{question.question_id}|{idx}",
                display_text=option,
            )
        )
        for idx, option in enumerate(question.options[:13])
    ]
    messages.append(
        TextMessage(
            text=f"❓ 今日小測驗\n\n{question.question_text}",
            quick_reply=QuickReply(items=items),
        )
    )
    return messages


def push_daily_question(force: bool = False) -> None:
    """推送今天的題目給所有好友。force=True 時略過「今天已推送過」的檢查（測試用）。"""
    db = SessionLocal()
    try:
        today = datetime.now(TAIPEI).date()
        if not force:
            latest_push = crud.get_latest_daily_push(db)
            if latest_push and latest_push.pushed_at.astimezone(TAIPEI).date() == today:
                logger.info("今天已經推送過題目，略過。")
                return

        question = crud.get_next_unpushed_question(db, today)
        if question is None:
            logger.info("今天沒有排定要推送的題目（可能是週末／空檔週，或題庫已全部推送完畢）。")
            return

        api = get_messaging_api()
        api.broadcast(BroadcastRequest(messages=_build_quiz_messages(question)))
        crud.record_daily_push(db, question.question_id)
        logger.info("已推送 question_id=%s", question.question_id)
    finally:
        db.close()
