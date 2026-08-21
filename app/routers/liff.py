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
def assessment_form(request: Request):
    """頁面本身不依賴 round 這個 query 參數就能載入。

    LINE 的 LIFF 轉址不保證第一次進到後端的請求就帶著原始網址上的 query string
    （LINE 會把它編碼進 liff.state，要等瀏覽器裡的 liff.init() 執行完才會補回網址），
    所以「要顯示哪一輪問卷」這件事挪到前端 JS 處理：liff.init() 完成後才從網址讀 round，
    再打 /liff/assessment/questions 拿題目動態把表單畫出來，而不是在這裡用 Jinja2 先渲染好。
    """
    return templates.TemplateResponse("assessment.html", {"request": request, "liff_id": settings.liff_id})


@router.get("/assessment/questions")
def assessment_questions_api(round: str):
    if round not in assessment_questions.ROUNDS:
        raise HTTPException(status_code=404, detail="不存在的問卷輪次")

    return {
        "round_label": assessment_questions.ROUND_LABELS[round],
        "questions": assessment_questions.get_questions_for_round(round),
    }


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
