/**
 * Khối biểu đồ diễn biến các chỉ số dạng số của bệnh nhân, đặt ngay dưới bảng
 * KHÁM BỆNH.
 *
 * Mỗi chỉ số một biểu đồ nhỏ riêng thay vì gộp chung khung — xem `MetricTrendChart`.
 * Bộ lọc nằm trên một hàng phía trên và áp cho cả biểu đồ lẫn bảng số liệu, nên
 * hai cách xem luôn nói cùng một con số.
 */

import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, LineChart, Minus, Table2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Card, EmptyState, Loading, Select } from '@/components/ui'
import { cn } from '@/lib/utils'
import { getExaminationMetrics } from '../api'
import {
  deltaOf,
  formatExamDate,
  formatMetricValue,
  groupsOf,
  measuredDateRange,
  measuredTimes,
  toMetricSeries,
  type MetricSeries,
} from '../metrics'
import { MetricTrendChart } from './MetricTrendChart'

const ALL_GROUPS = 'all'

const RECENT_OPTIONS = [
  { value: 'all', label: 'Toàn bộ thời gian' },
  { value: '5', label: '5 lần khám gần nhất' },
  { value: '10', label: '10 lần khám gần nhất' },
  { value: '20', label: '20 lần khám gần nhất' },
]

// ==================== Thẻ một chỉ số ====================

function DeltaChip({ series }: { series: MetricSeries }) {
  const delta = deltaOf(series.points)
  if (delta === null) return null

  const previous = series.points[series.points.length - 2]
  // Cố tình *không* tô xanh/đỏ: tăng hay giảm là tốt còn tuỳ chỉ số (cân nặng,
  // bạch cầu, SGOT...), gán màu tốt/xấu ở đây là kết luận thay bác sĩ.
  const Icon = delta === 0 ? Minus : delta > 0 ? ArrowUp : ArrowDown

  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-200"
      title={`So với lần khám ${formatExamDate(previous.date)}`}
    >
      <Icon className="h-3 w-3" />
      {delta === 0 ? 'Không đổi' : formatMetricValue(Math.abs(delta))}
    </span>
  )
}

function MetricCard({ series }: { series: MetricSeries }) {
  const latest = series.points[series.points.length - 1]

  return (
    <figure className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 transition-shadow hover:shadow-card">
      <figcaption>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-700" title={series.label}>
              {series.label}
            </p>
            <p className="mt-0.5 truncate text-xs text-slate-400" title={series.groupLabel}>
              {series.groupLabel}
            </p>
          </div>
          <DeltaChip series={series} />
        </div>

        <p className="mt-2 flex items-baseline gap-1">
          <span className="text-2xl font-semibold leading-none text-slate-900">
            {formatMetricValue(latest.value)}
          </span>
          {series.unit && <span className="text-xs text-slate-500">{series.unit}</span>}
        </p>
      </figcaption>

      <MetricTrendChart points={series.points} unit={series.unit} label={series.label} />

      <p className="mt-1.5 text-[11px] text-slate-400">
        {series.points.length === 1
          ? `Mới có 1 lần đo · ${formatExamDate(latest.date)}`
          : `${series.points.length} lần đo · gần nhất ${formatExamDate(latest.date)}`}
      </p>
    </figure>
  )
}

// ==================== Bảng số liệu (bản song sinh của biểu đồ) ====================

function MetricTable({ series }: { series: MetricSeries[] }) {
  const rows = useMemo(() => {
    const byExam = new Map<number, { date: string; time: number; values: Record<string, number> }>()
    for (const item of series) {
      for (const point of item.points) {
        const row = byExam.get(point.examId) ?? { date: point.date, time: point.time, values: {} }
        row.values[item.key] = point.value
        byExam.set(point.examId, row)
      }
    }
    return [...byExam.entries()]
      .map(([examId, row]) => ({ examId, ...row }))
      .sort((a, b) => a.time - b.time)
  }, [series])

  return (
    <div className="scrollbar-slim overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50">
          <tr>
            <th className="sticky left-0 z-10 whitespace-nowrap bg-slate-50 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              Ngày khám
            </th>
            {series.map((item) => (
              <th
                key={item.key}
                className="whitespace-nowrap px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-600"
                title={`${item.groupLabel} · ${item.label}`}
              >
                {item.label}
                {item.unit && (
                  <span className="ml-1 font-normal normal-case text-slate-400">({item.unit})</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.examId} className="group hover:bg-slate-50">
              {/* Ô ngày ghim trái phải tự đổi nền, nếu không hover sẽ đứt một đoạn. */}
              <td className="sticky left-0 z-10 whitespace-nowrap bg-white px-3 py-2.5 font-medium text-slate-900 group-hover:bg-slate-50">
                {formatExamDate(row.date)}
              </td>
              {series.map((item) => (
                <td
                  key={item.key}
                  className="whitespace-nowrap px-3 py-2.5 text-right text-slate-700"
                  style={{ fontVariantNumeric: 'tabular-nums' }}
                >
                  {row.values[item.key] === undefined
                    ? '—'
                    : formatMetricValue(row.values[item.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ==================== Khối chính ====================

export function ExamMetricsSection({ patientId }: { patientId: number }) {
  const [groupKey, setGroupKey] = useState<string>(ALL_GROUPS)
  const [recent, setRecent] = useState<string>('all')
  const [view, setView] = useState<'chart' | 'table'>('chart')

  const { data: metrics, isLoading } = useQuery({
    // Cùng tiền tố với query danh sách nên mọi thao tác thêm/sửa/xoá lần khám
    // đã invalidate sẵn, biểu đồ tự cập nhật theo.
    queryKey: ['exams', patientId, 'metrics'],
    queryFn: () => getExaminationMetrics(patientId),
  })

  const allSeries = useMemo(() => toMetricSeries(metrics), [metrics])
  const groups = useMemo(() => groupsOf(allSeries), [allSeries])

  const visible = useMemo(() => {
    // Mốc cắt tính trên toàn bộ chỉ số, không theo nhóm đang chọn: đổi nhóm thì
    // khoảng thời gian đang xem phải giữ nguyên.
    const times = measuredTimes(allSeries)
    const take = recent === 'all' ? times.length : Number(recent)
    const cutoff = times.length > take ? times[times.length - take] : Number.NEGATIVE_INFINITY

    return allSeries
      .filter((item) => groupKey === ALL_GROUPS || item.groupKey === groupKey)
      .map((item) => ({ ...item, points: item.points.filter((p) => p.time >= cutoff) }))
      .filter((item) => item.points.length > 0)
  }, [allSeries, groupKey, recent])

  if (isLoading) {
    return (
      <Card size="full">
        <Loading text="Đang tải biểu đồ chỉ số..." />
      </Card>
    )
  }

  // Chưa có lần khám nào thì khối KHÁM BỆNH ở trên đã nói rồi, không lặp lại.
  if (!metrics || metrics.exam_count === 0) return null

  const measured = measuredTimes(visible)
  const range = measuredDateRange(visible)
  const span = range ? `${formatExamDate(range[0])} – ${formatExamDate(range[1])}` : ''
  const truncatedNote = metrics.truncated ? ' · chỉ vẽ các lần khám gần nhất' : ''

  return (
    <Card size="full">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">BIỂU ĐỒ DIỄN BIẾN CHỈ SỐ</h3>
          <p className="mt-1 text-sm text-slate-500">
            {allSeries.length === 0
              ? 'Chưa có chỉ số dạng số nào được ghi nhận'
              : `${visible.length} chỉ số · ${measured.length} lần đo${
                  span ? ` · ${span}` : ''
                }${truncatedNote}`}
          </p>
        </div>

        {allSeries.length > 0 && (
          <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
            {(
              [
                { key: 'chart', label: 'Biểu đồ', Icon: LineChart },
                { key: 'table', label: 'Bảng số liệu', Icon: Table2 },
              ] as const
            ).map(({ key, label, Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setView(key)}
                aria-pressed={view === key}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors',
                  view === key
                    ? 'bg-brand-50 text-brand-800'
                    : 'text-slate-500 hover:text-slate-900',
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {allSeries.length === 0 ? (
        <EmptyState
          icon={<LineChart className="h-6 w-6" />}
          message="Chưa có chỉ số dạng số nào được ghi nhận"
          description="Các chỉ số như cân nặng, mạch, nhiệt độ hay kết quả xét nghiệm sẽ tự lên biểu đồ ngay khi được nhập trong phần khám bệnh."
        />
      ) : (
        <>
          {/* Bộ lọc: một hàng, đứng trên và áp cho mọi thứ bên dưới. */}
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <FilterChip
              label="Tất cả"
              count={allSeries.length}
              active={groupKey === ALL_GROUPS}
              onClick={() => setGroupKey(ALL_GROUPS)}
            />
            {groups.map((group) => (
              <FilterChip
                key={group.key}
                label={group.label}
                count={group.count}
                active={groupKey === group.key}
                onClick={() => setGroupKey(group.key)}
              />
            ))}

            <div className="ml-auto w-full sm:w-56">
              <Select
                selectSize="sm"
                aria-label="Khoảng thời gian"
                options={RECENT_OPTIONS}
                value={recent}
                onChange={(event) => setRecent(event.target.value)}
              />
            </div>
          </div>

          {visible.length === 0 ? (
            <EmptyState
              icon={<LineChart className="h-6 w-6" />}
              message="Không có chỉ số nào trong khoảng đã chọn"
              description="Thử mở rộng khoảng thời gian hoặc chọn nhóm chỉ số khác."
            />
          ) : view === 'chart' ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {visible.map((series) => (
                <MetricCard key={series.key} series={series} />
              ))}
            </div>
          ) : (
            <MetricTable series={visible} />
          )}
        </>
      )}
    </Card>
  )
}

function FilterChip({
  label,
  count,
  active,
  onClick,
}: {
  label: string
  count: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
        active
          ? 'border-brand-200 bg-brand-50 text-brand-800'
          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900',
      )}
    >
      {label}
      <span className={cn('text-xs', active ? 'text-brand-600' : 'text-slate-400')}>{count}</span>
    </button>
  )
}
