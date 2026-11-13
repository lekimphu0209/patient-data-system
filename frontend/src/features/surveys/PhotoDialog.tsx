import { useState } from 'react'
import { surveyError } from './api'
import { birthLabel, isSampleCode, newId, prepareAnswers, progress, subjectErrors, today, validDate, validateAnswers,
  type Answers, type Survey, type SurveyForm } from './model'
import { Icon, Modal } from './ui'
import { isoDate, MAX_FILE_SIZE, mergeSubject } from './workbook'
import workerPath from 'tesseract.js/dist/worker.min.js?url'

const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[đĐ]/g, 'd')
  .toLowerCase().replace(/\s+/g, ' ').trim()

function extractPhoto(text: string, form: SurveyForm) {
  const lines = text.split(/\r?\n/)
  const field = (pattern: RegExp) => {
    for (const line of lines) {
      if (!pattern.test(normalize(line))) continue
      const colon = line.search(/[:：]/)
      const value = line.slice(colon + 1).replace(/^[.\s_…]+|[.\s_…]+$/g, '')
      if (colon >= 0 && value) return value
    }
    return ''
  }
  const code = (value: string) => value.replace(/\s+/g, '-').slice(0, 80)
  const birthDate = isoDate(field(/^ngay\s*(thang\s*)?(nam\s*)?sinh\s*[:：]/))
  const birthYear = field(/^nam\s*sinh\s*[:：]/)
  const date = isoDate(field(/^ngay\s*khao\s*sat\s*[:：]/))
  const patient = {
    fullName: field(/^ho\s*(va\s*)?ten\s*[:：]/).slice(0, 255),
    birthDate: validDate(birthDate) && birthDate <= today() ? birthDate : '',
    birthYear: /^(19|20)\d{2}$/.test(birthYear) && birthYear <= today().slice(0, 4) ? birthYear : '',
    hometown: field(/^que\s*quan\s*[:：]/).slice(0, 255),
  }
  if (patient.birthDate && patient.birthYear && patient.birthDate.slice(0, 4) !== patient.birthYear) patient.birthYear = ''
  const answers: Answers = {}
  for (const question of form.questions) {
    const explicit = new RegExp(`^\\s*${question.id}\\s*[:=.-]\\s*(.+)`, 'i')
    const captured = lines.find(line => explicit.test(line))?.match(explicit)?.[1]?.trim()
    if (captured) {
      if (!question.options.length) answers[question.id] = captured.slice(0, 20000)
      else {
        const choices = question.multi ? captured.split('|').map(option => option.trim()) : [captured]
        if (choices.every(option => question.options.includes(option))) {
          answers[question.id] = question.multi ? choices : choices[0]
        }
      }
    }
    const token = question.label.match(/^(?:Câu\s+)?([A-Z]?\d+(?:\.\d+)?[ab]?)\./i)?.[1]
    if (answers[question.id] || !token || !question.options.length) continue
    const prefix = new RegExp(`^\\s*(?:C[aâ]u\\s+)?${token.replace(/\./g, '\\.')}[.：:]`, 'i')
    const start = lines.findIndex(line => prefix.test(line))
    if (start < 0) continue
    const chunk = lines.slice(start, start + 9)
    const next = chunk.findIndex((line, index) => index > 0 && /^\s*(?:Câu\s+)?(?:[A-Z]\d+|\d+(?:\.\d+)?[ab]?)\./i.test(line))
    const marked = (next > 0 ? chunk.slice(0, next) : chunk)
      .filter(line => /(?:\[[xX]\]|[☑✓✔]|(?:^|\s)[xX]\s)/.test(line)).map(normalize)
    const choices = question.options.filter(option => marked.some(line => line.includes(normalize(option))))
    if (choices.length === 1 || (choices.length > 0 && question.multi)) {
      answers[question.id] = question.multi ? choices : choices[0]
    }
  }
  return {
    patient, answers, date: validDate(date) ? date : '',
    person: code(field(/^ma\s*(doi\s*tuong|so)\s*[:：]/)), id: code(field(/^ma\s*phieu\s*[:：]/)),
    unit: field(/^(don\s*vi|dia\s*ban)\s*[:：]/).slice(0, 255),
    conclusion: field(/^ket\s*luan(\s*ve\s*benh)?\s*[:：]/).slice(0, 20000),
  }
}

async function compress(file: File) {
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    const scale = Math.min(1, 1400 / image.width, 2200 / image.height)
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(image.width * scale))
    canvas.height = Math.max(1, Math.round(image.height * scale))
    const context = canvas.getContext('2d')!
    context.fillStyle = '#fff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.68)
  } finally {
    URL.revokeObjectURL(url)
  }
}

export function PhotoDialog({ form, records, close, save, open, notify }: {
  form: SurveyForm
  records: Survey[]
  close: () => void
  save: (row: Survey) => Promise<void>
  open: (row: Survey) => void
  notify: (message: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [image, setImage] = useState('')
  const [status, setStatus] = useState('')
  const [percent, setPercent] = useState(0)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<Survey>()
  const [saved, setSaved] = useState<Survey>()
  const counts = saved ? progress(form, saved.answers) : undefined

  async function persist(row: Survey) {
    setStatus('Đang lưu bản ghi vào cơ sở dữ liệu…')
    await save(row)
    setPending(undefined)
    setSaved(row)
    setPercent(100)
    setStatus('Đã trích xuất và lưu bản ghi')
    notify('Đã tạo bản ghi từ ảnh khảo sát.')
  }

  function fail(error: unknown) {
    const message = surveyError(error)
    setError(message)
    setStatus('Cần kiểm tra lại')
    notify(message)
  }

  async function recognize(file?: File) {
    if (!file || busy) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      notify('Hãy chọn tệp ảnh JPG, PNG hoặc WebP.')
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      notify('Ảnh vượt quá 10 MB.')
      return
    }
    setBusy(true)
    setSaved(undefined)
    setPending(undefined)
    setError('')
    setImage('')
    setPercent(0)
    setStatus('Đang tải mô hình ngôn ngữ OCR…')
    try {
      const preview = await compress(file)
      setImage(preview)
      const { createWorker } = await import('tesseract.js')
      let timeout: number | undefined
      const loading = new Promise<Awaited<ReturnType<typeof createWorker>>>((resolve, reject) => {
        timeout = window.setTimeout(() => reject(Error('Không tải được mô hình OCR. Hãy kiểm tra kết nối và thử lại.')), 45000)
        createWorker('vie+eng', 1, {
          workerPath,
          workerBlobURL: false,
          logger: message => {
            if (timeout === undefined) return
            setPercent(Math.round(message.progress * 75))
            setStatus(message.status === 'recognizing text' ? 'Đang nhận dạng văn bản…' : 'Đang chuẩn bị mô hình OCR…')
          },
          errorHandler: error => {
            if (timeout !== undefined) reject(Error(String(error)))
          },
        }).then(worker => {
          if (timeout === undefined) void worker.terminate()
          else resolve(worker)
        }, error => reject(Error(String(error || 'Không tải được mô hình OCR.'))))
      })
      const worker = await loading.finally(() => {
        window.clearTimeout(timeout)
        timeout = undefined
      })
      setStatus('Đang nhận dạng văn bản…')
      setPercent(75)
      let text: string
      try {
        text = (await worker.recognize(file)).data.text.trim()
      } finally {
        await worker.terminate()
      }
      if (!text) throw Error('Không nhận dạng được văn bản. Hãy chụp lại ảnh rõ nét hơn.')
      const extracted = extractPhoto(text, form)
      const id = extracted.id || newId('OCR')
      if (isSampleCode(id) || records.some(row => row.id === id)) throw Error('Mã phiếu trên ảnh đã tồn tại hoặc dành cho dữ liệu mẫu.')
      const person = extracted.person || newId('OCR')
      const known = records.find(row => !row.sample && row.person === person && row.group === form.group)?.patient
      const patient = mergeSubject(extracted.patient, known)
      if (subjectErrors(patient).length) {
        patient.birthDate = known?.birthDate || ''
        patient.birthYear = known?.birthYear || ''
      }
      const answers = prepareAnswers(form, extracted.answers, patient)
      for (const error of validateAnswers(form, answers)) delete answers[error.split(':')[0]]
      const counts = progress(form, answers)
      const row: Survey = {
        id, person, patient, form: form.id, group: form.group, unit: extracted.unit, conclusion: extracted.conclusion,
        date: extracted.date || today(), status: counts.count === counts.total ? 'review' : 'draft', source: 'OCR',
        answers, ocr: text.slice(0, 200000), ocrImage: preview,
        note: `Tự động từ ảnh ${file.name}. Cần đối chiếu các trường thiếu hoặc chưa rõ. ${extracted.date
          ? 'Đã nhận dạng ngày khảo sát, cần đối chiếu ảnh gốc.' : 'Ngày khảo sát tạm dùng ngày nhập và cần xác nhận.'}`,
      }
      setPending(row)
      await persist(row)
    } catch (error) {
      fail(error)
    } finally {
      setBusy(false)
    }
  }

  async function retry() {
    if (!pending || busy) return
    setBusy(true)
    setError('')
    try { await persist(pending) } catch (error) { fail(error) } finally { setBusy(false) }
  }

  return <Modal title="Tải file khảo sát" size="slim" close={() => busy ? notify('Đang xử lý dữ liệu, vui lòng chờ hoàn tất.') : close()}>
    <p className="survey-upload-form">{form.title}</p>
    <label htmlFor="photo-file" className={`survey-upload-zone ${dragging ? 'is-dragover' : ''}`}
      onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true) }} onDragLeave={() => setDragging(false)}
      onDrop={event => {
        event.preventDefault()
        setDragging(false)
        if (busy) return
        if (event.dataTransfer.files.length !== 1) notify('Vui lòng tải lên một ảnh khảo sát.')
        else void recognize(event.dataTransfer.files[0])
      }}>
      <input id="photo-file" className="survey-upload-input" type="file" aria-label="Chọn ảnh khảo sát"
        accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => {
          void recognize(event.target.files?.[0])
          event.target.value = ''
        }} />
      {image ? <img className="ocr-image" src={image} alt="Ảnh khảo sát đã chọn" /> : <span id="photo-upload-copy">
        <span className="survey-upload-symbol" aria-hidden="true"><Icon name="upload" /></span>
        <strong>Nhấn để chọn hoặc kéo thả ảnh vào đây</strong><span>JPG, PNG, WebP · Tối đa 10 MB</span>
      </span>}
    </label>
    {status && <div className="survey-upload-processing"><div className="progress"><div style={{ width: `${percent}%` }} /></div>
      <p className="reading" role="status">{status}</p></div>}
    {error && <div className="notice amber">{error}</div>}
    {error && pending && <button className="smallbtn" onClick={retry}>Thử lưu lại bản ghi</button>}
    {saved && counts && <>
      <div className="upload-summary"><b>Đã tự động lưu phiếu {saved.id}</b><br />
        {counts.count}/{counts.total} câu trả lời có thể trích xuất. {counts.count < counts.total && 'Các mục còn lại cần đối soát.'}</div>
      <div className="photo-fields">{[
        ['Họ và tên', saved.patient.fullName], ['Ngày sinh', birthLabel(saved.patient)],
        ['Quê quán', saved.patient.hometown], ['Kết luận được ghi trên phiếu', saved.conclusion],
      ].map(([key, value]) => <div className="photo-value" key={key}><label>{key}</label>
        {value && value !== '—' ? value : 'Chưa nhận dạng được'}</div>)}</div>
      <div className="actions spaced"><button className="primary" onClick={() => open(saved)}>View / đối soát phiếu →</button></div>
    </>}
  </Modal>
}
