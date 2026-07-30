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
