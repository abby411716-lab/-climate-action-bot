from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class School(Base):
    __tablename__ = "schools"

    school_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_name: Mapped[str] = mapped_column(String(200), nullable=False)
    join_link_code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    students: Mapped[list["Student"]] = relationship(back_populates="school")


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.school_id"), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    badges: Mapped[list] = mapped_column(JSON, default=list)

    school: Mapped["School | None"] = relationship(back_populates="students")
    answer_logs: Mapped[list["AnswerLog"]] = relationship(back_populates="student")
    assessment_responses: Mapped[list["AssessmentResponse"]] = relationship(back_populates="student")
    eco_checkins: Mapped[list["EcoCheckin"]] = relationship(back_populates="student")


class Question(Base):
    __tablename__ = "questions"

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_card_text: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_card_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    answer_logs: Mapped[list["AnswerLog"]] = relationship(back_populates="question")


class AnswerLog(Base):
    __tablename__ = "answer_logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.question_id"), nullable=False)
    selected_option: Mapped[str] = mapped_column(String(200), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student: Mapped["Student"] = relationship(back_populates="answer_logs")
    question: Mapped["Question"] = relationship(back_populates="answer_logs")


class DailyPush(Base):
    """每次「每日推送」實際送出的題目紀錄，用來決定下一次要推哪一題、避免同一天重複推送。"""

    __tablename__ = "daily_pushes"

    push_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.question_id"), unique=True, nullable=False)
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EcoCheckin(Base):
    """學生拍照打卡的環保行動，需經老師審核通過才會實際發放能量／徽章。"""

    __tablename__ = "eco_checkins"

    checkin_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"), nullable=False)
    line_message_id: Mapped[str] = mapped_column(String(100), nullable=False)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    image_mime: Mapped[str] = mapped_column(String(50), default="image/jpeg")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / approved / rejected
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped["Student"] = relationship(back_populates="eco_checkins")


class AssessmentResponse(Base):
    """學生對某一輪成效評估問卷（baseline／midterm／posttest）的回答。

    問卷本身沒有標準答案（自我評估／態度／行為題），跟每日測驗的客觀對錯（answer_logs）
    是分開的兩種資料，所以這裡不像 Question 那樣有 correct_option／score 的概念，
    全部題目的回答都存在 responses 這個 JSON 欄位裡，key 是題目代碼（見 app/assessment_questions.py）。
    """

    __tablename__ = "assessment_responses"
    __table_args__ = (UniqueConstraint("student_id", "assessment_round", name="uq_assessment_student_round"),)

    response_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"), nullable=False)
    assessment_round: Mapped[str] = mapped_column(String(50), nullable=False)
    responses: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student: Mapped["Student"] = relationship(back_populates="assessment_responses")
