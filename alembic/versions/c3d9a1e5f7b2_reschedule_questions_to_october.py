"""Reschedule daily questions: 10/1 baseline, 10/2~10/31 one question per day

Revision ID: c3d9a1e5f7b2
Revises: b5a7d02c67e2
Create Date: 2026-09-30 12:00:00.000000

資料變更（不改 schema）：把 30 題正式題庫的 scheduled_date 從原本「Round1 9/21~10/9、
Round2 10/12~10/30，只推平日」改成「10/2~10/31 每天一題（含週末）」，10/1 當天只推前測問卷、
不推題目。依原本的 scheduled_date 順序（再以 question_id 排序）依序重排，不寫死 question_id，
本機 SQLite 跟 Render Postgres 的 id 就算不同也能正確套用；Render 部署時 startCommand 會自動
跑 alembic upgrade head。
"""
from datetime import date, timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d9a1e5f7b2'
down_revision: Union[str, Sequence[str], None] = 'b5a7d02c67e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_START = date(2026, 10, 2)


def _weekdays(start: date, count: int) -> list[date]:
    days = []
    d = start
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


# 原本的排程：9/21 起 15 個平日（Round1）＋ 10/12 起 15 個平日（Round2），downgrade 用
OLD_DATES = _weekdays(date(2026, 9, 21), 15) + _weekdays(date(2026, 10, 12), 15)


def _scheduled_question_ids(conn) -> list[int]:
    rows = conn.execute(
        sa.text(
            "SELECT question_id FROM questions WHERE scheduled_date IS NOT NULL "
            "ORDER BY scheduled_date, question_id"
        )
    )
    return [row[0] for row in rows]


def _assign_dates(conn, dates: list[date]) -> None:
    for question_id, new_date in zip(_scheduled_question_ids(conn), dates):
        conn.execute(
            sa.text("UPDATE questions SET scheduled_date = :d WHERE question_id = :qid"),
            {"d": new_date, "qid": question_id},
        )


def upgrade() -> None:
    conn = op.get_bind()
    count = len(_scheduled_question_ids(conn))
    _assign_dates(conn, [NEW_START + timedelta(days=i) for i in range(count)])


def downgrade() -> None:
    _assign_dates(op.get_bind(), OLD_DATES)
