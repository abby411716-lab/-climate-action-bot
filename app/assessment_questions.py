"""成效評估問卷（LIFF 表單）的題目定義與驗證邏輯。

問卷分三輪：baseline（前測，9/14 那週）／midterm（中測，10/12 那週，跟 Round2
第一天同步發送）／posttest（後測，11/3 那週）。核心題三輪都問（拿來畫出同一個
學生的前中後變化曲線），少數題目只在特定輪次出現，詳見下方 ROUNDS。

題目內容改編自使用者提供的「青少年氣候行為調查」問卷（教育部青年發展署 Young
飛計畫），拿掉了完全客觀對錯的知識題（每日測驗 answer_logs 已經在記錄這塊），
專注在每日測驗測不到的自我覺察／態度／行為／動機。
"""

from typing import Any, Literal

QuestionType = Literal["single_choice", "multi_choice", "scale", "short_text"]

# ---- 共用選項 ----

_KNOWN_CONCEPTS_OPTIONS = [
    ("warming_greenhouse", "全球暖化/溫室效應"),
    ("carbon_neutral", "碳中和/淨零排放"),
    ("carbon_footprint", "碳足跡計算"),
    ("biochar_pyrolysis", "生物碳/熱裂解技術"),
    ("natural_carbon_sink", "自然碳匯"),
    ("paris_agreement", "巴黎協定/1.5度降溫目標"),
    ("none_familiar", "以上都不太清楚"),
]

_EMOTIONS_OPTIONS = [
    ("anxious", "焦慮"),
    ("nervous", "緊張"),
    ("afraid", "害怕"),
    ("helpless", "無助"),
    ("sad", "傷心"),
    ("curious", "好奇"),
    ("hopeful", "充滿希望"),
    ("numb", "無感"),
    ("none", "以上皆無"),
]

_RECENT_ACTIONS_OPTIONS = [
    ("reduce_plastic", "主動減少一次性塑膠使用"),
    ("walk_bike_transit", "選擇步行、腳踏車或大眾交通運輸工具"),
    ("share_online", "網路分享、倡議氣候資訊"),
    ("join_activities", "參加環境友善活動、社團"),
    ("encourage_family", "鼓勵家人朋友相關環保行為"),
    ("waste_sorting", "參與垃圾分類、廚餘堆肥"),
    ("organic_waste_awareness", "注意過校園或家中的有機廢棄物去哪裡（落葉、廚餘、枯枝）"),
    ("researched_carbon", "查詢過碳足跡、碳匯或固碳相關知識"),
    ("none", "以上皆無"),
]

_MOTIVATOR_OPTIONS = [
    ("science_data", "看到科學數據，知道自己的行動有真實效果"),
    ("peers_acting", "身邊的朋友也一起行動"),
    ("guided_by_someone", "有人帶領我、告訴我具體怎麼做"),
    ("pioneer_feeling", "知道自己是第一批這樣做的人（先驅感）"),
    ("recognition", "獲得某種認可或成就感（證書、紀錄）"),
]

# ---- 題目定義：key -> 題目設定 ----
# scale 題一律是 1~5，low_label/high_label 是量表兩端的文字

QUESTION_DEFS: dict[str, dict[str, Any]] = {
    "grade": {
        "type": "single_choice",
        "text": "你目前就讀幾年級？",
        "options": [("grade10", "高一"), ("grade11", "高二"), ("grade12", "高三")],
    },
    "gender": {
        "type": "single_choice",
        "text": "你的性別認同",
        "options": [
            ("male", "男性"),
            ("female", "女性"),
            ("nonbinary_other", "非二元性別/其他"),
            ("prefer_not", "不願透漏"),
        ],
    },
    "climate_understanding": {
        "type": "scale",
        "text": "你認為你對「氣候變遷」的了解程度如何？",
        "low_label": "完全不了解",
        "high_label": "非常了解",
    },
    "known_concepts": {
        "type": "multi_choice",
        "text": "以下哪些概念你已有基本了解？（可複選）",
        "options": _KNOWN_CONCEPTS_OPTIONS,
    },
    "biochar_familiarity": {
        "type": "single_choice",
        "text": "你是否聽過「生物碳（Biochar）」這個詞？",
        "options": [
            ("first_time", "第一次聽到"),
            ("heard_unclear", "聽過，不清楚"),
            ("roughly_know", "大概知道，能簡單說明"),
            ("clear", "清楚，了解原理"),
        ],
    },
    "emotions": {
        "type": "multi_choice",
        "text": "當你想到氣候變遷時，你最常出現的感受是什麼？（可選最多 3 項）",
        "options": _EMOTIONS_OPTIONS,
        "max_select": 3,
    },
    "action_efficacy": {
        "type": "scale",
        "text": "你相信「個人行動」能對氣候變遷產生實質影響的程度？",
        "low_label": "完全不相信",
        "high_label": "非常相信",
    },
    "future_optimism": {
        "type": "scale",
        "text": "你對未來氣候問題能被解決的希望感有多高？",
        "low_label": "非常悲觀",
        "high_label": "非常樂觀",
    },
    "recent_actions": {
        "type": "multi_choice",
        "text": "過去三個月，你做過哪些與環境相關的行動？（可複選）",
        "text_by_round": {
            "midterm": "從這學期參加計畫以來，你做過哪些與環境相關的行動？（可複選）",
            "posttest": "從這學期參加計畫以來，你做過哪些與環境相關的行動？（可複選）",
        },
        "options": _RECENT_ACTIONS_OPTIONS,
    },
    "action_frequency": {
        "type": "single_choice",
        "text": "承上題，你勾選的行動中，大多數的執行頻率是？",
        "options": [
            ("tried_once", "試過一兩次，沒有持續"),
            ("occasional", "偶爾（一個月幾次）"),
            ("weekly_habit", "固定習慣（每週都會做）"),
            ("automatic_habit", "已經成習慣，不需要特別提醒"),
        ],
    },
    "action_social_context": {
        "type": "single_choice",
        "text": "承上題，你做這些環境行動時，通常是？",
        "options": [
            ("alone", "一個人默默做，不會特別說"),
            ("tell_not_together", "會跟家人或朋友說，但不是一起行動"),
            ("with_friends", "和朋友或同學一起行動"),
            ("led_by_adult", "在老師或大人的帶領下才會做"),
            ("self_initiated", "我自己發起，帶動別人一起"),
        ],
    },
    "willingness_to_participate": {
        "type": "scale",
        "text": "如果有一個具體、可操作的方法讓你能參與環保固碳行動，你願意投入的意願有多高？",
        "low_label": "完全不願意",
        "high_label": "非常願意",
    },
    "barriers": {
        "type": "multi_choice",
        "text": "哪些因素讓你「難以採取更多氣候行動」？（可選最多 3 項）",
        "options": [
            ("no_idea_where", "不知從何開始"),
            ("effort_too_small", "一己之力太小"),
            ("lack_of_time", "缺乏時間精力"),
            ("peers_not_interested", "周遭人群不關注"),
            ("lack_of_resources", "沒有資源、機會、管道"),
            ("feel_ineffective", "覺得環保行為沒有效果"),
            ("other", "其他"),
        ],
        "max_select": 3,
    },
    "top_motivators": {
        "type": "multi_choice",
        "text": "最能激勵你行動的是什麼？（可選最多 2 項）",
        "options": _MOTIVATOR_OPTIONS,
        "max_select": 2,
    },
    "actual_motivators": {
        "type": "multi_choice",
        "text": "這學期下來，實際上真正讓你採取行動的是什麼？（可選最多 2 項）",
        "options": _MOTIVATOR_OPTIONS,
        "max_select": 2,
    },
    "program_helpfulness": {
        "type": "scale",
        "text": "活動整體來說，線上學習計畫（比歐小助教功能）對你的氣候行動有多少幫助？",
        "low_label": "完全沒幫助",
        "high_label": "非常有幫助",
    },
    "self_perceived_growth": {
        "type": "scale",
        "text": "跟活動開始前比，你覺得自己在氣候知識/行動上進步了多少？",
        "low_label": "沒有進步",
        "high_label": "進步很多",
    },
    "would_recommend": {
        "type": "scale",
        "text": "你會推薦同學參加這個計畫嗎？",
        "low_label": "完全不會",
        "high_label": "非常會",
    },
    "most_memorable": {
        "type": "short_text",
        "text": "這學期印象最深的一件事或一個知識點是？（選填）",
        "required": False,
        "max_length": 200,
    },
}

_CORE_KEYS = [
    "climate_understanding",
    "known_concepts",
    "biochar_familiarity",
    "emotions",
    "action_efficacy",
    "future_optimism",
    "recent_actions",
    "action_frequency",
    "action_social_context",
    "willingness_to_participate",
]

# 核心題裡只有量表題（1~5 分）有數值大小可以比較，適合拿來畫「前中後測變化」折線圖；
# 單選/多選題沒有數值意義，維持原本的文字列表呈現（見 teacher_dashboard.describe_assessment_response）。
CORE_SCALE_KEYS = [k for k in _CORE_KEYS if QUESTION_DEFS[k]["type"] == "scale"]

ROUND_LABELS = {"baseline": "前測", "midterm": "中測", "posttest": "後測"}

ROUNDS: dict[str, list[str]] = {
    "baseline": ["grade", "gender", *_CORE_KEYS, "barriers", "top_motivators"],
    "midterm": [*_CORE_KEYS, "barriers", "top_motivators"],
    "posttest": [
        *_CORE_KEYS,
        "actual_motivators",
        "program_helpfulness",
        "self_perceived_growth",
        "most_memorable",
        "would_recommend",
    ],
}


def get_questions_for_round(assessment_round: str) -> list[dict[str, Any]]:
    """回傳某一輪要顯示的題目清單，每題附上該輪次專用的題目文字。"""
    keys = ROUNDS.get(assessment_round)
    if keys is None:
        raise ValueError(f"未知的 assessment_round: {assessment_round}")

    questions = []
    for key in keys:
        q = dict(QUESTION_DEFS[key])
        text_by_round = q.pop("text_by_round", None)
        if text_by_round and assessment_round in text_by_round:
            q["text"] = text_by_round[assessment_round]
        q["key"] = key
        questions.append(q)
    return questions


class ValidationError(Exception):
    pass


def validate_answers(assessment_round: str, answers: dict[str, Any]) -> dict[str, Any]:
    """驗證並回傳整理過的回答（只保留該輪次題目對應的 key）。answers 格式不合法就丟 ValidationError。"""
    questions = get_questions_for_round(assessment_round)
    cleaned: dict[str, Any] = {}

    for q in questions:
        key = q["key"]
        required = q.get("required", True)
        value = answers.get(key)

        if value in (None, "", []):
            if required:
                raise ValidationError(f"「{q['text']}」為必填")
            continue

        if q["type"] == "single_choice":
            valid_values = {v for v, _ in q["options"]}
            if value not in valid_values:
                raise ValidationError(f"「{q['text']}」的答案不合法")
            cleaned[key] = value

        elif q["type"] == "multi_choice":
            if not isinstance(value, list) or not value:
                raise ValidationError(f"「{q['text']}」為必填")
            valid_values = {v for v, _ in q["options"]}
            if not set(value).issubset(valid_values):
                raise ValidationError(f"「{q['text']}」的答案不合法")
            max_select = q.get("max_select")
            if max_select and len(value) > max_select:
                raise ValidationError(f"「{q['text']}」最多只能選 {max_select} 項")
            cleaned[key] = value

        elif q["type"] == "scale":
            try:
                int_value = int(value)
            except (TypeError, ValueError):
                raise ValidationError(f"「{q['text']}」的答案不合法")
            if not 1 <= int_value <= 5:
                raise ValidationError(f"「{q['text']}」的答案不合法")
            cleaned[key] = int_value

        elif q["type"] == "short_text":
            text_value = str(value).strip()[: q.get("max_length", 200)]
            cleaned[key] = text_value

    return cleaned
