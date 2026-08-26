"""教師後台頁面用的統計彙整邏輯，集中在這裡讓 app/routers/teacher.py 只處理路由與畫面渲染。"""

from collections import Counter

from sqlalchemy.orm import Session

from app import assessment_questions, carbon_footprint, crud, models


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
