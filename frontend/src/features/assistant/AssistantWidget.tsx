import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle, BarChart3, Check, ChevronDown, Copy, FileText, Info, LayoutDashboard, ListChecks, Maximize2, Minimize2,
  RotateCcw, SendHorizontal, Sparkles, Table2, TrendingUp, UserRound, Users, X, type LucideIcon,
} from 'lucide-react'
import { askAssistant, assistantError, getSuggestions, type AssistantReply, type Turn } from './api'
import { Blocks, RichText } from './blocks'
import './assistant.css'

type Message =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; reply: AssistantReply }
  | { id: string; role: 'error'; text: string; question: string }

const STORE_KEY = 'ta-assistant-v1'
const MAX_STORED = 30
const MAX_LENGTH = 1000
const ICONS: Record<string, LucideIcon> = {
  layout: LayoutDashboard, bar: BarChart3, file: FileText, grid: Table2, users: Users, user: UserRound, check: ListChecks, trend: TrendingUp,
}
const STEPS = ['Đang hiểu câu hỏi…', 'Đang truy vấn dữ liệu khảo sát…', 'Đang tính toán số liệu…', 'Đang soạn câu trả lời…']
const newId = () => Math.random().toString(36).slice(2)

function readStored(): Message[] {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORE_KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

function history(messages: Message[]): Turn[] {
  return messages.flatMap((message): Turn[] => message.role === 'user' ? [{ role: 'user', content: message.text }]
    : message.role === 'assistant' ? [{ role: 'assistant', content: message.reply.answer }] : []).slice(-8)
}

function Thinking() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setStep(value => Math.min(value + 1, STEPS.length - 1)), 2600)
    return () => window.clearInterval(timer)
  }, [])
  return <div className="ast-row assistant" aria-live="polite">
    <span className="ast-avatar"><Sparkles size={15} /></span>
    <div className="ast-thinking"><span className="ast-dots"><i /><i /><i /></span>{STEPS[step]}</div>
  </div>
}

function Answer({ reply, openPerson }: { reply: AssistantReply; openPerson: (group: string, person: string) => void }) {
  const [copied, setCopied] = useState(false)
  const [showMethod, setShowMethod] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(reply.answer.replace(/\*\*/g, ''))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch { /* Trình duyệt chặn clipboard: bỏ qua. */ }
  }
  return <div className="ast-row assistant">
    <span className="ast-avatar"><Sparkles size={15} /></span>
    <div className="ast-answer">
      <RichText text={reply.answer} />
      {reply.blocks.length > 0 && <div className="ast-blocks"><Blocks blocks={reply.blocks} openPerson={openPerson} /></div>}
      {(reply.methods.length > 0 || reply.tools.length > 0) && <div className="ast-meta">
        {reply.methods.length > 0 && <button type="button" className={`ast-method-toggle ${showMethod ? 'open' : ''}`}
          aria-expanded={showMethod} onClick={() => setShowMethod(value => !value)}>
          <Info size={13} />Cách tính<ChevronDown size={13} /></button>}
        {reply.tools.map(tool => <span key={tool} className="ast-tool-chip">{tool}</span>)}
        <button type="button" className="ast-icon-button ast-copy" title={copied ? 'Đã chép' : 'Chép câu trả lời'}
          aria-label="Chép câu trả lời" onClick={() => void copy()}>{copied ? <Check size={14} /> : <Copy size={14} />}</button>
      </div>}
      {showMethod && <ul className="ast-method">{reply.methods.map(method => <li key={method}>{method}</li>)}</ul>}
    </div>
  </div>
}

export function AssistantWidget({ openPerson }: { openPerson: (group: string, person: string) => void }) {
  const [open, setOpen] = useState(false)
  const [wide, setWide] = useState(false)
  const [messages, setMessages] = useState<Message[]>(readStored)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const launcher = useRef<HTMLButtonElement>(null)
  const suggestions = useQuery({ queryKey: ['assistant-suggestions'], queryFn: getSuggestions, enabled: open, staleTime: Infinity })

  useEffect(() => {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify(messages.slice(-MAX_STORED)))
    } catch { /* Hết chỗ lưu phiên: hội thoại vẫn dùng được. */ }
  }, [messages])
  useEffect(() => {
    if (open) scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy, open])
  useEffect(() => {
    if (open) window.setTimeout(() => textarea.current?.focus(), 60)
  }, [open])
  useEffect(() => {
    const element = textarea.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 132)}px`
  }, [input, open])

  async function send(text: string) {
    const question = text.trim().slice(0, MAX_LENGTH)
    if (!question || busy) return
    const previous = history(messages)
    setMessages(list => [...list, { id: newId(), role: 'user', text: question }])
    setInput('')
    setBusy(true)
    try {
      const reply = await askAssistant(question, previous)
      setMessages(list => [...list, { id: newId(), role: 'assistant', reply }])
    } catch (error) {
      setMessages(list => [...list, { id: newId(), role: 'error', text: assistantError(error), question }])
    } finally {
      setBusy(false)
      textarea.current?.focus()
    }
  }
  function retry(message: Extract<Message, { role: 'error' }>) {
    setMessages(list => {
      const index = list.findIndex(item => item.id === message.id)
      return index > 0 && list[index - 1].role === 'user' ? list.slice(0, index - 1) : list.filter(item => item.id !== message.id)
    })
    void send(message.question)
  }
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void send(input)
    }
  }
  function close() {
    setOpen(false)
    launcher.current?.focus()
  }

  return <>
    {open && <section className={`ast-panel ${wide ? 'wide' : ''}`} role="dialog" aria-label="Trợ lý dữ liệu"
      onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close() } }}>
      <header className="ast-header">
        <span className="ast-header-icon"><Sparkles size={18} /></span>
        <div className="ast-header-text"><h2>Trợ lý dữ liệu</h2><p>Hỏi đáp về dữ liệu khảo sát bằng tiếng Việt</p></div>
        <div className="ast-header-actions">
          {messages.length > 0 && <button type="button" title="Cuộc trò chuyện mới" aria-label="Cuộc trò chuyện mới"
            disabled={busy} onClick={() => setMessages([])}><RotateCcw size={16} /></button>}
          <button type="button" className="ast-wide-toggle" title={wide ? 'Thu nhỏ khung' : 'Mở rộng khung'}
            aria-label={wide ? 'Thu nhỏ khung' : 'Mở rộng khung'} onClick={() => setWide(value => !value)}>
            {wide ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>
          <button type="button" title="Đóng" aria-label="Đóng trợ lý" onClick={close}><X size={18} /></button>
        </div>
      </header>
      <div className="ast-body" ref={scroller}>
        {messages.length === 0 && <div className="ast-welcome">
          <div className="ast-hello"><strong>Xin chào!</strong> Bạn có thể hỏi bất kỳ điều gì về dữ liệu phiếu khảo sát:
            số liệu tổng hợp, phân bố câu trả lời, so sánh giữa các nhóm, hay tìm những đối tượng cần quan tâm.</div>
          <h3>Gợi ý câu hỏi</h3>
          {suggestions.isPending && <div className="ast-skeleton" aria-hidden="true"><i /><i /><i /></div>}
          {suggestions.isError && <p className="ast-muted">Chưa tải được gợi ý — bạn vẫn có thể gõ câu hỏi bên dưới.</p>}
          <div className="ast-suggestions">{suggestions.data?.map(item => {
            const ToolIcon = ICONS[item.icon] || Sparkles
            return <article key={item.tool} className="ast-suggestion">
              <div className="ast-suggestion-head"><span><ToolIcon size={16} /></span><div><b>{item.title}</b><small>{item.description}</small></div></div>
              <div className="ast-chips">{item.examples.map(example => <button type="button" key={example} disabled={busy}
                onClick={() => void send(example)}>{example}</button>)}</div>
            </article>
          })}</div>
        </div>}
        {messages.map(message => message.role === 'user'
          ? <div key={message.id} className="ast-row user"><div className="ast-bubble">{message.text}</div></div>
          : message.role === 'assistant' ? <Answer key={message.id} reply={message.reply} openPerson={openPerson} />
            : <div key={message.id} className="ast-row assistant">
              <span className="ast-avatar error"><AlertCircle size={15} /></span>
              <div className="ast-error"><p>{message.text}</p>
                <button type="button" disabled={busy} onClick={() => retry(message)}><RotateCcw size={13} />Thử lại</button></div>
            </div>)}
        {busy && <Thinking />}
      </div>
      <form className="ast-composer" onSubmit={event => { event.preventDefault(); void send(input) }}>
        <textarea ref={textarea} rows={1} value={input} maxLength={MAX_LENGTH} disabled={busy}
          placeholder="Hỏi về dữ liệu khảo sát…" aria-label="Câu hỏi cho trợ lý dữ liệu"
          onChange={event => setInput(event.target.value)} onKeyDown={onKey} />
        <button type="submit" className="ast-send" disabled={busy || !input.trim()} aria-label="Gửi câu hỏi" title="Gửi (Enter)">
          <SendHorizontal size={18} /></button>
      </form>
      <p className="ast-disclaimer">Enter để gửi · Shift+Enter xuống dòng · Số liệu sàng lọc, không thay cho chẩn đoán.</p>
    </section>}
    <button ref={launcher} type="button" className={`ast-launcher ${open ? 'open' : ''}`} aria-expanded={open}
      aria-label={open ? 'Đóng trợ lý dữ liệu' : 'Mở trợ lý dữ liệu'} onClick={() => open ? close() : setOpen(true)}>
      {open ? <X size={24} /> : <Sparkles size={24} />}
      {!open && <span className="ast-launcher-label">Trợ lý dữ liệu</span>}
    </button>
  </>
}
