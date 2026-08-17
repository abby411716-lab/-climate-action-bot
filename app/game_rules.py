"""積分／連續天數／徽章的遊戲規則。

規格書沒有寫死這部分的細節，這裡先訂一版合理規則，數值都集中在這個檔案，之後要調整
（例如改分數、改徽章門檻）都只需要改這裡，不用動流程邏輯。

故事線設定：每個學生是一位「氣候行動守護者」，靠每天累積的「能量」（積分）成長，
從幼苗一路長成氣候英雄；答題的連續天數則代表「行動不間斷」，斷了就得從頭累積。
"""

from datetime import date
from typing import Callable
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

CORRECT_POINTS = 10
INCORRECT_POINTS = 2  # 答錯仍給少量「參與能量」，鼓勵每天持續作答
ECO_CHECKIN_POINTS = 15  # 拍照打卡經老師審核通過後發放的能量，比答題略高以鼓勵實際行動

# (累積能量門檻, 稱號, 故事文案)，由低到高排列
RANKS: list[tuple[int, str, str]] = [
    (0, "🌱 幼苗守護者", "才剛踏上氣候行動的旅程，每一步都算數！"),
    (50, "🌿 綠芽行動家", "知識的嫩芽冒出來了，繼續每天累積能量！"),
    (150, "🌳 森林守護者", "你已經是守護森林的中堅力量！"),
    (300, "🌍 地球衛士", "你的行動正在為地球累積改變的力量！"),
    (600, "⭐ 氣候英雄", "傳說等級！你是氣候行動的英雄！"),
]

# (代碼, 顯示名稱, 說明, 判斷條件)；代碼會存進 Student.badges，判斷條件用來檢查是否應該解鎖
# stats 用 .get(..., 0) 讀取，因為答題流程跟打卡流程各自只會算出自己相關的統計數字
BADGES: list[tuple[str, str, str, Callable[[dict], bool]]] = [
    ("first_step", "🥾 踏出第一步", "完成第一次答題", lambda s: s.get("answered_count", 0) >= 1),
    ("first_correct", "🎯 首次命中", "第一次答對題目", lambda s: s.get("correct_count", 0) >= 1),
    ("streak_3", "🔥 三日不間斷", "連續 3 天回答", lambda s: s.get("current_streak", 0) >= 3),
    ("streak_7", "🔥 一週戰士", "連續 7 天回答", lambda s: s.get("current_streak", 0) >= 7),
    ("streak_30", "🔥 月度傳奇", "連續 30 天回答", lambda s: s.get("current_streak", 0) >= 30),
    ("knowledge_10", "📚 知識累積者", "累計答對 10 題", lambda s: s.get("correct_count", 0) >= 10),
    ("knowledge_30", "📚 氣候學者", "累計答對 30 題", lambda s: s.get("correct_count", 0) >= 30),
    ("points_300", "💎 行動力達人", "累積能量達 300", lambda s: s.get("total_points", 0) >= 300),
    ("eco_first", "🌎 環保初體驗", "第一次環保打卡通過審核", lambda s: s.get("eco_checkin_count", 0) >= 1),
    ("eco_10", "♻️ 環保達人", "累計 10 次環保打卡通過審核", lambda s: s.get("eco_checkin_count", 0) >= 10),
]

_BADGE_DISPLAY = {code: name for code, name, _desc, _check in BADGES}


def badge_display(code: str) -> str:
    return _BADGE_DISPLAY.get(code, code)


def current_rank(total_points: int) -> tuple[str, str]:
    """回傳目前稱號與故事文案（依累積能量取最高門檻）。"""
    name, flavor = RANKS[0][1], RANKS[0][2]
    for threshold, rank_name, flavor_text in RANKS:
        if total_points >= threshold:
            name, flavor = rank_name, flavor_text
    return name, flavor


def next_streak(previous_answer_date: date | None, today: date, current_streak: int) -> int:
    """依照上次答題日期決定今天答題後的連續天數。

    - 從沒答過：streak 從 1 開始
    - 上次就是今天：代表今天已經算過一次了，維持不變（同一天補答其他題不重複累計）
    - 上次是昨天：延續，+1
    - 中間斷過：從 1 重新開始
    """
    if previous_answer_date is None:
        return 1
    if previous_answer_date == today:
        return current_streak
    if (today - previous_answer_date).days == 1:
        return current_streak + 1
    return 1


def evaluate_new_badges(existing_codes: list[str], stats: dict) -> list[tuple[str, str]]:
    """回傳這次應該新解鎖的徽章 (代碼, 顯示名稱) 列表，已排除已擁有的。"""
    return [(code, name) for code, name, _desc, check in BADGES if code not in existing_codes and check(stats)]
