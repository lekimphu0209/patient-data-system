"""Vòng hội thoại function calling của trợ lý dữ liệu."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import settings

from .snapshot import FORM_TITLES, QUESTIONS, SCHEMA_DOC, QueryError, Snapshot
from .tools import TOOLS, ToolError, openai_tools

logger = logging.getLogger(__name__)

MAX_TOOL_RESULT_CHARS = 12_000
MAX_BLOCKS = 6
MAX_HISTORY = 8


class AssistantUnavailable(RuntimeError):
    """Chưa cấu hình được LLM (thiếu khoá, chế độ giả lập)."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMReply:
    content: str | None
    tool_calls: list[ToolCall]
    usage: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    # Mục đầu ra riêng của nhà cung cấp (VD suy luận đã mã hoá) cần gửi lại ở lượt sau.
    items: list[dict[str, Any]] = field(default_factory=list)


class AssistantLLM(Protocol):
    """``messages`` theo dạng chat: system/user/assistant, assistant kèm ``tool_calls`` (và ``items``), tool."""

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> LLMReply: ...


class OpenAIAssistantLLM:
    """Gọi OpenAI Responses API (model suy luận chỉ hỗ trợ function calling ở đây).

    ``store=False``: OpenAI không lưu hội thoại; phần suy luận được trả về dạng mã hoá để gửi lại.
    """

    def __init__(self, model: str | None = None):
        self.model = model or settings.ASSISTANT_MODEL or settings.OCR_MODEL

    @staticmethod
    def _input(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
        instructions, items = None, []
        for message in messages:
            role = message["role"]
            if role == "system":
                instructions = message["content"]
            elif role == "tool":
                items.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                              "output": message["content"]})
            elif message.get("tool_calls"):
                items.extend(message.get("items") or [
                    {"type": "function_call", "call_id": call["id"], "name": call["function"]["name"],
                     "arguments": call["function"]["arguments"]} for call in message["tool_calls"]])
            else:
                items.append({"role": role, "content": message.get("content") or ""})
        return instructions, items

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> LLMReply:
        from app.core.openai_client import openai_client

        instructions, items = self._input(messages)
        options: dict[str, Any] = {}
        effort = settings.ASSISTANT_REASONING_EFFORT.strip().lower()
        if effort:
            options["reasoning"] = {"effort": effort}
            options["include"] = ["reasoning.encrypted_content"]
        if tools:
            options["tools"] = [{"type": "function", **tool["function"]} for tool in tools]
        response = openai_client().responses.create(
            model=self.model, instructions=instructions, input=items, max_output_tokens=8_000, store=False, **options,
        )
        output = [item.model_dump(exclude_none=True) for item in response.output or []]
        calls = [ToolCall(item["call_id"], item["name"], item.get("arguments") or "{}")
                 for item in output if item.get("type") == "function_call"]
        usage = response.usage.model_dump() if response.usage else {}
        return LLMReply(
            content=response.output_text, tool_calls=calls, model=response.model or self.model, items=output,
            usage={"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0),
                   "total_tokens": usage.get("total_tokens", 0)},
        )


def get_assistant_llm() -> AssistantLLM:
    if not settings.OPENAI_API_KEY or settings.OCR_PROVIDER.strip().lower() == "stub":
        raise AssistantUnavailable("Trợ lý dữ liệu chưa được cấu hình (thiếu OPENAI_API_KEY).")
    return OpenAIAssistantLLM()


def _catalog() -> str:
    lines = []
    for form_id, title in sorted(FORM_TITLES.items()):
        group = "thanh niên" if form_id in ("F08", "F09") else "quân nhân"
        lines.append(f"## {form_id} · {title} ({group})")
        for (form, question), meta in QUESTIONS.items():
            if form != form_id:
                continue
            kind = {"identity": " [định danh — không thống kê]", "text": " [tự do]", "multi": " [nhiều lựa chọn]"}.get(
                meta["kind"], "")
            label = meta["label"] if len(meta["label"]) <= 120 else meta["label"][:117] + "…"
            lines.append(f"{question}: {label}{kind}")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""Bạn là "Trợ lý dữ liệu" của hệ thống quản lý phiếu khảo sát sức khỏe tâm thần, Bệnh viện Quân y 103.
Người hỏi là cán bộ, bác sĩ của bệnh viện. Luôn trả lời bằng tiếng Việt.

Dữ liệu: phiếu sàng lọc của hai nhóm đối tượng — thanh niên (youth; mẫu F08, F09) và quân nhân (military; mẫu F01–F07).
Mỗi đối tượng có mã (VD PT.CK.001, PT.TL.012, QK1.198); đầu mã PT.CK, PT.TL là thanh niên của hai địa bàn, QK1 là quân nhân.
Trạng thái phiếu: complete = Đã hoàn tất (đã đối soát), review = Chờ đối soát, draft = Bản nháp. Phần lớn phiếu hiện
chưa đối soát, nên khi nêu số liệu hãy nói rõ là tính trên các phiếu nào (công cụ đã trả về phần "Cách tính" cho người dùng).

Cách làm việc:
- Luôn lấy số liệu bằng công cụ; KHÔNG BAO GIỜ tự bịa số. Ưu tiên công cụ chuyên biệt; chỉ dùng run_sql khi các công cụ
  khác không đáp ứng được.
- Chưa chắc câu hỏi nằm ở mẫu/câu nào thì gọi find_questions trước (danh mục rút gọn ở cuối).
- Người dùng nói "thanh niên"/"quân nhân" thì đặt filters.group tương ứng. "Đã đối soát"/"đã hoàn tất" = statuses ["complete"].
- Câu hỏi mơ hồ: chọn cách hiểu hợp lý nhất và nói rõ cách hiểu; chỉ hỏi lại khi thật sự không thể đoán.
- Công cụ báo lỗi tham số thì sửa tham số và gọi lại.

Cách trả lời:
- Ngắn gọn, 1–5 câu, nêu các con số chính (có thể in đậm bằng **...**). Không dựng bảng trong câu trả lời — bảng và biểu
  đồ đã hiển thị bên dưới cho người dùng; chỉ cần nhắc "xem bảng bên dưới" khi cần.
- KHÔNG hiển thị SQL, tên công cụ, tên bảng hay tên cột kỹ thuật.
- Đây là số liệu sàng lọc, không phải chẩn đoán: không kết luận ai mắc bệnh; dùng cách nói "trả lời", "có dấu hiệu",
  "sàng lọc".
- Bạn không bao giờ thấy họ tên, ngày sinh, quê quán; danh sách người cụ thể hiển thị trực tiếp cho người dùng. Không
  đoán hay bịa họ tên.
- Câu hỏi ngoài phạm vi dữ liệu khảo sát: nói lịch sự rằng bạn chỉ hỗ trợ hỏi đáp về dữ liệu khảo sát.

Dữ liệu cho run_sql:
{SCHEMA_DOC}

Danh mục câu hỏi (mã câu: nội dung):
{_catalog()}
"""


@dataclass
class AssistantAnswer:
    text: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)  # nhật ký (kể cả SQL) — không trả về giao diện
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


def _add_usage(total: dict[str, int], usage: dict[str, Any]) -> None:
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            total[key] = total.get(key, 0) + value


def run(llm: AssistantLLM, snapshot: Snapshot, question: str, history: list[dict[str, str]],
        max_steps: int | None = None) -> AssistantAnswer:
    steps = max_steps or settings.ASSISTANT_MAX_STEPS
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-MAX_HISTORY:]:
        if turn.get("role") in ("user", "assistant") and (turn.get("content") or "").strip():
            messages.append({"role": turn["role"], "content": turn["content"][:2_000]})
    messages.append({"role": "user", "content": question})
    answer = AssistantAnswer(text="")
    tools = openai_tools()
    for step in range(steps):
        final_step = step == steps - 1
        reply = llm.complete(messages, None if final_step else tools)
        _add_usage(answer.usage, reply.usage)
        answer.model = reply.model or answer.model
        if not reply.tool_calls or final_step:
            answer.text = (reply.content or "").strip()
            break
        messages.append({
            "role": "assistant", "content": reply.content or None, "items": reply.items,
            "tool_calls": [{"id": call.id, "type": "function",
                            "function": {"name": call.name, "arguments": call.arguments}} for call in reply.tool_calls],
        })
        for call in reply.tool_calls:
            payload = _execute(snapshot, call, answer)
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(payload, ensure_ascii=False, default=str)[:MAX_TOOL_RESULT_CHARS]})
    if not answer.text:
        answer.text = ("Mình chưa tìm được câu trả lời phù hợp. Bạn thử hỏi cụ thể hơn, ví dụ nêu nhóm đối tượng "
                       "hoặc nội dung câu hỏi trong phiếu.")
    answer.blocks = answer.blocks[-MAX_BLOCKS:]
    return answer


def _execute(snapshot: Snapshot, call: ToolCall, answer: AssistantAnswer) -> dict[str, Any]:
    tool = TOOLS.get(call.name)
    record: dict[str, Any] = {"tool": call.name, "arguments": call.arguments}
    answer.calls.append(record)
    if tool is None:
        record["error"] = "unknown tool"
        return {"error": f"Không có công cụ {call.name}."}
    try:
        arguments = json.loads(call.arguments or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")
    except (json.JSONDecodeError, ValueError):
        record["error"] = "invalid arguments"
        return {"error": "Tham số không phải JSON hợp lệ."}
    try:
        result = tool.run(snapshot, arguments)
    except (ToolError, QueryError) as error:
        record["error"] = str(error)
        return {"error": str(error)}
    except Exception as error:  # noqa: BLE001 - lỗi bất ngờ của một công cụ không làm hỏng cả câu trả lời
        logger.exception("Công cụ %s lỗi", call.name)
        record["error"] = f"{type(error).__name__}: {error}"
        return {"error": "Công cụ gặp lỗi khi tính; thử cách khác."}
    record.update(result.audit)
    if tool.title not in answer.tools and call.name != "find_questions":
        answer.tools.append(tool.title)
    answer.blocks.extend(result.blocks)
    if result.method and result.method not in answer.methods:
        answer.methods.append(result.method)
    return result.llm
