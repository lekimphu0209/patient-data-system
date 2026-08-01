/**
 * Kiểu dữ liệu và tiện ích cho biểu đồ diễn biến chỉ số.
 *
 * Việc suy ra "field nào là số" nằm ở backend (`metrics_service.py`) vì
 * form_schema.json là nguồn sự thật của backend, và vì trả sẵn chuỗi số nhẹ hơn
 * nhiều so với gửi cả bản ghi lần khám. Phần còn lại ở đây chỉ là chuyển đổi
 * sang dạng thuận cho việc vẽ, cùng vài hàm định dạng.
 */

import type { ExaminationMetrics } from './api'

export interface MetricPoint {
  examId: number
  /** Ngày khám dạng YYYY-MM-DD. */
  date: string
  /** Mốc thời gian (ms) — trục X dùng thời gian thật nên khoảng cách giữa các lần khám đúng tỉ lệ. */
  time: number
  value: number
}

export interface MetricSeries {
  /** Đường dẫn tới field trong biểu mẫu, ví dụ `general_lab.blood_count.hgb`. */
  key: string
  label: string
  unit?: string
  /** Nhóm gần nhất chứa field — dùng làm bộ lọc và dòng phụ đề của thẻ. */
  groupKey: string
  groupLabel: string
  points: MetricPoint[]
}

export interface MetricGroup {
  key: string
  label: string
  count: number
}

// ==================== Ngày tháng ====================

/**
 * `new Date("2025-08-13")` được hiểu là nửa đêm UTC, nên ở múi giờ âm sẽ lùi
 * mất một ngày. Ngày khám là ngày theo lịch, không phải một thời điểm, nên tách
 * tay rồi dựng theo giờ địa phương.
 */
function parseExamDate(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return new Date(iso)
  return new Date(year, month - 1, day)
}

export function formatExamDate(iso: string): string {
  const date = parseExamDate(iso)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('vi-VN')
}

// ==================== Chuyển đổi ====================

/** Đổi payload của API sang dạng dùng để vẽ (thêm mốc thời gian cho trục X). */
export function toMetricSeries(payload: ExaminationMetrics | undefined): MetricSeries[] {
  return (payload?.series ?? []).map((series) => ({
    key: series.key,
    label: series.label,
    unit: series.unit ?? undefined,
    groupKey: series.group_key,
    groupLabel: series.group_label,
    points: series.points.map((point) => ({
      examId: point.exam_id,
      date: point.date,
      time: parseExamDate(point.date).getTime(),
      value: point.value,
    })),
  }))
}

/** Danh sách nhóm có dữ liệu, giữ nguyên thứ tự xuất hiện trong biểu mẫu. */
export function groupsOf(series: MetricSeries[]): MetricGroup[] {
  const groups = new Map<string, MetricGroup>()
  for (const item of series) {
    const existing = groups.get(item.groupKey)
    if (existing) existing.count += 1
    else groups.set(item.groupKey, { key: item.groupKey, label: item.groupLabel, count: 1 })
  }
  return [...groups.values()]
}

/** Mốc thời gian của các lần khám có ít nhất một chỉ số — dùng cho bộ lọc "N lần gần nhất". */
export function measuredTimes(series: MetricSeries[]): number[] {
  const times = new Set<number>()
  for (const item of series) for (const point of item.points) times.add(point.time)
  return [...times].sort((a, b) => a - b)
}

/**
 * Ngày đầu và ngày cuối của các điểm đang hiển thị.
 * So sánh thẳng trên chuỗi `YYYY-MM-DD` — thứ tự từ điển trùng thứ tự thời gian,
 * nên không phải đổi qua lại giữa mốc mili-giây và ngày.
 */
export function measuredDateRange(series: MetricSeries[]): [string, string] | null {
  let from: string | undefined
  let to: string | undefined
  for (const item of series) {
    for (const point of item.points) {
      if (from === undefined || point.date < from) from = point.date
      if (to === undefined || point.date > to) to = point.date
    }
  }
  return from !== undefined && to !== undefined ? [from, to] : null
}

// ==================== Định dạng ====================

const numberFormat = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 })

export function formatMetricValue(value: number): string {
  return numberFormat.format(value)
}

/** Chênh lệch so với lần đo liền trước — `null` khi chỉ mới có một lần đo. */
export function deltaOf(points: MetricPoint[]): number | null {
  if (points.length < 2) return null
  return points[points.length - 1].value - points[points.length - 2].value
}
