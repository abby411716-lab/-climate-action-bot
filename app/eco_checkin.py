"""拍照打卡（環保行動）的圖片壓縮與審核核發邏輯。"""

import io

from linebot.v3.messaging import PushMessageRequest, TextMessage
from PIL import Image
from sqlalchemy.orm import Session

from app import crud, game_rules, models
from app.line_client import get_messaging_api


def compress_image(data: bytes, max_side: int = 1000, quality: int = 70) -> bytes:
    """打卡照片統一壓縮成 JPEG 後才存進資料庫，避免占用過多儲存空間。"""
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def approve_checkin(
    db: Session,
    checkin: models.EcoCheckin,
    points: int = game_rules.ECO_CHECKIN_POINTS,
    reviewed_by: str | None = None,
) -> tuple[models.Student, list[tuple[str, str]]]:
    """老師審核通過：發放能量、檢查是否解鎖新徽章（不影響每日答題的連續天數）。"""
    student = crud.get_student_by_id(db, checkin.student_id)
    crud.finalize_eco_checkin(db, checkin, status="approved", points_awarded=points, reviewed_by=reviewed_by)

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


def reject_checkin(db: Session, checkin: models.EcoCheckin, reviewed_by: str | None = None) -> None:
    crud.finalize_eco_checkin(db, checkin, status="rejected", points_awarded=0, reviewed_by=reviewed_by)


def notify_checkin_approved(student: models.Student, points: int, new_badges: list[tuple[str, str]]) -> None:
    lines = [f"✅ 你的環保打卡通過審核囉！+{points} 能量", f"目前能量：{student.total_points}"]
    if new_badges:
        lines.append("\n".join(f"🏅 解鎖新徽章：{name}" for _code, name in new_badges))
    api = get_messaging_api()
    api.push_message(PushMessageRequest(to=student.line_user_id, messages=[TextMessage(text="\n\n".join(lines))]))


def notify_checkin_rejected(student: models.Student) -> None:
    api = get_messaging_api()
    api.push_message(
        PushMessageRequest(
            to=student.line_user_id,
            messages=[TextMessage(text="很抱歉，這張環保打卡照片沒有通過審核，要不要再試一次呢？📸")],
        )
    )
