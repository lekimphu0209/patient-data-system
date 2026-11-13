"""Add survey subjects and survey records."""

from alembic import op
import sqlalchemy as sa

revision = "20261113_surveys"
down_revision = "20260728_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if op.get_context().as_sql or not sa.inspect(bind).has_table("survey_subjects"):
        op.create_table(
            "survey_subjects",
            sa.Column("subject_group", sa.String(10), primary_key=True),
            sa.Column("person", sa.String(120), primary_key=True),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("birth_date", sa.Date()),
            sa.Column("birth_year", sa.String(4), nullable=False),
            sa.Column("hometown", sa.String(255), nullable=False),
        )
    if op.get_context().as_sql or not sa.inspect(bind).has_table("survey_records"):
        op.create_table(
            "survey_records",
            sa.Column("id", sa.String(120), primary_key=True),
            sa.Column("subject_group", sa.String(10), nullable=False),
            sa.Column("person", sa.String(120), nullable=False),
            sa.Column("form", sa.String(3), nullable=False),
            sa.Column("unit", sa.String(255), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("conclusion", sa.Text(), nullable=False),
            sa.Column("answers", sa.JSON(), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("ocr", sa.Text()),
            sa.Column("ocr_image", sa.Text()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["subject_group", "person"],
                ["survey_subjects.subject_group", "survey_subjects.person"],
            ),
        )


def downgrade() -> None:
    op.drop_table("survey_records")
    op.drop_table("survey_subjects")
