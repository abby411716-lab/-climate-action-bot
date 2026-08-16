import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    QuickReply,
    QuickReplyItem,
    ReplyMessageRequest,
    PostbackAction,
    TextMessage,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, PostbackEvent, TextMessageContent
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.line_client import get_messaging_api, webhook_parser

router = APIRouter()
logger = logging.getLogger("webhook")

SCHOOL_POSTBACK_PREFIX = "school_id="


def _school_selection_message(db: Session) -> TextMessage:
    schools = crud.list_schools(db)
    items = [
        QuickReplyItem(
            action=PostbackAction(
                label=school.school_name[:20],
                data=f"{SCHOOL_POSTBACK_PREFIX}{school.school_id}",
                display_text=school.school_name,
            )
        )
        for school in schools[:13]
    ]
    return TextMessage(
        text="請問你是哪間學校的同學？請點選下方按鈕確認 🌱",
        quick_reply=QuickReply(items=items) if items else None,
    )


def _handle_follow(event: FollowEvent, db: Session) -> None:
    line_user_id = event.source.user_id
    school_id = None

    follow_detail = getattr(event, "follow", None)
    params = getattr(follow_detail, "params", None) if follow_detail else None
    school_code = params.get("school") if isinstance(params, dict) else None
    if school_code:
        school = crud.get_school_by_join_code(db, school_code)
        if school:
            school_id = school.school_id

    student = crud.get_or_create_student(db, line_user_id, school_id)

    api = get_messaging_api()
    if student.school_id is not None:
        school = crud.get_school_by_id(db, student.school_id)
        reply = TextMessage(text=f"歡迎加入！已為你登記為「{school.school_name}」的同學 🎉")
    else:
        reply = _school_selection_message(db)

    api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))


def _handle_postback(event: PostbackEvent, db: Session) -> None:
    data = event.postback.data or ""
    api = get_messaging_api()

    if data.startswith(SCHOOL_POSTBACK_PREFIX):
        line_user_id = event.source.user_id
        student = crud.get_or_create_student(db, line_user_id)
        try:
            school_id = int(data.removeprefix(SCHOOL_POSTBACK_PREFIX))
        except ValueError:
            return
        school = crud.get_school_by_id(db, school_id)
        if not school:
            reply = TextMessage(text="找不到這間學校，請聯絡老師確認連結是否正確。")
        else:
            crud.set_student_school(db, student, school.school_id)
            reply = TextMessage(text=f"已為你登記為「{school.school_name}」的同學 🎉 之後每天都會收到氣候知識卡與小測驗！")
        api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))


def _handle_text_message(event: MessageEvent, db: Session) -> None:
    line_user_id = event.source.user_id
    student = crud.get_or_create_student(db, line_user_id)
    api = get_messaging_api()

    if student.school_id is None:
        reply = _school_selection_message(db)
    else:
        reply = TextMessage(
            text=(
                f"目前積分：{student.total_points}\n"
                f"連續天數：{student.current_streak}（最長 {student.longest_streak}）\n"
                f"徽章：{'、'.join(student.badges) if student.badges else '尚無'}"
            )
        )
    api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))


@router.post("/webhook")
async def line_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_line_signature: str = Header(default=""),
):
    body = (await request.body()).decode("utf-8")

    try:
        events = webhook_parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        try:
            if isinstance(event, FollowEvent):
                _handle_follow(event, db)
            elif isinstance(event, PostbackEvent):
                _handle_postback(event, db)
            elif isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                _handle_text_message(event, db)
        except Exception:
            logger.exception("Failed to handle LINE event: %s", event)

    return "OK"
