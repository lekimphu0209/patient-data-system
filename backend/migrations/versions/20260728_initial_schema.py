"""Initial schema

Revision ID: 20260728_initial
Revises: 
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260728_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('email', sa.String(255), unique=True, index=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('role', sa.String(50), default='doctor'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('patient_code', sa.String(50), unique=True, index=True, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('disease_type', sa.String(100), nullable=True),
        sa.Column('diagnosis', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('contact_info', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'encounters',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('visit_date', sa.Date(), nullable=False),
        sa.Column('source_type', sa.String(50), default='manual'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('form_data', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id'), nullable=True),
        sa.Column('encounter_id', sa.Integer(), sa.ForeignKey('encounters.id'), nullable=True),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('relative_path', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=True),
        sa.Column('checksum', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'ocr_extractions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('provider', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('raw_result', sa.JSON(), nullable=True),
        sa.Column('reviewed_result', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('ocr_extractions')
    op.drop_table('documents')
    op.drop_table('encounters')
    op.drop_table('patients')
    op.drop_table('users')
