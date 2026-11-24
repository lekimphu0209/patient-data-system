/**
 * Bệnh án F20 (tâm thần phân liệt) và F32 (trầm cảm): danh sách bệnh nhân và trang bệnh án.
 * Markup và class giữ đúng bản thiết kế 103_design_v2 (clinical.js); dữ liệu lưu trên máy chủ.
 */
import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { formatDate, today } from '../surveys/model'
import { Icon, Modal } from '../surveys/ui'
import {
  clinicalError, deletePatient, extractPatient, getClinicalSpec, getOriginal, getPatients, isClinicalType, savePatient,
  type ClinicalFieldDef, type ClinicalSpec, type ClinicalType, type FieldValue, type Patient, type Visit,
} from './api'
import styles from './clinical.css?url'

export type ClinicalRoute = { type: ClinicalType; route: 'list' | 'new' | 'record'; id: string }
/** Chặn rời trang khi còn thay đổi chưa lưu: trả về true nếu đã chặn (sẽ gọi ``proceed`` khi người dùng đồng ý). */
export type LeaveGuard = (proceed: () => void) => boolean
type Go = (type: ClinicalType, id?: string, route?: 'list' | 'new' | 'record') => void

export const PATIENTS_KEY = ['clinical-patients'] as const
const REQUIRED = ['code', 'fullName', 'age', 'sex']
// Khớp EXTRACTION_MAX_FILE_MB ở backend và client_max_body_size của nginx.
const MAX_UPLOAD_MB = 40

export function readClinicalRoute(parts: string[]): ClinicalRoute {
  const [type, id] = parts
  let decoded = ''
  try {
    decoded = id && id !== 'new' ? decodeURIComponent(id) : ''
  } catch { decoded = '' }
  return { type: isClinicalType(type) ? type : 'F20', route: id === 'new' ? 'new' : id ? 'record' : 'list', id: decoded }
}
export const clinicalHash = (type: ClinicalType, id = '', route: 'list' | 'new' | 'record' = 'list') =>
  'clinical/' + type + (route === 'new' ? '/new' : id ? '/' + encodeURIComponent(id) : '')

const uid = () => (crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`).replace(/[^\w]/g, '').slice(0, 32)
const newVisit = (): Visit => ({ id: uid(), date: today(), createdAt: new Date().toISOString(), fields: {} })
const sortVisits = (visits: Visit[]) => visits.slice()
  .sort((a, b) => b.date.localeCompare(a.date) || b.createdAt.localeCompare(a.createdAt))
export const latestVisit = (patient: Patient) => sortVisits(patient.visits || [])[0]
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value))

function SectionIcon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    history: <><path d="M9 5H5a2 2 0 0 0-2 2v13h14V7a2 2 0 0 0-2-2h-2" /><rect x="7" y="3" width="6" height="4" rx="1" /><path d="M7 11h6m-6 4h6" /></>,
    physical: <><path d="M6 3v6a5 5 0 0 0 10 0V3M4 3h4m6 0h4M11 14v2a5 5 0 0 0 10 0v-2" /><circle cx="21" cy="11" r="2" /></>,
    brain: <path d="M12 5a3 3 0 0 0-5-2 4 4 0 0 0-3 6 4 4 0 0 0 0 7 4 4 0 0 0 4 5c2 1 4-1 4-3V5Zm0 0a3 3 0 0 1 5-2 4 4 0 0 1 3 6 4 4 0 0 1 0 7 4 4 0 0 1-4 5c-2 1-4-1-4-3M7 8l3 2m7-2-3 2M6 15l4-1m8 1-4-1" />,
    lab: <><path d="M9 3h6m-5 0v7L4 20a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1l-6-10V3M7 15h10" /><path d="M10 18h.01m4-1h.01" /></>,
    mood: <><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /><path d="M6 12h3l2-4 2 8 2-4h3" /></>,
    treatment: <path d="m8 15 7-7M6 18a5 5 0 0 1-1-7l6-6a5 5 0 0 1 7 7l-6 6a5 5 0 0 1-6 0Z" />,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 11h18m-13 5 2 2 5-5" /></>,
  }
  if (name === 'observation' || name === 'perception') return <Icon name="eye" />
  if (name === 'admin' || name === 'diagnosis') return <Icon name="file" />
  const key = ['conscious', 'thinking', 'attention', 'behavior'].includes(name) ? 'brain' : name === 'anxiety' ? 'mood'
    : name === 'otherTests' ? 'lab' : name === 'somatic' ? 'physical' : name
  return <svg className="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true">{paths[key] || paths.brain}</svg>
}

// ---------- trang chung ----------

export function ClinicalPage({ route, go, notify, setGuard }: {
  route: ClinicalRoute
  go: Go
  notify: (message: string) => void
  setGuard: (guard: LeaveGuard | null) => void
}) {
  const spec = useQuery({ queryKey: ['clinical-spec'], queryFn: getClinicalSpec, staleTime: Infinity })
  const patients = useQuery({ queryKey: PATIENTS_KEY, queryFn: getPatients })
  const name = spec.data?.forms[route.type]?.title || (route.type === 'F20' ? 'Tâm thần phân liệt' : 'Trầm cảm')
  const error = spec.error || patients.error
  let content: ReactNode
  if (!spec.data || !patients.data) {
    content = <div className="clinical-workspace"><h1>Bệnh án · {name}</h1><div className="clinical-empty">
      {error ? <><p>{clinicalError(error)}</p><button className="btn primary" onClick={() => {
        void spec.refetch()
        void patients.refetch()
      }}>Thử tải lại</button></> : 'Đang tải danh sách bệnh nhân…'}</div></div>
  } else if (route.route === 'list') {
    content = <ClinicalList spec={spec.data} type={route.type} patients={patients.data} go={go} notify={notify} />
  } else {
    content = <ClinicalEditor key={`${route.type}/${route.route}/${route.id}`} spec={spec.data} route={route}
      patients={patients.data} go={go} notify={notify} setGuard={setGuard} />
  }
  return <><link rel="stylesheet" href={styles} />{content}</>
}

// ---------- danh sách bệnh nhân ----------

function ClinicalList({ spec, type, patients, go, notify }: {
  spec: ClinicalSpec
  type: ClinicalType
  patients: Patient[]
  go: Go
  notify: (message: string) => void
}) {
  const client = useQueryClient()
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(new Set<string>())
  const [removing, setRemoving] = useState<Patient>()
  const [deleting, setDeleting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const selectAll = useRef<HTMLInputElement>(null)
  const name = spec.forms[type].title
  const rows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('vi')
    return patients.filter(patient => patient.type === type && (!query || [patient.code, patient.fullName,
      String(latestVisit(patient)?.fields?.diagnosis || '')].some(value => value.toLocaleLowerCase('vi').includes(query))))
      .sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''))
  }, [patients, search, type])
  const all = rows.length > 0 && rows.every(patient => selected.has(patient.id))
  useEffect(() => {
    if (selectAll.current) selectAll.current.indeterminate = selected.size > 0 && !all
  }, [selected, all])

  async function confirmDelete() {
    if (!removing) return
    setDeleting(true)
    try {
      await deletePatient(removing.id, removing.revision)
      client.setQueryData<Patient[]>(PATIENTS_KEY, list => list?.filter(item => item.id !== removing.id))
      setSelected(previous => {
        const next = new Set(previous)
        next.delete(removing.id)
        return next
      })
      setRemoving(undefined)
      notify('Đã xóa bệnh nhân và các lần khám.')
    } catch (error) {
      notify(clinicalError(error))
    } finally {
      setDeleting(false)
    }
  }

  return <div className="clinical-workspace">
    <div className="clinical-pagehead"><div><div className="clinical-crumb">Bệnh án</div><h1>{name}</h1></div>
      <div className="clinical-head-actions">
        <button className="btn" onClick={() => setUploading(true)}><Icon name="upload" /> Tải bệnh án</button>
        <button className="btn primary" onClick={() => go(type, '', 'new')}><Icon name="plus" /> Thêm bệnh nhân</button>
      </div></div>
    <section className="clinical-list-panel">
      <div className="clinical-toolbar">
        <label className="clinical-search"><Icon name="search" /><input aria-label="Tìm bệnh nhân" placeholder="Tìm mã, họ tên, chẩn đoán…"
          value={search} onChange={event => { setSearch(event.target.value); setSelected(new Set()) }} /></label>
        <span id="clinical-count">{selected.size ? `${selected.size} đã chọn / ${rows.length} bệnh nhân` : `${rows.length} bệnh nhân`}</span>
      </div>
      <div className="clinical-table-wrap"><table className="clinical-table">
        <colgroup>{[65, 54, 170, 260, 85, 115, 330, 144].map((width, index) => <col key={index} style={{ width }} />)}</colgroup>
        <thead><tr><th>STT</th><th><input ref={selectAll} type="checkbox" id="clinical-select-all" aria-label="Chọn tất cả bệnh nhân"
          checked={all} disabled={!rows.length} onChange={event => setSelected(new Set(event.target.checked ? rows.map(p => p.id) : []))} /></th>
          <th>MÃ BỆNH NHÂN</th><th>HỌ VÀ TÊN</th><th>TUỔI</th><th>GIỚI TÍNH</th><th>CHẨN ĐOÁN</th><th className="clinical-actions">THAO TÁC</th></tr></thead>
        <tbody id="clinical-rows">{rows.length ? rows.map((patient, index) => {
          const diagnosis = String(latestVisit(patient)?.fields?.diagnosis || '') || 'Chưa ghi nhận'
          return <tr key={patient.id}>
            <td>{index + 1}</td>
            <td><input type="checkbox" aria-label={`Chọn ${patient.code}`} checked={selected.has(patient.id)} onChange={event => {
              const next = new Set(selected)
              if (event.target.checked) next.add(patient.id)
              else next.delete(patient.id)
              setSelected(next)
            }} /></td>
            <td title={patient.code}><strong>{patient.code}</strong></td>
            <td title={patient.fullName}><button className="clinical-patient-link" onClick={() => go(patient.type, patient.id)}>
              {patient.fullName || 'Chưa nhận dạng họ tên'}</button></td>
            <td>{patient.age || '—'}</td>
            <td>{patient.sex || '—'}</td>
            <td title={diagnosis}>{diagnosis}</td>
            <td className="clinical-actions"><div className="clinical-row-actions">
              <button className="clinical-view" title="Xem bệnh án" aria-label={`Xem bệnh án ${patient.code}`}
                onClick={() => go(patient.type, patient.id)}><Icon name="eye" /></button>
              <button className="clinical-delete" title="Xóa bệnh nhân" aria-label={`Xóa bệnh nhân ${patient.code}`}
                onClick={() => setRemoving(patient)}><Icon name="trash" /></button>
            </div></td>
          </tr>
        }) : <tr><td colSpan={8}><div className="clinical-empty"><Icon name="users" />
          <h3>{search ? 'Không tìm thấy bệnh nhân' : 'Chưa có bệnh nhân'}</h3>
          <p>{search ? 'Hãy thử tìm bằng thông tin khác.' : 'Thêm bệnh nhân để tạo bệnh án lần khám đầu tiên.'}</p>
          {!search && <button className="btn primary" onClick={() => go(type, '', 'new')}><Icon name="plus" /> Thêm bệnh nhân</button>}
        </div></td></tr>}</tbody>
      </table></div>
    </section>
    {removing && <Modal title="Xóa bệnh nhân" size="clinical-modal" close={() => {
      if (deleting) notify('Đang xử lý dữ liệu, vui lòng chờ hoàn tất.')
      else setRemoving(undefined)
    }} footer={<>
      <button className="btn" onClick={() => !deleting && setRemoving(undefined)}>Hủy</button>
      <button className="btn danger" id="clinical-confirm-delete" disabled={deleting} onClick={() => void confirmDelete()}>
        {deleting ? 'Đang xóa…' : <><Icon name="trash" /> Xóa bệnh nhân</>}</button>
    </>}>
      <div className="clinical-confirm"><span className="clinical-confirm-icon danger"><Icon name="trash" /></span>
        <h3>Xóa bệnh án của {removing.fullName || removing.code}?</h3>
        <p>Mã bệnh nhân <strong>{removing.code}</strong> · {removing.visits.length} lần khám</p>
        <p>Toàn bộ các lần khám của bệnh nhân sẽ bị xóa. Không thể hoàn tác.</p></div>
    </Modal>}
    {uploading && <ClinicalUpload type={type} name={name} notify={notify} close={() => setUploading(false)}
      saved={patient => client.setQueryData<Patient[]>(PATIENTS_KEY, list => [patient, ...(list || []).filter(p => p.id !== patient.id)])}
      open={patient => { setUploading(false); go(patient.type, patient.id) }} />}
  </div>
}

// ---------- tải bệnh án (ảnh/PDF -> model thị giác) ----------

function ClinicalUpload({ type, name, notify, close, saved, open }: {
  type: ClinicalType
  name: string
  notify: (message: string) => void
  close: () => void
  saved: (patient: Patient) => void
  open: (patient: Patient) => void
}) {
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [preview, setPreview] = useState('')
  const [fileName, setFileName] = useState('')
  const [progress, setProgress] = useState<{ width: number; status: string }>()
  const [error, setError] = useState('')
  const [result, setResult] = useState<Patient>()
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  async function run(file?: File) {
    if (!file || busy) return
    const image = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
    if (!image && file.type !== 'application/pdf' && !/\.pdf$/i.test(file.name)) {
      notify('Vui lòng chọn ảnh JPG, PNG, WebP hoặc file PDF.')
      return
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      notify(`File vượt quá ${MAX_UPLOAD_MB} MB.`)
      return
    }
    setBusy(true)
    setError('')
    setResult(undefined)
    setFileName(file.name)
    setPreview(image ? URL.createObjectURL(file) : '')
    setProgress({ width: 3, status: 'Đang tải ảnh lên máy chủ…' })
    try {
      const patient = await extractPatient(type, file, fraction => {
        if (fraction < 1) setProgress({ width: 3 + Math.round(fraction * 22), status: 'Đang tải ảnh lên máy chủ…' })
        else setProgress({ width: 55, status: 'Đang nhận dạng nội dung bệnh án bằng AI — thường mất 20–60 giây…' })
      })
      saved(patient)
      setResult(patient)
      setProgress({ width: 100, status: 'Đã nhập bệnh án và thêm bệnh nhân vào danh sách' })
      notify('Đã thêm một bệnh nhân từ ảnh bệnh án.')
    } catch (problem) {
      const message = clinicalError(problem)
      setError(message)
      setProgress(previous => ({ width: previous?.width || 0, status: 'Chưa thể hoàn tất' }))
      notify(message)
    } finally {
      setBusy(false)
    }
  }

  return <Modal title="Tải bệnh án" size="clinical-upload-modal" close={() => busy ? notify('Đang xử lý dữ liệu, vui lòng chờ hoàn tất.') : close()}>
    <div className="clinical-upload-kind"><Icon name="file" /><strong>Bệnh án {name.toLowerCase()}</strong></div>
    <label className={`clinical-upload-zone ${dragging ? 'is-dragover' : ''}`} id="clinical-upload-zone"
      onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true) }} onDragLeave={() => setDragging(false)}
      onDrop={event => {
        event.preventDefault()
        setDragging(false)
        if (busy) return
        if (event.dataTransfer.files.length !== 1) notify('Vui lòng chọn một ảnh bệnh án.')
        else void run(event.dataTransfer.files[0])
      }}>
      <input id="clinical-image-file" type="file" accept="image/jpeg,image/png,image/webp,application/pdf,.pdf"
        aria-label="Chọn ảnh bệnh án" disabled={busy} onChange={event => { void run(event.target.files?.[0]); event.target.value = '' }} />
      <span id="clinical-upload-copy" hidden={Boolean(preview || (fileName && !preview && progress))}>
        <span className="clinical-upload-symbol"><Icon name="upload" /></span>
        <strong>Chọn hoặc kéo thả ảnh bệnh án</strong>
        <span>JPG, PNG, WebP, PDF · Tối đa {MAX_UPLOAD_MB} MB</span>
      </span>
      {!preview && fileName && progress && <span><span className="clinical-upload-symbol"><Icon name="file" /></span>
        <strong>{fileName}</strong><span>{busy ? 'Đang xử lý…' : 'Chọn hoặc kéo thả để tải bệnh án khác'}</span></span>}
      <img id="clinical-upload-preview" hidden={!preview} src={preview || undefined} alt="Ảnh bệnh án đã tải lên" />
    </label>
    <div className="clinical-ocr-progress" id="clinical-ocr-progress" hidden={!progress}>
      <div className="clinical-ocr-progress-track"><span id="clinical-ocr-bar" className={busy && progress?.width === 55 ? 'is-working' : undefined}
        style={{ width: `${progress?.width || 0}%` }} /></div>
      <p role="status" id="clinical-ocr-status">{progress?.status}</p>
    </div>
    <div id="clinical-ocr-result" aria-live="polite">
      {error && <div className="clinical-ocr-error">{error}</div>}
      {result && <>
        <div className="clinical-ocr-success"><span><Icon name="check" /></span><div>
          <strong>{result.fullName || 'Chưa nhận dạng họ tên'}</strong>
          <p>{result.code} · {result.ocr?.extractedCount ?? 0} trường đã bóc tách</p></div></div>
        <p className="clinical-ocr-note">Các trường chưa rõ được để trống để bổ sung khi đối soát.</p>
        <button className="btn primary" onClick={() => open(result)}><Icon name="eye" /> Xem bệnh án</button>
      </>}
    </div>
  </Modal>
}

function OcrSource({ patient }: { patient: Patient }) {
  const [url, setUrl] = useState('')
  const [failed, setFailed] = useState(false)
  const requested = useRef(false)
  useEffect(() => () => { if (url) URL.revokeObjectURL(url) }, [url])
  const ocr = patient.ocr
  const text = ocr ? [
    `Số trang đã đọc: ${ocr.pages}`,
    `Số trường đã bóc tách: ${ocr.extractedCount}`,
    ocr.uncertain.length ? `Cần đối soát: ${ocr.uncertain.join('; ')}` : 'Cần đối soát: không có mục nào được đánh dấu',
    ocr.notes ? `Ghi chú khi đọc: ${ocr.notes}` : '',
    ocr.dateInferred ? 'Ngày khám: chưa đọc được trên bệnh án, tạm dùng ngày tải ảnh.' : '',
    `Mô hình: ${ocr.model}`,
  ].filter(Boolean).join('\n') : ''
  return <details className="clinical-ocr-source" onToggle={event => {
    if (!(event.currentTarget as HTMLDetailsElement).open || requested.current || !patient.hasOriginal) return
    requested.current = true
    getOriginal(patient.id).then(blob => setUrl(URL.createObjectURL(blob))).catch(() => setFailed(true))
  }}>
    <summary><Icon name="image" /> Ảnh bệnh án và nội dung OCR <span>Cần đối soát</span></summary>
    <div className="clinical-ocr-source-grid">
      {url ? patient.originalType === 'pdf' ? <iframe src={url} title="Bệnh án gốc" style={{ width: '100%', height: 650, border: 0 }} />
        : <img src={url} alt="Ảnh bệnh án gốc" /> : patient.hasOriginal && <p>{failed ? 'Không tải được file bệnh án gốc.' : 'Đang tải ảnh bệnh án…'}</p>}
      <div><strong>{ocr?.sourceFile || 'Ảnh bệnh án'}</strong><pre>{text}</pre>
        <p>Trường chưa đọc được để trống. Ngày khám tạm dùng ngày tải ảnh nếu không nhận dạng được ngày khám hoặc ngày vào viện.</p></div>
    </div>
  </details>
}

// ---------- trang bệnh án ----------

type Scope = 'patient' | 'visit' | 'fields'

const Field = memo(function Field({ field, value, scope, required, onChange }: {
  field: ClinicalFieldDef
  value: FieldValue | undefined
  scope: Scope
  required: boolean
  onChange: (scope: Scope, key: string, value: FieldValue) => void
}) {
  const { key, kind, label } = field
  const id = `cl-${scope}-${key}`
  let input: ReactNode
  if (kind === 'multi') {
    const chosen = Array.isArray(value) ? value : []
    input = <fieldset id={id} data-cl-scope={scope} data-cl-key={key} className="clinical-options">
      <legend className="sr-only">{label}</legend>
      {(field.options || []).map(option => <label key={option}><input type="checkbox" value={option} checked={chosen.includes(option)}
        onChange={event => onChange(scope, key, event.target.checked ? [...new Set([...chosen, option])] : chosen.filter(item => item !== option))} />
        {' '}<span>{option}</span></label>)}
    </fieldset>
  } else if (kind === 'select') {
    input = <select id={id} required={required} value={typeof value === 'string' ? value : ''}
      onChange={event => onChange(scope, key, event.target.value)}>
      <option value="">Chưa chọn</option>
      {(field.options || []).map(option => <option key={option}>{option}</option>)}
    </select>
  } else if (kind === 'textarea') {
    input = <textarea id={id} rows={3} value={typeof value === 'string' ? value : ''} onChange={event => onChange(scope, key, event.target.value)} />
  } else {
    input = <input id={id} type={kind === 'number' ? 'number' : kind === 'date' ? 'date' : 'text'} required={required}
      value={typeof value === 'string' ? value : value === undefined ? '' : String(value)}
      onChange={event => onChange(scope, key, event.target.value)}
      {...(kind === 'number' ? { min: 0, step: key === 'age' ? 1 : 'any', ...(key === 'age' ? { max: 150 } : {}) } : {})}
      {...(key === 'code' ? { maxLength: 80 } : key === 'fullName' ? { maxLength: 200 } : {})} />
  }
  return <div className={`clinical-field ${kind === 'multi' || kind === 'textarea' ? 'clinical-wide' : ''}`}>
    <label htmlFor={kind === 'multi' ? undefined : id}>{label}{required && <> <span className="clinical-required">*</span></>}</label>
    {input}
  </div>
})

function validate(patient: Patient, spec: ClinicalSpec, others: Patient[]) {
  if (!patient.code.trim() || !patient.fullName.trim() || patient.age === '' || !patient.sex) {
    throw Error('Vui lòng nhập mã bệnh nhân, họ tên, tuổi và giới tính.')
  }
  const age = Number(patient.age)
  if (!Number.isInteger(age) || age < 0 || age > 150) throw Error('Tuổi phải là số nguyên từ 0 đến 150.')
  for (const visit of patient.visits) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(visit.date) || Number.isNaN(Date.parse(visit.date))) {
      throw Error('Vui lòng nhập ngày khám cho từng lần khám.')
    }
    for (const field of spec.forms[patient.type].sections.flatMap(section => section.fields)) {
      const value = visit.fields[field.key]
      if (field.kind === 'number' && value !== undefined && value !== '' && (!Number.isFinite(Number(value)) || Number(value) < 0)) {
        throw Error(field.label + ': giá trị phải từ 0 trở lên.')
      }
    }
  }
  const code = patient.code.trim().toLocaleLowerCase('vi')
  if (others.some(other => other.id !== patient.id && other.code.toLocaleLowerCase('vi') === code)) {
    throw Error('Mã bệnh nhân đã tồn tại. Vui lòng dùng mã khác.')
  }
}

function ClinicalEditor({ spec, route, patients, go, notify, setGuard }: {
  spec: ClinicalSpec
  route: ClinicalRoute
  patients: Patient[]
  go: Go
  notify: (message: string) => void
  setGuard: (guard: LeaveGuard | null) => void
}) {
  const client = useQueryClient()
  const fresh = route.route === 'new'
  const type = route.type
  const form = spec.forms[type]
  const name = form.title
  const [draft, setDraft] = useState<Patient | null>(() => {
    if (fresh) return { id: uid(), type, code: '', fullName: '', age: '', sex: '', visits: [newVisit()], revision: 0 }
    const found = patients.find(patient => patient.id === route.id && patient.type === type)
    return found ? clone(found) : null
  })
  const [visitId, setVisitId] = useState(() => (draft ? sortVisits(draft.visits)[0]?.id : '') || '')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [folds, setFolds] = useState<Record<string, boolean>>({})
  const [leaving, setLeaving] = useState<() => void>()
  const dirtyRef = useRef(false)
  dirtyRef.current = dirty

  useEffect(() => {
    setGuard(proceed => {
      if (!dirtyRef.current) return false
      setLeaving(() => proceed)
      return true
    })
    return () => setGuard(null)
  }, [setGuard])
  useEffect(() => {
    if (!dirty) return
    const onUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', onUnload)
    return () => window.removeEventListener('beforeunload', onUnload)
  }, [dirty])

  const change = useMemo(() => (scope: Scope, key: string, value: FieldValue) => {
    setDraft(previous => {
      if (!previous) return previous
      const next = { ...previous }
      if (scope === 'patient') next[key] = value
      else next.visits = previous.visits.map(visit => visit.id !== visitIdRef.current ? visit
        : scope === 'visit' ? { ...visit, [key]: value } : { ...visit, fields: { ...visit.fields, [key]: value } })
      return next
    })
    setDirty(true)
  }, [])
  const visitIdRef = useRef(visitId)
  visitIdRef.current = visitId

  if (!draft) {
    return <div className="clinical-workspace"><h1>Không tìm thấy bệnh nhân</h1>
      <button className="btn" onClick={() => go(type)}>Danh sách bệnh nhân</button></div>
  }
  const visit = draft.visits.find(item => item.id === visitId) || draft.visits[0]
  const first = draft.visits[0]
  const foldOpen = (key: string) => folds[key] ?? fresh
  const toggleFold = (key: string, force?: boolean) => setFolds(previous => ({ ...previous, [key]: force ?? !(previous[key] ?? fresh) }))
  const scrollToVisit = () => window.setTimeout(() =>
    document.querySelector('.clinical-visit-heading')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30)

  function leave(next: () => void) {
    if (dirty) setLeaving(() => next)
    else next()
  }
  function switchVisit(id: string) {
    if (busy) return
    setVisitId(id)
    scrollToVisit()
  }
  function addVisit() {
    if (busy || !draft) return
    const item = newVisit()
    setDraft({ ...draft, visits: [...draft.visits, item] })
    setVisitId(item.id)
    setDirty(true)
    scrollToVisit()
  }
  async function save() {
    if (busy || !draft) return
    try {
      validate(draft, spec, patients)
    } catch (error) {
      notify((error as Error).message)
      return
    }
    setBusy(true)
    try {
      const patient = await savePatient({ ...draft, code: draft.code.trim(), fullName: draft.fullName.trim() }, fresh)
      client.setQueryData<Patient[]>(PATIENTS_KEY, list => [patient, ...(list || []).filter(item => item.id !== patient.id)])
      dirtyRef.current = false
      setDirty(false)
      setDraft(clone(patient))
      notify(`Đã lưu bệnh nhân và ${patient.visits.length} lần khám.`)
      if (fresh) go(patient.type, patient.id, 'record')
    } catch (error) {
      notify(clinicalError(error))
    } finally {
      setBusy(false)
    }
  }

  return <div className="clinical-workspace">
    <div className="clinical-pagehead"><div>
      <button className="clinical-back" onClick={() => leave(() => go(type))}>Danh sách bệnh nhân</button>
      <h1>{fresh ? 'Thêm bệnh nhân' : draft.fullName || 'Bệnh nhân ' + draft.code}</h1></div>
      <div className="clinical-head-actions">
        <a className="btn" href={`/clinical/clinical-${type}.docx`} download><Icon name="download" /> Mẫu bệnh án</a>
        {!fresh && <button className="btn" onClick={addVisit}><Icon name="plus" /> Thêm lần khám</button>}
      </div></div>
    <div className="clinical-record-banner"><span className="clinical-record-icon"><Icon name="file" /></span>
      <div><strong>Bệnh án {name.toLowerCase()}</strong><span>{fresh ? 'Lần khám đầu tiên' : `${draft.code} · ${draft.visits.length} lần khám`}</span></div>
      <span className="clinical-save-status" id="clinical-save-status">{dirty ? 'Chưa lưu thay đổi' : fresh ? 'Bệnh án mới' : 'Đã lưu'}</span>
    </div>
    {draft.source === 'OCR' && <OcrSource patient={draft} />}
    <form id="clinical-form" onSubmit={event => { event.preventDefault(); void save() }} onInvalidCapture={event => {
      const panel = (event.target as HTMLElement).closest('[id^=clinical-fold-]') as HTMLElement | null
      if (panel?.hidden) toggleFold(panel.id.replace('clinical-fold-', ''), true)
    }}>
      <section className="clinical-horizontal-history" aria-label="Lịch sử khám">
        <h2><span className="clinical-heading-icon"><SectionIcon name="calendar" /></span>Lịch sử khám</h2>
        <div className="clinical-timeline-items">{sortVisits(draft.visits).map(item => <button type="button" key={item.id}
          className={item.id === visit.id ? 'active' : ''} aria-pressed={item.id === visit.id} onClick={() => switchVisit(item.id)}>
          <span className="clinical-timeline-dot" /><strong>{formatDate(item.date)}</strong>
          <span>{item.id === first.id ? 'Khám lần đầu' : 'Tái khám'}</span></button>)}</div>
      </section>
      <div className="clinical-record-layout">
        <aside className="clinical-section-index"><nav className="clinical-section-nav" aria-label="Các phần bệnh án">
          {form.sections.map(section => <a key={section.key} href={`#cl-section-${section.key}`} onClick={event => {
            event.preventDefault()
            if (section.key === 'admin') toggleFold('admin', true)
            document.getElementById('cl-section-' + section.key)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }}><span className="clinical-index-icon"><SectionIcon name={section.key} /></span>
            <span>{section.title.replace('Khám tâm thần · ', '')}</span></a>)}
        </nav></aside>
        <div className="clinical-visit-content">
          <section className={`clinical-card ${foldOpen('identity') ? '' : 'clinical-is-folded'}`} id="cl-identity">
            <FoldHeader id="identity" label="Thông tin bệnh nhân" icon={<Icon name="users" />} open={foldOpen('identity')} toggle={toggleFold} />
            <div id="clinical-fold-identity" className="clinical-field-grid" hidden={!foldOpen('identity')}>
              {spec.identity.map(field => <Field key={field.key} field={field} scope="patient" required={REQUIRED.includes(field.key)}
                value={draft[field.key] as FieldValue | undefined} onChange={change} />)}
            </div>
          </section>
          <section className="clinical-card clinical-visit-heading">
            <div className="clinical-visit-title"><span className="clinical-visit-emblem"><SectionIcon name="calendar" /></span>
              <h2>{visit.id === first.id ? 'Bệnh án lần khám đầu tiên' : 'Bệnh án tái khám'}</h2></div>
            <label htmlFor="clinical-visit-date">Ngày khám <span className="clinical-required">*</span>
              <input id="clinical-visit-date" type="date" required value={visit.date}
                onChange={event => change('visit', 'date', event.target.value)} /></label>
          </section>
          {form.sections.map(section => {
            const admin = section.key === 'admin'
            return <section key={section.key} className={`clinical-card ${admin && !foldOpen('admin') ? 'clinical-is-folded' : ''}`}
              id={`cl-section-${section.key}`}>
              {admin ? <FoldHeader id="admin" label={section.title} icon={<SectionIcon name={section.key} />} open={foldOpen('admin')} toggle={toggleFold} />
                : <div className="clinical-card-title"><span className="clinical-heading-icon"><SectionIcon name={section.key} /></span><h2>{section.title}</h2></div>}
              <div id={admin ? 'clinical-fold-admin' : undefined} hidden={admin && !foldOpen('admin')} className="clinical-field-grid">
                {section.fields.map(field => <Field key={field.key} field={field} scope="fields" required={false}
                  value={visit.fields[field.key]} onChange={change} />)}
              </div>
            </section>
          })}
        </div>
      </div>
      <div className="clinical-savebar">
        <span id="clinical-save-hint">{dirty ? 'Có thay đổi chưa lưu' : fresh ? 'Nhập thông tin và bệnh án lần khám đầu tiên' : 'Đã lưu bệnh án'}</span>
        <div><button type="button" className="btn" onClick={() => leave(() => go(type))}>Đóng</button>
          <button type="submit" className="btn primary" id="clinical-save" disabled={busy}>
            {busy ? 'Đang lưu…' : <><Icon name="check" /> {fresh ? 'Lưu bệnh nhân' : 'Lưu bệnh án'}</>}</button></div>
      </div>
    </form>
    {leaving && <Modal title="Chưa lưu thay đổi" size="clinical-modal" close={() => setLeaving(undefined)} footer={<>
      <button className="btn" onClick={() => setLeaving(undefined)}>Tiếp tục nhập</button>
      <button className="btn danger" id="clinical-discard" onClick={() => {
        const proceed = leaving
        dirtyRef.current = false
        setDirty(false)
        setLeaving(undefined)
        proceed()
      }}>Bỏ thay đổi</button>
    </>}>
      <div className="clinical-confirm"><span className="clinical-confirm-icon"><Icon name="file" /></span>
        <h3>Bạn muốn rời bệnh án?</h3><p>Các thay đổi chưa được lưu sẽ bị bỏ.</p></div>
    </Modal>}
  </div>
}

function FoldHeader({ id, label, icon, open, toggle }: {
  id: string
  label: string
  icon: ReactNode
  open: boolean
  toggle: (key: string) => void
}) {
  return <div className="clinical-card-title clinical-fold-title"><h2><button type="button" className="clinical-fold-toggle"
    aria-expanded={open} aria-controls={`clinical-fold-${id}`} onClick={() => toggle(id)}>
    <span className="clinical-heading-icon">{icon}</span><span>{label}</span><span className="clinical-fold-chevron"><Icon name="chevron" /></span>
  </button></h2></div>
}
