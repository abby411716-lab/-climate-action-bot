"""碳足跡打卡計算器：交通／居家能源／垃圾回收三大類，共 6 題單選，每題 0~3 分，
加總換算成 0~100 的「綠色分數」，並對應一個等級／故事文案（風格比照 app/game_rules.py 的 RANKS）。

刻意不做成精確的公斤 CO2e 估算——那需要具體、有公信力的排放係數，容易被質疑不準確——
而是相對分數，重點是讓學生反思自己的生活習慣、看到努力方向，不是要精算數字。

獨立的 LIFF App／Endpoint URL（`/liff/carbon-footprint`，對應 .env 的 CARBON_LIFF_ID），
跟成效評估問卷（app/assessment_questions.py，走 /liff/assessment、LIFF_ID）分開，
改哪一邊的 LIFF Endpoint URL（例如本機測試接 ngrok/cloudflared tunnel）都不會互相影響。
頁面模板仍共用 app/templates/assessment.html 這個殼子，靠伺服器端渲染的 mode 變數
決定要顯示哪種表單。
"""

from typing import Any

from linebot.v3.messaging import BroadcastRequest, TextMessage
from sqlalchemy.orm import Session

from app import crud, game_rules, models
from app.config import settings
from app.line_client import get_messaging_api

LIFF_BASE_URL = "https://liff.line.me"

QUESTIONS: list[dict[str, Any]] = [
    {
        "key": "transport_commute",
        "category": "交通方式",
        "text": "平常上學／通勤最常用的交通方式是？",
        "options": [
            ("walk_bike", "走路或腳踏車", 3),
            ("public_transit", "公車、捷運等大眾運輸", 2),
            ("carpool", "跟家人朋友共乘（一起載好幾個人）", 1),
            ("alone_motor", "自己騎機車，或只有你自己搭車／被接送", 0),
        ],
    },
    {
        "key": "transport_long_distance",
        "category": "交通方式",
        "text": "上個月你搭過幾次飛機，或開車／騎車跑過幾趟 100 公里以上的長途？",
        "options": [
            ("none", "完全沒有", 3),
            ("once", "1 次", 2),
            ("few", "2~3 次", 1),
            ("many", "4 次以上", 0),
        ],
    },
    {
        "key": "energy_ac",
        "category": "居家能源",
        "text": "家裡冷氣的使用習慣？",
        "options": [
            ("rarely", "很少開，主要用電扇或自然通風", 3),
            ("controlled", "會開，但有控制溫度（26 度以上）跟時間", 2),
            ("often", "常開，沒有特別注意溫度或時間", 1),
            ("always", "幾乎整天開著", 0),
        ],
    },
    {
        "key": "energy_habit",
        "category": "居家能源",
        "text": "離開房間會不會隨手關燈、拔插頭？",
        "options": [
            ("always", "每次都會", 3),
            ("mostly", "大部分時候會", 2),
            ("sometimes", "偶爾會", 1),
            ("rarely", "很少注意", 0),
        ],
    },
    {
        "key": "waste_sorting",
        "category": "垃圾與資源回收",
        "text": "垃圾分類、資源回收的習慣？",
        "options": [
            ("always", "都會確實分類回收", 3),
            ("mostly", "大部分會，偶爾偷懶", 2),
            ("sometimes", "只在方便的時候做", 1),
            ("rarely", "很少做", 0),
        ],
    },
    {
        "key": "waste_disposables",
        "category": "垃圾與資源回收",
        "text": "免洗餐具、塑膠袋、寶特瓶這類一次性用品的使用頻率？",
        "options": [
            ("rarely", "幾乎不用，自備餐具／環保杯袋", 3),
            ("sometimes", "偶爾用", 2),
            ("often", "常用", 1),
            ("always", "幾乎每天用", 0),
        ],
    },
]

MAX_SCORE = sum(max(points for _v, _l, points in q["options"]) for q in QUESTIONS)

# (最低綠色分數門檻, 等級, 故事文案)，由低到高排列，風格比照 game_rules.RANKS
LEVELS: list[tuple[int, str, str]] = [
    (0, "💭 剛開始關注", "生活習慣還有很大的調整空間，找一兩件事開始改變就是好的開始！"),
    (35, "🌱 起步中", "已經有一些好習慣了，繼續留意還可以更好的地方！"),
    (60, "🌿 持續實踐", "在日常生活中已經展現不少低碳習慣，很不錯！"),
    (85, "🌳 低碳生活家", "生活習慣對環境很友善，是同學的好榜樣！"),
]


def get_questions() -> list[dict[str, Any]]:
    """回傳給前端的題目清單，故意不附上每個選項的分數，避免學生用猜分數的方式亂填。"""
    return [
        {
            "key": q["key"],
            "category": q["category"],
            "text": q["text"],
            "options": [[value, label] for value, label, _points in q["options"]],
        }
        for q in QUESTIONS
    ]


class ValidationError(Exception):
    pass


def score_answers(answers: dict[str, Any]) -> tuple[dict[str, str], int]:
    """驗證並計算分數。回傳 (整理過的回答, 總分 0~MAX_SCORE)。answers 格式不合法就丟 ValidationError。"""
    cleaned: dict[str, str] = {}
    total = 0
    for q in QUESTIONS:
        key = q["key"]
        value = answers.get(key)
        if not value:
            raise ValidationError(f"「{q['text']}」為必填")
        option = next((opt for opt in q["options"] if opt[0] == value), None)
        if option is None:
            raise ValidationError(f"「{q['text']}」的答案不合法")
        cleaned[key] = value
        total += option[2]
    return cleaned, total


def green_score(total_score: int) -> int:
    """把原始總分（0~MAX_SCORE）換算成 0~100 的綠色分數。"""
    return round(total_score / MAX_SCORE * 100)


def current_level(score: int) -> tuple[str, str]:
    """回傳目前等級與故事文案（依綠色分數取最高門檻，比照 game_rules.current_rank）。"""
    name, flavor = LEVELS[0][1], LEVELS[0][2]
    for threshold, level_name, flavor_text in LEVELS:
        if score >= threshold:
            name, flavor = level_name, flavor_text
    return name, flavor


def award_first_completion(db: Session, student: models.Student) -> list[tuple[str, str]]:
    """第一次完成碳足跡計算時發放能量、檢查是否解鎖徽章。回傳新解鎖的徽章 (代碼, 顯示名稱) 清單。"""
    new_points = student.total_points + game_rules.CARBON_CALC_POINTS
    stats = {
        "total_points": new_points,
        "current_streak": student.current_streak,
        "carbon_calc_done": True,
    }
    new_badges = game_rules.evaluate_new_badges(student.badges, stats)
    updated_badges = list(student.badges) + [code for code, _name in new_badges]

    crud.save_student_progress(
        db,
        student,
        total_points=new_points,
        current_streak=student.current_streak,
        longest_streak=student.longest_streak,
        badges=updated_badges,
    )
    return new_badges


def build_carbon_footprint_url() -> str:
    return f"{LIFF_BASE_URL}/{settings.carbon_liff_id}"


def broadcast_carbon_footprint_invite() -> None:
    url = build_carbon_footprint_url()
    text = (
        "🧮 碳足跡打卡計算器上線囉！\n\n"
        "花 2 分鐘想想你的交通、居家能源、垃圾回收習慣，看看自己的「綠色分數」，"
        f"完成就能拿到 {game_rules.CARBON_CALC_POINTS} 能量 🌱（之後也可以重新填寫更新分數）\n\n"
        f"{url}"
    )
    api = get_messaging_api()
    api.broadcast(BroadcastRequest(messages=[TextMessage(text=text)]))
