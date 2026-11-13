import { GROUP, isSampleCode, isSkipped, prepareAnswers, progress, subjectErrors, subjectFields, validDate, validateAnswers,
  type Answers, type Subject, type Survey, type SurveyForm } from './model'

const META = [
  'ma_phieu', 'ma_doi_tuong', 'ma_bieu_mau', 'ho_va_ten', 'ngay_sinh', 'nam_sinh',
  'que_quan', 'don_vi', 'ngay_khao_sat', 'ket_luan', 'ghi_chu',
]
export const MAX_FILE_SIZE = 10 * 1024 * 1024

export function isoDate(value: unknown) {
  if (value instanceof Date) {
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  }
  const text = String(value ?? '').trim()
  const match = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(text)
  return match ? `${match[3]}-${match[2].padStart(2, '0')}-${match[1].padStart(2, '0')}` : text
}

function dictionary(form: SurveyForm) {
  return form.questions.map(question => ({
    ma_cau: question.id, cau_hoi: question.label,
    kieu: question.multi ? 'Nhieu lua chon' : question.options.length ? 'Mot lua chon' : 'Van ban',
    dap_an_hop_le: question.options.join(' | '),
  }))
}

export async function downloadTemplate(form: SurveyForm) {
  const { utils, writeFile } = await import('xlsx')
  const book = utils.book_new()
  const headers = [...META, ...form.questions.map(question => question.id)]
  const sheet = utils.aoa_to_sheet([headers])
  sheet['!cols'] = headers.map(header => ({ wch: header === 'ho_va_ten' || header === 'ket_luan' ? 30 : 22 }))
  utils.book_append_sheet(book, sheet, 'Du_lieu')
  utils.book_append_sheet(book, utils.json_to_sheet(dictionary(form)), 'Tu_dien')
  utils.book_append_sheet(book, utils.aoa_to_sheet([
    ['THÔNG TIN', 'HƯỚNG DẪN'],
    ['Biểu mẫu', `${form.id} - ${form.title}`], ['Mã biểu mẫu', form.id],
    ['Ngày', 'Nhập YYYY-MM-DD hoặc DD/MM/YYYY. Không tự suy diễn ngày sinh từ năm sinh.'],
    ['Mã đối tượng', 'Các phiếu cùng người dùng chung mã trong cùng nhóm.'],
    ['Đáp án', 'Dùng chính xác giá trị từ Tu_dien. Nhiều đáp án cách nhau bằng |.'],
    ['Kết luận', 'Nhập kết luận do chuyên môn ghi nhận, để trống nếu chưa có.'],
    ['Trạng thái', 'Phiếu đủ câu trả lời được nhập Chờ đối soát. Phiếu thiếu được nhập Bản nháp.'],
    ['Giới hạn', 'Tệp tối đa 10 MB và 2.000 hàng mỗi lần nhập.'],
  ]), 'Huong_dan')
  writeFile(book, `Mau_khao_sat_${form.id}.xlsx`)
}

export async function exportWorkbook(rows: Survey[], forms: SurveyForm[]) {
  const { utils, writeFile } = await import('xlsx')
  const book = utils.book_new()
  const titles = new Map(forms.map(form => [form.id, form.title]))
  const base = (row: Survey) => ({
    ma_phieu: row.id, ma_doi_tuong: row.person, ma_bieu_mau: row.form, loai_phieu: titles.get(row.form),
    nhom: GROUP[row.group], ho_va_ten: row.patient.fullName, ngay_sinh: row.patient.birthDate,
    nam_sinh: row.patient.birthYear, que_quan: row.patient.hometown, ket_luan: row.conclusion,
    don_vi: row.unit, ngay_khao_sat: row.date, nguon_nhap: row.source,
    du_lieu_mau: row.sample ? 'Có' : 'Không', trang_thai: row.status, ghi_chu: row.note,
  })
  const summary = utils.json_to_sheet(rows.map(base))
  summary['!cols'] = [24, 24, 16, 45, 18, 28, 18, 12, 25, 45].map(wch => ({ wch }))
  utils.book_append_sheet(book, summary, 'Danh_sach')
  const selectedForms = forms.filter(form => rows.some(row => row.form === form.id))
  for (const form of selectedForms) {
    const data = rows.filter(row => row.form === form.id).map(row => ({
      ...base(row),
      ...Object.fromEntries(form.questions.map(question => {
        const answer = row.answers[question.id]
        return [question.id, isSkipped(form, row.answers, question) ? '' : Array.isArray(answer) ? answer.join(' | ') : answer || '']
      })),
    }))
    utils.book_append_sheet(book, utils.json_to_sheet(data), form.id)
  }
  utils.book_append_sheet(book, utils.json_to_sheet(selectedForms.flatMap(form => form.questions.map(question => ({
    ma_bieu_mau: form.id, ma_cau: question.id, cau_hoi: question.label, dap_an: question.options.join(' | '),
  })))), 'Tu_dien')
  utils.book_append_sheet(book, utils.aoa_to_sheet([
    ['Dữ liệu mẫu', rows.filter(row => row.sample).length], ['Số phiếu xuất', rows.length],
    ['Thời điểm xuất', new Date().toISOString()],
  ]), 'Thong_tin')
  writeFile(book, `Suc_khoe_tam_than_${rows.length}_phieu.xlsx`)
}

export function mergeSubject(provided: Subject, known?: Subject): Subject {
  return {
    fullName: provided.fullName || known?.fullName || '',
    birthDate: provided.birthDate || known?.birthDate || '',
    birthYear: provided.birthYear || known?.birthYear || '',
    hometown: provided.hometown || known?.hometown || '',
  }
}

export type ImportRow = { row: number; errors: string[]; warnings: string[]; record: Survey }

export async function readWorkbook(file: File, form: SurveyForm, records: Survey[]): Promise<ImportRow[]> {
  if (file.size > MAX_FILE_SIZE) throw Error('Tệp vượt quá 10 MB.')
  const { read, utils, SSF } = await import('xlsx')
  const book = read(await file.arrayBuffer(), { type: 'array', cellDates: true, sheetRows: 2002 })
  const sheet = book.Sheets.Du_lieu || book.Sheets[book.SheetNames[0]]
  if (!sheet) throw Error('Tệp chưa có dữ liệu.')
  const headers = utils.sheet_to_json<unknown[]>(sheet, { header: 1 })[0] || []
  const rows = utils.sheet_to_json<Record<string, unknown> & { __rowNum__?: number }>(sheet, { raw: true, defval: '' })
  if (!rows.length) throw Error('Tệp chưa có dữ liệu.')
  if (rows.length > 2000 || (sheet['!fullref'] && utils.decode_range(sheet['!fullref']).e.r > 2000)) {
    throw Error('Tệp vượt quá 2.000 hàng. Hãy chia thành nhiều tệp.')
  }
  if (['ma_phieu', 'ma_doi_tuong', 'ma_bieu_mau', 'ngay_khao_sat'].some(header => !headers.includes(header))) {
    throw Error('Thiếu cột bắt buộc. Hãy tải và dùng mẫu Excel tương ứng.')
  }
  const formatDateCell = (value: unknown) => {
    if (typeof value === 'number' && value > 10000) {
      const date = SSF.parse_date_code(value, { date1904: book.Workbook?.WBProps?.date1904 })
      if (date) return `${date.y}-${String(date.m).padStart(2, '0')}-${String(date.d).padStart(2, '0')}`
    }
    return isoDate(value)
  }
  const seen = new Set(records.map(row => row.id))
  const known = new Map(records.filter(row => row.group === form.group).map(row => [row.person, row.patient]))
  const subjects = new Map<string, Subject>()
  const result = rows.map((cells, index): ImportRow => {
    const value = (key: string) => String(cells[key] ?? '').trim()
    const errors: string[] = []
    const warnings: string[] = []
    const id = value('ma_phieu')
    const person = value('ma_doi_tuong')
    const date = formatDateCell(cells.ngay_khao_sat)
    const earlier = subjects.get(person)
    const patient = mergeSubject({
      fullName: value('ho_va_ten'), birthDate: formatDateCell(cells.ngay_sinh),
      birthYear: value('nam_sinh'), hometown: value('que_quan'),
    }, earlier || known.get(person))
    if (!id || !person) errors.push('Thiếu mã phiếu / mã đối tượng')
    if (id.length > 120 || person.length > 120) errors.push('Mã phiếu / mã đối tượng vượt quá 120 ký tự')
    if (seen.has(id)) errors.push('Mã phiếu trùng')
    if (isSampleCode(id)) errors.push('Mã dành cho dữ liệu mẫu')
    if (value('ma_bieu_mau') !== form.id) errors.push('Sai mã biểu mẫu')
    if (!validDate(date)) errors.push('Ngày khảo sát không hợp lệ')
    if ([patient.fullName, patient.hometown, value('don_vi')].some(text => text.length > 255)) {
      errors.push('Họ tên, quê quán hoặc đơn vị vượt quá 255 ký tự')
    }
    if (earlier && subjectFields.some(key => patient[key] && earlier[key] && patient[key] !== earlier[key])) {
      errors.push('Thông tin cùng mã đối tượng không thống nhất')
    }
    const answers: Answers = {}
    for (const question of form.questions) {
      const answer = value(question.id)
      if (answer) answers[question.id] = question.multi ? answer.split('|').map(option => option.trim()).filter(Boolean) : answer
    }
    const prepared = prepareAnswers(form, answers, patient)
    const conclusion = value('ket_luan')
    const note = value('ghi_chu')
    if ([conclusion, note, ...Object.values(prepared).flat()].some(text => text.length > 20000)) {
      errors.push('Kết luận, ghi chú hoặc đáp án vượt quá 20.000 ký tự')
    }
    errors.push(...subjectErrors(patient), ...validateAnswers(form, prepared))
    if (!errors.length) {
      subjects.set(person, patient)
      seen.add(id)
    }
    return {
      row: (cells.__rowNum__ ?? index + 1) + 1, errors, warnings,
      record: { id, person, patient, date, form: form.id, group: form.group, unit: value('don_vi'),
        source: 'Excel', status: 'draft', conclusion, note, answers: prepared },
    }
  })
  for (const { record, errors, warnings } of result) {
    if (errors.length) continue
    record.patient = subjects.get(record.person)!
    record.answers = prepareAnswers(form, record.answers, record.patient)
    const { count, total } = progress(form, record.answers)
    record.status = count === total ? 'review' : 'draft'
    if (count < total) warnings.push(`Thiếu ${total - count} câu trả lời`)
    if (!record.patient.fullName) warnings.push('Chưa có họ tên')
  }
  return result
}
