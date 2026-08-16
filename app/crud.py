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
