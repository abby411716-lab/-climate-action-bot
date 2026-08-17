"""拍照打卡（環保行動）的圖片壓縮與審核核發邏輯。"""

import io

from PIL import Image
from sqlalchemy.orm import Session

from app import crud, game_rules, models


def compress_image(data: bytes, max_side: int = 1000, quality: int = 70) -> bytes:
    """打卡照片統一壓縮成 JPEG 後才存進資料庫，避免占用過多儲存空間。"""
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def approve_checkin(
    db: Session, checkin: models.EcoCheckin, points: int = game_rules.ECO_CHECKIN_POINTS
) -> tuple[models.Student, list[tuple[str, str]]]:
    """老師審核通過：發放能量、檢查是否解鎖新徽章（不影響每日答題的連續天數）。"""
    student = crud.get_student_by_id(db, checkin.student_id)
    crud.finalize_eco_checkin(db, checkin, status="approved", points_awarded=points)

    new_points = student.total_points + points
    stats = {
        "total_points": new_points,
        "current_streak": student.current_streak,
        "eco_checkin_count": crud.count_approved_checkins(db, student.student_id),
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
    return student, new_badges


def reject_checkin(db: Session, checkin: models.EcoCheckin) -> None:
    crud.finalize_eco_checkin(db, checkin, status="rejected", points_awarded=0)
