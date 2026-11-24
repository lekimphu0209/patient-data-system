import { Fragment, type ReactNode } from 'react'
import { Download, ExternalLink } from 'lucide-react'
import type { BarsBlock, Block, StatsBlock, TableBlock } from './api'

const number = (value: number) => value.toLocaleString('vi-VN')
const percent = (value: number | null) => value === null ? '' : `${value.toLocaleString('vi-VN', { maximumFractionDigits: 1 })}%`

/** Chữ đậm **...** trong một dòng. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> : <Fragment key={index}>{part}</Fragment>)
}

/** Hiển thị câu trả lời: đoạn văn, gạch đầu dòng, danh sách đánh số, chữ đậm — không dùng HTML thô. */
export function RichText({ text }: { text: string }) {
  const nodes: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  const flush = () => {
    if (!list) return
    const items = list.items.map((item, index) => <li key={index}>{inline(item)}</li>)
    nodes.push(list.ordered ? <ol key={nodes.length}>{items}</ol> : <ul key={nodes.length}>{items}</ul>)
    list = null
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const bullet = line.match(/^[-•*]\s+(.*)$/)
    const numbered = line.match(/^\d+[.)]\s+(.*)$/)
    if (bullet || numbered) {
      const ordered = Boolean(numbered)
      if (list && list.ordered !== ordered) flush()
      list = list || { ordered, items: [] }
      list.items.push((bullet || numbered)![1])
      continue
    }
    flush()
    if (line) nodes.push(<p key={nodes.length}>{inline(line.replace(/^#+\s*/, ''))}</p>)
  }
  flush()
  return <div className="ast-rich">{nodes}</div>
}

function Stats({ block }: { block: StatsBlock }) {
  return <div className="ast-stats">{block.items.map(item => <div key={item.label} className={`ast-stat ${item.tone}`}>
    <span>{item.label}</span><strong>{number(item.value)}</strong></div>)}</div>
}

function Bars({ block }: { block: BarsBlock }) {
  const max = Math.max(1, ...block.items.map(item => item.count))
  return <section className="ast-block">
    <h4 title={block.title}>{block.title}</h4>
    <div className="ast-bars">{block.items.map(item => <div className="ast-bar" key={item.label}>
      <div className="ast-bar-label" title={item.label}>{item.label}</div>
      <div className="ast-bar-row">
        <div className="ast-bar-track"><span style={{ width: `${item.count / max * 100}%` }} /></div>
        <span className="ast-bar-value"><b>{number(item.count)}</b>{item.percent !== null && <em>{percent(item.percent)}</em>}</span>
      </div>
    </div>)}</div>
    <div className="ast-block-foot">Đơn vị: {block.unit}{block.note ? ` · ${block.note}` : ''}</div>
  </section>
}

function csvCell(value: unknown) {
  const text = value === null || value === undefined ? '' : String(value)
  return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function downloadCsv(block: TableBlock) {
  const lines = [block.columns.map(column => csvCell(column.label)).join(',')]
  for (const row of block.rows) lines.push(block.columns.map(column => csvCell(row[column.key])).join(','))
  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${block.csvName}-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}

function Table({ block, openPerson }: { block: TableBlock; openPerson?: (group: string, person: string) => void }) {
  const personColumn = block.personKey ? block.columns.find(column => column.key === block.personKey
    || column.label === 'Mã đối tượng')?.key : undefined
  return <section className="ast-block">
    <div className="ast-table-head">
      <h4 title={block.title}>{block.title}</h4>
      <button type="button" className="ast-icon-button" title="Tải bảng (CSV)" aria-label={`Tải bảng ${block.title} dạng CSV`}
        onClick={() => downloadCsv(block)}><Download size={15} /></button>
    </div>
    {block.rows.length ? <div className="ast-table-wrap" tabIndex={0} aria-label={block.title}><table className="ast-table">
      <thead><tr>{block.columns.map(column => <th key={column.key}>{column.label}</th>)}</tr></thead>
      <tbody>{block.rows.map((row, index) => <tr key={index}>{block.columns.map(column => {
        const value = row[column.key]
        const text = value === null || value === undefined || value === '' ? '—' : typeof value === 'number' ? number(value) : value
        if (column.key === personColumn && openPerson && block.personKey && block.groupKey && row[block.groupKey]) {
          return <td key={column.key}><button type="button" className="ast-person" title="Mở hồ sơ phiếu của đối tượng"
            onClick={() => openPerson(String(row[block.groupKey!]), String(row[block.personKey!]))}>
            {text}<ExternalLink size={12} /></button></td>
        }
        const long = typeof text === 'string' && text.length > 24
        return <td key={column.key} className={long ? 'wrap' : undefined}>{text}</td>
      })}</tr>)}</tbody>
    </table></div> : <p className="ast-empty-table">Không có dòng nào.</p>}
    {block.truncated && <div className="ast-block-foot">Hiển thị {number(block.rows.length)}/{number(block.total)} dòng · tải CSV
      để có danh sách đang hiển thị.</div>}
  </section>
}

export function Blocks({ blocks, openPerson }: { blocks: Block[]; openPerson?: (group: string, person: string) => void }) {
  return <>{blocks.map((block, index) => block.type === 'stats' ? <Stats key={index} block={block} />
    : block.type === 'bars' ? <Bars key={index} block={block} />
      : <Table key={index} block={block} openPerson={openPerson} />)}</>
}
