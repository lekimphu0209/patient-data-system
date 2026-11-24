import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { Question } from './model'
import { Icon } from './ui'

const fold = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase()

/** Chọn câu hỏi: nút gọn một dòng, mở danh sách có ô tìm, mỗi câu hiện mã + nội dung (tối đa 2 dòng). */
export function QuestionPicker({ questions, value, onChange }: {
  questions: Question[]
  value: string
  onChange: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const listId = useId()
  const selected = questions.find(question => question.id === value) || questions[0]
  const matches = useMemo(() => {
    const words = fold(query).split(/\s+/).filter(Boolean)
    return questions.filter(question => words.every(word => fold(`${question.id} ${question.label}`).includes(word)))
  }, [questions, query])

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    return () => document.removeEventListener('pointerdown', onPointer)
  }, [open])
  useEffect(() => {
    list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  function show() {
    setQuery('')
    setActive(Math.max(0, questions.findIndex(question => question.id === selected.id)))
    setOpen(true)
  }
  function choose(question?: Question) {
    if (!question) return
    onChange(question.id)
    setOpen(false)
    trigger.current?.focus()
  }
  function onKey(event: KeyboardEvent) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActive(index => Math.min(Math.max(index + step, 0), Math.max(matches.length - 1, 0)))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      choose(matches[active])
    } else if (event.key === 'Escape') {
      // Chỉ đóng danh sách, không đóng cả hộp thoại phân tích.
      event.stopPropagation()
      setOpen(false)
      trigger.current?.focus()
    }
  }

  return <div className={`question-picker ${open ? 'open' : ''}`} ref={root}>
    <button ref={trigger} type="button" className="question-picker-trigger" aria-haspopup="listbox" aria-expanded={open}
      aria-controls={listId} aria-label={`Câu hỏi phân tích: ${selected.id} ${selected.label}`} title={selected.label}
      onClick={() => open ? setOpen(false) : show()}
      onKeyDown={event => { if (event.key === 'ArrowDown' && !open) { event.preventDefault(); show() } }}>
      <span className="question-code">{selected.id}</span>
      <span className="question-picker-label">{selected.label}</span>
      <Icon name="chevron" />
    </button>
    {open && <div className="question-picker-panel" onKeyDown={onKey}>
      <div className="question-picker-search"><Icon name="search" />
        <input autoFocus value={query} placeholder="Tìm theo mã hoặc nội dung câu hỏi…" aria-label="Tìm câu hỏi"
          aria-controls={listId} aria-activedescendant={matches[active] ? `${listId}-${matches[active].id}` : undefined}
          onChange={event => { setQuery(event.target.value); setActive(0) }} />
        <span className="question-picker-count">{matches.length}/{questions.length}</span>
      </div>
      <ul ref={list} id={listId} role="listbox" aria-label="Danh sách câu hỏi">
        {matches.length ? matches.map((question, index) => <li key={question.id} id={`${listId}-${question.id}`} role="option"
          data-index={index} aria-selected={question.id === selected.id}
          className={`${index === active ? 'active' : ''} ${question.id === selected.id ? 'selected' : ''}`}
          onPointerEnter={() => setActive(index)} onClick={() => choose(question)}>
          <span className="question-code">{question.id}</span>
          <span className="question-option-label">{question.label}</span>
          {question.id === selected.id && <Icon name="check" />}
        </li>) : <li className="question-picker-empty" role="presentation">Không có câu hỏi phù hợp</li>}
      </ul>
    </div>}
  </div>
}
