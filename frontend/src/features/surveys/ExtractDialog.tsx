import { useEffect, useMemo, useRef, useState } from 'react'
import { discardDocuments, extractBundle, extractSurvey, surveyError, type BundleResult, type SurveyDraft } from './api'
import { birthLabel, GROUP, newId, pageRanges, prepareAnswers, progress, resolvePerson, subjectErrors, today, validateAnswers,
  type Group, type Survey, type SurveyForm } from './model'
import { Badge, Icon, Modal } from './ui'
import { mergeSubject } from './workbook'

// Khớp EXTRACTION_MAX_FILE_MB ở backend và client_max_body_size của nginx.
const MAX_SCAN_MB = 40
const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
const ACCEPTED_EXTENSIONS = /\.(jpe?g|png|webp|pdf)$/i

type Stage = 'idle' | 'upload' | 'read' | 'confirm' | 'save' | 'done'

/** Một phiếu đơn được xử lý như file nhiều phiếu chỉ có một phiếu. */
const single = (draft: SurveyDraft): BundleResult => ({
  fileName: draft.fileName, pageCount: draft.pageCount, model: draft.model, subject: draft.subject,
  codeCandidates: draft.subject.code ? [draft.subject.code] : [], drafts: [draft], skipped: [], warnings: [],
})

/** Mã đọc từ phiếu chỉ được dùng thẳng khi chắc chắn; còn lại người dùng xác nhận trước khi lưu. */
const codeIsDoubtful = (result: BundleResult) => result.codeCandidates.length !== 1
  || result.drafts.some(draft => draft.uncertain.includes('code'))

/** Ghép kết quả bóc tách với mã đối tượng thành các bản ghi khảo sát (một phiếu một bản ghi). */
function buildRecords(forms: SurveyForm[], group: Group, result: BundleResult, records: Survey[], person: string,
  codeConfirmed: boolean): Survey[] {
  const others = records.filter(row => row.group === group && row.person === person)
  const known = others[0]?.patient
  const subject = result.subject
  const patient = mergeSubject({
    fullName: subject.full_name || '', birthDate: subject.birth_date || '',
    birthYear: subject.birth_year || '', hometown: subject.hometown || '',
  }, known)
  if (subjectErrors(patient).length) {
    patient.birthDate = known?.birthDate || ''
    patient.birthYear = known?.birthYear || ''
  }
  const bundle = result.drafts.length > 1 || result.skipped.length > 0
  return result.drafts.map(draft => {
    const form = forms.find(item => item.id === draft.form)!
    const answers = prepareAnswers(form, draft.answers, patient)
    for (const error of validateAnswers(form, answers)) delete answers[error.split(':')[0]]
    const counts = progress(form, answers)
    // Mã đã được người dùng nhập/xác nhận thì không còn là mục nghi vấn.
    const uncertain = draft.uncertain.filter(key => !(codeConfirmed && key === 'code'))
    const duplicates = others.filter(row => row.form === form.id).map(row => row.id)
    const date = draft.subject.survey_date || subject.survey_date
    const note = [
      bundle ? `Tự tách từ file ${result.fileName}, trang ${pageRanges(draft.pagesRead)}.`
        : `Tự động trích xuất từ file ${draft.fileName}.`,
      uncertain.length ? `Cần đối soát ${uncertain.length} mục: ${uncertain.join(', ')}.` : 'Đối chiếu với phiếu gốc trước khi hoàn tất.',
      date ? '' : 'Ngày khảo sát tạm dùng ngày nhập, cần xác nhận.',
      duplicates.length ? `Đối tượng đã có phiếu cùng loại: ${duplicates.join(', ')} — kiểm tra trùng.` : '',
      ...result.warnings,
    ].filter(Boolean).join(' ')
    return {
      id: newId('OCR'), person, patient, group, form: form.id,
      unit: draft.subject.unit || subject.unit || '', conclusion: '', date: date || today(),
      status: counts.count === counts.total && !uncertain.length ? 'review' : 'draft',
      source: 'OCR', answers, note, ocr: draft.summary, documentId: draft.documentId,
    }
  })
}

/** Tải một file phiếu đã điền của MỘT người: một mẫu đã chọn (``form``), hoặc nhiều mẫu tự tách. */
export function ExtractDialog({ form, group, forms, records, close, save, open, viewOriginal, notify }: {
  form?: SurveyForm
  group: Group
  forms: SurveyForm[]
  records: Survey[]
  close: () => void
  save: (rows: Survey[]) => Promise<void>
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
  const [result, setResult] = useState<BundleResult>()
  const [code, setCode] = useState('')
  const [codeConfirmed, setCodeConfirmed] = useState(false)
  const [saved, setSaved] = useState<Survey[]>()
  const results = useRef<HTMLDivElement>(null)
  const busy = stage === 'upload' || stage === 'read' || stage === 'save'
  const groupForms = forms.filter(item => item.group === group)
  const persons = useMemo(() => [...new Set(records.filter(row => row.group === group)
    .map(row => row.person))].sort(), [records, group])
  const percent = { idle: 0, upload: 5 + uploaded * 25, read: 55, confirm: 80, save: 90, done: 100 }[stage]
  const localUrl = useMemo(() => file ? URL.createObjectURL(file) : '', [file])

  useEffect(() => () => { if (localUrl) URL.revokeObjectURL(localUrl) }, [localUrl])
  // Kết quả nằm dưới vùng upload — cuộn tới để người dùng thấy ngay.
  useEffect(() => {
    if (saved || stage === 'confirm') results.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [saved, stage])

  function fail(problem: unknown, next: Stage) {
    const message = surveyError(problem)
    setError(message)
    setStage(next)
    notify(message)
  }

  async function persist(extracted: BundleResult, chosen: string, confirmed: boolean) {
    const subject = chosen ? resolvePerson(chosen, persons) : newId('OCR')
    const rows = buildRecords(forms, group, extracted, records, subject, confirmed)
    setStage('save')
    setError('')
    try {
      await save(rows)
    } catch (problem) {
      setCode(subject)
      fail(problem, 'confirm')
      return
    }
    setCodeConfirmed(confirmed)
    setSaved(rows)
    setStage('done')
    notify(rows.length > 1 ? `Đã tách và lưu ${rows.length} phiếu của đối tượng ${subject}.` : `Đã trích xuất và lưu phiếu ${rows[0].id}.`)
  }

  async function extract(chosen?: File) {
    if (!chosen || busy) return
    if (!ACCEPTED.includes(chosen.type) && !ACCEPTED_EXTENSIONS.test(chosen.name)) {
      notify('Hãy chọn ảnh JPG, PNG, WebP hoặc file PDF.')
      return
    }
    if (chosen.size > MAX_SCAN_MB * 1024 * 1024) {
      notify(`File vượt quá ${MAX_SCAN_MB} MB.`)
      return
    }
    setFile(chosen)
    setError('')
    setResult(undefined)
    setSaved(undefined)
    setUploaded(0)
    setStage('upload')
    const onUpload = (fraction: number) => {
      setUploaded(fraction)
      if (fraction >= 1) setStage('read')
    }
    let extracted: BundleResult
    try {
      extracted = form ? single(await extractSurvey(form.id, chosen, onUpload)) : await extractBundle(group, chosen, onUpload)
    } catch (problem) {
      fail(problem, 'idle')
      return
    }
    setResult(extracted)
    const typed = person.trim()
    if (typed) await persist(extracted, typed, true)
    else if (!codeIsDoubtful(extracted)) await persist(extracted, extracted.codeCandidates[0], false)
    else {
      setCode(extracted.codeCandidates[0] || '')
      setStage('confirm')
    }
  }

  function dismiss() {
    if (busy) {
      notify('Đang xử lý dữ liệu, vui lòng chờ hoàn tất.')
      return
    }
    // Đã bóc tách nhưng chưa lưu: bỏ file trên máy chủ để không để lại rác.
    if (result && !saved) void discardDocuments(result.drafts.map(draft => draft.documentId)).catch(() => undefined)
    close()
  }

  const status = {
    idle: '', upload: 'Đang tải file lên máy chủ…',
    read: form ? 'Đang đọc phiếu bằng AI — thường mất 10–40 giây, vui lòng giữ cửa sổ này…'
      : 'Đang nhận diện và đọc từng phiếu bằng AI — thường mất 30 giây đến 2 phút, vui lòng giữ cửa sổ này…',
    confirm: 'Đã đọc xong — cần xác nhận mã đối tượng trước khi lưu',
    save: 'Đang lưu bản ghi vào cơ sở dữ liệu…', done: 'Đã trích xuất và lưu bản ghi',
  }[stage]
  const notices = result ? [...new Set([...result.warnings, ...result.drafts.flatMap(draft => draft.warnings)])] : []
  const patient = saved?.[0]?.patient

  return <Modal title="Tải file khảo sát" size="slim" close={dismiss}>
    {form ? <p className="survey-upload-form">{form.title}<span className="pick-meta">{form.id} · {form.code}</span></p>
      : <p className="survey-upload-form">Nhiều phiếu của một người · tự tách theo mẫu
        <span className="pick-meta">{GROUP[group]} · nhận diện {groupForms.map(item => item.id).join(', ')}</span></p>}
    <div className="field extract-person">
      <label htmlFor="extract-person">Mã đối tượng (không bắt buộc)</label>
      <input id="extract-person" list="extract-persons" maxLength={120} disabled={busy || stage === 'confirm'} value={person}
        placeholder={group === 'youth' ? 'VD: PT.CK.001' : 'VD: QK1.01'} onChange={event => setPerson(event.target.value)} />
      <datalist id="extract-persons">{persons.map(code => <option key={code} value={code} />)}</datalist>
      <span className="hint">Nhập để gắn phiếu vào đối tượng đã có. Để trống: dùng mã ghi trên phiếu; mã không rõ hoặc không có thì hỏi lại trước khi lưu.</span>
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
        accept="image/jpeg,image/png,image/webp,application/pdf,.pdf" disabled={busy || stage === 'confirm'} onChange={event => {
          void extract(event.target.files?.[0])
          event.target.value = ''
        }} />
      <span id="photo-upload-copy">
        <span className="survey-upload-symbol" aria-hidden="true"><Icon name={file ? 'file' : 'upload'} /></span>
        <strong>{file ? file.name : 'Nhấn để chọn hoặc kéo thả file vào đây'}</strong>
        <span>{file && stage !== 'idle' ? 'Chọn file khác sau khi xử lý xong'
          : form ? `Ảnh chụp, PDF scan hoặc PDF · JPG, PNG, WebP, PDF · Tối đa ${MAX_SCAN_MB} MB`
            : `Một file gồm các phiếu của MỘT người · PDF hoặc ảnh · Tối đa ${MAX_SCAN_MB} MB`}</span>
      </span>
    </label>
    {!form && stage === 'idle' && <p className="hint">Hệ thống tự nhận diện từng mẫu trong file và tạo một bản ghi cho mỗi phiếu.
      Trang trắng và mẫu chưa có trong hệ thống được bỏ qua. File có phiếu của nhiều người sẽ bị từ chối.</p>}
    {stage !== 'idle' && <div className="survey-upload-processing"><div className="progress"><div className={stage === 'read' ? 'is-working' : ''}
      style={{ width: `${percent}%` }} /></div><p className="reading" role="status">{status}</p></div>}
    {error && <div className="notice amber">{error}</div>}

    {result && !saved && stage === 'confirm' && <div ref={results} className="extract-confirm">
      <b>{result.codeCandidates.length > 1 ? 'Mã đối tượng đọc được không khớp nhau — chọn hoặc sửa mã:'
        : result.codeCandidates.length ? 'Mã đối tượng viết tay chưa rõ — kiểm tra lại mã:'
          : 'Phiếu không ghi mã đối tượng — nhập mã để gắn vào đúng người:'}</b>
      {result.codeCandidates.length > 1 && <div className="code-choices">{result.codeCandidates.map(candidate =>
        <button type="button" key={candidate} className={`smallbtn ${candidate === code ? 'active' : ''}`}
          aria-pressed={candidate === code} onClick={() => setCode(candidate)}>{candidate}</button>)}</div>}
      <input aria-label="Mã đối tượng xác nhận" list="extract-persons" maxLength={120} value={code}
        placeholder="Để trống để tạo mã mới" onChange={event => setCode(event.target.value)} />
      <p className="hint">{result.drafts.length} phiếu đọc được: {result.drafts.map(draft => draft.form).join(', ')}.
        {localUrl && <> <a href={localUrl} target="_blank" rel="noopener noreferrer">Mở file vừa tải</a> để đối chiếu mã.</>}</p>
      <div className="actions spaced">
        <button type="button" onClick={dismiss}>Hủy, không lưu</button>
        <button type="button" className="primary" onClick={() => void persist(result, code.trim(), true)}>
          Lưu {result.drafts.length} phiếu</button>
      </div>
    </div>}

    {saved && result && patient && <div ref={results}>
      <div className="upload-summary"><b>Đã tự động lưu {saved.length} phiếu</b> · đối tượng {saved[0].person}<br />
        Đọc từ file {result.fileName} ({result.pageCount} trang).</div>
      {notices.length > 0 && <div className="notice amber">{notices.map(text => <p key={text}>{text}</p>)}</div>}
      <div className="photo-fields">{[
        ['Họ và tên', patient.fullName], ['Năm sinh / ngày sinh', birthLabel(patient)],
        ['Mã đối tượng', saved[0].person], ['Ngày khảo sát', result.subject.survey_date ? saved[0].date : ''],
      ].map(([key, value]) => <div className="photo-value" key={key}><label>{key}</label>
        {value && value !== '—' ? value : 'Chưa nhận dạng được'}</div>)}</div>
      <div className="extract-results">{saved.map((row, index) => {
        const draft = result.drafts[index]
        const rowForm = forms.find(item => item.id === row.form)!
        const labels = new Map(rowForm.questions.map(question => [question.id, question.label]))
        const counts = progress(rowForm, row.answers)
        const uncertain = draft.uncertain.filter(key => !(codeConfirmed && key === 'code'))
        return <section className="extract-result" key={row.id} aria-label={`Phiếu ${rowForm.title}`}>
          <div className="extract-result-head"><span><b>{rowForm.title}</b>
            <span className="pick-meta">{rowForm.id} · trang {pageRanges(draft.pagesRead)} · {counts.count}/{counts.total} câu đọc được</span></span>
            <Badge status={row.status} /></div>
          {uncertain.length > 0 && <details className="extract-uncertain" open={saved.length === 1}>
            <summary>Cần đối soát với phiếu gốc ({uncertain.length} mục)</summary>
            <ul>{uncertain.map(key => <li key={key}><span className="qindex">{key}</span>{labels.get(key) || 'Thông tin định danh'}</li>)}</ul>
          </details>}
          {draft.notes && <p className="hint">{draft.notes}</p>}
          <div className="actions">
            <button onClick={() => viewOriginal({ ...row, hasOriginal: true })}><Icon name="file" /><span>Xem phiếu gốc</span></button>
            <button className="primary" onClick={() => open(row)}>View / đối soát phiếu →</button>
          </div>
        </section>
      })}</div>
      {result.skipped.length > 0 && <div className="hint extract-skipped"><b>Trang bỏ qua:</b>
        <ul>{result.skipped.map(item => <li key={item.pages.join()}>Trang {pageRanges(item.pages)}: {item.reason}</li>)}</ul></div>}
    </div>}
  </Modal>
}
