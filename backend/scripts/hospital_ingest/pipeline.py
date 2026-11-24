"""Điều phối: quét file -> nhận diện trang -> đọc phiếu -> gán mã -> ghi.

Ba giai đoạn gọi VLM/ghi đều chạy lại được: mỗi kết quả VLM nằm trong cache ngay khi
có; file chỉ được ghi khi mọi kết quả của nó đã đủ (thiếu do mạng/hết ngân sách thì để
lần chạy sau); việc ghi bỏ qua phiếu đã có.
"""

from __future__ import annotations

import csv
import fcntl
import hashlib
import json
import random
import shutil
import threading
import time
from collections import defaultdict
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.surveys.ocr.bundle import CLASSIFY_PROMPT, classify_prompt, classify_schema, page_ranges
from app.modules.surveys.ocr.extractor import (
    ModelOutput, ModelResponseError, StubSurveyExtractor, get_survey_extractor,
)
from app.modules.surveys.ocr.pages import BLANK_INK_RATIO, JPEG_QUALITY, PageSet
from app.modules.surveys.ocr.schema import SYSTEM_PROMPT, form_prompt, normalize, response_schema
from app.modules.surveys.ocr.service import STORAGE_DIR
from app.modules.surveys.schemas import FORMS

from . import render
from .cache import Cache, fingerprint
from .segment import (
    Segment, assign_numbers, choose_prefix, choose_width, format_code, numbers_read, segment_pages,
)
from .sources import SourceFile, discover, fold, sha256
from .store import FormResult, Ledger, Person, foreign_records, sweep_orphans, write_person

# Giá gpt-5.6-luna (USD / 1 triệu token) — chỉ để ước tính và chặn ngân sách.
PRICE_INPUT = 0.20
PRICE_OUTPUT = 1.20
CLASSIFY_BATCH = 10
SCAN_BATCH = 50
ATTEMPTS = 5
MODEL_ERROR_ATTEMPTS = 3
GROUP_LABEL = {"youth": "Thanh niên", "military": "Quân nhân"}


class TransientFailure(RuntimeError):
    """Lỗi tạm thời (mạng, quá tải, hết ngân sách): không lưu, lần chạy sau thử lại."""


class BudgetExceeded(TransientFailure):
    pass


@dataclass
class Options:
    data: Path
    work: Path
    workers: int = 24
    processes: int = 16
    max_pages: int | None = None
    only: list[str] = field(default_factory=list)
    max_cost: float = 40.0
    retry_failed: bool = False
    dry_run: bool = False
    allow_existing: bool = False


@dataclass
class FileState:
    source: SourceFile
    checksum: str | None = None
    total_pages: int = 0
    blank: list[int] = field(default_factory=list)
    error: str | None = None
    numbers: list[int] = field(default_factory=list)  # trang có nội dung được xử lý
    truncated: bool = False  # chạy thử: chỉ xử lý một phần đầu file
    labels: dict[int, dict[str, Any]] | None = None
    segments: list[Segment] = field(default_factory=list)
    # Người có trang không nhận diện được (hoặc sát cạnh trang đó): ranh giới không chắc.
    unreliable: dict[int, str] = field(default_factory=dict)
    persons: list[Person] = field(default_factory=list)
    prefix: str | None = None
    prefix_note: str = ""
    mode: str = ""
    status: str = ""


def usage_cost(usage: dict[str, Any] | None) -> float:
    usage = usage or {}
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    return (prompt * PRICE_INPUT + completion * PRICE_OUTPUT) / 1_000_000


def _pages_key(pages: list[int]) -> str:
    return hashlib.sha1(",".join(map(str, pages)).encode()).hexdigest()[:8]


class Runner:
    def __init__(
        self,
        options: Options,
        *,
        extractor=None,
        executor_factory: Callable[[int], Executor] | None = None,
        session_factory=SessionLocal,
        storage_dir: Path | None = None,
        log: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.options = options
        self.extractor = extractor
        self.executor_factory = executor_factory or self._process_pool
        self.session_factory = session_factory
        self.storage_dir = storage_dir or STORAGE_DIR
        self.log = log or (lambda message: print(message, flush=True))
        self.sleep = sleep
        self.cache = Cache(options.work / "cache")
        self.ledger = Ledger(options.work / "ledger.jsonl")
        self.forms = {group: [form for form in FORMS if form["group"] == group] for group in GROUP_LABEL}
        self.model = settings.OCR_MODEL
        self._lock = threading.Lock()
        self.calls = 0
        self.spent = 0.0
        self.failures: dict[tuple[str, str], str] = {}
        self._budget_warned = False

    @staticmethod
    def _process_pool(size: int) -> Executor:
        import multiprocessing

        return ProcessPoolExecutor(max_workers=size, mp_context=multiprocessing.get_context("spawn"))

    # ---------- điểm vào ----------

    def scan(self) -> list[FileState]:
        with self._locked(), self.executor_factory(self.options.processes) as pool:
            return self._prepare(pool)

    def run(self) -> list[FileState]:
        with self._locked():
            if not self.options.dry_run and not self.options.allow_existing:
                with self.session_factory() as db:
                    existing = foreign_records(db)
                if existing:
                    raise SystemExit(
                        f"Database còn {existing} phiếu khảo sát không do script này nạp. Chạy bước sao lưu + xoá "
                        "dữ liệu cũ trước (hoặc thêm --allow-existing nếu cố ý nạp chồng)."
                    )
            if self.options.retry_failed:
                self.log(f"Xoá {self.cache.drop_failures()} kết quả lỗi đã lưu để đọc lại.")
            if self.extractor is None:
                self.extractor = get_survey_extractor()
                if isinstance(self.extractor, StubSurveyExtractor):
                    raise SystemExit("OCR_PROVIDER đang là 'stub' (dữ liệu giả). Cấu hình OPENAI_API_KEY và "
                                     "OCR_PROVIDER=openai trong .env trước khi nạp dữ liệu thật.")
            with self.executor_factory(self.options.processes) as pool:
                states = self._prepare(pool)
                ready = [state for state in states if state.error is None]
                self._run_units("Nhận diện trang", pool, [unit for state in ready for unit in self._classify_units(state)])
                for state in ready:
                    self._load_labels(state)
                labelled = [state for state in ready if state.labels is not None]
                self._run_units("Đọc phiếu", pool, [unit for state in labelled for unit in self._extract_units(state)])
            self._decide(labelled)
            self._write(labelled)
            self._report(states)
            return states

    # ---------- quét file ----------

    def _prepare(self, pool: Executor) -> list[FileState]:
        files = discover(self.options.data)
        if self.options.only:
            wanted = [fold(text) for text in self.options.only]
            files = [item for item in files if any(text in fold(item.label) for text in wanted)]
        if not files:
            raise SystemExit(f"Không thấy file PDF nào trong thư mục nhóm đối tượng dưới {self.options.data}.")
        states = [FileState(source) for source in files]
        index = self._file_index()
        for state in states:
            stat = state.source.path.stat()
            entry = index.get(state.source.label)
            if entry and entry["size"] == stat.st_size and entry["mtime"] == stat.st_mtime_ns:
                state.checksum = entry["sha256"]
            else:
                state.checksum = sha256(state.source.path)
                index[state.source.label] = {"size": stat.st_size, "mtime": stat.st_mtime_ns, "sha256": state.checksum}
        self._save_file_index(index)

        scan_print = fingerprint("scan", BLANK_INK_RATIO)
        pending: list[tuple[FileState, Any]] = []
        for state in states:
            cached = self.cache.get(state.checksum, "scan", scan_print)
            if cached:
                state.total_pages, state.blank, state.error = cached["pages"], cached["blank"], cached.get("error")
                continue
            try:
                state.total_pages = pool.submit(render.page_count, str(state.source.path)).result()
            except Exception as error:  # noqa: BLE001 - PyMuPDF báo lỗi bằng nhiều loại exception
                state.error = f"không mở được file PDF (file hỏng hoặc chép chưa xong): {error}"
                self.cache.put(state.checksum, "scan", {"fingerprint": scan_print, "pages": 0, "blank": [],
                                                        "error": state.error})
                continue
            numbers = list(range(1, state.total_pages + 1))
            batches = [numbers[i:i + SCAN_BATCH] for i in range(0, len(numbers), SCAN_BATCH)]
            pending.append((state, [pool.submit(render.blank_pages, str(state.source.path), batch) for batch in batches]))
        for state, futures in pending:
            try:
                state.blank = sorted(number for future in futures for number in future.result())
            except Exception as error:  # noqa: BLE001
                state.error = f"không đọc được trang của file PDF: {error}"
                continue
            self.cache.put(state.checksum, "scan", {"fingerprint": scan_print, "pages": state.total_pages,
                                                    "blank": state.blank})

        for state in states:
            if state.error:
                continue
            blank = set(state.blank)
            numbers = [number for number in range(1, state.total_pages + 1) if number not in blank]
            if self.options.max_pages and state.total_pages > self.options.max_pages:
                numbers = [number for number in numbers if number <= self.options.max_pages]
                state.truncated = True
            state.numbers = numbers
            if not numbers:
                state.error = "mọi trang đều trắng"
        return states

    def _file_index(self) -> dict[str, Any]:
        path = self.options.work / "files.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_file_index(self, index: dict[str, Any]) -> None:
        path = self.options.work / "files.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- gọi VLM ----------

    def _classify_print(self, group: str) -> str:
        forms = self.forms[group]
        return fingerprint("classify", self.model, settings.EXTRACTION_PDF_DPI, JPEG_QUALITY, CLASSIFY_PROMPT,
                           classify_prompt(forms), classify_schema(forms))

    def _extract_print(self, form: dict[str, Any]) -> str:
        return fingerprint("extract", self.model, settings.EXTRACTION_PDF_DPI, JPEG_QUALITY, SYSTEM_PROMPT,
                           form_prompt(form), response_schema(form))

    def _classify_batches(self, state: FileState) -> list[list[int]]:
        numbers = state.numbers
        return [numbers[i:i + CLASSIFY_BATCH] for i in range(0, len(numbers), CLASSIFY_BATCH)]

    def _classify_units(self, state: FileState):
        group = state.source.group
        stamp = self._classify_print(group)
        for batch in self._classify_batches(state):
            name = f"classify_{batch[0]:04d}-{batch[-1]:04d}"
            if self.cache.get(state.checksum, name, stamp) is None:
                yield (state, name, stamp, batch,
                       lambda pages, group=group: self.extractor.classify(self.forms[group], pages))

    def _extract_units(self, state: FileState):
        for index, segment in enumerate(state.segments):
            if index in state.unreliable:
                continue
            for part in segment.parts:
                stamp = self._extract_print(part.form)
                name = self._extract_name(part.form["id"], part.pages)
                if self.cache.get(state.checksum, name, stamp) is None:
                    yield (state, name, stamp, part.pages,
                           lambda pages, form=part.form: self.extractor.extract(form, pages))

    @staticmethod
    def _extract_name(form_id: str, pages: list[int]) -> str:
        return f"extract_{form_id}_{pages[0]:04d}_{_pages_key(pages)}"

    def _run_units(self, title: str, pool: Executor, units: list[tuple]) -> None:
        if not units:
            self.log(f"[{title}] mọi phần đã có kết quả từ lần chạy trước — không gọi VLM.")
            return
        self.log(f"[{title}] {len(units)} lượt gọi VLM cần chạy ...")
        started, done, failed = time.time(), 0, 0
        with ThreadPoolExecutor(max_workers=self.options.workers) as threads:
            futures = [threads.submit(self._unit, pool, *unit) for unit in units]
            for future in as_completed(futures):
                done += 1
                failed += not future.result()
                if done % 20 == 0 or done == len(units):
                    elapsed = time.time() - started
                    rest = elapsed / done * (len(units) - done)
                    self.log(f"[{title}] {done}/{len(units)} — lỗi {failed} — chi phí lần chạy này ~${self.spent:.2f}"
                             f" — đã chạy {elapsed / 60:.1f} phút, còn ~{rest / 60:.1f} phút")

    def _unit(self, pool: Executor, state: FileState, name: str, stamp: str, numbers: list[int], call) -> bool:
        """Một lượt VLM; trả về True nếu đã có kết quả (đúng hoặc lỗi cố định) trong cache."""
        try:
            images = pool.submit(render.render_pages, str(state.source.path), numbers,
                                 settings.EXTRACTION_PDF_DPI).result()
        except BrokenProcessPool as error:
            self.failures[(state.source.label, name)] = f"tiến trình đọc trang bị dừng: {error}"
            return False
        except Exception as error:  # noqa: BLE001 - trang hỏng: lỗi cố định, lưu lại để không thử mãi
            message = f"không đọc được trang {page_ranges(numbers)}: {type(error).__name__}: {error}"
            self.cache.put(state.checksum, name, {"fingerprint": stamp, "pages": numbers, "error": message})
            self.failures[(state.source.label, name)] = message
            return False
        try:
            output = self._call(lambda: call(PageSet(pages=images, total_pages=state.total_pages)))
        except ModelResponseError as error:
            self.cache.put(state.checksum, name, {"fingerprint": stamp, "pages": numbers, "error": str(error)})
            self.failures[(state.source.label, name)] = str(error)
            return False
        except TransientFailure as error:
            self.failures[(state.source.label, name)] = str(error)
            return False
        self.cache.put(state.checksum, name, {
            "fingerprint": stamp, "pages": numbers, "raw": output.raw, "usage": output.usage,
            "model": output.model, "provider": output.provider,
        })
        return True

    def _call(self, request: Callable[[], ModelOutput]) -> ModelOutput:
        model_errors = 0
        for attempt in range(1, ATTEMPTS + 1):
            with self._lock:
                if self.spent >= self.options.max_cost:
                    if not self._budget_warned:
                        self._budget_warned = True
                        self.log(f"[DỪNG] Đã chạm ngân sách ${self.options.max_cost:.2f} cho lần chạy này. "
                                 "Chạy lại với --max-cost cao hơn để tiếp tục (phần đã xong không gọi lại).")
                    raise BudgetExceeded("hết ngân sách cho lần chạy này")
                self.calls += 1
            try:
                output = request()
            except ModelResponseError:
                model_errors += 1
                if model_errors >= MODEL_ERROR_ATTEMPTS:
                    raise
            except Exception as error:  # noqa: BLE001 - mạng, 429, 5xx, timeout: thử lại có giãn cách
                if attempt == ATTEMPTS:
                    raise TransientFailure(f"{type(error).__name__}: {error}") from error
            else:
                with self._lock:
                    self.spent += usage_cost(output.usage)
                return output
            self.sleep(min(60.0, 5 * 2 ** (attempt - 1)) + random.random())
        raise TransientFailure("hết số lần thử")

    # ---------- tách người, gán mã ----------

    def _load_labels(self, state: FileState) -> None:
        stamp = self._classify_print(state.source.group)
        labels: dict[int, dict[str, Any]] = {}
        failed: dict[int, str] = {}
        for batch in self._classify_batches(state):
            entry = self.cache.get(state.checksum, f"classify_{batch[0]:04d}-{batch[-1]:04d}", stamp)
            if entry is None:
                state.status = "chưa nhận diện xong trang — chạy lại để tiếp tục"
                return
            if "error" in entry:
                failed.update(dict.fromkeys(batch, entry["error"]))
                continue
            for item in (entry["raw"] or {}).get("pages") or []:
                if isinstance(item, dict) and item.get("page") in batch:
                    labels.setdefault(item["page"], item)
        state.labels = labels
        state.segments = segment_pages(self.forms[state.source.group], state.numbers, labels)
        if state.truncated and state.segments:
            state.segments.pop()  # người cuối có thể bị cắt dở ở giới hạn trang chạy thử
        # Trang không nhận diện được có thể là ranh giới giữa hai người: không đoán, người chứa
        # trang đó và hai người kề bên chuyển sang nạp tay.
        for index, segment in enumerate(state.segments):
            pages = [number for number in segment.pages if number in failed]
            if not pages:
                continue
            reason = (f"trang {page_ranges(pages)} không nhận diện được ({failed[pages[0]]}) nên ranh giới "
                      "giữa các người quanh đó không chắc chắn")
            for near in (index - 1, index, index + 1):
                if 0 <= near < len(state.segments):
                    state.unreliable.setdefault(near, reason)

    def _decide(self, states: list[FileState]) -> None:
        by_group: dict[str, list[FileState]] = defaultdict(list)
        for state in states:
            if self._collect(state):
                by_group[state.source.group].append(state)
        decisions = self._decisions()
        for group, items in by_group.items():
            reads = [person.reads for state in items for person in state.persons]
            fallback = next((state.source.digits for state in items if state.source.digits), None)
            width = choose_width(reads, fallback)
            fixed = decisions.setdefault("width", {}).get(group)
            if fixed is None:
                decisions["width"][group] = width
            elif fixed != width:
                self.log(f"[CHÚ Ý] Số chữ số của mã nhóm {GROUP_LABEL[group]} lần này tính ra {width}, "
                         f"giữ {fixed} như lần nạp trước để mã thống nhất.")
            width = decisions["width"][group]
            for state in items:
                self._assign(state, width)
        self._save_decisions(decisions)

        seen: dict[tuple[str, str], str] = {}
        for state in states:
            for person in state.persons:
                if person.problem or not person.code:
                    continue
                key = (state.source.group, person.code)
                where = f"{state.source.label} (người thứ {person.index + 1})"
                if key in seen:
                    person.problem = f"trùng mã {person.code} với {seen[key]}"
                else:
                    seen[key] = where

    def _collect(self, state: FileState) -> bool:
        """Đọc kết quả VLM của mọi phiếu trong file; False nếu còn thiếu."""
        persons: list[Person] = []
        for index, segment in enumerate(state.segments):
            forms: list[FormResult] = []
            for part in segment.parts:
                if index in state.unreliable:
                    forms.append(FormResult(part, problem="không xác định chắc trang thuộc người nào"))
                    continue
                entry = self.cache.get(state.checksum, self._extract_name(part.form["id"], part.pages),
                                       self._extract_print(part.form))
                if entry is None:
                    state.status = "chưa đọc xong các phiếu — chạy lại để tiếp tục"
                    return False
                item = FormResult(part)
                if "error" in entry:
                    item.problem = f"VLM không đọc được ({entry['error']})"
                else:
                    item.output = ModelOutput(raw=entry["raw"], provider=entry["provider"], model=entry["model"],
                                              usage=entry.get("usage") or {})
                    item.result = normalize(part.form, entry["raw"])
                    if not item.result.is_expected_form:
                        item.problem = f"VLM nhận đây không phải mẫu {part.form['id']}"
                    elif item.result.is_empty:
                        item.problem = "không đọc được câu trả lời nào"
                forms.append(item)
            person = Person(
                source=state.source, checksum=state.checksum, total_pages=state.total_pages,
                index=index, count=len(state.segments), segment=segment, forms=forms,
                labels=[state.labels[number] for number in segment.pages if number in state.labels],
            )
            person.problem = state.unreliable.get(index)
            person.reads = [code for _, code in segment.written] + [
                item.result.subject["code"] for item in person.accepted if item.result.subject.get("code")
            ]
            persons.append(person)
        state.persons = persons
        if not persons:
            state.status = f"không nhận ra phiếu nào thuộc nhóm {GROUP_LABEL[state.source.group]}"
        return True

    def _assign(self, state: FileState, width: int) -> None:
        source = state.source
        reads = [person.reads for person in state.persons]
        state.prefix, state.prefix_note = choose_prefix(source.hint, reads)
        end = source.end
        if state.truncated and source.start is not None:
            end = source.start + len(state.persons) - 1  # chạy thử: chỉ có một phần đầu file
        numbering = assign_numbers(source.start, end, [numbers_read(item) for item in reads])
        state.mode = numbering.mode
        for person, number in zip(state.persons, numbering.numbers):
            if person.problem:
                continue
            counter = numbers_read(person.reads)
            ranked = counter.most_common(2)
            if not person.accepted:
                person.problem = "không đọc được phiếu nào của người này"
            elif state.prefix is None:
                person.problem = "không xác định được tiền tố mã đối tượng của file"
            elif number is None:
                person.problem = numbering.problems.get(person.index, "không xác định được mã")
            elif len(ranked) == 2 and ranked[1][1] >= 2 and ranked[1][1] * 2 >= ranked[0][1]:
                person.problem = (f"các phiếu ghi mã khác nhau ({', '.join(sorted(set(person.reads)))}) — "
                                  "có thể gộp nhầm phiếu của hai người")
            if person.problem:
                continue
            person.code = format_code(state.prefix, number, width)
            position = f"người thứ {person.index + 1}/{len(state.persons)} trong file"
            if numbering.mode == "anchors":
                person.code_doubtful = True
                person.code_note = (f"Mã đối tượng {person.code} suy ra từ mã viết tay đọc được và vị trí ({position}), "
                                    "vì số người tách được không khớp dải mã trên tên file — đối chiếu mã trên phiếu gốc.")
            elif not counter:
                person.code_note = f"Mã đối tượng {person.code} gán theo thứ tự trong file ({position}); không đọc được mã viết tay để đối chiếu."
            elif number in counter:
                person.code_note = f"Mã đối tượng {person.code} gán theo thứ tự trong file ({position}), khớp mã viết tay trên phiếu."
            else:
                person.code_doubtful = True
                person.code_note = (f"Mã đối tượng {person.code} gán theo thứ tự trong file ({position}) nhưng mã viết tay "
                                    f"đọc được là {', '.join(sorted(set(person.reads)))} — đối chiếu mã trên phiếu gốc.")

    def _decisions(self) -> dict[str, Any]:
        path = self.options.work / "decisions.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_decisions(self, decisions: dict[str, Any]) -> None:
        if self.options.dry_run:
            return
        path = self.options.work / "decisions.json"
        path.write_text(json.dumps(decisions, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- ghi ----------

    def _write(self, states: list[FileState]) -> None:
        import fitz

        manual = self.options.work / "manual"
        with self.session_factory() as db:
            if not self.options.dry_run:
                removed = sweep_orphans(db, self.storage_dir)
                if removed:
                    self.log(f"Đã xoá {removed} file tách dở của lần chạy bị ngắt trước.")
            for state in states:
                if not state.persons:
                    continue
                # PDF nạp tay của file này được tạo lại mỗi lần chạy (bỏ bản cũ đã nạp được).
                folder = manual / state.source.group / state.source.path.stem
                shutil.rmtree(folder, ignore_errors=True)
                with fitz.open(state.source.path) as document:
                    for person in state.persons:
                        if person.problem:
                            self._export(document, folder, f"nguoi-{person.index + 1:03d}", person.segment.pages)
                            continue
                        if not self.options.dry_run:
                            try:
                                write_person(db, person, document, self.storage_dir, self.ledger.ids)
                            except Exception as error:  # noqa: BLE001 - một người lỗi không chặn người khác
                                person.problem = f"lỗi khi ghi: {type(error).__name__}: {error}"
                                continue
                            self.ledger.add(person.created)
                        for item in person.forms:
                            if item.problem:
                                self._export(document, folder, f"{person.code}_{item.part.form['id']}", item.part.pages)
                state.status = state.status or ("đã xử lý (chạy thử, chưa ghi)" if self.options.dry_run else "đã nạp")

    def _export(self, document, folder: Path, stem: str, pages: list[int]) -> None:
        """PDF để nạp tay qua giao diện (tải file của một người hoặc một phiếu)."""
        import fitz

        folder.mkdir(parents=True, exist_ok=True)
        first, last = min(pages), max(pages)
        with fitz.open() as output:
            output.insert_pdf(document, from_page=first - 1, to_page=last - 1)
            output.save(folder / f"{stem}_trang-{first}-{last}.pdf", garbage=3, deflate=True)

    # ---------- báo cáo ----------

    def _report(self, states: list[FileState]) -> None:
        folder = self.options.work / "report"
        folder.mkdir(parents=True, exist_ok=True)
        total_cost = 0.0
        with (folder / "nguoi.csv").open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.writer(output)
            writer.writerow(["nhom", "file", "nguoi_thu", "trang", "ma_doi_tuong", "ma_doc_duoc", "phieu_da_nap",
                             "phieu_da_co", "phieu_loi", "can_nap_tay", "ghi_chu_ma"])
            for state in states:
                for person in state.persons:
                    writer.writerow([
                        GROUP_LABEL[state.source.group], state.source.label, person.index + 1,
                        page_ranges(person.segment.pages), person.code or "", "; ".join(person.reads),
                        " ".join(person.created), " ".join(person.existing),
                        "; ".join(f"{item.part.form['id']} trang {page_ranges(item.part.pages)}: {item.problem}"
                                  for item in person.forms if item.problem),
                        person.problem or "", person.code_note,
                    ])
        lines = []
        for state in states:
            if state.checksum:
                total_cost += self._cached_cost(state.checksum)
            source = state.source
            if state.error:
                lines.append(f"- {source.label}: BỎ QUA — {state.error}")
                continue
            expected = source.expected
            found = len(state.persons) or len(state.segments)
            manual = sum(1 for person in state.persons if person.problem)
            created = sum(len(person.created) for person in state.persons)
            existing = sum(len(person.existing) for person in state.persons)
            failed_forms = sum(1 for person in state.persons if not person.problem for item in person.forms if item.problem)
            doubtful = sum(1 for person in state.persons if person.code_doubtful and not person.problem)
            lines.append(
                f"- {source.label}: {state.total_pages} trang ({len(state.blank)} trắng)"
                f"{' [chạy thử ' + str(len(state.numbers)) + ' trang đầu]' if state.truncated else ''}; "
                f"tách được {found} người (dải mã trên tên file: {expected if expected is not None else '?'}); "
                f"tiền tố {state.prefix or '?'} ({state.prefix_note or '-'}); "
                f"gán mã {'theo thứ tự' if state.mode == 'order' else 'theo mã đọc được' if state.mode else '-'}; "
                f"phiếu mới {created}, đã có {existing}; mã cần đối chiếu {doubtful}; "
                f"phiếu lỗi {failed_forms}; người cần nạp tay {manual}; {state.status or '-'}"
            )
        summary = [
            f"Lượt gọi VLM lần chạy này: {self.calls} — chi phí ~${self.spent:.2f}; "
            f"tổng chi phí VLM đã dùng cho các file này (mọi lần chạy) ~${total_cost:.2f}.",
            *lines,
        ]
        if self.failures:
            summary.append(f"{len(self.failures)} phần chưa xong/lỗi (chạy lại để tiếp tục):")
            summary += [f"  {label} {name}: {message}" for (label, name), message in sorted(self.failures.items())[:30]]
        text = "\n".join(summary)
        (folder / "tom-tat.txt").write_text(text + "\n", encoding="utf-8")
        self.log("\n" + text)
        self.log(f"\nBáo cáo chi tiết: {folder / 'nguoi.csv'}; PDF cần nạp tay (nếu có): {self.options.work / 'manual'}")

    def _cached_cost(self, checksum: str) -> float:
        total = 0.0
        for path in (self.cache.root / checksum[:16]).glob("*.json"):
            try:
                total += usage_cost(json.loads(path.read_text(encoding="utf-8")).get("usage"))
            except (OSError, json.JSONDecodeError):
                continue
        return total

    # ---------- khoá ----------

    def _locked(self):
        runner = self

        class _Lock:
            def __enter__(self):
                runner.options.work.mkdir(parents=True, exist_ok=True)
                self.handle = (runner.options.work / ".lock").open("w")
                try:
                    fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    self.handle.close()
                    raise SystemExit("Đang có một lượt nạp khác chạy trên cùng thư mục làm việc.") from None

            def __exit__(self, *exc):
                fcntl.flock(self.handle, fcntl.LOCK_UN)
                self.handle.close()

        return _Lock()
