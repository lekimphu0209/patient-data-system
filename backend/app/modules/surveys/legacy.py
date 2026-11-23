"""Chuyển câu trả lời đã lưu theo tên phương án cũ sang tên mới khi biểu mẫu đổi tên phương án.

Chạy lúc khởi động, lặp lại nhiều lần vẫn an toàn: chỉ sửa bản ghi còn dùng tên cũ.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.surveys.models import SurveyRecord

# (mã biểu mẫu, mã câu) -> {tên phương án cũ: tên mới}
RENAMED_OPTIONS: dict[tuple[str, str], dict[str, str]] = {
    # F08 Câu 7: bỏ dấu chấm điền tay khỏi tên phương án "Khác".
    ("F08", "Q007"): {"Khác: ................": "Khác"},
}


def rename_legacy_options(db: Session) -> int:
    """Trả về số bản ghi đã sửa."""
    changed = 0
    for (form, question), renames in RENAMED_OPTIONS.items():
        rows = db.execute(select(SurveyRecord.id, SurveyRecord.answers).where(SurveyRecord.form == form))
        for record_id, answers in rows.all():
            value = (answers or {}).get(question)
            if isinstance(value, list):
                renamed = [renames.get(item, item) for item in value]
            elif isinstance(value, str):
                renamed = renames.get(value, value)
            else:
                continue
            if renamed != value:
                db.execute(
                    update(SurveyRecord)
                    .where(SurveyRecord.id == record_id)
                    .values(answers={**answers, question: renamed})
                )
                changed += 1
    db.commit()
    return changed
