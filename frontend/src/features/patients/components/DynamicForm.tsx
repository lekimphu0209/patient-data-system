/**
 * Render bệnh án từ schema do backend trả về (form_schema.json).
 *
 * Không có field nào được hard-code ở frontend: thêm/bớt mục trong template chỉ
 * cần sửa JSON ở backend. Giá trị được lưu lồng đúng theo cấu trúc group của
 * schema, ví dụ `{ general: { weight: 60 }, mental_exam: { emotion: {...} } }`.
 */

import { useEffect, useState } from 'react'

import { FormField, Input, Textarea } from '@/components/ui'
import type { FormNode, FormValues } from '../api'

// ==================== Helpers ====================

const isLeaf = (node: FormNode) => node.type !== 'group' && node.type !== 'block'

function isVisible(node: FormNode, siblingValues: FormValues): boolean {
  const rule = node.show_if
  if (!rule) return true
  const target = siblingValues?.[rule.field]
  if (rule.includes !== undefined) {
    return Array.isArray(target) && target.includes(rule.includes)
  }
  if (rule.equals !== undefined) {
    return target === rule.equals
  }
  return true
}

function optionLabel(node: FormNode, value: unknown) {
  return node.options?.find((o) => o.value === value)?.label ?? String(value ?? '')
}

/** Chuyển giá trị của một field thành chuỗi hiển thị ở chế độ xem. */
export function formatFieldValue(node: FormNode, value: unknown): string {
  if (value === undefined || value === null || value === '') return ''

  switch (node.type) {
    case 'radio':
      return optionLabel(node, value)
    case 'checkbox_group':
      if (!Array.isArray(value) || value.length === 0) return ''
      return value.map((v) => optionLabel(node, v)).join(', ')
    case 'matrix': {
      if (typeof value !== 'object') return ''
      const parts = (node.rows ?? [])
        .filter((row) => (value as FormValues)[row.id])
        .map((row) => {
          const col = node.columns?.find((c) => c.value === (value as FormValues)[row.id])
          return `${row.label}: ${col?.label ?? ''}`
        })
      return parts.join('; ')
    }
    case 'date': {
      const parsed = new Date(String(value))
      return Number.isNaN(parsed.getTime())
        ? String(value)
        : parsed.toLocaleDateString('vi-VN')
    }
    case 'number':
      return node.unit ? `${value} ${node.unit}` : String(value)
    default:
      return String(value)
  }
}

/** Số ô của một node — bảng ma trận tính theo số dòng. */
export function countLeaves(node: FormNode): number {
  if (node.type === 'matrix') return node.rows?.length ?? 0
  if (isLeaf(node)) return 1
  return (node.children ?? []).reduce((total, child) => total + countLeaves(child), 0)
}

/** Số ô đã có dữ liệu — dùng để báo tiến độ soát từng mục. */
export function countFilled(node: FormNode, value: unknown): number {
  if (!isLeaf(node)) {
    const values = (value ?? {}) as FormValues
    return (node.children ?? []).reduce(
      (total, child) => total + countFilled(child, values[child.id]),
      0,
    )
  }

  if (node.type === 'matrix') {
    if (!value || typeof value !== 'object') return 0
    const cells = value as FormValues
    return (node.rows ?? []).filter((row) => cells[row.id]).length
  }

  if (value === undefined || value === null || value === '') return 0
  if (Array.isArray(value)) return value.length > 0 ? 1 : 0
  return 1
}

/** Tóm tắt một group thành một dòng ngắn — dùng cho ô trong bảng lần khám. */
export function summarizeGroup(node: FormNode, values: FormValues | undefined): string {
  if (!values) return ''
  const parts: string[] = []
  for (const child of node.children ?? []) {
    if (isLeaf(child)) {
      const text = formatFieldValue(child, values[child.id])
      if (text) parts.push(`${child.label}: ${text}`)
    } else {
      const nested = summarizeGroup(child, values[child.id])
      if (nested) parts.push(nested)
    }
  }
  return parts.join(' · ')
}

// ==================== Input controls ====================

/**
 * Ô nhập số giữ nguyên chuỗi đang gõ để không chặn số thập phân: gõ "36." mà
 * đẩy ngay Number() lên state thì ký tự "." bị nuốt, không nhập nổi 36.8.
 */
function NumberInput({
  id,
  value,
  disabled,
  onChange,
}: {
  id: string
  value: unknown
  disabled?: boolean
  onChange: (next: number | undefined) => void
}) {
  const incoming = value === undefined || value === null ? '' : String(value)
  const [text, setText] = useState(incoming)

  useEffect(() => {
    // Chỉ đồng bộ lại khi giá trị bên ngoài thực sự khác (reset form, tải xong).
    setText((current) => (Number(current) === Number(incoming) && (incoming !== '' || current === '') ? current : incoming))
  }, [incoming])

  return (
    <Input
      id={id}
      type="number"
      step="any"
      value={text}
      disabled={disabled}
      onChange={(e) => {
        const next = e.target.value
        setText(next)
        if (next === '') onChange(undefined)
        else if (!Number.isNaN(Number(next))) onChange(Number(next))
      }}
    />
  )
}

function LeafInput({
  node,
  fieldId,
  value,
  onChange,
}: {
  node: FormNode
  fieldId: string
  value: unknown
  onChange: (next: unknown) => void
}) {
  switch (node.type) {
    case 'textarea':
      return (
        <Textarea
          id={fieldId}
          rows={3}
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={node.readonly}
        />
      )

    case 'number':
      return (
        <NumberInput id={fieldId} value={value} disabled={node.readonly} onChange={onChange} />
      )

    case 'date':
      return (
        <Input
          id={fieldId}
          type="date"
          value={(value as string)?.slice(0, 10) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={node.readonly}
          required={node.required}
        />
      )

    case 'radio':
      return (
        <div className="flex flex-wrap gap-x-5 gap-y-2 pt-1">
          {node.options?.map((option) => (
            <label key={option.value} className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="radio"
                name={fieldId}
                checked={value === option.value}
                onChange={() => onChange(option.value)}
                disabled={node.readonly}
                className="h-4 w-4 accent-brand-600"
              />
              {option.label}
            </label>
          ))}
          {value !== undefined && value !== '' && !node.readonly && (
            <button
              type="button"
              onClick={() => onChange(undefined)}
              className="text-xs text-slate-400 underline hover:text-slate-600"
            >
              Bỏ chọn
            </button>
          )}
        </div>
      )

    case 'checkbox_group': {
      const selected: string[] = Array.isArray(value) ? value : []
      return (
        <div className="flex flex-wrap gap-x-5 gap-y-2 pt-1">
          {node.options?.map((option) => (
            <label key={option.value} className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={selected.includes(option.value)}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...selected, option.value]
                      : selected.filter((v) => v !== option.value),
                  )
                }
                disabled={node.readonly}
                className="h-4 w-4 accent-brand-600"
              />
              {option.label}
            </label>
          ))}
        </div>
      )
    }

    case 'matrix': {
      const current: FormValues = (value as FormValues) ?? {}
      return (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Triệu chứng
                </th>
                {node.columns?.map((col) => (
                  <th
                    key={col.value}
                    className="w-24 px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-600"
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {node.rows?.map((row) => (
                <tr key={row.id}>
                  <td className="px-3 py-2 text-slate-700">{row.label}</td>
                  {node.columns?.map((col) => (
                    <td key={col.value} className="px-3 py-2 text-center">
                      <input
                        type="radio"
                        name={`${fieldId}-${row.id}`}
                        checked={current[row.id] === col.value}
                        onChange={() => onChange({ ...current, [row.id]: col.value })}
                        disabled={node.readonly}
                        className="h-4 w-4 accent-brand-600"
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    default:
      return (
        <Input
          id={fieldId}
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={node.readonly}
        />
      )
  }
}

// ==================== Node renderers ====================

/** Field rộng hết hàng thay vì nằm trong lưới 2 cột. */
const isWide = (node: FormNode) =>
  node.type === 'textarea' || node.type === 'matrix' || node.type === 'checkbox_group'

function LeafView({ node, value }: { node: FormNode; value: unknown }) {
  const text = formatFieldValue(node, value)
  return (
    <div className="grid grid-cols-[minmax(140px,220px)_1fr] items-baseline gap-4 py-1">
      <dt className="text-sm font-medium text-slate-600">{node.label}</dt>
      <dd className="whitespace-pre-wrap text-sm text-slate-900">{text || '—'}</dd>
    </div>
  )
}

function NodeChildren({
  nodes,
  values,
  onChange,
  mode,
  path,
}: {
  nodes: FormNode[]
  values: FormValues
  onChange: (next: FormValues) => void
  mode: 'edit' | 'view'
  path: string
}) {
  const setChild = (id: string, next: unknown) => onChange({ ...values, [id]: next })
  const visible = nodes.filter((node) => isVisible(node, values))

  return (
    <div className="space-y-4">
      {visible.map((node) => {
        // Id/name phải kèm đường dẫn: nhiều group dùng chung id ("description",
        // "finding", "symptoms"...) nên nếu chỉ lấy node.id thì các nhóm radio
        // khác nhau sẽ dùng chung name và đá lẫn nhau.
        const nodePath = `${path}.${node.id}`

        if (!isLeaf(node)) {
          return (
            <SubGroup
              key={node.id}
              node={node}
              path={nodePath}
              values={values[node.id] ?? {}}
              onChange={(next) => setChild(node.id, next)}
              mode={mode}
            />
          )
        }

        if (mode === 'view') {
          return <LeafView key={node.id} node={node} value={values[node.id]} />
        }

        return (
          <div key={node.id} className={isWide(node) ? '' : 'max-w-xl'}>
            <FormField
              label={node.unit && node.type !== 'number' ? `${node.label} (${node.unit})` : node.label}
              htmlFor={nodePath}
              required={node.required}
              hint={node.type === 'number' && node.unit ? `Đơn vị: ${node.unit}` : undefined}
            >
              <LeafInput
                node={node}
                fieldId={nodePath}
                value={values[node.id]}
                onChange={(v) => setChild(node.id, v)}
              />
            </FormField>
          </div>
        )
      })}
    </div>
  )
}

function SubGroup({
  node,
  values,
  onChange,
  mode,
  path,
}: {
  node: FormNode
  values: FormValues
  onChange: (next: FormValues) => void
  mode: 'edit' | 'view'
  path: string
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50/60 p-4">
      <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-700">
        {node.label}
      </h4>
      <NodeChildren
        nodes={node.children ?? []}
        values={values}
        onChange={onChange}
        mode={mode}
        path={path}
      />
    </section>
  )
}

/**
 * Render toàn bộ một khối (block) của bệnh án.
 * `values` lồng theo group; `onChange` trả lại toàn bộ object đã cập nhật.
 */
export function DynamicForm({
  block,
  values,
  onChange,
  mode = 'edit',
}: {
  block: FormNode
  values: FormValues
  onChange?: (next: FormValues) => void
  mode?: 'edit' | 'view'
}) {
  return (
    <NodeChildren
      nodes={block.children ?? []}
      values={values ?? {}}
      onChange={(next) => onChange?.(next)}
      mode={mode}
      path={block.id}
    />
  )
}
