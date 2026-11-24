"""Tách trang của một file thành từng người và gán mã đối tượng.

Phần này chỉ là logic thuần (không đọc file, không gọi VLM) để kiểm thử kỹ được.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.modules.surveys.ocr.schema import canonical_code

CODE_PARTS = re.compile(r"^(?P<prefix>.*?)(?P<number>\d+)$")
# Số lần liên tiếp mã đọc được lệch cùng một khoảng so với thứ tự trong file thì coi
# là thứ tự đã bị xô lệch (tách sai một người), không còn tin thứ tự được nữa.
SHIFT_RUN = 3


@dataclass
class Part:
    form: dict[str, Any]
    pages: list[int] = field(default_factory=list)


@dataclass
class Segment:
    """Các trang có nội dung của một người, theo thứ tự trong file."""

    pages: list[int] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    other: list[int] = field(default_factory=list)
    # Mã viết tay đọc được ở trang tiêu đề các phiếu: (số trang, mã như đã chép).
    written: list[tuple[int, str]] = field(default_factory=list)
    _latest: dict[str, Part] = field(default_factory=dict, repr=False)
    _last_form: str | None = field(default=None, repr=False)

    def part(self, form_id: str) -> Part | None:
        return self._latest.get(form_id)


def lead_form(form_ids: set[str], labels: dict[int, dict[str, Any]]) -> str | None:
    """Mẫu mở đầu bộ phiếu của mỗi người, nếu file có.

    Mã đối tượng viết tay chỉ có ở trang đầu bộ phiếu (F02 của quân nhân, F08 của thanh
    niên). Mẫu chiếm ít nhất 4/5 số trang mở đầu có ghi mã thì coi là mẫu mở đầu; không
    rõ ràng như vậy thì None.
    """
    votes = Counter(
        item.get("form") for item in labels.values()
        if item.get("form") in form_ids and item.get("starts_form") is True
        and isinstance(item.get("subject_code"), str) and item["subject_code"].strip()
    )
    if not votes:
        return None
    form_id, count = votes.most_common(1)[0]
    return form_id if count >= 2 and count * 5 >= sum(votes.values()) * 4 else None


def segment_pages(forms: list[dict[str, Any]], numbers: list[int], labels: dict[int, dict[str, Any]]) -> list[Segment]:
    """Gom các trang (đã bỏ trang trắng) thành từng người.

    Cùng nguyên tắc với tải file một người trên giao diện: một mẫu đã có của người hiện
    tại lại xuất hiện (thêm trang tiêu đề, hoặc lặp lại sau một mẫu khác) nghĩa là đã
    sang phiếu của người tiếp theo. Trang không thuộc mẫu nào trong nhóm (ví dụ Mẫu 02
    của quân nhân) đi theo người đang xét.

    File có mẫu mở đầu rõ ràng (xem `lead_form`) thì trang đầu của mẫu đó luôn mở người
    mới. Khi đó một trang tiếp nối (không phải trang đầu mẫu) bị nhận nhầm số mẫu, ví dụ
    trang 2 của Mẫu 06 đọc thành "Mẫu 05", được giữ với phiếu đang đọc thay vì tách người.
    Nếu tách ở đó, mọi ranh giới phía sau trong file sẽ lệch nửa người.
    """
    by_id = {form["id"]: form for form in forms}
    lead = lead_form(set(by_id), {number: labels[number] for number in numbers if number in labels})
    segments: list[Segment] = []
    current = Segment()
    for number in numbers:
        item = labels.get(number) or {}
        form_id = item.get("form")
        starts = item.get("starts_form") is True
        if form_id in by_id:
            part = current.part(form_id)
            repeated = part is not None and (starts or current._last_form != form_id)
            if lead is not None and form_id != lead and repeated and not starts:
                current._latest[current._last_form].pages.append(number)
                current.pages.append(number)
                continue
            if repeated or (form_id == lead and starts and current.parts):
                segments.append(current)
                current = Segment()
                part = None
            if part is None:
                part = current._latest[form_id] = Part(by_id[form_id])
                current.parts.append(part)
            part.pages.append(number)
            current._last_form = form_id
        else:
            current.other.append(number)
        current.pages.append(number)
        written = item.get("subject_code")
        if starts and isinstance(written, str) and written.strip():
            current.written.append((number, written.strip()))
    segments.append(current)
    return [segment for segment in segments if segment.parts]


def split_code(value: Any) -> tuple[str, str] | None:
    """"PT.TL 085" -> ("PT.TL", "085"); "QK1.41" -> ("QK1", "41"); "085" -> ("", "085").

    Không kết thúc bằng số -> None. Tiền tố không có chữ cái nào thì bỏ (chỉ còn số).
    """
    match = CODE_PARTS.match(canonical_code(value) or "")
    if not match:
        return None
    prefix = match.group("prefix").rstrip(".")
    return (prefix if re.search(r"[^\W\d_]", prefix) else ""), match.group("number")


def numbers_read(reads: list[str]) -> Counter[int]:
    """Số thứ tự trong các mã đọc được của một người, kèm số lần đọc ra số đó."""
    counter: Counter[int] = Counter()
    for read in reads:
        parts = split_code(read)
        if parts:
            counter[int(parts[1])] += 1
    return counter


def choose_prefix(hint: str | None, reads_per_segment: list[list[str]]) -> tuple[str | None, str]:
    """Tiền tố mã của cả file: (tiền tố, cách chọn).

    Tên file có thể ghi sai tiền tố (file "PT.PL ..." nhưng trên phiếu viết "PT.TL"),
    nên ưu tiên tiền tố viết trên phiếu khi đa số người trong file đọc ra cùng một tiền
    tố. Mực đỏ khó đọc làm tiền tố đọc ra lộn xộn ("QH1", "QCH") thì giữ theo tên file
    nếu tên file vẫn được ít nhất 1/5 số người xác nhận.
    """
    votes: Counter[str] = Counter()
    voters = 0
    for reads in reads_per_segment:
        prefixes = {parts[0] for parts in map(split_code, reads) if parts and parts[0]}
        votes.update(prefixes)
        voters += bool(prefixes)
    if hint and voters and votes[hint] * 5 >= voters:
        return hint, f"theo tên file, {votes[hint]}/{voters} người đọc được cùng tiền tố"
    if votes:
        top, count = votes.most_common(1)[0]
        if count * 2 > voters:
            return top, f"theo mã viết tay, {count}/{voters} người"
    if hint:
        return hint, "theo tên file (không đọc được đủ mã viết tay để đối chiếu)"
    return None, "không xác định được tiền tố mã"


def choose_width(reads_per_segment: list[list[str]], fallback: int | None) -> int:
    """Số chữ số của phần số trong mã (PT.CK.001 -> 3, QK1.01 -> 2), theo cách người điền viết."""
    votes: Counter[int] = Counter()
    for reads in reads_per_segment:
        lengths = Counter(
            len(parts[1]) for parts in map(split_code, reads)
            if parts and int(parts[1]) < 100 and len(parts[1]) <= 4
        )
        if lengths:
            votes[lengths.most_common(1)[0][0]] += 1
    if votes:
        return votes.most_common(1)[0][0]
    return fallback or 2


def format_code(prefix: str, number: int, width: int) -> str:
    return f"{prefix}.{number:0{width}d}"


def _plurality(counter: Counter[int], *, minimum: int) -> int | None:
    """Số được đọc ra nhiều nhất (ít nhất ``minimum`` lần, không hoà)."""
    ranked = counter.most_common(2)
    if not ranked or ranked[0][1] < minimum or (len(ranked) > 1 and ranked[1][1] == ranked[0][1]):
        return None
    return ranked[0][0]


def _shifted(start: int, reads: list[Counter[int]]) -> bool:
    """Thứ tự trong file đã lệch so với mã đọc được (tách sai một chỗ nào đó)?"""
    run_offset, run = None, 0
    compared = disagreed = 0
    for index, counter in enumerate(reads):
        read = _plurality(counter, minimum=1)
        if read is None:
            continue
        compared += 1
        offset = read - (start + index)
        if offset == 0 or (start + index) in counter:
            run_offset, run = None, 0
            continue
        disagreed += 1
        run = run + 1 if offset == run_offset else 1
        run_offset = offset
        if run >= SHIFT_RUN:
            return True
    return compared >= 4 and disagreed * 2 > compared


@dataclass
class Numbering:
    mode: str  # "order": theo thứ tự trong file; "anchors": theo mã đọc được
    numbers: list[int | None]
    problems: dict[int, str]


def assign_numbers(start: int | None, end: int | None, reads: list[Counter[int]]) -> Numbering:
    """Số thứ tự (phần số của mã) cho từng người trong file.

    Bình thường file xếp đúng thứ tự và số người khớp dải mã trên tên file: gán theo
    thứ tự, mã đọc được chỉ để đối chiếu. Số người không khớp (thiếu/thừa một người,
    hoặc tách sai) thì neo theo các mã đọc chắc chắn (ít nhất hai lần đọc ra cùng số) rồi
    đếm tiếp giữa các điểm neo; người nằm giữa hai đoạn lệch nhau thì không gán.
    """
    count = len(reads)
    if start is not None and end is not None and count == end - start + 1 and not _shifted(start, reads):
        return Numbering("order", [start + index for index in range(count)], {})

    low = start if start is not None else 1
    anchors = {
        index: number for index, counter in enumerate(reads)
        if (number := _plurality(counter, minimum=2)) is not None
        and number >= low and (end is None or number <= end)
    }
    offsets = {index: number - index for index, number in anchors.items()}
    ordered = sorted(offsets)
    # Một điểm neo lệch khỏi hai điểm neo hai bên (vốn khớp nhau) là đọc nhầm số.
    trusted = {
        index: offsets[index] for position, index in enumerate(ordered)
        if not (
            0 < position < len(ordered) - 1
            and offsets[ordered[position - 1]] == offsets[ordered[position + 1]] != offsets[index]
        )
    }
    keys = sorted(trusted)
    numbers: list[int | None] = []
    problems: dict[int, str] = {}
    for index in range(count):
        before = max((key for key in keys if key <= index), default=None)
        after = min((key for key in keys if key >= index), default=None)
        guesses = {trusted[key] + index for key in (before, after) if key is not None}
        if len(guesses) == 1:
            numbers.append(guesses.pop())
            continue
        numbers.append(None)
        problems[index] = (
            "không đọc chắc được mã nào trong file để xác định thứ tự" if not guesses
            else "nằm giữa hai đoạn có thứ tự lệch nhau (có thể thiếu/thừa trang hoặc tách sai người)"
        )

    for index, number in enumerate(numbers):
        if number is not None and (number < low or (end is not None and number > end)):
            numbers[index] = None
            problems[index] = f"số thứ tự suy ra ({number}) nằm ngoài dải mã của file"
    repeated = Counter(number for number in numbers if number is not None)
    for index, number in enumerate(numbers):
        if number is not None and repeated[number] > 1:
            numbers[index] = None
            problems[index] = f"trùng số thứ tự {number} với người khác trong file"
    return Numbering("anchors", numbers, problems)
