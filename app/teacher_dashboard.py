"""教師後台頁面用的統計彙整邏輯，集中在這裡讓 app/routers/teacher.py 只處理路由與畫面渲染。"""

from collections import Counter

from sqlalchemy.orm import Session

from app import assessment_questions, carbon_footprint, crud, models

# 個別學生頁「前中後測變化」小圖表的固定版面座標（SVG viewBox 尺寸）。
# 只有這四題（CORE_SCALE_KEYS）是三輪都問的量表題，1~5 分才有數值可以連成折線；
# 其他核心題是單選/多選，沒有大小可言，維持原本的文字列表呈現。
TREND_ROUNDS = ["baseline", "midterm", "posttest"]
_CHART_W, _CHART_H = 200, 130
_PLOT_LEFT, _PLOT_RIGHT = 20, 180
_PLOT_TOP, _PLOT_BOTTOM = 30, 96
_X_POSITIONS = [_PLOT_LEFT, (_PLOT_LEFT + _PLOT_RIGHT) // 2, _PLOT_RIGHT]

TREND_CHART_META = {
    "w": _CHART_W,
    "h": _CHART_H,
    "plot_left": _PLOT_LEFT,
    "plot_right": _PLOT_RIGHT,
    "plot_bottom": _PLOT_BOTTOM,
}


def _value_to_y(value: int) -> float:
    return _PLOT_TOP + (5 - value) / 4 * (_PLOT_BOTTOM - _PLOT_TOP)


_MISSING_Y = (_PLOT_TOP + _PLOT_BOTTOM) / 2  # 缺考的輪次畫在垂直置中，避免誤讀成「接近 1 分」

TREND_CHART_META["grid_ys"] = [round(_value_to_y(v), 1) for v in (5, 3, 1)]


def overview_stats(db: Session) -> dict:
    schools = crud.list_schools(db)
    school_rows = []
    for school in schools:
        students = crud.list_students(db, school_id=school.school_id)
        registered = [s for s in students if s.nickname]
        avg_points = round(sum(s.total_points for s in students) / len(students), 1) if students else 0
        school_rows.append(
            {
                "school": school,
                "student_count": len(students),
                "registered_count": len(registered),
                "avg_points": avg_points,
            }
        )

    return {
        "total_students": crud.count_students(db),
        "school_rows": school_rows,
        "pending_checkins": len(crud.list_eco_checkins(db, status="pending")),
        "assessment_counts": [
            {"round": r, "label": label, "count": len(crud.list_assessment_responses(db, r))}
            for r, label in assessment_questions.ROUND_LABELS.items()
        ],
        "carbon_footprint_count": len(crud.list_carbon_footprint_responses(db)),
    }


def question_stats(db: Session, question: models.Question) -> dict:
    logs = crud.list_answer_logs_for_question(db, question.question_id)
    total = len(logs)
    correct = sum(1 for log in logs if log.is_correct)
    option_counts = Counter(log.selected_option for log in logs)
    options = [
        {"text": opt, "count": option_counts.get(opt, 0), "is_correct": opt == question.correct_option}
        for opt in question.options
    ]
    return {
        "question": question,
        "total_answered": total,
        "correct_count": correct,
        "accuracy": round(correct / total * 100, 1) if total else None,
        "options": options,
    }


def assessment_round_stats(db: Session, assessment_round: str) -> dict:
    responses = crud.list_assessment_responses(db, assessment_round)
    questions = assessment_questions.get_questions_for_round(assessment_round)

    scale_summaries = []
    open_text_answers = []
    for q in questions:
        key = q["key"]
        if q["type"] == "scale":
            values = [r.responses[key] for r in responses if key in r.responses]
            scale_summaries.append(
                {
                    "text": q["text"],
                    "low_label": q["low_label"],
                    "high_label": q["high_label"],
                    "average": round(sum(values) / len(values), 2) if values else None,
                    "count": len(values),
                }
            )
        elif q["type"] == "short_text":
            for r in responses:
                text = r.responses.get(key)
                if text:
                    open_text_answers.append({"question_text": q["text"], "text": text})

    return {
        "round": assessment_round,
        "round_label": assessment_questions.ROUND_LABELS[assessment_round],
        "response_count": len(responses),
        "scale_summaries": scale_summaries,
        "open_text_answers": open_text_answers,
    }


def carbon_footprint_stats(db: Session) -> dict:
    responses = crud.list_carbon_footprint_responses(db)

    level_counts: dict[str, int] = {}
    rows = []
    for r in responses:
        level_name, _flavor = carbon_footprint.current_level(r.green_score)
        level_counts[level_name] = level_counts.get(level_name, 0) + 1
        rows.append(
            {
                "student": crud.get_student_by_id(db, r.student_id),
                "green_score": r.green_score,
                "level_name": level_name,
                "submitted_at": r.submitted_at,
                "updated_at": r.updated_at,
            }
        )
    rows.sort(key=lambda row: row["green_score"], reverse=True)

    return {
        "response_count": len(responses),
        "avg_score": round(sum(r.green_score for r in responses) / len(responses), 1) if responses else None,
        "level_counts": level_counts,
        "rows": rows,
    }


def describe_carbon_footprint_response(response: models.CarbonFootprintResponse) -> list[dict]:
    """把碳足跡計算器的原始回答（存的是選項代碼）轉成人看得懂的文字，給個別學生頁顯示用。"""
    label_maps = {q["key"]: {v: l for v, l, _p in q["options"]} for q in carbon_footprint.QUESTIONS}
    described = []
    for q in carbon_footprint.QUESTIONS:
        key = q["key"]
        if key not in response.responses:
            continue
        value = response.responses[key]
        described.append({"category": q["category"], "text": q["text"], "answer": label_maps[key].get(value, value)})
    return described


def student_assessment_trend(db: Session, student_id: int) -> list[dict]:
    """把學生三輪問卷裡的核心量表題整理成「前中後測變化」折線圖的座標資料。

    每題回傳三個點（baseline/midterm/posttest），缺考的輪次 value 是 None、
    y 座標退回畫在底部（模板畫成空心點＋「－」，不連線到相鄰的點，避免暗示
    一個不存在的數值）。segments 只包含兩端都有作答的相鄰點，缺考處線段自然斷開。
    """
    responses = {r.assessment_round: r.responses for r in crud.list_assessment_responses_for_student(db, student_id)}

    charts = []
    for key in assessment_questions.CORE_SCALE_KEYS:
        q = assessment_questions.QUESTION_DEFS[key]
        points = []
        for round_name, x in zip(TREND_ROUNDS, _X_POSITIONS):
            round_responses = responses.get(round_name)
            value = round_responses.get(key) if round_responses else None
            points.append(
                {
                    "round_label": assessment_questions.ROUND_LABELS[round_name],
                    "value": value,
                    "x": x,
                    "y": _value_to_y(value) if value is not None else _MISSING_Y,
                }
            )

        if not any(p["value"] is not None for p in points):
            continue

        segments = [
            f"{points[i]['x']},{points[i]['y']:.1f} {points[i + 1]['x']},{points[i + 1]['y']:.1f}"
            for i in range(len(points) - 1)
            if points[i]["value"] is not None and points[i + 1]["value"] is not None
        ]

        charts.append(
            {
                "text": q["text"],
                "low_label": q["low_label"],
                "high_label": q["high_label"],
                "points": points,
                "segments": segments,
            }
        )
    return charts


def describe_assessment_response(assessment_round: str, responses: dict) -> list[dict]:
    """把某一輪問卷的原始回答（存的是選項代碼）轉成人看得懂的文字，給個別學生頁顯示用。"""
    questions = assessment_questions.get_questions_for_round(assessment_round)
    described = []
    for q in questions:
        key = q["key"]
        if key not in responses:
            continue
        value = responses[key]
        if q["type"] in ("single_choice", "multi_choice"):
            label_map = dict(q["options"])
            if isinstance(value, list):
                display = "、".join(label_map.get(v, v) for v in value)
            else:
                display = label_map.get(value, value)
        elif q["type"] == "scale":
            display = f"{value} / 5"
        else:
            display = value
        described.append({"text": q["text"], "answer": display})
    return described
