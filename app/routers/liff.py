from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import assessment_questions, crud
from app.config import settings
from app.database import get_db
from app.line_client import LiffAuthError, get_liff_user_id

router = APIRouter(prefix="/liff", tags=["liff"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/assessment")
def assessment_form(request: Request, round: str):
    if round not in assessment_questions.ROUNDS:
        raise HTTPException(status_code=404, detail="不存在的問卷輪次")

    questions = assessment_questions.get_questions_for_round(round)
    return templates.TemplateResponse(
        "assessment.html",
        {
            "request": request,
            "liff_id": settings.liff_id,
            "assessment_round": round,
            "round_label": assessment_questions.ROUND_LABELS[round],
            "questions": questions,
        },
    )


class AssessmentSubmitRequest(BaseModel):
    assessment_round: str
    access_token: str
    answers: dict


@router.post("/assessment/submit")
def submit_assessment(payload: AssessmentSubmitRequest, db: Session = Depends(get_db)):
    if payload.assessment_round not in assessment_questions.ROUNDS:
        raise HTTPException(status_code=400, detail="不存在的問卷輪次")

    try:
        line_user_id = get_liff_user_id(payload.access_token)
    except LiffAuthError:
        raise HTTPException(status_code=401, detail="身份驗證失敗，請透過 LINE 重新開啟這個連結")

    student = crud.get_student_by_line_id(db, line_user_id)
    if student is None:
        raise HTTPException(status_code=400, detail="請先加 LINE 好友並完成學校設定，再填寫問卷")

    try:
        cleaned = assessment_questions.validate_answers(payload.assessment_round, payload.answers)
    except assessment_questions.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.assessment_round == "baseline":
        student.grade = cleaned.get("grade", student.grade)
        student.gender = cleaned.get("gender", student.gender)
        db.commit()

    crud.upsert_assessment_response(db, student, payload.assessment_round, cleaned)
    return {"status": "ok"}
