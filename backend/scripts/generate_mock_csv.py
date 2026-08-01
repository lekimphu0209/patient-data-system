#!/usr/bin/env python3
"""Sinh CSV dữ liệu mẫu bám đúng form_schema.json.

Chạy:  python scripts/generate_mock_csv.py

Sinh ra 2 file trong scripts/mock_data/:
  - patients.csv      : mỗi dòng 1 bệnh nhân (khối hành chính + khối hỏi bệnh)
  - examinations.csv  : mỗi dòng 1 lần khám (khối khám bệnh)

Tên cột là đường dẫn đầy đủ trong schema, ví dụ
``examination.general.weight`` hay ``medical_history.disease_history.onset_age``.
Trường nhiều lựa chọn (checkbox_group) ghi nhiều giá trị ngăn bằng dấu "|".
Nhờ vậy loader chỉ cần tách theo dấu chấm là dựng lại được cấu trúc phân cấp,
không cần biết trước có những trường nào.
"""

from __future__ import annotations

import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.patients.form_service import FormService  # noqa: E402

OUT_DIR = Path(__file__).parent / "mock_data"
SEED = 20260801
EXAMS_PER_PATIENT = 10

# ==================== Kho giá trị lâm sàng ====================

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô"]
DEM_NAM = ["Văn", "Hữu", "Đức", "Quang", "Minh", "Thành"]
DEM_NU = ["Thị", "Thu", "Ngọc", "Thanh", "Kim", "Hồng"]
TEN_NAM = ["An", "Bình", "Cường", "Dũng", "Hải", "Khánh", "Long", "Nam", "Phong", "Sơn"]
TEN_NU = ["Anh", "Chi", "Dung", "Hà", "Hoa", "Lan", "Mai", "Ngân", "Thảo", "Yến"]

QUE_QUAN = [
    "Hà Nội", "Nam Định", "Thái Bình", "Thanh Hóa", "Nghệ An", "Hải Dương",
    "Bắc Giang", "Phú Thọ", "Hưng Yên", "Ninh Bình", "Hà Nam", "Vĩnh Phúc",
]
DAN_TOC = ["Kinh", "Kinh", "Kinh", "Tày", "Mường", "Thái", "Nùng"]

TEXT_POOL: dict[str, list[str]] = {
    "body_condition": ["Trung bình", "Gầy", "Béo", "Khá", "Suy kiệt nhẹ"],
    "skin_mucosa": ["Hồng hào", "Nhợt nhạt nhẹ", "Bình thường", "Kém hồng"],
    "blood_pressure": ["120/80", "110/70", "125/85", "130/80", "115/75", "105/65"],
    "onset_time": ["Từ từ trong vài tháng", "Đột ngột sau sang chấn", "Âm thầm, khó xác định"],
    "medications_before_detail": [
        "Olanzapine 10mg/ngày, không đều",
        "Risperidone 2mg x 2 lần/ngày",
        "Sertraline 50mg/ngày trong 3 tháng",
        "Amitriptyline 25mg buổi tối",
        "Không nhớ rõ tên thuốc",
    ],
    "onset_circumstances_detail": [
        "Sau khi mất việc làm",
        "Sau mâu thuẫn gia đình kéo dài",
        "Sau khi người thân qua đời",
        "Sau đợt sốt virus kéo dài",
    ],
    "other_mental_detail": ["Rối loạn lo âu lan tỏa", "Rối loạn giấc ngủ mạn tính"],
    "somatic_disease_detail": [
        "Viêm dạ dày mạn tính",
        "Tăng huyết áp độ 1",
        "Chưa phát hiện bệnh lý thực thể",
        "Đái tháo đường type 2",
    ],
    "other_detail": ["Anh trai mắc rối loạn lưỡng cực", "Bác ruột điều trị tâm thần phân liệt"],
    "previous_diagnoses_other": ["Rối loạn phân liệt cảm xúc", "Rối loạn lo âu"],
    "psychotic_symptoms_other": ["Cho rằng mình có khả năng đặc biệt"],
    "behavior_disorder_other": ["Đập phá đồ đạc trong nhà"],
    "depressive_reasons_other": ["Đau đầu, mất tập trung kéo dài"],
    "hallucinations_other": ["Nghe tiếng gọi tên mình lúc nửa đêm"],
    "other_perception_detail": ["Cảm giác cơ thể biến dạng"],
    "content_other": ["Hoang tưởng phát minh"],
}

TEXTAREA_POOL: dict[str, list[str]] = {
    "cardiovascular": ["Nhịp tim đều, T1 T2 rõ, không nghe tiếng thổi bệnh lý."],
    "respiratory": ["Lồng ngực cân đối, rì rào phế nang êm dịu hai bên, không rale."],
    "digestive": ["Bụng mềm, không chướng, gan lách không sờ thấy, đại tiện bình thường."],
    "urinary": ["Hai thận không sờ thấy, không đau vùng thắt lưng, tiểu tiện bình thường."],
    "neurological": [
        "Không có dấu hiệu thần kinh khu trú, phản xạ gân xương hai bên đều.",
        "Không liệt khu trú, không hội chứng màng não, đồng tử hai bên đều.",
    ],
    "other_body_parts": ["Tai mũi họng, răng hàm mặt chưa phát hiện bất thường."],
    "ecg": ["Nhịp xoang đều, tần số 78 ck/phút, không rối loạn dẫn truyền."],
    "eeg": ["Sóng alpha chiếm ưu thế vùng chẩm, không ghi nhận sóng kịch phát."],
    "ct_mri": ["Nhu mô não không thấy tổn thương khu trú, hệ thống não thất không giãn."],
    "eeg_result": ["Điện não đồ trong giới hạn bình thường."],
    "dermatoglyphics": ["Chỉ số vân tay trong giới hạn tham chiếu."],
    "eye_tracking": ["Vận nhãn theo dõi mục tiêu có gián đoạn nhẹ."],
    "gene": ["Chưa phát hiện đột biến có ý nghĩa lâm sàng."],
    "neurotransmitter": ["Nồng độ serotonin huyết tương giảm nhẹ so với tham chiếu."],
    "other": ["Không có xét nghiệm bổ sung."],
    "description": [
        "Bệnh nhân tiếp xúc được, trả lời chậm, cần gợi ý nhiều.",
        "Triệu chứng thuyên giảm so với lần khám trước.",
        "Bệnh nhân hợp tác kém, cần người nhà hỗ trợ khai thác.",
        "Diễn biến ổn định, dung nạp thuốc tốt.",
    ],
}

# Cột "Chẩn đoán" ở bảng danh sách bệnh nhân chỉ nhận đúng 3 nhãn này để khớp
# với bộ lọc chẩn đoán trên giao diện. Mã ICD chi tiết nằm ở "Chẩn đoán xác định"
# của từng lần khám.
PATIENT_DIAGNOSIS = {
    "f20": "Tâm thần phân liệt",
    "f32": "Trầm cảm",
    "normal": "Bình thường",
}

DIAGNOSIS_BY_DISEASE = {
    "f20": [
        "F20.0 - Tâm thần phân liệt thể paranoid",
        "F20.1 - Tâm thần phân liệt thể thanh xuân",
        "F20.3 - Tâm thần phân liệt thể không biệt định",
    ],
    "f32": [
        "F32.1 - Giai đoạn trầm cảm vừa",
        "F32.2 - Giai đoạn trầm cảm nặng không có triệu chứng loạn thần",
        "F32.3 - Giai đoạn trầm cảm nặng có triệu chứng loạn thần",
    ],
    "normal": ["Chưa phát hiện rối loạn tâm thần", "Theo dõi sức khỏe định kỳ"],
}

DIFFERENTIAL_BY_DISEASE = {
    "f20": ["Rối loạn phân liệt cảm xúc; Rối loạn hoang tưởng dai dẳng"],
    "f32": ["Rối loạn lưỡng cực giai đoạn trầm cảm; Rối loạn lo âu lan tỏa"],
    "normal": ["Không"],
}

MEDICATIONS_BY_DISEASE = {
    "f20": [
        "Olanzapine 10mg/ngày; Diazepam 5mg buổi tối",
        "Risperidone 2mg x 2 lần/ngày; Trihexyphenidyl 2mg/ngày",
        "Haloperidol 5mg/ngày; Olanzapine 5mg buổi tối",
    ],
    "f32": [
        "Sertraline 50mg/ngày; Mirtazapine 15mg buổi tối",
        "Fluoxetine 20mg/ngày; Olanzapine 5mg buổi tối",
        "Venlafaxine 75mg/ngày; Zopiclone 7.5mg khi mất ngủ",
    ],
    "normal": ["Không dùng thuốc; tư vấn vệ sinh giấc ngủ"],
}

# Khoảng giá trị cho từng chỉ số định lượng.
NUMBER_RANGE: dict[str, tuple[float, float, int]] = {
    "weight": (45, 78, 0),
    "height": (150, 180, 0),
    "pulse": (62, 96, 0),
    "temperature": (36.2, 37.4, 1),
    "rbc": (3.8, 5.5, 2),
    "hgb": (110, 158, 0),
    "wbc": (4.2, 10.5, 1),
    "neutrophil": (45, 72, 0),
    "lymphocyte": (20, 40, 0),
    "monocyte": (3, 9, 0),
    "glucose": (4.1, 6.4, 1),
    "ure": (3.2, 7.2, 1),
    "creatinin": (58, 105, 0),
    "sgot": (18, 46, 0),
    "sgpt": (16, 52, 0),
    "sggt": (14, 58, 0),
    "inpatient_days": (7, 35, 0),
    "onset_age": (16, 42, 0),
    "duration_years": (1, 12, 0),
    "duration_months": (1, 11, 0),
    "relapse_count": (0, 6, 0),
    "previous_inpatient_count": (0, 5, 0),
    "age": (18, 65, 0),
}

# Triệu chứng đặc trưng — cho "Có" với xác suất cao để dữ liệu trông hợp lý.
TYPICAL_SYMPTOMS = {
    "depressed_mood", "anhedonia", "sadness", "loss_of_energy", "pessimism",
    "worthlessness", "insomnia", "fatigue", "anorexia", "weight_loss",
    "slow_thinking", "poor_communication", "future_worry", "hypokinesia",
}


# ==================== Sinh giá trị theo từng node ====================


def rand_number(node_id: str, rng: random.Random) -> float | int:
    low, high, digits = NUMBER_RANGE.get(node_id, (1, 20, 0))
    value = rng.uniform(low, high)
    return round(value, digits) if digits else int(round(value))


def rand_text(node_id: str, rng: random.Random, disease: str) -> str:
    if node_id in TEXT_POOL:
        return rng.choice(TEXT_POOL[node_id])
    if node_id in TEXTAREA_POOL:
        return rng.choice(TEXTAREA_POOL[node_id])
    if node_id == "definitive":
        return rng.choice(DIAGNOSIS_BY_DISEASE[disease])
    if node_id == "differential":
        return rng.choice(DIFFERENTIAL_BY_DISEASE[disease])
    if node_id == "medications":
        return rng.choice(MEDICATIONS_BY_DISEASE[disease])
    if node_id == "finding":
        return ""  # điền theo tên group ở tầng trên
    return rng.choice(TEXTAREA_POOL["description"])


def fill_node(node: dict, rng: random.Random, disease: str, group_id: str = "") -> object:
    """Sinh giá trị cho một leaf node theo đúng kiểu khai báo trong schema."""
    node_id = node["id"]
    node_type = node["type"]

    if node_type == "number":
        return rand_number(node_id, rng)

    if node_type == "date":
        return (date.today() - timedelta(days=rng.randint(30, 900))).isoformat()

    if node_type == "radio":
        return rng.choice(node.get("options", [{"value": ""}]))["value"]

    if node_type == "checkbox_group":
        options = [o["value"] for o in node.get("options", [])]
        if not options:
            return []
        count = min(len(options), rng.randint(1, 3))
        return sorted(rng.sample(options, count), key=options.index)

    if node_type == "matrix":
        columns = [c["value"] for c in node.get("columns", [])]
        result = {}
        for row in node.get("rows", []):
            if columns == ["yes", "no"]:
                weight = 0.75 if row["id"] in TYPICAL_SYMPTOMS else 0.3
                result[row["id"]] = "yes" if rng.random() < weight else "no"
            else:
                result[row["id"]] = rng.choice(columns)
        return result

    # text / textarea
    if node_id == "finding" and group_id in TEXTAREA_POOL:
        return rng.choice(TEXTAREA_POOL[group_id])
    return rand_text(node_id, rng, disease)


def show_if_satisfied(node: dict, sibling_values: dict) -> bool:
    rule = node.get("show_if")
    if not rule:
        return True
    target = sibling_values.get(rule["field"])
    if "includes" in rule:
        return isinstance(target, list) and rule["includes"] in target
    if "equals" in rule:
        return target == rule["equals"]
    return True


def fill_children(nodes: list[dict], rng: random.Random, disease: str, group_id: str) -> dict:
    """Điền toàn bộ con của một group, tôn trọng điều kiện show_if."""
    values: dict = {}
    for node in nodes:
        if node["type"] == "group":
            values[node["id"]] = fill_children(node["children"], rng, disease, node["id"])
        else:
            values[node["id"]] = fill_node(node, rng, disease, group_id)

    # Trường phụ thuộc mà không thoả điều kiện thì để trống cho đúng logic form.
    for node in nodes:
        if node["type"] != "group" and not show_if_satisfied(node, values):
            values[node["id"]] = "" if node["type"] != "checkbox_group" else []
    return values


# ==================== Làm phẳng ra CSV ====================


def flatten(prefix: str, values: dict, out: dict) -> None:
    for key, value in values.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flatten(path, value, out)
        elif isinstance(value, list):
            out[path] = "|".join(str(v) for v in value)
        else:
            out[path] = "" if value is None else str(value)


def column_paths(prefix: str, nodes: list[dict]) -> list[str]:
    """Danh sách cột theo đúng thứ tự trong schema — CSV đọc dễ hơn."""
    paths: list[str] = []
    for node in nodes:
        path = f"{prefix}.{node['id']}" if prefix else node["id"]
        if node["type"] == "group":
            paths.extend(column_paths(path, node["children"]))
        elif node["type"] == "matrix":
            paths.extend(f"{path}.{row['id']}" for row in node.get("rows", []))
        else:
            paths.append(path)
    return paths


# ==================== Chương trình chính ====================


def compute_age(birth: date, today: date | None = None) -> int:
    """Cùng công thức với backend để tuổi và ngày sinh không lệch nhau."""
    today = today or date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def build_patient(index: int, disease: str, rng: random.Random, service: FormService) -> tuple[dict, list[dict]]:
    schema = service.get_schema(disease)
    blocks = {b["id"]: b for b in schema["blocks"]}

    gender = rng.choice(["male", "female"])
    ho = rng.choice(HO)
    dem = rng.choice(DEM_NAM if gender == "male" else DEM_NU)
    ten = rng.choice(TEN_NAM if gender == "male" else TEN_NU)
    full_name = f"{ho} {dem} {ten}"
    patient_code = f"BA{index:04d}"

    # Bốc ngày sinh trước rồi suy ra tuổi, tránh hai trường đá nhau trên giao diện.
    birth_date = date.today() - timedelta(days=rng.randint(18 * 365, 65 * 365))

    admin = fill_children(blocks["administrative"]["children"], rng, disease, "administrative")
    admin["patient_code"] = patient_code
    admin["full_name"] = full_name
    admin["age"] = compute_age(birth_date)
    admin["gender"] = gender
    admin["hometown"] = rng.choice(QUE_QUAN)
    admin["ethnicity"] = rng.choice(DAN_TOC)
    admin["admission_date"] = (date.today() - timedelta(days=rng.randint(60, 720))).isoformat()

    row: dict = {
        "patient_code": patient_code,
        "disease_code": disease,
        "birth_date": birth_date.isoformat(),
        "diagnosis": PATIENT_DIAGNOSIS[disease],
        "disease_type": {"f20": "schizophrenia", "f32": "depression", "normal": "normal"}[disease],
    }
    flatten("administrative", admin, row)

    if "medical_history" in blocks:
        history = fill_children(
            blocks["medical_history"]["children"], rng, disease, "medical_history"
        )
        flatten("medical_history", history, row)

    # Các lần khám: cách nhau vài tuần, gần nhất ở cuối.
    exams: list[dict] = []
    exam_day = date.today() - timedelta(days=rng.randint(20, 60))
    for _ in range(EXAMS_PER_PATIENT):
        values = fill_children(blocks["examination"]["children"], rng, disease, "examination")
        values["exam_info"]["exam_date"] = exam_day.isoformat()
        exam_row: dict = {"patient_code": patient_code}
        flatten("examination", values, exam_row)
        exams.append(exam_row)
        exam_day -= timedelta(days=rng.randint(21, 45))

    return row, exams


def main() -> None:
    rng = random.Random(SEED)
    service = FormService()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 10 tâm thần phân liệt + 8 trầm cảm + 2 bình thường.
    diseases = ["f20"] * 10 + ["f32"] * 8 + ["normal"] * 2

    patient_rows: list[dict] = []
    exam_rows: list[dict] = []
    for index, disease in enumerate(diseases, start=1):
        row, exams = build_patient(index, disease, rng, service)
        patient_rows.append(row)
        exam_rows.extend(exams)

    # Cột lấy từ schema đầy đủ nhất của mỗi khối để không bỏ sót trường nào.
    f20 = {b["id"]: b for b in service.get_schema("f20")["blocks"]}
    f32 = {b["id"]: b for b in service.get_schema("f32")["blocks"]}

    patient_columns = ["patient_code", "disease_code", "birth_date", "diagnosis", "disease_type"]
    patient_columns += column_paths("administrative", f20["administrative"]["children"])
    seen = set(patient_columns)
    for block in (f20["medical_history"], f32["medical_history"]):
        for path in column_paths("medical_history", block["children"]):
            if path not in seen:
                seen.add(path)
                patient_columns.append(path)

    exam_columns = ["patient_code"]
    seen = set(exam_columns)
    for block in (f20["examination"], f32["examination"]):
        for path in column_paths("examination", block["children"]):
            if path not in seen:
                seen.add(path)
                exam_columns.append(path)

    with (OUT_DIR / "patients.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=patient_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(patient_rows)

    with (OUT_DIR / "examinations.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=exam_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(exam_rows)

    print(f"patients.csv     : {len(patient_rows)} bệnh nhân, {len(patient_columns)} cột")
    print(f"examinations.csv : {len(exam_rows)} lần khám, {len(exam_columns)} cột")
    print(f"Thư mục: {OUT_DIR}")


if __name__ == "__main__":
    main()
