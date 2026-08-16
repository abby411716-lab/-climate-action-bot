from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
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
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    badges: Mapped[list] = mapped_column(JSON, default=list)

    school: Mapped["School | None"] = relationship(back_populates="students")
    answer_logs: Mapped[list["AnswerLog"]] = relationship(back_populates="student")
    assessment_responses: Mapped[list["AssessmentResponse"]] = relationship(back_populates="student")


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


class AssessmentResponse(Base):
    __tablename__ = "assessment_responses"

    response_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"), nullable=False)
    assessment_round: Mapped[str] = mapped_column(String(50), nullable=False)
    knowledge_score: Mapped[int] = mapped_column(Integer, nullable=False)
    action_responses: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    student: Mapped["Student"] = relationship(back_populates="assessment_responses")
