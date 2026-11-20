"""Link survey records to their uploaded original file."""

from alembic import op
import sqlalchemy as sa

revision = "20261120_survey_documents"
down_revision = "20261113_surveys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    present = (
        set()
        if op.get_context().as_sql
        else {column["name"] for column in sa.inspect(bind).get_columns("survey_records")}
    )
    if "document_id" not in present:
        op.add_column("survey_records", sa.Column("document_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_survey_records_document_id", "survey_records", "documents", ["document_id"], ["id"]
        )


def downgrade() -> None:
    op.drop_constraint("fk_survey_records_document_id", "survey_records", type_="foreignkey")
    op.drop_column("survey_records", "document_id")
