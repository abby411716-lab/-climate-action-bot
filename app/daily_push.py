"""每日推送：找出下一題、廣播知識卡＋測驗給所有已加好友的學生。"""

import logging
from datetime import date, datetime

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

# 跟當天（Asia/Taipei）的題目一起推送的公告，放在知識卡前面。同一次 broadcast 裡多放一則訊息
# 不會多耗額度（LINE 按「人數 × 群發次數」計），比另外從官方帳號後台群發省。
# 一次 broadcast 最多 5 則訊息：公告 1 ＋ 知識卡圖片 0~1 ＋ 知識卡文字 1 ＋ 測驗 1。
ANNOUNCEMENTS: dict[date, str] = {
    date(2026, 10, 3): (
        "🌱 環保打卡升級囉！\n\n"
        "點下方選單的「🧮 環保打卡」：\n"
        "1️⃣ 第一次點 → 先填碳足跡計算器，算出你的「綠色分數」，完成可得 20 能量\n"
        "2️⃣ 之後再點 → 出現「📷 拍照」按鈕，拍下你的環保行動（自備餐具、搭大眾運輸、資源回收⋯⋯），"
        "老師審核通過可得 15 能量！\n\n"
        "⚠️ 10/1～10/2 填過碳足跡計算器的同學：系統更新後之前的紀錄沒有記到你的帳號，"
        "請從選單點「環保打卡」重新填一次，能量會重新發給你 🙏\n\n"
        "如果選單沒有更新，退出聊天室再重新進來就可以了 😊"
    ),
}

# LINE Quick Reply 按鈕文字最多 20 字，選項常常更長會被截斷，所以完整選項寫在題目訊息裡，
# 按鈕只放選項字母；學生點下去後聊天室會顯示「B. 完整選項」（display_text 上限 300 字）
OPTION_LETTERS = "ABCDEFGHIJKLM"


def option_label(options: list[str], option: str) -> str:
    """回傳「B. 選項文字」這種帶字母的格式，給題目訊息和答題回饋共用。"""
    return f"{OPTION_LETTERS[options.index(option)]}. {option}"


def answer_actions(question: models.Question) -> list[PostbackAction]:
    """每個選項一顆作答按鈕（按鈕上只有字母），每日推送的 Quick Reply 和提醒訊息共用。"""
    options = question.options[:13]
    return [
        PostbackAction(
            label=OPTION_LETTERS[idx],
            data=f"{ANSWER_POSTBACK_PREFIX}{question.question_id}|{idx}",
            display_text=option_label(options, option)[:300],
        )
        for idx, option in enumerate(options)
    ]


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

    options = question.options[:13]
    items = [QuickReplyItem(action=action) for action in answer_actions(question)]
    option_lines = "\n".join(option_label(options, option) for option in options)
    messages.append(
        TextMessage(
            text=f"❓ 今日小測驗\n\n{question.question_text}\n\n{option_lines}\n\n👇 請點選下方按鈕作答",
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
            logger.info("今天沒有排定要推送的題目（可能是前測日等非排程日，或題庫已全部推送完畢）。")
            return

        messages = _build_quiz_messages(question)
        if announcement := ANNOUNCEMENTS.get(today):
            messages.insert(0, TextMessage(text=announcement))

        api = get_messaging_api()
        api.broadcast(BroadcastRequest(messages=messages))
        crud.record_daily_push(db, question.question_id)
        logger.info("已推送 question_id=%s", question.question_id)
    finally:
        db.close()
