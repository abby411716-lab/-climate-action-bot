"""教師後台：總覽、學生列表／個別學生頁、題目分析、成效總覽、環保打卡審核。

登入沿用既有的 ADMIN_API_KEY（跟 /admin 系列 API 共用同一把金鑰），登入後把金鑰存進
httpOnly cookie，之後每個頁面用這個 cookie 判斷是否已登入，不用每個請求都手動帶 Header。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import assessment_questions, crud, eco_checkin, game_rules, teacher_dashboard
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/teacher", tags=["teacher"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

COOKIE_NAME = "teacher_key"


def _authed(request: Request) -> bool:
    return bool(settings.admin_api_key) and request.cookies.get(COOKIE_NAME) == settings.admin_api_key


def require_teacher(request: Request) -> RedirectResponse | None:
    """回傳 None 代表已登入可以繼續；否則回傳導向登入頁的 Response，路由裡要接著 `return` 它。"""
    if _authed(request):
        return None
    return RedirectResponse(url="/teacher/login", status_code=303)


@router.get("/login")
def login_page(request: Request):
    if _authed(request):
        return RedirectResponse(url="/teacher", status_code=303)
    return templates.TemplateResponse("teacher/login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(request: Request, admin_key: str = Form(...)):
    if not settings.admin_api_key or admin_key != settings.admin_api_key:
        return templates.TemplateResponse(
            "teacher/login.html", {"request": request, "error": "金鑰錯誤，請再試一次"}, status_code=401
        )
    resp = RedirectResponse(url="/teacher", status_code=303)
    resp.set_cookie(COOKIE_NAME, admin_key, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/teacher/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/")
def overview(request: Request, db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    stats = teacher_dashboard.overview_stats(db)
    return templates.TemplateResponse("teacher/overview.html", {"request": request, "active": "overview", **stats})


@router.get("/students")
def students_list(request: Request, school_id: int | None = None, db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    students = crud.list_students(db, school_id=school_id)
    rows = [
        {
            "student": s,
            "rank_name": game_rules.current_rank(s.total_points)[0],
            "school_name": s.school.school_name if s.school else "（尚未選校）",
        }
        for s in students
    ]
    return templates.TemplateResponse(
        "teacher/students.html",
        {
            "request": request,
            "active": "students",
            "rows": rows,
            "schools": crud.list_schools(db),
            "selected_school_id": school_id,
        },
    )


@router.get("/students/{student_id}")
def student_detail(request: Request, student_id: int, db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    student = crud.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    rank_name, rank_flavor = game_rules.current_rank(student.total_points)
    assessment_sections = [
        {
            "round_label": assessment_questions.ROUND_LABELS.get(r.assessment_round, r.assessment_round),
            "submitted_at": r.submitted_at,
            "answers": teacher_dashboard.describe_assessment_response(r.assessment_round, r.responses),
        }
        for r in crud.list_assessment_responses_for_student(db, student_id)
    ]

    return templates.TemplateResponse(
        "teacher/student_detail.html",
        {
            "request": request,
            "active": "students",
            "student": student,
            "rank_name": rank_name,
            "rank_flavor": rank_flavor,
            "badge_names": [game_rules.badge_display(c) for c in student.badges],
            "answer_logs": crud.list_answer_logs_for_student(db, student_id),
            "checkins": crud.list_eco_checkins_for_student(db, student_id),
            "assessment_sections": assessment_sections,
        },
    )


@router.get("/questions")
def questions_analysis(request: Request, db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    rows = [teacher_dashboard.question_stats(db, q) for q in crud.list_questions(db)]
    return templates.TemplateResponse(
        "teacher/questions.html", {"request": request, "active": "questions", "rows": rows}
    )


@router.get("/assessment")
def assessment_overview(request: Request, db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    rounds = [teacher_dashboard.assessment_round_stats(db, r) for r in assessment_questions.ROUNDS]
    return templates.TemplateResponse(
        "teacher/assessment.html", {"request": request, "active": "assessment", "rounds": rounds}
    )


@router.get("/checkins")
def checkins_page(request: Request, status: str = "pending", db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    checkins = crud.list_eco_checkins(db, status=None if status == "all" else status)
    rows = [{"checkin": c, "student": crud.get_student_by_id(db, c.student_id)} for c in checkins]
    return templates.TemplateResponse(
        "teacher/checkins.html", {"request": request, "active": "checkins", "rows": rows, "status": status}
    )


@router.get("/checkins/{checkin_id}/image")
def checkin_image(request: Request, checkin_id: int, db: Session = Depends(get_db)):
    if not _authed(request):
        raise HTTPException(status_code=403, detail="Forbidden")
    checkin = crud.get_eco_checkin_by_id(db, checkin_id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Checkin not found")
    return Response(content=checkin.image_data, media_type=checkin.image_mime)


@router.post("/checkins/{checkin_id}/approve")
def checkin_approve(request: Request, checkin_id: int, db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    checkin = crud.get_eco_checkin_by_id(db, checkin_id)
    if not checkin or checkin.status != "pending":
        raise HTTPException(status_code=404, detail="Checkin not found or already reviewed")
    student, new_badges = eco_checkin.approve_checkin(db, checkin, points=game_rules.ECO_CHECKIN_POINTS)
    eco_checkin.notify_checkin_approved(student, game_rules.ECO_CHECKIN_POINTS, new_badges)
    return RedirectResponse(url="/teacher/checkins", status_code=303)


@router.post("/checkins/{checkin_id}/reject")
def checkin_reject(request: Request, checkin_id: int, db: Session = Depends(get_db)):
    if resp := require_teacher(request):
        return resp
    checkin = crud.get_eco_checkin_by_id(db, checkin_id)
    if not checkin or checkin.status != "pending":
        raise HTTPException(status_code=404, detail="Checkin not found or already reviewed")
    student = crud.get_student_by_id(db, checkin.student_id)
    eco_checkin.reject_checkin(db, checkin)
    eco_checkin.notify_checkin_rejected(student)
    return RedirectResponse(url="/teacher/checkins", status_code=303)
