/**
 * Biểu đồ đường một chỉ số theo trục thời gian, vẽ bằng SVG thuần.
 *
 * Mỗi chỉ số một biểu đồ riêng (small multiples) chứ không gộp nhiều chỉ số lên
 * cùng một khung: cân nặng (kg), mạch (l/p) và creatinin (µmol/l) khác thang đo
 * hoàn toàn, chồng lên nhau bằng hai trục Y sẽ tạo ra tương quan không có thật.
 */

import { useId, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { cn } from '@/lib/utils'
import { formatExamDate, formatMetricValue, type MetricPoint } from '../metrics'

// Màu series là brand-600 của hệ thiết kế, đã kiểm đạt tương phản >= 3:1 trên
// nền thẻ màu trắng. Trục và lưới lùi hẳn về sau, chỉ đường dữ liệu được đậm.
const SERIES_COLOR = '#0d9488'
const GRID_COLOR = '#e2e8f0'
const AXIS_COLOR = '#cbd5e1'
const LABEL_COLOR = '#94a3b8'
const SURFACE_COLOR = '#ffffff'

const PAD = { top: 14, right: 12, bottom: 20, left: 44 }
/** Quá nhiều điểm thì chấm tròn dính vào nhau — lúc đó chỉ giữ điểm cuối. */
const MAX_VISIBLE_DOTS = 14

function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(0)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const update = () => setWidth(element.clientWidth)
    update()
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [ref, width] as const
}

/** Mốc trục Y tròn số (1 / 2 / 5 × 10^n) thay vì chia đều min–max ra số lẻ. */
function niceTicks(min: number, max: number, count = 3): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return []
  const rawStep = (max - min) / Math.max(count - 1, 1)
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const normalized = rawStep / magnitude
  // Làm tròn về bước gần nhất chứ không làm tròn lên: bước lớn hơn cần thiết
  // (6,5 -> 10) đẩy biểu đồ xuống chỉ còn một đường lưới duy nhất.
  const step = (normalized < 1.5 ? 1 : normalized < 3 ? 2 : normalized < 7 ? 5 : 10) * magnitude

  const ticks: number[] = []
  for (let value = Math.ceil(min / step) * step; value <= max + step * 1e-6; value += step) {
    ticks.push(Number(value.toFixed(10)))
  }
  return ticks
}

export function MetricTrendChart({
  points,
  unit,
  label,
  height = 116,
}: {
  points: MetricPoint[]
  unit?: string
  /** Dùng cho nhãn trợ năng của biểu đồ. */
  label: string
  height?: number
}) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>()
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  // Nhãn chỉ số có dấu và khoảng trắng nên không dùng làm id của gradient được.
  const fillId = `metric-fill-${useId().replace(/:/g, '')}`

  const plotWidth = Math.max(width - PAD.left - PAD.right, 1)
  const plotBottom = PAD.top + height
  const svgHeight = plotBottom + PAD.bottom

  const scale = useMemo(() => {
    const values = points.map((point) => point.value)
    let low = Math.min(...values)
    let high = Math.max(...values)

    if (low === high) {
      // Chỉ số phẳng (hoặc mới có một lần đo) vẫn cần một khoảng để đường nằm giữa.
      const pad = Math.max(Math.abs(low) * 0.1, 1)
      low -= pad
      high += pad
    } else {
      const pad = (high - low) * 0.15
      low -= pad
      high += pad
    }

    const firstTime = points[0]?.time ?? 0
    const lastTime = points[points.length - 1]?.time ?? 0
    const span = lastTime - firstTime

    return {
      x: (time: number) =>
        span > 0 ? PAD.left + ((time - firstTime) / span) * plotWidth : PAD.left + plotWidth / 2,
      y: (value: number) => PAD.top + (1 - (value - low) / (high - low)) * height,
      ticks: niceTicks(low, high),
    }
  }, [points, plotWidth, height])

  const coords = useMemo(
    () => points.map((point) => ({ x: scale.x(point.time), y: scale.y(point.value) })),
    [points, scale],
  )

  const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`).join(' ')
  const areaPath =
    coords.length > 1
      ? `${linePath} L${coords[coords.length - 1].x},${plotBottom} L${coords[0].x},${plotBottom} Z`
      : ''

  const active = activeIndex === null ? null : points[activeIndex]
  const activeCoord = activeIndex === null ? null : coords[activeIndex]
  const showAllDots = points.length <= MAX_VISIBLE_DOTS

  /** Con trỏ chỉ cần tới gần theo trục X là bắt được điểm — không phải trúng chấm tròn. */
  const pickNearest = (clientX: number, element: SVGSVGElement) => {
    const box = element.getBoundingClientRect()
    const x = clientX - box.left
    let nearest = 0
    for (let i = 1; i < coords.length; i += 1) {
      if (Math.abs(coords[i].x - x) < Math.abs(coords[nearest].x - x)) nearest = i
    }
    setActiveIndex(nearest)
  }

  const moveActive = (step: number) => {
    setActiveIndex((current) => {
      const next = (current === null ? points.length - 1 : current + step)
      return Math.min(Math.max(next, 0), points.length - 1)
    })
  }

  return (
    // SVG được đặt absolute: nếu để trong luồng, chiều rộng tính bằng px của nó
    // trở thành min-content của ô lưới, thẻ không co lại được khi thu hẹp cửa sổ
    // và ResizeObserver đo lại đúng bề rộng đã phình ra — vòng lặp không gỡ được.
    <div ref={containerRef} className="relative mt-3" style={{ height: svgHeight }}>
      {width > 0 && (
        <svg
          width={width}
          height={svgHeight}
          role="img"
          aria-label={`Biểu đồ ${label} qua ${points.length} lần khám`}
          tabIndex={0}
          className="absolute left-0 top-0 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
          onPointerMove={(event) => pickNearest(event.clientX, event.currentTarget)}
          onPointerLeave={() => setActiveIndex(null)}
          onFocus={() => setActiveIndex(points.length - 1)}
          onBlur={() => setActiveIndex(null)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowLeft') {
              event.preventDefault()
              moveActive(-1)
            } else if (event.key === 'ArrowRight') {
              event.preventDefault()
              moveActive(1)
            }
          }}
        >
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SERIES_COLOR} stopOpacity="0.16" />
              <stop offset="100%" stopColor={SERIES_COLOR} stopOpacity="0.01" />
            </linearGradient>
          </defs>

          {/* Lưới ngang mảnh, liền nét — đủ để dò giá trị mà không tranh với dữ liệu. */}
          {scale.ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={PAD.left + plotWidth}
                y1={scale.y(tick)}
                y2={scale.y(tick)}
                stroke={GRID_COLOR}
                strokeWidth={1}
              />
              <text
                x={PAD.left - 8}
                y={scale.y(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={10}
                fill={LABEL_COLOR}
                style={{ fontVariantNumeric: 'tabular-nums' }}
              >
                {formatMetricValue(tick)}
              </text>
            </g>
          ))}

          <line
            x1={PAD.left}
            x2={PAD.left + plotWidth}
            y1={plotBottom}
            y2={plotBottom}
            stroke={AXIS_COLOR}
            strokeWidth={1}
          />

          {areaPath && <path d={areaPath} fill={`url(#${fillId})`} />}
          {coords.length > 1 && (
            <path
              d={linePath}
              fill="none"
              stroke={SERIES_COLOR}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {activeCoord && (
            <line
              x1={activeCoord.x}
              x2={activeCoord.x}
              y1={PAD.top}
              y2={plotBottom}
              stroke={AXIS_COLOR}
              strokeWidth={1}
            />
          )}

          {coords.map((coord, index) => {
            const isEdge = index === coords.length - 1
            if (!showAllDots && !isEdge && index !== activeIndex) return null
            return (
              <circle
                key={points[index].examId}
                cx={coord.x}
                cy={coord.y}
                r={4}
                fill={SERIES_COLOR}
                stroke={SURFACE_COLOR}
                strokeWidth={2}
              />
            )
          })}

          {activeCoord && (
            <circle
              cx={activeCoord.x}
              cy={activeCoord.y}
              r={5.5}
              fill={SERIES_COLOR}
              stroke={SURFACE_COLOR}
              strokeWidth={2}
            />
          )}

          <text x={PAD.left} y={svgHeight - 4} fontSize={10} fill={LABEL_COLOR}>
            {formatExamDate(points[0].date)}
          </text>
          {points.length > 1 && (
            <text
              x={PAD.left + plotWidth}
              y={svgHeight - 4}
              textAnchor="end"
              fontSize={10}
              fill={LABEL_COLOR}
            >
              {formatExamDate(points[points.length - 1].date)}
            </text>
          )}
        </svg>
      )}

      {active && activeCoord && (
        <div
          className={cn(
            'pointer-events-none absolute z-10 -translate-x-1/2 rounded-lg border border-slate-200',
            'bg-white px-2.5 py-1.5 text-center shadow-popover',
            activeCoord.y < 52 ? 'translate-y-2' : '-translate-y-[calc(100%+8px)]',
          )}
          style={{
            left: Math.min(Math.max(activeCoord.x, 52), Math.max(width - 52, 52)),
            top: activeCoord.y,
          }}
        >
          <p className="whitespace-nowrap text-sm font-semibold text-slate-900">
            {formatMetricValue(active.value)}
            {unit && <span className="ml-1 text-xs font-normal text-slate-500">{unit}</span>}
          </p>
          <p className="whitespace-nowrap text-[11px] text-slate-500">{formatExamDate(active.date)}</p>
        </div>
      )}
    </div>
  )
}
