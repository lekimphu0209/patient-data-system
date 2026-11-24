"""Công cụ phân tích cho trợ lý dữ liệu (function calling).

Mỗi công cụ trả về ``ToolResult``:

- ``llm``: phần tóm tắt gửi lại cho LLM — chỉ số liệu tổng hợp, KHÔNG có họ tên, ngày sinh,
  quê quán (và không có mã đối tượng trừ khi người dùng hỏi đúng mã đó);
- ``blocks``: khối hiển thị cho giao diện (thẻ số, thanh phân bố, bảng);
- ``method``: "Cách tính" bằng lời thường cho người dùng (không có SQL).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .snapshot import (
    AGE_GROUPS, EXPECTED_FORMS, FORM_TITLES, GROUP_LABEL, QUESTIONS, STATUS_LABEL, STATUS_ORDER, UNKNOWN,
    QueryError, Snapshot, code_key, code_prefix, fold,
)

FORM_IDS = sorted(FORM_TITLES)
LIST_LIMIT = 200
SQL_LIMIT = 200
LLM_ROWS = 60
SENSITIVE_COLUMNS = {"full_name", "birth_date", "hometown"}


class ToolError(Exception):
    """Tham số không dùng được; thông điệp gửi lại để LLM tự sửa."""


@dataclass
class ToolResult:
    llm: dict[str, Any]
    blocks: list[dict[str, Any]] = field(default_factory=list)
    method: str | None = None
    audit: dict[str, Any] = field(default_factory=dict)


# ---------- tiện ích chung ----------


def pct(part: int, whole: int) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


def pct_text(part: int, whole: int) -> str:
    value = pct(part, whole)
    return "—" if value is None else f"{value:.1f}".replace(".", ",") + "%"


def natural(value: str) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value or "")]


def nullable(schema: dict[str, Any]) -> dict[str, Any]:
    result = dict(schema)
    result["type"] = [schema["type"], "null"]
    if "enum" in result:
        result["enum"] = [*result["enum"], None]
    return result


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


FILTERS_SCHEMA = obj({
    "group": nullable({"type": "string", "enum": ["youth", "military"],
                       "description": "youth = thanh niên, military = quân nhân; null = cả hai"}),
    "forms": nullable({"type": "array", "items": {"type": "string", "enum": FORM_IDS},
                       "description": "Chỉ tính các mẫu này; null = mọi mẫu"}),
    "statuses": nullable({"type": "array", "items": {"type": "string", "enum": list(STATUS_ORDER)},
                          "description": "complete = Đã hoàn tất, review = Chờ đối soát, draft = Bản nháp; null = mọi trạng thái"}),
    "code_prefix": nullable({"type": "string", "description": "Phần đầu mã đối tượng, VD 'PT.CK', 'PT.TL', 'QK1'"}),
    "date_from": nullable({"type": "string", "description": "Ngày khảo sát từ (YYYY-MM-DD)"}),
    "date_to": nullable({"type": "string", "description": "Ngày khảo sát đến (YYYY-MM-DD)"}),
})
FILTERS_SCHEMA["description"] = "Phạm vi dữ liệu; để mọi trường null nếu người dùng không giới hạn."


def normalize_prefix(value: str) -> str:
    return code_prefix(".".join(part for part in re.split(r"[\s._\-–—·:]+", value.upper()) if part))


def scope(filters: dict[str, Any] | None, alias: str = "r", forms: list[str] | None = None) -> tuple[str, list[Any]]:
    """Điều kiện WHERE trên bảng records theo bộ lọc."""
    filters = filters or {}
    clauses, params = ["1=1"], []
    if filters.get("group"):
        clauses.append(f"{alias}.grp = ?")
        params.append(filters["group"])
    chosen = forms if forms is not None else filters.get("forms")
    if chosen:
        clauses.append(f"{alias}.form IN ({','.join('?' * len(chosen))})")
        params.extend(chosen)
    if filters.get("statuses"):
        clauses.append(f"{alias}.status IN ({','.join('?' * len(filters['statuses']))})")
        params.extend(filters["statuses"])
    if filters.get("code_prefix"):
        prefix = normalize_prefix(filters["code_prefix"])
        clauses.append(f"({alias}.code_prefix = ? OR {alias}.person LIKE ?)")
        params.extend([prefix, prefix + ".%"])
    for key, op in (("date_from", ">="), ("date_to", "<=")):
        value = filters.get(key)
        if value:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ToolError(f"{key} phải có dạng YYYY-MM-DD.")
            clauses.append(f"{alias}.survey_date {op} ?")
            params.append(value)
    return " AND ".join(clauses), params


def describe_scope(snapshot: Snapshot, filters: dict[str, Any] | None, forms: list[str] | None = None,
                   unit: str = "phiếu") -> str:
    """'Tính trên 249 phiếu F01 · Quân nhân · mọi trạng thái (Đã hoàn tất 12, …)'."""
    filters = filters or {}
    where, params = scope(filters, forms=forms)
    counts = dict(snapshot.query(f"SELECT status, COUNT(*) FROM records r WHERE {where} GROUP BY status", params).rows)
    total = sum(counts.values())
    chosen = forms if forms is not None else filters.get("forms")
    parts = [f"{total:,} phiếu".replace(",", ".") + (f" {', '.join(chosen)}" if chosen else "")]
    if filters.get("group"):
        parts.append(GROUP_LABEL[filters["group"]])
    if filters.get("code_prefix"):
        parts.append(f"mã {normalize_prefix(filters['code_prefix'])}")
    if filters.get("date_from") or filters.get("date_to"):
        parts.append(f"ngày khảo sát {filters.get('date_from') or '…'} → {filters.get('date_to') or '…'}")
    breakdown = ", ".join(f"{STATUS_LABEL[status]} {counts[status]}" for status in STATUS_ORDER if counts.get(status))
    label = ("chỉ " + ", ".join(STATUS_LABEL[s] for s in filters["statuses"])) if filters.get("statuses") else "mọi trạng thái"
    parts.append(f"{label}" + (f" ({breakdown})" if breakdown else ""))
    return "Tính trên " + " · ".join(parts) + f"; đếm theo {unit}."


def question_meta(form: str, question: str) -> dict[str, Any]:
    form = (form or "").upper().strip()
    question = (question or "").upper().strip()
    if re.fullmatch(r"Q?\d{1,3}", question):
        question = "Q" + question.lstrip("Q").zfill(3)
    meta = QUESTIONS.get((form, question))
    if meta is None:
        raise ToolError(f"Không có câu {question} trong mẫu {form}. Dùng find_questions để tìm đúng mã câu.")
    if meta["kind"] == "identity":
        raise ToolError(f"{form} {question} là thông tin định danh (họ tên/địa chỉ), không thống kê được.")
    return meta


def match_values(meta: dict[str, Any], values: list[str]) -> list[str]:
    """Ánh xạ đáp án LLM đưa (gần đúng, không dấu) về đúng chữ của đáp án trong biểu mẫu."""
    if meta["kind"] == "text":
        return [value.strip() for value in values if value.strip()]
    chosen = []
    for value in values:
        target = fold(value)
        exact = [option for option in meta["options"] if fold(option) == target]
        loose = [option for option in meta["options"] if target and target in fold(option)]
        found = exact or (loose if len(loose) == 1 else [])
        if not found:
            raise ToolError(f"Đáp án “{value}” không có trong {meta['form']} {meta['question']}. "
                            f"Các đáp án: {' | '.join(meta['options'])}")
        chosen.append(found[0])
    return list(dict.fromkeys(chosen))


def table(title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]], *, total: int | None = None,
          truncated: bool = False, person: bool = False, csv: str = "tro-ly-du-lieu") -> dict[str, Any]:
    block = {
        "type": "table", "title": title,
        "columns": [{"key": key, "label": label} for key, label in columns],
        "rows": rows, "total": len(rows) if total is None else total, "truncated": truncated, "csvName": csv,
    }
    if person:
        block["personKey"], block["groupKey"] = "person", "grp"
    return block


def bars(title: str, items: list[tuple[str, int, float | None]], unit: str, note: str | None = None) -> dict[str, Any]:
    return {"type": "bars", "title": title, "unit": unit, "note": note,
            "items": [{"label": label, "count": count, "percent": percent} for label, count, percent in items]}


def stats(items: list[tuple[str, int, str]]) -> dict[str, Any]:
    return {"type": "stats", "items": [{"label": label, "value": value, "tone": tone} for label, value, tone in items]}


# ---------- 1. tra cứu câu hỏi ----------


def find_questions(snapshot: Snapshot, keyword: str, form: str | None) -> ToolResult:
    words = fold(keyword).split()
    candidates = [item for item in QUESTIONS.values() if not form or item["form"] == form.upper()]
    scored = []
    for item in candidates:
        text = fold(f"{item['form']} {item['question']} {item['form_title']} {item['label']} {' '.join(item['options'])}")
        score = sum(1 for word in words if word in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["form"], pair[1]["position"]))
    found = [{
        "form": item["form"], "form_title": item["form_title"], "group": item["grp"], "question": item["question"],
        "label": item["label"], "kind": item["kind"], "options": item["options"],
        **({"note": "thông tin định danh — không thống kê"} if item["kind"] == "identity" else {}),
    } for score, item in scored[:12] if score >= max(1, len(words) // 2)]
    return ToolResult(llm={"matches": found, "count": len(found)})


# ---------- 2. tổng quan ----------


def overview(snapshot: Snapshot, filters: dict[str, Any] | None) -> ToolResult:
    where, params = scope(filters)
    rows = snapshot.query(
        f"SELECT form, status, COUNT(*), COUNT(DISTINCT grp || '|' || person) FROM records r WHERE {where} "
        "GROUP BY form, status", params).rows
    by_form: dict[str, dict[str, int]] = {}
    for form, status, count, _ in rows:
        by_form.setdefault(form, {})[status] = count
    persons_by_form = dict(snapshot.query(
        f"SELECT form, COUNT(DISTINCT grp || '|' || person) FROM records r WHERE {where} GROUP BY form", params).rows)
    persons_by_group = dict(snapshot.query(
        f"SELECT grp, COUNT(DISTINCT person) FROM records r WHERE {where} GROUP BY grp", params).rows)
    total = sum(sum(item.values()) for item in by_form.values())
    status_total = {status: sum(item.get(status, 0) for item in by_form.values()) for status in STATUS_ORDER}
    persons = sum(persons_by_group.values())
    table_rows = [{
        "form": form, "title": FORM_TITLES.get(form, form), "records": sum(counts.values()),
        "persons": persons_by_form.get(form, 0), **{status: counts.get(status, 0) for status in STATUS_ORDER},
    } for form, counts in sorted(by_form.items())]
    blocks = [
        stats([("Phiếu khảo sát", total, "navy"), ("Đối tượng", persons, "blue"),
               ("Đã hoàn tất", status_total["complete"], "teal"),
               ("Cần đối soát", status_total["review"] + status_total["draft"], "amber")]),
        table("Theo loại phiếu", [("form", "Mẫu"), ("title", "Loại phiếu"), ("records", "Số phiếu"),
                                  ("persons", "Đối tượng"), ("complete", "Đã hoàn tất"), ("review", "Chờ đối soát"),
                                  ("draft", "Bản nháp")], table_rows, csv="tong-quan"),
    ]
    return ToolResult(
        llm={"total_records": total, "total_persons": persons,
             "persons_by_group": {GROUP_LABEL[g]: n for g, n in persons_by_group.items()},
             "by_status": {STATUS_LABEL[s]: n for s, n in status_total.items()},
             "by_form": [{"form": row["form"], "title": row["title"], "records": row["records"], "persons": row["persons"],
                          "by_status": {STATUS_LABEL[s]: row[s] for s in STATUS_ORDER}} for row in table_rows]},
        blocks=blocks, method=describe_scope(snapshot, filters))


# ---------- 3. phân bố đáp án ----------


def answer_distribution(snapshot: Snapshot, form: str, question: str, filters: dict[str, Any] | None) -> ToolResult:
    meta = question_meta(form, question)
    forms = [meta["form"]]
    where, params = scope(filters, forms=forms)
    total = snapshot.query(f"SELECT COUNT(*) FROM records r WHERE {where}", params).rows[0][0]
    base = (f"FROM answers a JOIN records r ON r.record_id = a.record_id WHERE {where} AND a.question = ?")
    answered = snapshot.query(f"SELECT COUNT(DISTINCT a.record_id) {base}", [*params, meta["question"]]).rows[0][0]
    counts = dict(snapshot.query(f"SELECT a.value, COUNT(DISTINCT a.record_id) {base} GROUP BY a.value",
                                 [*params, meta["question"]]).rows)
    if meta["kind"] == "text":
        numeric = all(re.fullmatch(r"\d+", value) for value in counts)
        ordered = sorted(counts.items(), key=(lambda item: int(item[0])) if numeric else (lambda item: (-item[1], item[0])))
        items = ordered[:25]
    else:
        items = [(option, counts.get(option, 0)) for option in meta["options"]]
        items += [(value, count) for value, count in counts.items() if value not in meta["options"]]
    rows = [(value, count, pct(count, answered)) for value, count in items]
    notes = [f"{total - answered} phiếu chưa trả lời hoặc không áp dụng câu này."] if total - answered else []
    if meta["kind"] == "multi":
        notes.append("Câu nhiều lựa chọn: tổng tỷ lệ có thể vượt 100%.")
    block = bars(f"{meta['form']} · {meta['label']}", rows, "phiếu", " ".join(notes) or None)
    return ToolResult(
        llm={"form": meta["form"], "form_title": meta["form_title"], "question": meta["question"],
             "label": meta["label"], "kind": meta["kind"], "records_in_scope": total, "answered": answered,
             "distribution": [{"answer": value, "count": count, "percent_of_answered": percent}
                              for value, count, percent in rows]},
        blocks=[block], method=describe_scope(snapshot, filters, forms) + " Tỷ lệ tính trên số phiếu có trả lời câu này.")


# ---------- 4. so sánh theo nhóm (bảng chéo) ----------

DIMENSION_KINDS = ["question", "gender", "age_group", "group", "code_prefix", "status"]
DIMENSION_LABEL = {"gender": "Giới tính", "age_group": "Nhóm tuổi", "group": "Nhóm đối tượng",
                   "code_prefix": "Đầu mã đối tượng", "status": "Trạng thái phiếu"}
DIMENSION_SCHEMA = obj({
    "kind": {"type": "string", "enum": DIMENSION_KINDS,
             "description": "question = một câu hỏi; gender = giới tính; age_group = nhóm tuổi; group = thanh niên/quân "
                            "nhân; code_prefix = đầu mã (PT.CK, PT.TL, QK1); status = trạng thái phiếu"},
    "form": nullable({"type": "string", "enum": FORM_IDS, "description": "Khi kind = question"}),
    "question": nullable({"type": "string", "description": "Mã câu, VD 'Q026'; khi kind = question"}),
})


def _dimension(snapshot: Snapshot, spec: dict[str, Any], filters: dict[str, Any] | None
               ) -> tuple[str, list[str], dict[tuple[str, str], set[str]], list[str]]:
    """(tên chiều, thứ tự giá trị, đối tượng -> tập giá trị, các mẫu liên quan)."""
    kind = spec.get("kind")
    if kind == "question":
        meta = question_meta(spec.get("form") or "", spec.get("question") or "")
        where, params = scope(filters, forms=[meta["form"]])
        values: dict[tuple[str, str], set[str]] = {}
        for grp, person, value in snapshot.query(
                f"SELECT a.grp, a.person, a.value FROM answers a JOIN records r ON r.record_id = a.record_id "
                f"WHERE {where} AND a.question = ?", [*params, meta["question"]], limit=100_000).rows:
            values.setdefault((grp, person), set()).add(value)
        seen = {value for group in values.values() for value in group}
        order = [o for o in meta["options"] if o in seen] if meta["options"] else sorted(seen, key=natural)
        order += sorted(seen - set(order), key=natural)
        return f"{meta['form']} {meta['question']} · {meta['label']}", order, values, [meta["form"]]
    if kind not in DIMENSION_LABEL:
        raise ToolError(f"Chiều phân tích không hợp lệ: {kind}")
    where, params = scope(filters)
    if kind == "status":
        values = {}
        for grp, person, status in snapshot.query(f"SELECT grp, person, status FROM records r WHERE {where}",
                                                  params, limit=100_000).rows:
            values.setdefault((grp, person), set()).add(STATUS_LABEL[status])
        return DIMENSION_LABEL[kind], [STATUS_LABEL[s] for s in STATUS_ORDER], values, []
    column = {"gender": "s.gender", "age_group": "s.age_group", "group": "s.grp", "code_prefix": "s.code_prefix"}[kind]
    rows = snapshot.query(
        f"SELECT DISTINCT s.grp, s.person, {column} FROM subjects s JOIN records r ON r.grp = s.grp AND r.person = s.person "
        f"WHERE {where}", params, limit=100_000).rows
    values = {}
    for grp, person, value in rows:
        label = GROUP_LABEL.get(value, value) if kind == "group" else (value or UNKNOWN)
        values[(grp, person)] = {label}
    seen = {value for group in values.values() for value in group}
    order = {"gender": ["Nam", "Nữ", UNKNOWN], "age_group": [*AGE_GROUPS, UNKNOWN],
             "group": list(GROUP_LABEL.values())}.get(kind) or sorted(seen, key=natural)
    return DIMENSION_LABEL[kind], [value for value in order if value in seen], values, []


def cross_tab(snapshot: Snapshot, row: dict[str, Any], column: dict[str, Any], filters: dict[str, Any] | None) -> ToolResult:
    row_name, row_order, row_values, row_forms = _dimension(snapshot, row, filters)
    col_name, col_order, col_values, col_forms = _dimension(snapshot, column, filters)
    persons = set(row_values) & set(col_values)
    counts = {(r, c): 0 for r in row_order for c in col_order}
    row_totals = {r: 0 for r in row_order}
    for person in persons:
        for r in row_values[person]:
            row_totals[r] += 1
            for c in col_values[person]:
                counts[(r, c)] += 1
    columns = [("row", row_name)] + [(f"c{index}", label) for index, label in enumerate(col_order)] + [("total", "Tổng")]
    rows = []
    for r in row_order:
        if not row_totals[r]:
            continue
        line: dict[str, Any] = {"row": r, "total": row_totals[r]}
        for index, c in enumerate(col_order):
            n = counts[(r, c)]
            line[f"c{index}"] = f"{n} ({pct_text(n, row_totals[r])})"
        rows.append(line)
    forms = sorted(set(row_forms + col_forms)) or None
    method = describe_scope(snapshot, filters, forms, unit="đối tượng") + (
        f" {len(persons)} người có dữ liệu ở cả hai chiều; tỷ lệ tính theo hàng.")
    return ToolResult(
        llm={"rows_dimension": row_name, "columns_dimension": col_name, "persons": len(persons),
             "table": [{"row": r, "row_total": row_totals[r],
                        "cells": [{"column": c, "count": counts[(r, c)], "percent_of_row": pct(counts[(r, c)], row_totals[r])}
                                  for c in col_order]} for r in row_order if row_totals[r]]},
        blocks=[table(f"{row_name} × {col_name}", columns, rows, csv="so-sanh")], method=method)


# ---------- 5. tìm đối tượng ----------

CONDITION_SCHEMA = obj({
    "form": {"type": "string", "enum": FORM_IDS},
    "question": {"type": "string", "description": "Mã câu, VD 'Q042'"},
    "values": {"type": "array", "items": {"type": "string"},
               "description": "Các đáp án được tính là khớp (đúng chữ trong biểu mẫu), ít nhất một"},
})


def _subject_rows(snapshot: Snapshot, persons: list[tuple[str, str]]) -> dict[tuple[str, str], tuple]:
    found: dict[tuple[str, str], tuple] = {}
    for start in range(0, len(persons), 400):
        chunk = persons[start:start + 400]
        where = " OR ".join("(grp = ? AND person = ?)" for _ in chunk)
        params = [value for pair in chunk for value in pair]
        for row in snapshot.query(
                f"SELECT grp, person, full_name, gender, age, birth_year, hometown, code_prefix FROM subjects WHERE {where}",
                params, limit=1000).rows:
            found[(row[0], row[1])] = row
    return found


def find_subjects(snapshot: Snapshot, conditions: list[dict[str, Any]], match: str,
                  filters: dict[str, Any] | None) -> ToolResult:
    if not conditions:
        raise ToolError("Cần ít nhất một điều kiện.")
    resolved, sets, forms = [], [], []
    for condition in conditions[:5]:
        meta = question_meta(condition.get("form") or "", condition.get("question") or "")
        values = match_values(meta, condition.get("values") or [])
        if not values:
            raise ToolError("Mỗi điều kiện cần ít nhất một đáp án.")
        where, params = scope(filters, forms=[meta["form"]])
        rows = snapshot.query(
            f"SELECT DISTINCT a.grp, a.person FROM answers a JOIN records r ON r.record_id = a.record_id "
            f"WHERE {where} AND a.question = ? AND a.value IN ({','.join('?' * len(values))})",
            [*params, meta["question"], *values], limit=100_000).rows
        sets.append({tuple(row) for row in rows})
        resolved.append((meta, values))
        forms.append(meta["form"])
    persons = set.intersection(*sets) if match != "any" else set.union(*sets)
    ordered = sorted(persons, key=lambda pair: (pair[0], natural(pair[1])))
    subjects = _subject_rows(snapshot, ordered[:LIST_LIMIT])

    answers: dict[tuple[str, str, str, str], list[str]] = {}
    statuses: dict[tuple[str, str], set[str]] = {}
    shown = ordered[:LIST_LIMIT]
    for meta, _ in resolved:
        where, params = scope(filters, forms=[meta["form"]])
        for grp, person, value, status in snapshot.query(
                f"SELECT a.grp, a.person, a.value, a.status FROM answers a JOIN records r ON r.record_id = a.record_id "
                f"WHERE {where} AND a.question = ?", [*params, meta["question"]], limit=100_000).rows:
            if (grp, person) in persons:
                answers.setdefault((grp, person, meta["form"], meta["question"]), []).append(value)
                statuses.setdefault((grp, person), set()).add(STATUS_LABEL[status])
    rows = []
    for grp, person in shown:
        subject = subjects.get((grp, person))
        matched = "; ".join(
            f"{meta['form']} {meta['question']}: {', '.join(answers.get((grp, person, meta['form'], meta['question']), []))}"
            for meta, _ in resolved if answers.get((grp, person, meta["form"], meta["question"])))
        rows.append({
            "person": person, "grp": grp, "name": (subject[2] if subject else None) or "—",
            "group": GROUP_LABEL[grp], "gender": (subject[3] if subject else None) or "—",
            "age": subject[4] if subject and subject[4] is not None else "—",
            "answers": matched, "status": ", ".join(s for s in (STATUS_LABEL[x] for x in STATUS_ORDER)
                                                     if s in statuses.get((grp, person), set())),
        })
    by_group: dict[str, int] = {}
    by_prefix: dict[str, int] = {}
    by_gender: dict[str, int] = {}
    all_subjects = _subject_rows(snapshot, ordered) if len(ordered) > LIST_LIMIT else subjects
    for pair in ordered:
        subject = all_subjects.get(pair)
        by_group[GROUP_LABEL[pair[0]]] = by_group.get(GROUP_LABEL[pair[0]], 0) + 1
        prefix = code_prefix(pair[1])
        by_prefix[prefix] = by_prefix.get(prefix, 0) + 1
        gender = (subject[3] if subject else None) or UNKNOWN
        by_gender[gender] = by_gender.get(gender, 0) + 1
    description = (" VÀ " if match != "any" else " HOẶC ").join(
        f"{meta['form']} {meta['question']} ∈ {{{', '.join(values)}}}" for meta, values in resolved)
    block = table(
        f"Đối tượng khớp điều kiện ({len(ordered)})",
        [("person", "Mã đối tượng"), ("name", "Họ và tên"), ("group", "Nhóm"), ("gender", "Giới tính"),
         ("age", "Tuổi"), ("answers", "Câu trả lời khớp"), ("status", "Trạng thái phiếu")],
        rows, total=len(ordered), truncated=len(ordered) > LIST_LIMIT, person=True, csv="danh-sach-doi-tuong")
    labels = "; ".join(f"{meta['form']} {meta['question']} “{meta['label']}” là {', '.join(values)}"
                       for meta, values in resolved)
    method = (describe_scope(snapshot, filters, sorted(set(forms)), unit="đối tượng")
              + f" Điều kiện ({'tất cả' if match != 'any' else 'một trong các'}): {labels}.")
    return ToolResult(
        llm={"matched_persons": len(ordered), "conditions": description, "match": match,
             "by_group": by_group, "by_code_prefix": by_prefix, "by_gender": by_gender,
             "note": "Danh sách họ tên chỉ hiển thị cho người dùng trong bảng bên dưới; bạn không thấy họ tên."},
        blocks=[block], method=method)


# ---------- 6. hồ sơ đối tượng ----------


def subject_profile(snapshot: Snapshot, person: str, forms: list[str] | None) -> ToolResult:
    key = code_key(person)
    subjects = [row for row in snapshot.query(
        "SELECT grp, person, full_name, gender, age, birth_year, birth_date, hometown FROM subjects", limit=100_000).rows
        if code_key(row[1]) == key]
    if not subjects:
        raise ToolError(f"Không tìm thấy đối tượng có mã {person}.")
    grp, code, name, gender, age, birth_year, birth_date, hometown = subjects[0]
    records = snapshot.query(
        "SELECT record_id, form, status, survey_date, answered, applicable, has_conclusion FROM records "
        "WHERE grp = ? AND person = ? ORDER BY form", [grp, code]).rows
    present = {row[1] for row in records}
    missing = [form for form in EXPECTED_FORMS[grp] if form not in present]
    info_rows = [{"field": label, "value": value} for label, value in (
        ("Mã đối tượng", code), ("Họ và tên", name or "—"), ("Nhóm", GROUP_LABEL[grp]), ("Giới tính", gender or "—"),
        ("Tuổi", age if age is not None else "—"), ("Ngày sinh / năm sinh", birth_date or birth_year or "—"),
        ("Quê quán", hometown or "—"))]
    form_rows = [{"form": form, "title": FORM_TITLES.get(form, form), "status": STATUS_LABEL[status],
                  "date": survey_date or "—", "progress": f"{answered}/{applicable}",
                  "conclusion": "Có" if has_conclusion else "Chưa"}
                 for _, form, status, survey_date, answered, applicable, has_conclusion in records]
    blocks = [
        table("Thông tin đối tượng", [("field", "Thông tin"), ("value", "Giá trị")], info_rows, csv=f"ho-so-{code}"),
        table(f"Các phiếu đã có ({len(records)})", [("form", "Mẫu"), ("title", "Loại phiếu"), ("status", "Trạng thái"),
                                                    ("date", "Ngày khảo sát"), ("progress", "Số câu trả lời"),
                                                    ("conclusion", "Kết luận")], form_rows, csv=f"phieu-{code}"),
    ]
    llm_answers = {}
    for form in [f.upper() for f in (forms or []) if f.upper() in present][:3]:
        record_id = next(row[0] for row in records if row[1] == form)
        values: dict[str, list[str]] = {}
        for question, value in snapshot.query("SELECT question, value FROM answers WHERE record_id = ?", [record_id],
                                              limit=1000).rows:
            values.setdefault(question, []).append(value)
        lines = [{"question": meta["question"], "label": meta["label"], "answer": ", ".join(values.get(meta["question"], []))
                  or "Chưa trả lời / không áp dụng"}
                 for (form_id, _), meta in QUESTIONS.items() if form_id == form and meta["kind"] != "identity"]
        llm_answers[form] = lines
        blocks.append(table(f"Câu trả lời {form} · {FORM_TITLES[form]}", [("question", "Câu"), ("label", "Nội dung"),
                                                                           ("answer", "Trả lời")], lines,
                            csv=f"{code}-{form}"))
    return ToolResult(
        llm={"person": code, "group": GROUP_LABEL[grp], "gender": gender, "age": age,
             "forms": [{"form": row["form"], "title": row["title"], "status": row["status"], "survey_date": row["date"],
                        "answered_of_applicable": row["progress"], "has_conclusion": row["conclusion"] == "Có"}
                       for row in form_rows],
             "missing_forms": missing, "answers": llm_answers,
             "note": "Họ tên, ngày sinh, quê quán chỉ hiển thị cho người dùng; bạn không thấy các thông tin này."},
        blocks=blocks,
        method=f"Hồ sơ đối tượng {code} ({GROUP_LABEL[grp]}): {len(records)} phiếu"
               + (f"; còn thiếu {', '.join(missing)}." if missing else "; đủ các mẫu của nhóm."))


# ---------- 7. tiến độ đối soát ----------


def review_progress(snapshot: Snapshot, by: str, filters: dict[str, Any] | None) -> ToolResult:
    column = {"form": "r.form", "code_prefix": "r.code_prefix", "group": "r.grp"}.get(by)
    if column is None:
        raise ToolError("by phải là form, code_prefix hoặc group.")
    where, params = scope(filters)
    rows = snapshot.query(
        f"SELECT {column}, status, COUNT(*), SUM(answered < applicable) FROM records r WHERE {where} "
        f"GROUP BY {column}, status", params).rows
    grouped: dict[str, dict[str, int]] = {}
    for key, status, count, incomplete in rows:
        item = grouped.setdefault(key, {"incomplete": 0})
        item[status] = count
        item["incomplete"] += incomplete or 0
    label = {"form": "Mẫu", "code_prefix": "Đầu mã", "group": "Nhóm"}[by]
    table_rows = []
    for key in sorted(grouped, key=natural):
        item = grouped[key]
        total = sum(item.get(status, 0) for status in STATUS_ORDER)
        table_rows.append({
            "key": GROUP_LABEL.get(key, key) if by == "group" else (f"{key} · {FORM_TITLES.get(key, '')}" if by == "form" else key),
            "total": total, **{status: item.get(status, 0) for status in STATUS_ORDER},
            "incomplete": item["incomplete"], "done": pct_text(item.get("complete", 0), total),
        })
    totals = {status: sum(row[status] for row in table_rows) for status in STATUS_ORDER}
    incomplete = sum(row["incomplete"] for row in table_rows)

    # Đối tượng còn thiếu phiếu (so với bộ mẫu của nhóm), trong phạm vi lọc trừ bộ lọc mẫu.
    person_filters = {**(filters or {}), "forms": None, "statuses": None}
    person_where, person_params = scope(person_filters)
    present: dict[tuple[str, str], set[str]] = {}
    for grp, person, form in snapshot.query(f"SELECT grp, person, form FROM records r WHERE {person_where}",
                                            person_params, limit=100_000).rows:
        present.setdefault((grp, person), set()).add(form)
    missing = {pair: [f for f in EXPECTED_FORMS[pair[0]] if f not in forms] for pair, forms in present.items()}
    missing = {pair: forms for pair, forms in missing.items() if forms}
    missing_by_form: dict[str, int] = {}
    for forms in missing.values():
        for form in forms:
            missing_by_form[form] = missing_by_form.get(form, 0) + 1
    blocks = [
        stats([("Đã hoàn tất", totals["complete"], "teal"), ("Chờ đối soát", totals["review"], "amber"),
               ("Bản nháp", totals["draft"], "gray"), ("Phiếu chưa đủ câu", incomplete, "navy")]),
        table(f"Tiến độ theo {label.lower()}", [("key", label), ("total", "Tổng phiếu"), ("complete", "Đã hoàn tất"),
                                                ("review", "Chờ đối soát"), ("draft", "Bản nháp"),
                                                ("incomplete", "Chưa đủ câu"), ("done", "% hoàn tất")],
              table_rows, csv="tien-do-doi-soat"),
    ]
    if missing:
        ordered = sorted(missing, key=lambda pair: (pair[0], natural(pair[1])))
        subjects = _subject_rows(snapshot, ordered[:LIST_LIMIT])
        blocks.append(table(
            f"Đối tượng còn thiếu phiếu ({len(missing)})",
            [("person", "Mã đối tượng"), ("name", "Họ và tên"), ("group", "Nhóm"), ("missing", "Thiếu mẫu")],
            [{"person": person, "grp": grp, "name": (subjects.get((grp, person)) or (None, None, None))[2] or "—",
              "group": GROUP_LABEL[grp], "missing": ", ".join(missing[(grp, person)])} for grp, person in ordered[:LIST_LIMIT]],
            total=len(missing), truncated=len(missing) > LIST_LIMIT, person=True, csv="doi-tuong-thieu-phieu"))
    return ToolResult(
        llm={"by": by, "totals": {STATUS_LABEL[s]: n for s, n in totals.items()}, "incomplete_records": incomplete,
             "rows": [{"key": row["key"], "total": row["total"], **{STATUS_LABEL[s]: row[s] for s in STATUS_ORDER},
                       "incomplete": row["incomplete"], "percent_complete": row["done"]} for row in table_rows],
             "persons_missing_forms": len(missing), "missing_by_form": missing_by_form},
        blocks=blocks,
        method=describe_scope(snapshot, filters) + " \"Chưa đủ câu\" = phiếu còn câu áp dụng chưa trả lời; "
               "\"thiếu phiếu\" so với bộ mẫu của nhóm (thanh niên F08–F09, quân nhân F01–F07).")


# ---------- 8. xu hướng theo thời gian ----------


def trend(snapshot: Snapshot, period: str, split: str, filters: dict[str, Any] | None) -> ToolResult:
    bucket = {"day": "r.survey_date", "week": "strftime('%Y-W%W', r.survey_date)",
              "month": "substr(r.survey_date, 1, 7)"}.get(period)
    if bucket is None:
        raise ToolError("period phải là day, week hoặc month.")
    where, params = scope(filters)
    period_label = {"day": "ngày", "week": "tuần", "month": "tháng"}[period]
    method = (describe_scope(snapshot, filters) + " Theo ngày khảo sát ghi trên phiếu; phiếu không ghi ngày "
              "(phần lớn phiếu quân nhân) lấy ngày nhập vào hệ thống.")
    if split == "none":
        rows = snapshot.query(f"SELECT {bucket} AS b, COUNT(*) FROM records r WHERE {where} AND r.survey_date IS NOT NULL "
                              f"GROUP BY b ORDER BY b", params).rows
        total = sum(count for _, count in rows)
        block = bars(f"Số phiếu theo {period_label}", [(b, n, pct(n, total)) for b, n in rows], "phiếu")
        return ToolResult(llm={"period": period, "series": [{"bucket": b, "records": n} for b, n in rows]},
                          blocks=[block], method=method)
    column = {"group": "r.grp", "form": "r.form", "status": "r.status"}.get(split)
    if column is None:
        raise ToolError("split phải là none, group, form hoặc status.")
    rows = snapshot.query(f"SELECT {bucket} AS b, {column}, COUNT(*) FROM records r WHERE {where} "
                          f"AND r.survey_date IS NOT NULL GROUP BY b, {column} ORDER BY b", params).rows
    label = {"group": lambda v: GROUP_LABEL.get(v, v), "status": lambda v: STATUS_LABEL.get(v, v), "form": lambda v: v}[split]
    keys = sorted({row[1] for row in rows}, key=natural)
    series: dict[str, dict[str, int]] = {}
    for b, key, n in rows:
        series.setdefault(b, {})[key] = n
    columns = [("bucket", period_label.capitalize())] + [(f"k{i}", label(k)) for i, k in enumerate(keys)] + [("total", "Tổng")]
    table_rows = [{"bucket": b, **{f"k{i}": values.get(k, 0) for i, k in enumerate(keys)}, "total": sum(values.values())}
                  for b, values in series.items()]
    return ToolResult(
        llm={"period": period, "split": split,
             "series": [{"bucket": b, **{label(k): values.get(k, 0) for k in keys}} for b, values in series.items()]},
        blocks=[table(f"Số phiếu theo {period_label}", columns, table_rows, csv="xu-huong")], method=method)


# ---------- 9. truy vấn nâng cao (dự phòng) ----------

COLUMN_LABEL = {
    "person": "Mã đối tượng", "full_name": "Họ và tên", "grp": "Nhóm", "form": "Mẫu", "status": "Trạng thái",
    "value": "Trả lời", "question": "Câu", "label": "Nội dung câu", "survey_date": "Ngày khảo sát",
    "gender": "Giới tính", "age": "Tuổi", "age_group": "Nhóm tuổi", "code_prefix": "Đầu mã", "birth_year": "Năm sinh",
    "birth_date": "Ngày sinh", "hometown": "Quê quán", "record_id": "Mã phiếu", "form_title": "Loại phiếu",
}


def run_sql(snapshot: Snapshot, sql: str, purpose: str) -> ToolResult:
    try:
        result = snapshot.query(sql, limit=SQL_LIMIT)
    except QueryError as error:
        raise ToolError(f"Truy vấn lỗi: {error}") from error
    keys = [f"c{index}" for index in range(len(result.columns))]
    columns = list(zip(keys, [COLUMN_LABEL.get(name, name) for name in result.columns]))
    lower = [name.lower() for name in result.columns]
    rows = []
    for row in result.rows:
        line = {}
        for key, name, value in zip(keys, lower, row):
            if name == "grp":
                value = GROUP_LABEL.get(value, value)
            elif name == "status":
                value = STATUS_LABEL.get(value, value)
            line[key] = value
        if "person" in lower and "grp" in lower:
            line["person"] = row[lower.index("person")]
            line["grp"] = row[lower.index("grp")]
        rows.append(line)
    block = table("Kết quả", columns, rows, total=len(rows), truncated=result.truncated,
                  person="person" in lower and "grp" in lower, csv="truy-van")
    visible = [index for index, name in enumerate(lower) if name not in SENSITIVE_COLUMNS]
    # Truy vấn có đọc cột định danh: gửi ít dòng hơn, che cả chuỗi ngày.
    sample = result.rows[:20 if result.sensitive else LLM_ROWS]
    llm_rows = [[snapshot.redact(row[index], result.sensitive) for index in visible] for row in sample]
    return ToolResult(
        llm={"columns": [result.columns[index] for index in visible], "rows": llm_rows, "row_count": len(result.rows),
             "truncated": result.truncated, "rows_sent_to_you": len(llm_rows),
             **({"hidden_columns": [result.columns[i] for i in range(len(lower)) if i not in visible]}
                if len(visible) < len(lower) else {})},
        blocks=[block], method=(purpose or "Truy vấn tuỳ chỉnh trên dữ liệu khảo sát.").strip()[:300],
        audit={"sql": sql})


# ---------- danh mục công cụ ----------


@dataclass
class Tool:
    name: str
    title: str  # tên thân thiện hiển thị cho người dùng
    description: str  # mô tả cho LLM
    parameters: dict[str, Any]
    run: Callable[..., ToolResult]
    suggestion: dict[str, Any] | None = None  # thẻ gợi ý trên giao diện


TOOLS: dict[str, Tool] = {tool.name: tool for tool in [
    Tool("find_questions", "Tra cứu biểu mẫu",
         "Tìm câu hỏi theo từ khoá (không dấu cũng được) để biết mã mẫu, mã câu và các đáp án. Dùng trước khi phân tích "
         "nếu chưa chắc câu nào.",
         obj({"keyword": {"type": "string"}, "form": nullable({"type": "string", "enum": FORM_IDS})}),
         lambda s, a: find_questions(s, a["keyword"], a.get("form"))),
    Tool("overview", "Tổng quan số liệu",
         "Tổng số phiếu, số đối tượng, số phiếu theo mẫu và trạng thái.",
         obj({"filters": FILTERS_SCHEMA}), lambda s, a: overview(s, a.get("filters")),
         {"icon": "layout", "description": "Số phiếu, số đối tượng và trạng thái theo từng loại phiếu",
          "examples": ["Tổng quan dữ liệu khảo sát hiện có", "Nhóm quân nhân có bao nhiêu phiếu mỗi loại?"]}),
    Tool("answer_distribution", "Phân bố câu trả lời",
         "Mỗi đáp án của MỘT câu hỏi được chọn bao nhiêu phiếu, tỷ lệ bao nhiêu.",
         obj({"form": {"type": "string", "enum": FORM_IDS}, "question": {"type": "string", "description": "VD 'Q026'"},
              "filters": FILTERS_SCHEMA}),
         lambda s, a: answer_distribution(s, a["form"], a["question"], a.get("filters")),
         {"icon": "bar", "description": "Mỗi đáp án của một câu hỏi được chọn bao nhiêu lần",
          "examples": ["Quân nhân trả lời thế nào về ý định tự sát hiện tại?",
                       "Tần suất uống rượu bia của thanh niên trong 12 tháng qua"]}),
    Tool("cross_tab", "So sánh theo nhóm",
         "Bảng chéo giữa hai chiều (câu hỏi, giới tính, nhóm tuổi, nhóm đối tượng, đầu mã, trạng thái), đếm theo đối "
         "tượng. Hai câu ở hai mẫu khác nhau được ghép theo mã đối tượng.",
         obj({"row": DIMENSION_SCHEMA, "column": DIMENSION_SCHEMA, "filters": FILTERS_SCHEMA}),
         lambda s, a: cross_tab(s, a["row"], a["column"], a.get("filters")),
         {"icon": "grid", "description": "Đối chiếu hai câu hỏi, hoặc một câu theo giới tính, nhóm tuổi, đơn vị",
          "examples": ["So sánh tần suất uống rượu bia theo nhóm tuổi ở thanh niên",
                       "Khó khăn về giấc ngủ của thanh niên theo giới tính"]}),
    Tool("find_subjects", "Tìm đối tượng theo câu trả lời",
         "Danh sách đối tượng có câu trả lời khớp điều kiện (kết hợp tất cả hoặc một trong các điều kiện). "
         "Bạn chỉ nhận số lượng và phân bố; danh sách họ tên hiện cho người dùng.",
         obj({"conditions": {"type": "array", "items": CONDITION_SCHEMA, "description": "1–5 điều kiện"},
              "match": {"type": "string", "enum": ["all", "any"]}, "filters": FILTERS_SCHEMA}),
         lambda s, a: find_subjects(s, a["conditions"], a.get("match") or "all", a.get("filters")),
         {"icon": "users", "description": "Liệt kê những người có câu trả lời thoả điều kiện",
          "examples": ["Liệt kê thanh niên có nghĩ đến tự sát trong tháng qua", "Quân nhân nào từng toan tự sát?"]}),
    Tool("subject_profile", "Hồ sơ một đối tượng",
         "Thông tin và các phiếu của một đối tượng theo mã; có thể kèm câu trả lời của tối đa 3 mẫu.",
         obj({"person": {"type": "string", "description": "Mã đối tượng, VD 'QK1.198'"},
              "forms": nullable({"type": "array", "items": {"type": "string", "enum": FORM_IDS}})}),
         lambda s, a: subject_profile(s, a["person"], a.get("forms")),
         {"icon": "user", "description": "Xem nhanh thông tin, các phiếu và câu trả lời của một người",
          "examples": ["Tóm tắt hồ sơ đối tượng QK1.198", "PT.CK.001 trả lời phiếu F09 thế nào?"]}),
    Tool("review_progress", "Tiến độ đối soát",
         "Số phiếu theo trạng thái, phiếu chưa đủ câu, đối tượng còn thiếu mẫu phiếu; chia theo mẫu, đầu mã hoặc nhóm.",
         obj({"by": {"type": "string", "enum": ["form", "code_prefix", "group"]}, "filters": FILTERS_SCHEMA}),
         lambda s, a: review_progress(s, a.get("by") or "form", a.get("filters")),
         {"icon": "check", "description": "Phiếu nào đã xong, còn chờ đối soát, ai còn thiếu phiếu",
          "examples": ["Tiến độ đối soát theo từng loại phiếu", "Những đối tượng nào còn thiếu phiếu?"]}),
    Tool("trend", "Xu hướng theo thời gian",
         "Số phiếu theo ngày/tuần/tháng khảo sát, có thể tách theo nhóm, mẫu hoặc trạng thái.",
         obj({"period": {"type": "string", "enum": ["day", "week", "month"]},
              "split": {"type": "string", "enum": ["none", "group", "form", "status"]}, "filters": FILTERS_SCHEMA}),
         lambda s, a: trend(s, a.get("period") or "month", a.get("split") or "none", a.get("filters")),
         {"icon": "trend", "description": "Số phiếu theo ngày, tuần hoặc tháng",
          "examples": ["Số phiếu khảo sát theo tháng của từng nhóm"]}),
    Tool("run_sql", "Truy vấn nâng cao",
         "CHỈ dùng khi các công cụ trên không trả lời được. Viết MỘT câu SELECT (SQLite) trên các bảng questions, "
         "subjects, records, answers. Đặt bí danh cột bằng tiếng Việt dễ hiểu. purpose: mô tả cách tính bằng lời "
         "thường (không có SQL) để hiển thị cho người dùng.",
         obj({"sql": {"type": "string"}, "purpose": {"type": "string"}}),
         lambda s, a: run_sql(s, a["sql"], a.get("purpose") or "")),
]}


def suggestions() -> list[dict[str, Any]]:
    return [{"tool": tool.name, "title": tool.title, **tool.suggestion} for tool in TOOLS.values() if tool.suggestion]


def openai_tools() -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": tool.name, "description": tool.description,
                                              "parameters": tool.parameters, "strict": True}}
            for tool in TOOLS.values()]
