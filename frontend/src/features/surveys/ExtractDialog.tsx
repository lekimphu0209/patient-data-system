import { useEffect, useMemo, useRef, useState } from 'react'
import { extractSurvey, surveyError, type SurveyDraft } from './api'
import { birthLabel, newId, prepareAnswers, progress, subjectErrors, today, validateAnswers,
  type Survey, type SurveyForm } from './model'
import { Icon, Modal } from './ui'
import { mergeSubject } from './workbook'

// Khớp EXTRACTION_MAX_FILE_MB ở backend và client_max_body_size của nginx.
const MAX_SCAN_SIZE = 20 * 1024 * 1024
const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
const ACCEPTED_EXTENSIONS = /\.(jpe?g|png|webp|pdf)$/i

type Stage = 'idle' | 'upload' | 'read' | 'save' | 'done'

/** Ghép bản nháp từ máy chủ với mã đối tượng người dùng nhập thành bản ghi khảo sát. */
function buildRecord(form: SurveyForm, draft: SurveyDraft, records: Survey[], personInput: string): Survey {
  const person = personInput.trim() || draft.subject.code || newId('OCR')
  const others = records.filter(row => !row.sample && row.group === form.group && row.person === person)
  const known = others[0]?.patient
  const patient = mergeSubject({
    fullName: draft.subject.full_name || '',
    birthDate: draft.subject.birth_date || '',
    birthYear: draft.subject.birth_year || '',
    hometown: draft.subject.hometown || '',
  }, known)
  if (subjectErrors(patient).length) {
    patient.birthDate = known?.birthDate || ''
    patient.birthYear = known?.birthYear || ''
  }
  const answers = prepareAnswers(form, draft.answers, patient)
  for (const error of validateAnswers(form, answers)) delete answers[error.split(':')[0]]
  const counts = progress(form, answers)
  const duplicates = others.filter(row => row.form === form.id).map(row => row.id)
  const note = [
    `Tự động trích xuất từ file ${draft.fileName}.`,
    draft.uncertain.length ? `Cần đối soát ${draft.uncertain.length} mục: ${draft.uncertain.join(', ')}.`
      : 'Đối chiếu với phiếu gốc trước khi hoàn tất.',
    draft.subject.survey_date ? '' : 'Ngày khảo sát tạm dùng ngày nhập, cần xác nhận.',
    duplicates.length ? `Đối tượng đã có phiếu cùng loại: ${duplicates.join(', ')} — kiểm tra trùng.` : '',
  ].filter(Boolean).join(' ')
  return {
    id: newId('OCR'), person, patient, group: form.group, form: form.id,
    unit: draft.subject.unit || '', conclusion: '', date: draft.subject.survey_date || today(),
    status: counts.count === counts.total && !draft.uncertain.length ? 'review' : 'draft',
    source: 'OCR', answers, note, ocr: draft.summary, documentId: draft.documentId,
  }
}

export function ExtractDialog({ form, records, close, save, open, viewOriginal, notify }: {
  form: SurveyForm
  records: Survey[]
  close: () => void
  save: (row: Survey) => Promise<void>
  open: (row: Survey) => void
  viewOriginal: (row: Survey) => void
  notify: (message: string) => void
}) {
  const [person, setPerson] = useState('')
  const [file, setFile] = useState<File>()
  const [dragging, setDragging] = useState(false)
  const [stage, setStage] = useState<Stage>('idle')
  const [uploaded, setUploaded] = useState(0)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState<SurveyDraft>()
  const [pending, setPending] = useState<Survey>()
  const [saved, setSaved] = useState<Survey>()
  const result = useRef<HTMLDivElement>(null)
  const busy = stage === 'upload' || stage === 'read' || stage === 'save'
  const persons = useMemo(() => [...new Set(records.filter(row => !row.sample && row.group === form.group)
    .map(row => row.person))].sort(), [records, form.group])
  const labels = useMemo(() => new Map(form.questions.map(question => [question.id, question.label])), [form])
  const counts = saved ? progress(form, saved.answers) : undefined
  const percent = { idle: 0, upload: 5 + uploaded * 25, read: 55, save: 90, done: 100 }[stage]

  // Kết quả nằm dưới vùng upload — cuộn tới để người dùng thấy ngay.
  useEffect(() => {
    if (saved) result.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [saved])

  async function persist(row: Survey) {
    setStage('save')
    await save(row)
    setPending(undefined)
    setSaved(row)
    setStage('done')
    notify(`Đã trích xuất và lưu phiếu ${row.id}.`)
  }

  function fail(problem: unknown) {
    const message = surveyError(problem)
    setError(message)
    setStage('idle')
    notify(message)
  }

  async function extract(chosen?: File) {
    if (!chosen || busy) return
    if (!ACCEPTED.includes(chosen.type) && !ACCEPTED_EXTENSIONS.test(chosen.name)) {
      notify('Hãy chọn ảnh JPG, PNG, WebP hoặc file PDF.')
      return
    }
    if (chosen.size > MAX_SCAN_SIZE) {
      notify('File vượt quá 20 MB.')
      return
    }
    setFile(chosen)
    setError('')
    setDraft(undefined)
    setPending(undefined)
    setSaved(undefined)
    setUploaded(0)
    setStage('upload')
    try {
      const result = await extractSurvey(form.id, chosen, fraction => {
        setUploaded(fraction)
        if (fraction >= 1) setStage('read')
      })
      setDraft(result)
      const row = buildRecord(form, result, records, person)
      setPending(row)
      await persist(row)
    } catch (problem) {
      fail(problem)
    }
  }

  async function retry() {
    if (!pending || busy) return
    setError('')
    try { await persist(pending) } catch (problem) { fail(problem) }
  }

  const status = {
    idle: '', upload: 'Đang tải file lên máy chủ…',
    read: 'Đang đọc phiếu bằng AI — thường mất 10–40 giây, vui lòng giữ cửa sổ này…',
    save: 'Đang lưu bản ghi vào cơ sở dữ liệu…', done: 'Đã trích xuất và lưu bản ghi',
  }[stage]

  return <Modal title="Tải file khảo sát" size="slim" close={() => busy ? notify('Đang xử lý dữ liệu, vui lòng chờ hoàn tất.') : close()}>
    <p className="survey-upload-form">{form.title}<span className="pick-meta">{form.id} · {form.code}</span></p>
    <div className="field extract-person">
      <label htmlFor="extract-person">Mã đối tượng (không bắt buộc)</label>
      <input id="extract-person" list="extract-persons" maxLength={120} disabled={busy} value={person}
        placeholder="VD: QK1.01" onChange={event => setPerson(event.target.value)} />
      <datalist id="extract-persons">{persons.map(code => <option key={code} value={code} />)}</datalist>
      <span className="hint">Nhập để gắn phiếu vào đối tượng đã có. Để trống: dùng mã số ghi trên phiếu, không có thì tạo mã mới.</span>
    </div>
    <label htmlFor="extract-file" className={`survey-upload-zone ${dragging ? 'is-dragover' : ''}`}
      onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true) }} onDragLeave={() => setDragging(false)}
      onDrop={event => {
        event.preventDefault()
        setDragging(false)
        if (busy) return
        if (event.dataTransfer.files.length !== 1) notify('Vui lòng tải lên một file phiếu.')
        else void extract(event.dataTransfer.files[0])
      }}>
      <input id="extract-file" className="survey-upload-input" type="file" aria-label="Chọn ảnh hoặc PDF phiếu khảo sát"
        accept="image/jpeg,image/png,image/webp,application/pdf,.pdf" disabled={busy} onChange={event => {
          void extract(event.target.files?.[0])
          event.target.value = ''
        }} />
      <span id="photo-upload-copy">
        <span className="survey-upload-symbol" aria-hidden="true"><Icon name={file ? 'file' : 'upload'} /></span>
        <strong>{file ? file.name : 'Nhấn để chọn hoặc kéo thả file vào đây'}</strong>
        <span>{file && stage !== 'idle' ? 'Chọn file khác sau khi xử lý xong' : 'Ảnh chụp, PDF scan hoặc PDF · JPG, PNG, WebP, PDF · Tối đa 20 MB'}</span>
      </span>
    </label>
    {stage !== 'idle' && <div className="survey-upload-processing"><div className="progress"><div className={stage === 'read' ? 'is-working' : ''}
      style={{ width: `${percent}%` }} /></div><p className="reading" role="status">{status}</p></div>}
    {error && <div className="notice amber">{error}</div>}
    {error && pending && <button className="smallbtn" onClick={retry}>Thử lưu lại bản ghi</button>}
    {saved && counts && draft && <div ref={result}>
      <div className="upload-summary"><b>Đã tự động lưu phiếu {saved.id}</b> · đối tượng {saved.person}<br />
        {counts.count}/{counts.total} câu trả lời đọc được từ {draft.pagesRead.length} trang.
        {counts.count < counts.total && ' Các câu còn trống cần bổ sung khi đối soát.'}</div>
      {draft.uncertain.length > 0 && <div className="notice amber extract-uncertain">
        <b>Cần đối soát với phiếu gốc ({draft.uncertain.length} mục):</b>
        <ul>{draft.uncertain.map(key => <li key={key}><span className="qindex">{key}</span>{labels.get(key) || 'Thông tin định danh'}</li>)}</ul>
      </div>}
      {[draft.notes, ...draft.warnings].filter(Boolean).map(text => <p className="hint" key={text}>{text}</p>)}
      <div className="photo-fields">{[
        ['Họ và tên', saved.patient.fullName], ['Năm sinh / ngày sinh', birthLabel(saved.patient)],
        ['Mã đối tượng', saved.person], ['Ngày khảo sát', draft.subject.survey_date ? saved.date : ''],
      ].map(([key, value]) => <div className="photo-value" key={key}><label>{key}</label>
        {value && value !== '—' ? value : 'Chưa nhận dạng được'}</div>)}</div>
      <div className="actions spaced">
        <button onClick={() => viewOriginal({ ...saved, hasOriginal: true })}><Icon name="file" /><span>Xem phiếu gốc</span></button>
        <button className="primary" onClick={() => open(saved)}>View / đối soát phiếu →</button>
      </div>
    </div>}
  </Modal>
}
