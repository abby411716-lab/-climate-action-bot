from datetime import date

from sqlalchemy.orm import Session

from app import models


def get_school_by_join_code(db: Session, join_link_code: str) -> models.School | None:
    return db.query(models.School).filter(models.School.join_link_code == join_link_code).first()


def get_school_by_id(db: Session, school_id: int) -> models.School | None:
    return db.query(models.School).filter(models.School.school_id == school_id).first()


def list_schools(db: Session) -> list[models.School]:
    return db.query(models.School).order_by(models.School.school_id).all()


def get_student_by_line_id(db: Session, line_user_id: str) -> models.Student | None:
    return db.query(models.Student).filter(models.Student.line_user_id == line_user_id).first()


def create_student(db: Session, line_user_id: str, school_id: int | None = None) -> models.Student:
    student = models.Student(line_user_id=line_user_id, school_id=school_id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def set_student_school(db: Session, student: models.Student, school_id: int) -> models.Student:
    student.school_id = school_id
    db.commit()
    db.refresh(student)
    return student


def get_or_create_student(db: Session, line_user_id: str, school_id: int | None = None) -> models.Student:
    student = get_student_by_line_id(db, line_user_id)
    if student is None:
        student = create_student(db, line_user_id, school_id)
    return student


def get_student_by_id(db: Session, student_id: int) -> models.Student | None:
    return db.query(models.Student).filter(models.Student.student_id == student_id).first()


def set_student_nickname(db: Session, student: models.Student, nickname: str) -> models.Student:
    student.nickname = nickname
    db.commit()
    db.refresh(student)
    return student


def get_leaderboard(db: Session, school_id: int, limit: int = 10) -> list[models.Student]:
    return (
        db.query(models.Student)
        .filter(models.Student.school_id == school_id, models.Student.nickname.isnot(None))
        .order_by(models.Student.total_points.desc())
        .limit(limit)
        .all()
    )


def list_students(db: Session, school_id: int | None = None) -> list[models.Student]:
    query = db.query(models.Student)
    if school_id is not None:
        query = query.filter(models.Student.school_id == school_id)
    return query.order_by(models.Student.total_points.desc()).all()


def count_students(db: Session, school_id: int | None = None) -> int:
    query = db.query(models.Student)
    if school_id is not None:
        query = query.filter(models.Student.school_id == school_id)
    return query.count()


def list_answer_logs_for_student(db: Session, student_id: int) -> list[models.AnswerLog]:
    return (
        db.query(models.AnswerLog)
        .filter(models.AnswerLog.student_id == student_id)
        .order_by(models.AnswerLog.answered_at.desc())
        .all()
    )


def list_eco_checkins_for_student(db: Session, student_id: int) -> list[models.EcoCheckin]:
    return (
        db.query(models.EcoCheckin)
        .filter(models.EcoCheckin.student_id == student_id)
        .order_by(models.EcoCheckin.submitted_at.desc())
        .all()
    )


def list_assessment_responses_for_student(db: Session, student_id: int) -> list[models.AssessmentResponse]:
    return (
        db.query(models.AssessmentResponse)
        .filter(models.AssessmentResponse.student_id == student_id)
        .all()
    )


def create_eco_checkin(
    db: Session, student_id: int, line_message_id: str, image_data: bytes, image_mime: str
) -> models.EcoCheckin:
    checkin = models.EcoCheckin(
        student_id=student_id,
        line_message_id=line_message_id,
        image_data=image_data,
        image_mime=image_mime,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


def get_eco_checkin_by_id(db: Session, checkin_id: int) -> models.EcoCheckin | None:
    return db.query(models.EcoCheckin).filter(models.EcoCheckin.checkin_id == checkin_id).first()


def list_eco_checkins(db: Session, status: str | None = None) -> list[models.EcoCheckin]:
    query = db.query(models.EcoCheckin)
    if status:
        query = query.filter(models.EcoCheckin.status == status)
    return query.order_by(models.EcoCheckin.submitted_at.desc()).all()


def count_approved_checkins(db: Session, student_id: int) -> int:
    return (
        db.query(models.EcoCheckin)
        .filter(models.EcoCheckin.student_id == student_id, models.EcoCheckin.status == "approved")
        .count()
    )


def finalize_eco_checkin(
    db: Session, checkin: models.EcoCheckin, *, status: str, points_awarded: int
) -> models.EcoCheckin:
    checkin.status = status
    checkin.points_awarded = points_awarded
    checkin.reviewed_at = models.utcnow()
    db.commit()
    db.refresh(checkin)
    return checkin


def get_question_by_id(db: Session, question_id: int) -> models.Question | None:
    return db.query(models.Question).filter(models.Question.question_id == question_id).first()


def list_questions(db: Session) -> list[models.Question]:
    return (
        db.query(models.Question)
        .order_by(models.Question.scheduled_date.is_(None), models.Question.scheduled_date, models.Question.question_id)
        .all()
    )


def list_answer_logs_for_question(db: Session, question_id: int) -> list[models.AnswerLog]:
    return db.query(models.AnswerLog).filter(models.AnswerLog.question_id == question_id).all()


def get_next_unpushed_question(db: Session, today: date) -> models.Question | None:
    """取出「排定日期已到（scheduled_date <= today）、但還沒推送過」的下一題。

    沒有設定 scheduled_date 的題目不會被自動排程選到（例如 scripts/seed_question.py 建的測試題）。
    用 <= 而不是 == 是為了在服務曾經漏推（例如 Render 休眠跳過某一天）時能自動補推，
    同時排定日期落在週末／空檔週的日子會自然選不到題目而跳過，不需要另外判斷平假日。
    """
    pushed_ids = db.query(models.DailyPush.question_id)
    return (
        db.query(models.Question)
        .filter(~models.Question.question_id.in_(pushed_ids))
        .filter(models.Question.scheduled_date.isnot(None))
        .filter(models.Question.scheduled_date <= today)
        .order_by(models.Question.scheduled_date, models.Question.question_id)
        .first()
    )


def get_latest_daily_push(db: Session) -> models.DailyPush | None:
    return db.query(models.DailyPush).order_by(models.DailyPush.pushed_at.desc()).first()


def record_daily_push(db: Session, question_id: int) -> models.DailyPush:
    push = models.DailyPush(question_id=question_id)
    db.add(push)
    db.commit()
    db.refresh(push)
    return push


def get_answer_log(db: Session, student_id: int, question_id: int) -> models.AnswerLog | None:
    return (
        db.query(models.AnswerLog)
        .filter(models.AnswerLog.student_id == student_id, models.AnswerLog.question_id == question_id)
        .first()
    )


def get_latest_answer_log(db: Session, student_id: int) -> models.AnswerLog | None:
    return (
        db.query(models.AnswerLog)
        .filter(models.AnswerLog.student_id == student_id)
        .order_by(models.AnswerLog.answered_at.desc())
        .first()
    )


def count_correct_answers(db: Session, student_id: int) -> int:
    return (
        db.query(models.AnswerLog)
        .filter(models.AnswerLog.student_id == student_id, models.AnswerLog.is_correct.is_(True))
        .count()
    )


def count_answers(db: Session, student_id: int) -> int:
    return db.query(models.AnswerLog).filter(models.AnswerLog.student_id == student_id).count()


def create_answer_log(
    db: Session, student_id: int, question_id: int, selected_option: str, is_correct: bool
) -> models.AnswerLog:
    log = models.AnswerLog(
        student_id=student_id,
        question_id=question_id,
        selected_option=selected_option,
        is_correct=is_correct,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def upsert_assessment_response(
    db: Session, student: models.Student, assessment_round: str, responses: dict
) -> models.AssessmentResponse:
    """新增或覆蓋（同一學生同一輪次只留一筆，重填會覆蓋掉舊答案）某一輪問卷的回答。"""
    existing = (
        db.query(models.AssessmentResponse)
        .filter(
            models.AssessmentResponse.student_id == student.student_id,
            models.AssessmentResponse.assessment_round == assessment_round,
        )
        .first()
    )
    if existing:
        existing.responses = responses
        db.commit()
        db.refresh(existing)
        return existing

    response = models.AssessmentResponse(
        student_id=student.student_id, assessment_round=assessment_round, responses=responses
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


def list_assessment_responses(db: Session, assessment_round: str) -> list[models.AssessmentResponse]:
    return (
        db.query(models.AssessmentResponse)
        .filter(models.AssessmentResponse.assessment_round == assessment_round)
        .all()
    )


def save_student_progress(
    db: Session,
    student: models.Student,
    *,
    total_points: int,
    current_streak: int,
    longest_streak: int,
    badges: list[str],
) -> models.Student:
    student.total_points = total_points
    student.current_streak = current_streak
    student.longest_streak = longest_streak
    student.badges = badges
    db.commit()
    db.refresh(student)
    return student
