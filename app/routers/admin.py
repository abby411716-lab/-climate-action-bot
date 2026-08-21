from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from linebot.v3.messaging import PushMessageRequest, TextMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import assessment_questions, crud, eco_checkin, game_rules
from app.assessment import broadcast_assessment_invite
from app.config import settings
from app.daily_push import push_daily_question
from app.database import get_db
from app.line_client import get_messaging_api

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_key(x_admin_key: str = Header(default="")):
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


class SchoolCreate(BaseModel):
    school_name: str
    join_link_code: str


@router.post("/schools", dependencies=[Depends(require_admin_key)])
def create_school(payload: SchoolCreate, db: Session = Depends(get_db)):
    existing = crud.get_school_by_join_code(db, payload.join_link_code)
    if existing:
        return {"school_id": existing.school_id, "school_name": existing.school_name, "already_existed": True}

    from app import models

    school = models.School(school_name=payload.school_name, join_link_code=payload.join_link_code)
    db.add(school)
    db.commit()
    db.refresh(school)
    return {"school_id": school.school_id, "school_name": school.school_name, "already_existed": False}


@router.get("/schools", dependencies=[Depends(require_admin_key)])
def list_schools(db: Session = Depends(get_db)):
    return [
        {"school_id": s.school_id, "school_name": s.school_name, "join_link_code": s.join_link_code}
        for s in crud.list_schools(db)
    ]


class SchoolUpdate(BaseModel):
    school_name: str


@router.patch("/schools/{school_id}", dependencies=[Depends(require_admin_key)])
def update_school(school_id: int, payload: SchoolUpdate, db: Session = Depends(get_db)):
    school = crud.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    school.school_name = payload.school_name
    db.commit()
    db.refresh(school)
    return {"school_id": school.school_id, "school_name": school.school_name}


@router.post("/push-daily", dependencies=[Depends(require_admin_key)])
def trigger_daily_push(force: bool = False):
    """手動觸發一次每日推送，測試用（正式排程見 app/scheduler.py，每天 08:00 Asia/Taipei 自動執行）。"""
    push_daily_question(force=force)
    return {"status": "triggered", "force": force}


@router.post("/push-assessment", dependencies=[Depends(require_admin_key)])
def trigger_assessment_push(round: str):
    """廣播成效評估問卷連結給所有好友。round 傳 baseline / midterm / posttest。"""
    if round not in assessment_questions.ROUNDS:
        raise HTTPException(status_code=400, detail="round 必須是 baseline / midterm / posttest")
    broadcast_assessment_invite(round)
    return {"status": "triggered", "round": round}


@router.get("/checkins", dependencies=[Depends(require_admin_key)])
def list_checkins(status: str | None = None, db: Session = Depends(get_db)):
    """列出環保打卡照片，status 可傳 pending / approved / rejected 篩選，不傳則全部列出。"""
    checkins = crud.list_eco_checkins(db, status=status)
    result = []
    for c in checkins:
        student = crud.get_student_by_id(db, c.student_id)
        result.append(
            {
                "checkin_id": c.checkin_id,
                "student_id": c.student_id,
                "nickname": student.nickname if student else None,
                "school_id": student.school_id if student else None,
                "status": c.status,
                "submitted_at": c.submitted_at,
                "image_url": f"/admin/checkins/{c.checkin_id}/image",
            }
        )
    return result


@router.get("/checkins/{checkin_id}/image")
def get_checkin_image(
    checkin_id: int,
    admin_key: str = "",
    x_admin_key: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """給老師在瀏覽器直接開圖用，所以除了 Header 也接受網址參數帶 admin_key（僅限這個內部審核用途）。"""
    key = x_admin_key or admin_key
    if not settings.admin_api_key or key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    checkin = crud.get_eco_checkin_by_id(db, checkin_id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Checkin not found")
    return Response(content=checkin.image_data, media_type=checkin.image_mime)


@router.post("/checkins/{checkin_id}/approve", dependencies=[Depends(require_admin_key)])
def approve_checkin(checkin_id: int, points: int = game_rules.ECO_CHECKIN_POINTS, db: Session = Depends(get_db)):
    checkin = crud.get_eco_checkin_by_id(db, checkin_id)
    if not checkin or checkin.status != "pending":
        raise HTTPException(status_code=404, detail="Checkin not found or already reviewed")

    student, new_badges = eco_checkin.approve_checkin(db, checkin, points=points)

    lines = [f"✅ 你的環保打卡通過審核囉！+{points} 能量", f"目前能量：{student.total_points}"]
    if new_badges:
        lines.append("\n".join(f"🏅 解鎖新徽章：{name}" for _code, name in new_badges))
    api = get_messaging_api()
    api.push_message(
        PushMessageRequest(to=student.line_user_id, messages=[TextMessage(text="\n\n".join(lines))])
    )

    return {"checkin_id": checkin.checkin_id, "status": "approved", "points_awarded": points}


@router.post("/checkins/{checkin_id}/reject", dependencies=[Depends(require_admin_key)])
def reject_checkin(checkin_id: int, db: Session = Depends(get_db)):
    checkin = crud.get_eco_checkin_by_id(db, checkin_id)
    if not checkin or checkin.status != "pending":
        raise HTTPException(status_code=404, detail="Checkin not found or already reviewed")

    student = crud.get_student_by_id(db, checkin.student_id)
    eco_checkin.reject_checkin(db, checkin)

    api = get_messaging_api()
    api.push_message(
        PushMessageRequest(
            to=student.line_user_id,
            messages=[TextMessage(text="很抱歉，這張環保打卡照片沒有通過審核，要不要再試一次呢？📸")],
        )
    )

    return {"checkin_id": checkin.checkin_id, "status": "rejected"}
