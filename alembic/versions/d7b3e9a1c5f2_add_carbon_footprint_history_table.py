"""add carbon_footprint_history table

Revision ID: d7b3e9a1c5f2
Revises: 9e3c6dafb3dc
Create Date: 2026-10-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7b3e9a1c5f2'
down_revision: Union[str, Sequence[str], None] = '9e3c6dafb3dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('carbon_footprint_history',
    sa.Column('history_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('responses', sa.JSON(), nullable=False),
    sa.Column('total_score', sa.Integer(), nullable=False),
    sa.Column('max_score', sa.Integer(), nullable=False),
    sa.Column('green_score', sa.Integer(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['student_id'], ['students.student_id'], ),
    sa.PrimaryKeyConstraint('history_id')
    )
    with op.batch_alter_table('carbon_footprint_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_carbon_footprint_history_student_id'), ['student_id'], unique=False)

    # 把目前每位學生的最新結果複製一份當第一筆歷史紀錄（時間用最後一次填寫的 updated_at）
    op.execute(
        "INSERT INTO carbon_footprint_history (student_id, responses, total_score, max_score, green_score, submitted_at) "
        "SELECT student_id, responses, total_score, max_score, green_score, updated_at FROM carbon_footprint_responses"
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('carbon_footprint_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_carbon_footprint_history_student_id'))

    op.drop_table('carbon_footprint_history')
