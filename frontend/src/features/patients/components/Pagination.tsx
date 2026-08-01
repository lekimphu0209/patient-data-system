import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Select } from '@/components/ui'
import { PAGE_SIZE_OPTIONS } from '@/constants'
import { cn } from '@/lib/utils'

interface PaginationProps {
  page: number
  limit: number
  total: number
  totalPages: number
  onPageChange: (page: number) => void
  onLimitChange: (limit: number) => void
  /** Danh từ đếm trong dòng tóm tắt — bảng lần khám dùng "lần khám". */
  unit?: string
}

const ELLIPSIS = 'ellipsis'
type PageItem = number | typeof ELLIPSIS

/**
 * Windowed page list: first and last page are always reachable, the current page
 * keeps a neighbour on each side, and the gaps collapse into an ellipsis. Keeps
 * the control a fixed width no matter how far the dataset scales.
 */
export function buildPageItems(page: number, totalPages: number, siblings = 1): PageItem[] {
  // first + last + current + 2 ellipses + siblings on both sides
  const maxSlots = siblings * 2 + 5
  if (totalPages <= maxSlots) {
    return Array.from({ length: totalPages }, (_, i) => i + 1)
  }

  const left = Math.max(page - siblings, 1)
  const right = Math.min(page + siblings, totalPages)
  const showLeftEllipsis = left > 2
  const showRightEllipsis = right < totalPages - 1

  const items: PageItem[] = [1]
  if (showLeftEllipsis) items.push(ELLIPSIS)

  for (let p = Math.max(left, 2); p <= Math.min(right, totalPages - 1); p += 1) {
    items.push(p)
  }

  if (showRightEllipsis) items.push(ELLIPSIS)
  items.push(totalPages)
  return items
}

export function Pagination({
  page,
  limit,
  total,
  totalPages,
  onPageChange,
  onLimitChange,
  unit = 'bệnh nhân',
}: PaginationProps) {
  const from = total === 0 ? 0 : (page - 1) * limit + 1
  const to = Math.min(page * limit, total)
  const items = buildPageItems(page, totalPages)

  return (
    <div className="flex flex-col gap-3 border-t border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-slate-500">
        Hiển thị <span className="font-medium text-slate-900">{from}</span>–
        <span className="font-medium text-slate-900">{to}</span> trong{' '}
        <span className="font-medium text-slate-900">{total}</span> {unit}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <nav aria-label="Phân trang" className="flex items-center gap-1">
          <PageButton
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            label="Trang trước"
          >
            <ChevronLeft className="h-4 w-4" />
          </PageButton>

          {items.map((item, index) =>
            item === ELLIPSIS ? (
              <span
                key={`gap-${index}`}
                aria-hidden="true"
                className="px-1 text-sm text-slate-400"
              >
                …
              </span>
            ) : (
              <button
                key={item}
                onClick={() => onPageChange(item)}
                aria-current={item === page ? 'page' : undefined}
                className={cn(
                  'h-9 min-w-[2.25rem] rounded-lg px-2 text-sm font-medium transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-1',
                  item === page
                    ? 'bg-brand-700 text-white'
                    : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                )}
              >
                {item}
              </button>
            )
          )}

          <PageButton
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            label="Trang sau"
          >
            <ChevronRight className="h-4 w-4" />
          </PageButton>
        </nav>

        <div className="w-32">
          <Select
            selectSize="sm"
            aria-label="Số dòng mỗi trang"
            value={String(limit)}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            options={PAGE_SIZE_OPTIONS}
          />
        </div>
      </div>
    </div>
  )
}

function PageButton({
  children,
  onClick,
  disabled,
  label,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled: boolean
  label: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-40"
    >
      {children}
    </button>
  )
}
