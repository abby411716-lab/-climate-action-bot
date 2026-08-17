import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    QuickReply,
    QuickReplyItem,
    ReplyMessageRequest,
    PostbackAction,
    TextMessage,
)
from linebot.v3.webhooks import (
    FollowEvent,
    ImageMessageContent,
    MessageEvent,
    PostbackEvent,
    TextMessageContent,
)
from sqlalchemy.orm import Session

from app import crud, eco_checkin, game_rules, models
from app.daily_push import ANSWER_POSTBACK_PREFIX
from app.database import get_db
from app.game_rules import TAIPEI
from app.line_client import get_messaging_api, get_messaging_blob_api, webhook_parser

router = APIRouter()
logger = logging.getLogger("webhook")

SCHOOL_POSTBACK_PREFIX = "school_id="
MENU_POSTBACK_PREFIX = "menu|"


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


def _status_text(student: models.Student) -> str:
    rank_name, _flavor = game_rules.current_rank(student.total_points)
    badge_names = [game_rules.badge_display(code) for code in student.badges]
    return (
        f"目前身分：{rank_name}\n"
        f"目前能量：{student.total_points}\n"
        f"連續天數：{student.current_streak}（最長 {student.longest_streak}）\n"
        f"徽章：{'、'.join(badge_names) if badge_names else '尚無'}"
    )


def _profile_text(student: models.Student, school: models.School | None) -> str:
    return f"🏫 就讀學校：{school.school_name if school else '尚未設定'}\n📛 暱稱：{student.nickname or '尚未設定'}"


def _leaderboard_text(db: Session, school: models.School) -> str:
    students = crud.get_leaderboard(db, school.school_id, limit=10)
    if not students:
        return f"🏆 {school.school_name} 排行榜\n\n目前還沒有資料，快去答題或環保打卡衝積分吧！"
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"🏆 {school.school_name} 排行榜 TOP {len(students)}"]
    for i, s in enumerate(students):
        prefix = medals[i] if i < len(medals) else f"{i + 1}."
        lines.append(f"{prefix} {s.nickname}｜{s.total_points} 能量")
    return "\n".join(lines)


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


def _handle_school_postback(event: PostbackEvent, db: Session, data: str) -> None:
    api = get_messaging_api()
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
        reply = TextMessage(
            text=(
                f"已為你登記為「{school.school_name}」的同學 🎉 之後每天都會收到氣候知識卡與小測驗！\n\n"
                "最後一步，幫自己取一個暱稱吧（會顯示在排行榜上），直接打字輸入就可以了 😊"
            )
        )
    api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))


def _handle_menu_postback(event: PostbackEvent, db: Session, data: str) -> None:
    api = get_messaging_api()
    action = data.removeprefix(MENU_POSTBACK_PREFIX)
    line_user_id = event.source.user_id
    student = crud.get_or_create_student(db, line_user_id)

    if student.school_id is None:
        reply = _school_selection_message(db)
    elif student.nickname is None:
        reply = TextMessage(text="請先直接打字輸入一個暱稱，設定好之後才能使用選單功能喔 😊")
    elif action == "profile":
        school = crud.get_school_by_id(db, student.school_id)
        reply = TextMessage(text=_profile_text(student, school))
    elif action == "status":
        reply = TextMessage(text=_status_text(student))
    elif action == "checkin_info":
        reply = TextMessage(
            text=(
                "📸 直接把你的環保行動照片傳給我就可以打卡囉！\n"
                "（例如：自備餐具、搭乘大眾運輸、資源回收⋯⋯）\n\n"
                f"老師審核通過後會發放 {game_rules.ECO_CHECKIN_POINTS} 能量，也可能解鎖徽章！"
            )
        )
    elif action == "leaderboard":
        school = crud.get_school_by_id(db, student.school_id)
        reply = TextMessage(text=_leaderboard_text(db, school))
    else:
        return

    api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))


def _handle_answer_postback(event: PostbackEvent, db: Session, data: str) -> None:
    api = get_messaging_api()
    try:
        _, question_id_str, option_idx_str = data.split("|")
        question_id, option_idx = int(question_id_str), int(option_idx_str)
    except ValueError:
        return

    question = crud.get_question_by_id(db, question_id)
    if question is None or not (0 <= option_idx < len(question.options)):
        return

    line_user_id = event.source.user_id
    student = crud.get_or_create_student(db, line_user_id)

    if crud.get_answer_log(db, student.student_id, question_id):
        reply = TextMessage(text="這一題你已經回答過囉，明天還有新的題目等你！")
        api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))
        return

    selected_option = question.options[option_idx]
    is_correct = selected_option == question.correct_option

    previous_log = crud.get_latest_answer_log(db, student.student_id)
    today = datetime.now(TAIPEI).date()
    previous_date = previous_log.answered_at.astimezone(TAIPEI).date() if previous_log else None

    crud.create_answer_log(db, student.student_id, question_id, selected_option, is_correct)

    new_streak = game_rules.next_streak(previous_date, today, student.current_streak)
    new_points = student.total_points + (game_rules.CORRECT_POINTS if is_correct else game_rules.INCORRECT_POINTS)
    new_longest = max(student.longest_streak, new_streak)

    stats = {
        "current_streak": new_streak,
        "total_points": new_points,
        "correct_count": crud.count_correct_answers(db, student.student_id),
        "answered_count": crud.count_answers(db, student.student_id),
    }
    new_badges = game_rules.evaluate_new_badges(student.badges, stats)
    updated_badges = list(student.badges) + [code for code, _name in new_badges]

    crud.save_student_progress(
        db,
        student,
        total_points=new_points,
        current_streak=new_streak,
        longest_streak=new_longest,
        badges=updated_badges,
    )

    rank_name, rank_flavor = game_rules.current_rank(new_points)

    lines = []
    if is_correct:
        lines.append(f"✅ 答對了！+{game_rules.CORRECT_POINTS} 能量")
    else:
        lines.append(
            f"❌ 可惜，正確答案是「{question.correct_option}」 +{game_rules.INCORRECT_POINTS} 能量（感謝你的參與）"
        )
    lines.append(f"目前能量：{new_points}｜連續天數：{new_streak}（最長 {new_longest}）")
    lines.append(f"目前身分：{rank_name}\n{rank_flavor}")
    if new_badges:
        lines.append("\n".join(f"🏅 解鎖新徽章：{name}" for _code, name in new_badges))

    reply = TextMessage(text="\n\n".join(lines))
    api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))


def _handle_postback(event: PostbackEvent, db: Session) -> None:
    data = event.postback.data or ""

    if data.startswith(SCHOOL_POSTBACK_PREFIX):
        _handle_school_postback(event, db, data)
    elif data.startswith(ANSWER_POSTBACK_PREFIX):
        _handle_answer_postback(event, db, data)
    elif data.startswith(MENU_POSTBACK_PREFIX):
        _handle_menu_postback(event, db, data)


def _handle_text_message(event: MessageEvent, db: Session) -> None:
    line_user_id = event.source.user_id
    student = crud.get_or_create_student(db, line_user_id)
    api = get_messaging_api()

    if student.school_id is None:
        reply = _school_selection_message(db)
    elif student.nickname is None:
        nickname = event.message.text.strip()[:50]
        if not nickname:
            reply = TextMessage(text="暱稱不能是空白喔，請重新輸入一個暱稱吧！")
        else:
            crud.set_student_nickname(db, student, nickname)
            reply = TextMessage(
                text=(
                    f"暱稱設定完成：{nickname} 🎉\n\n"
                    "之後可以用下方選單查看基本資料、目前狀態、排行榜，或直接傳照片做環保打卡！"
                )
            )
    else:
        reply = TextMessage(text=_status_text(student))
    api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))


def _handle_image_message(event: MessageEvent, db: Session) -> None:
    line_user_id = event.source.user_id
    student = crud.get_or_create_student(db, line_user_id)
    api = get_messaging_api()

    if student.school_id is None:
        reply = _school_selection_message(db)
        api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply]))
        return

    blob_api = get_messaging_blob_api()
    raw_content = blob_api.get_message_content(event.message.id)
    compressed = eco_checkin.compress_image(bytes(raw_content))
    crud.create_eco_checkin(db, student.student_id, event.message.id, compressed, "image/jpeg")

    reply = TextMessage(
        text="已收到你的環保打卡照片 📸 老師審核通過後就會發放能量，請耐心等候通知～"
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
            elif isinstance(event, MessageEvent) and isinstance(event.message, ImageMessageContent):
                _handle_image_message(event, db)
        except Exception:
            logger.exception("Failed to handle LINE event: %s", event)

    return "OK"
