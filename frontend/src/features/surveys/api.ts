import { api } from '@/lib/api'
import type { Answers, Group, Survey, SurveyForm } from './model'

export type DraftSubject = {
  code: string | null
  full_name: string | null
  birth_year: string | null
  birth_date: string | null
  hometown: string | null
  unit: string | null
  survey_date: string | null
}

/** Bản nháp bóc tách một phiếu đã điền; chưa phải bản ghi. */
export type SurveyDraft = {
  form: string
  documentId: number
  fileName: string
  pageCount: number
  pagesRead: number[]
  model: string
  subject: DraftSubject
  answers: Answers
  uncertain: string[]
  notes: string
  warnings: string[]
  summary: string
}

/** Kết quả tách một file chứa nhiều phiếu của một người. */
export type BundleResult = {
  fileName: string
  pageCount: number
  model: string
  subject: DraftSubject
  /** Các cách đọc mã đối tượng khác nhau; hơn một mã nghĩa là cần người dùng xác nhận. */
  codeCandidates: string[]
  drafts: SurveyDraft[]
  skipped: { pages: number[]; reason: string }[]
  warnings: string[]
}

async function upload<T>(path: string, params: Record<string, string>, file: File, onUpload: (fraction: number) => void) {
  const body = new FormData()
  body.append('file', file)
  const response = await api.post<T>(path, body, {
    params,
    onUploadProgress: event => { if (event.total) onUpload(event.loaded / event.total) },
  })
  return response.data
}
export const extractSurvey = (form: string, file: File, onUpload: (fraction: number) => void) =>
  upload<SurveyDraft>('/surveys/extract', { form }, file, onUpload)
export const extractBundle = (group: Group, file: File, onUpload: (fraction: number) => void) =>
  upload<BundleResult>('/surveys/extract-bundle', { group }, file, onUpload)
/** Bỏ file đã bóc tách nhưng không lưu thành phiếu. */
export async function discardDocuments(ids: number[]) {
  if (ids.length) await api.post('/surveys/discard-documents', { ids })
}

export type OriginalFile = { url: string; type: string; name: string }

/** Tải file gốc về trình duyệt (cần token nên không mở thẳng URL API được). */
export async function getOriginal(record: Survey): Promise<OriginalFile> {
  try {
    const response = await api.get<Blob>('/surveys/original', { params: { id: record.id }, responseType: 'blob' })
    const type = response.data.type || 'application/octet-stream'
    const header = String(response.headers['content-disposition'] || '')
    const encoded = /filename\*=utf-8''([^;]+)/i.exec(header)?.[1]
    const plain = /filename="?([^";]+)"?/i.exec(header)?.[1]
    const name = encoded ? decodeURIComponent(encoded) : plain || `${record.id}.${type === 'application/pdf' ? 'pdf' : 'jpg'}`
    return { url: URL.createObjectURL(response.data), type, name }
  } catch (error) {
    // Lỗi trả về dạng Blob vì responseType: 'blob' — đọc lại thành JSON để lấy thông báo.
    const data = (error as { response?: { data?: unknown } })?.response?.data
    if (data instanceof Blob) {
      const detail = await data.text().then(text => JSON.parse(text).detail, () => undefined)
      if (typeof detail === 'string') throw Error(detail)
    }
    throw error
  }
}

export async function getForms(): Promise<SurveyForm[]> {
  return (await api.get('/surveys/forms')).data
}
export async function getRecords(): Promise<Survey[]> {
  return (await api.get('/surveys/records')).data
}
export async function getRecord(id: string): Promise<Survey> {
  return (await api.get('/surveys/record', { params: { id } })).data
}
export async function createRecords(records: Survey[]) {
  await api.post('/surveys/records', { records })
}
export async function updateRecord(record: Survey) {
  await api.put('/surveys/record', record)
}
export async function deleteRecords(ids: string[]) {
  await api.post('/surveys/delete', { ids })
}

export function surveyError(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: string | { msg: string }[] } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail[0]?.msg.replace(/^Value error, /, '') || 'Dữ liệu không hợp lệ.'
  return error instanceof Error ? error.message : 'Yêu cầu không thành công.'
}
