import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('vi-VN')
}

export function formatBirthDate(value: string | null | undefined) {
  return value ? value.slice(0, 10) : null
}

export function calculateAge(birthDate: string | null | undefined) {
  if (!birthDate) return null
  const today = new Date()
  const birth = new Date(birthDate)
  let age = today.getFullYear() - birth.getFullYear()
  const m = today.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) {
    age--
  }
  return age
}

export function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export function genderLabel(value: string | null | undefined) {
  if (!value) return null
  const map: Record<string, string> = { male: 'Nam', female: 'Nữ', other: 'Khác' }
  return map[value] || value
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Up to two initials from a Vietnamese full name (given name last). */
export function initialsOf(fullName: string | null | undefined) {
  const parts = (fullName || '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/** Pull a human-readable message out of an axios error, falling back sensibly. */
export function errorMessage(error: unknown, fallback = 'Đã có lỗi xảy ra, vui lòng thử lại.') {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  // FastAPI validation errors arrive as a list of {loc, msg, type}.
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined
    if (first?.msg) return first.msg
  }
  return fallback
}
