export const APP_NAME = 'Hệ thống quản lý và phân tích dữ liệu sức khỏe tâm thần'
export const GROUP = { youth: 'Thanh niên', military: 'Quân nhân' } as const
export const GROUPS = ['youth', 'military'] as const
export const SHORT: Record<string, string> = {
  F01: 'Nguy cơ tự sát · QN20', F02: 'Thông tin đối tượng', F03: 'Sàng lọc trầm cảm',
  F04: 'Cảm xúc lưỡng cực', F05: 'Tâm thần phân liệt', F06: 'Rối loạn sử dụng rượu',
  F07: 'Rối loạn lo âu', F08: 'Nhân khẩu học & yếu tố nguy cơ',
  F09: 'Tỷ lệ & cơ cấu rối loạn tâm thần',
}
export const STATUS = { draft: 'Bản nháp', review: 'Chờ đối soát', complete: 'Đã hoàn tất' } as const

export type Group = keyof typeof GROUP
export type Status = keyof typeof STATUS
export type Answer = string | string[]
export type Answers = Record<string, Answer>
/** Chỉ dẫn chuyển câu: câu không áp dụng khi câu ``question`` được trả lời ``answer``.
 *  ``keepAnswer``: câu chỉ hết bắt buộc, người trả lời vẫn đánh thì giữ; không có thì câu trả lời bị bỏ. */
export type SkipRule = { question: string; answer: string; keepAnswer?: boolean }
export type Question = { id: string; label: string; options: string[]; multi: boolean; skipIf?: SkipRule }
export type SurveyForm = {
  id: string
  group: Group
  code: string
  title: string
  questions: Question[]
  blocks: ({ text: string } | { rows: string[][] })[]
  source: string
}
export type Subject = { fullName: string; birthDate: string; birthYear: string; hometown: string }
export type Survey = {
  id: string
  group: Group
  person: string
  patient: Subject
  form: string
  unit: string
  date: string
  source: string
  status: Status
  conclusion: string
  answers: Answers
  note: string
  updatedAt?: string
  sample?: boolean
  ocr?: string | null
  hasOCR?: boolean
  /** File ảnh/PDF đã upload để bóc tách — chỉ gửi khi tạo bản ghi. */
  documentId?: number | null
  hasOriginal?: boolean
  originalType?: 'pdf' | 'image' | null
}
export type ImportAction = 'manual' | 'excel' | 'ocr'
export const today = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date())
export const nf = (value: number) => value.toLocaleString('vi-VN')
export const formatDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value)
  ? value.split('-').reverse().join('/') : value || '—'
export const birthLabel = (patient: Subject) => patient.birthDate ? formatDate(patient.birthDate)
  : patient.birthYear ? `Năm ${patient.birthYear}` : '—'
export const initials = (name: string) => name.trim().split(/\s+/).slice(-2).map(word => word[0]).join('').toUpperCase() || '—'
export const hasAnswer = (value?: Answer) => Array.isArray(value) ? value.length > 0 : Boolean(value?.trim())
export const answerText = (value?: Answer) => Array.isArray(value) ? value.join('; ') : value
export const validDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value)
  && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value
export const emptySubject: Subject = { fullName: '', birthDate: '', birthYear: '', hometown: '' }
export const subjectFields = ['fullName', 'birthDate', 'birthYear', 'hometown'] as const
export const isSampleCode = (id: string) => /^MAU-(TN|QN)-/i.test(id)
export const newId = (prefix: string) => `${prefix}-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`

// Mã đối tượng dạng thống nhất (khớp backend ``canonical_code``): chữ in hoa, các phần ngăn
// cách bằng một dấu chấm — "PT.CK 001", "pt. ck-001" -> "PT.CK.001"; "QK1. 02" -> "QK1.02".
const CODE_SEPARATOR = /[\s._\-–—·:]+/
export const canonicalCode = (value: string) => value.toUpperCase().split(CODE_SEPARATOR).filter(Boolean).join('.')
/** Khoá so khớp mã: bỏ thêm số 0 đứng đầu ("PT.CK.001" ~ "PT.CK.1"). */
export const codeKey = (value: string) => canonicalCode(value).split('.')
  .map(part => /^\d+$/.test(part) ? String(Number(part)) : part).join('.')
/** Mã nhập/đọc được -> mã đối tượng đã có nếu khớp, ngược lại dạng thống nhất. */
export function resolvePerson(value: string, known: string[]) {
  const code = canonicalCode(value)
  if (!code) return ''
  return known.find(person => codeKey(person) === codeKey(code)) || code
}

/** [1, 2, 3, 5] -> "1–3, 5" */
export function pageRanges(pages: number[]) {
  const ranges: [number, number][] = []
  for (const page of [...pages].sort((first, second) => first - second)) {
    const last = ranges[ranges.length - 1]
    if (last && last[1] === page - 1) last[1] = page
    else ranges.push([page, page])
  }
  return ranges.map(([start, end]) => start === end ? String(start) : `${start}–${end}`).join(', ')
}

export function subjectErrors(patient: Subject) {
  const errors = []
  if (patient.birthDate && (!validDate(patient.birthDate) || patient.birthDate > today())) {
    errors.push('Ngày sinh không hợp lệ')
  }
  if (patient.birthYear && (!/^(19|20)\d{2}$/.test(patient.birthYear) || patient.birthYear > today().slice(0, 4))) {
    errors.push('Năm sinh không hợp lệ')
  }
  if (patient.birthDate && patient.birthYear && patient.birthDate.slice(0, 4) !== patient.birthYear) {
    errors.push('Ngày sinh không khớp năm sinh')
  }
  return errors
}

export function isSkipped(answers: Answers, question: Question) {
  const rule = question.skipIf
  if (!rule) return false
  const value = answers[rule.question]
  return Array.isArray(value) ? value.includes(rule.answer) : value === rule.answer
}
/** Câu được chuyển qua nhưng vẫn giữ câu trả lời (chỉ hết bắt buộc). */
export const keepsSkippedAnswer = (question: Question) => Boolean(question.skipIf?.keepAnswer)
export function progress(form: SurveyForm, answers: Answers) {
  const applicable = form.questions.filter(question => !isSkipped(answers, question))
  return { count: applicable.filter(question => hasAnswer(answers[question.id])).length, total: applicable.length }
}
export function validateAnswers(form: SurveyForm, answers: Answers) {
  const errors: string[] = []
  for (const question of form.questions) {
    const answer = answers[question.id]
    if (!hasAnswer(answer) || (isSkipped(answers, question) && !keepsSkippedAnswer(question))) continue
    const values = Array.isArray(answer) ? answer : [answer]
    if (question.options.length && values.some(value => !question.options.includes(value))) {
      errors.push(`${question.id}: đáp án không hợp lệ`)
    }
    if (question.label.includes('tối đa 2') && values.length > 2) {
      errors.push(`${question.id}: chỉ chọn tối đa 2 đáp án`)
    }
    if (values.length > 1 && values.some(value => value.includes('Không gặp sự kiện đáng kể'))) {
      errors.push(`${question.id}: không chọn đồng thời “Không gặp sự kiện” và sự kiện khác`)
    }
  }
  return errors
}
export function prepareAnswers(form: SurveyForm, answers: Answers, patient: Subject) {
  const result = { ...answers }
  for (const question of form.questions) {
    const { id, label } = question
    if (/^(Họ và tên|1\. Họ và tên)/.test(label) && patient.fullName) result[id] = patient.fullName
    if (label === 'Năm sinh' && (patient.birthDate || patient.birthYear)) {
      result[id] = (patient.birthDate || patient.birthYear).slice(0, 4)
    }
    if (label === 'Địa chỉ' && patient.hometown && !result[id]) result[id] = patient.hometown
    if (typeof result[id] === 'string') result[id] = (result[id] as string).trim()
    if (!hasAnswer(result[id]) || (isSkipped(result, question) && !keepsSkippedAnswer(question))) delete result[id]
  }
  return result
}

const SAMPLE_KEY = 'ta-sample-v7'
const NAMES = [
  'Nguyễn Minh Anh', 'Trần Quốc Bảo', 'Lê Hoàng Nam', 'Phạm Đức Minh', 'Vũ Thanh Tùng', 'Đặng Quang Huy',
  'Nguyễn Hải Đăng', 'Hoàng Tuấn Kiệt', 'Bùi Gia Hưng', 'Đỗ Minh Quân', 'Trần Anh Dũng', 'Lê Ngọc Sơn',
  'Phạm Duy Khánh', 'Võ Tiến Đạt', 'Nguyễn Văn Long', 'Đinh Thành Trung',
]
const TOWNS = ['Hà Nội', 'Bắc Ninh', 'Hải Phòng', 'Ninh Bình', 'Thanh Hóa', 'Nghệ An']

export function readSamples(forms: SurveyForm[]): Survey[] {
  try {
    const stored = localStorage.getItem(SAMPLE_KEY)
    if (stored) {
      const rows: Survey[] = JSON.parse(stored)
      if (Array.isArray(rows) && rows.every(row => row.sample && forms.some(form => form.id === row.form))) return rows
    }
  } catch { /* Generate the initial sample set when local storage is unavailable. */ }

  return GROUPS.flatMap(group => {
    const youth = group === 'youth'
    const groupForms = forms.filter(form => form.group === group)
    return Array.from({ length: youth ? 16 : 8 }, (_, index) => {
      const prefix = youth ? 'MAU-TN-' : 'MAU-QN-'
      const person = prefix + String(index + 1).padStart(4, '0')
      const datePart = (value: number) => String(value).padStart(2, '0')
      const patient: Subject = {
        fullName: NAMES[index],
        birthDate: `${youth ? 2005 + index % 3 : 1995 + index % 10}-${datePart(index % 12 + 1)}-${datePart(index % 20 + 1)}`,
        birthYear: '', hometown: TOWNS[index % TOWNS.length],
      }
      return groupForms.map((form, formIndex): Survey => {
        const offset = index + formIndex
        const date = new Date(`${today()}T00:00:00Z`)
        date.setUTCDate(date.getUTCDate() - offset % 8)
        const answers: Answers = {}
        form.questions.forEach((question, questionIndex) => {
          if (offset % 5 === 0 && questionIndex % 4 === 0) return
          const option = question.options[(index + questionIndex) % question.options.length]
          answers[question.id] = question.options.length ? (question.multi ? [option] : option) : 'Thông tin mẫu'
        })
        return {
          sample: true, id: prefix + String(index + 1).padStart(3, '0') + '-' + form.id,
          person, patient, group, form: form.id,
          unit: (youth ? 'Địa bàn ' : 'Đơn vị ') + ['A', 'B', 'C'][index % 3],
          date: date.toISOString().slice(0, 10), source: 'Mẫu',
          status: offset % 5 === 0 ? 'draft' : offset % 4 === 0 ? 'review' : 'complete',
          conclusion: ['Chờ đánh giá chuyên môn', 'Không ghi nhận bất thường (mẫu)', ''][offset % 3],
          answers, note: 'Dữ liệu mẫu giả lập để thử chức năng; không phải hồ sơ bệnh nhân thật.',
          updatedAt: '2026-11-09T01:00:00Z',
        }
      })
    }).flat()
  })
}
export function persistSamples(rows: Survey[]) {
  localStorage.setItem(SAMPLE_KEY, JSON.stringify(rows))
}
