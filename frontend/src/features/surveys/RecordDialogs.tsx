import { useRef, useState } from 'react'
import {
  answerText, birthLabel, emptySubject, formatDate, GROUP, hasAnswer, initials, isSkipped,
  keepsSkippedAnswer, newId, prepareAnswers, progress, resolvePerson, STATUS, subjectErrors, subjectFields, today,
  validateAnswers,
  type Answers, type Status, type Survey, type SurveyForm,
} from './model'
import { Badge, Icon, Modal } from './ui'

const fieldLabels = {
  person: 'Mã đối tượng *', fullName: 'Họ và tên', birthDate: 'Ngày sinh',
  birthYear: 'Năm sinh (nếu chưa có ngày sinh)', hometown: 'Quê quán',
  unit: 'Đơn vị / địa bàn', id: 'Mã phiếu *', date: 'Ngày khảo sát *',
}

export function Editor({ form, original, records, busy, save, close, showSource, viewOriginal, notify }: {
  form: SurveyForm
  original?: Survey
  records: Survey[]
  busy: boolean
  save: (record: Survey, editing: boolean) => void
  close: () => void
  showSource: () => void
  viewOriginal: (record: Survey) => void
  notify: (message: string) => void
}) {
  const [person, setPerson] = useState(original?.person || '')
  const [patient, setPatient] = useState(original?.patient || emptySubject)
  const [id] = useState(original?.id || newId('P'))
  const [status, setStatus] = useState<Status>(original?.status || 'draft')
  const [answers, setAnswers] = useState<Answers>(original?.answers || {})
  const editor = useRef<HTMLFormElement>(null)
  const counts = progress(form, answers)

  const knownPersons = () => [...new Set(records.filter(record => record.group === form.group).map(record => record.person))]
  function fillKnownPatient() {
    if (original || !person.trim()) return
    const code = resolvePerson(person, knownPersons())
    setPerson(code)
    const existing = records.find(record => record.group === form.group && record.person === code)
    if (existing) {
      setPatient(existing.patient)
      notify('Đã điền thông tin hồ sơ có cùng mã đối tượng.')
    }
  }
  function submit(targetStatus: Status) {
    if (busy || !editor.current?.reportValidity()) return
    const data = new FormData(editor.current)
    const field = (name: string) => String(data.get(name) || '').trim()
    const recordId = field('id')
    const code = original ? original.person : resolvePerson(person, knownPersons())
    if (!code || !recordId) {
      notify('Mã đối tượng và mã phiếu không được để trống.')
      return
    }
    if (!original && records.some(row => row.id === recordId)) {
      notify('Mã phiếu đã tồn tại.')
      return
    }
    const subject = { ...patient, fullName: patient.fullName.trim(), hometown: patient.hometown.trim() }
    const prepared = prepareAnswers(form, answers, subject)
    const errors = [...subjectErrors(subject), ...validateAnswers(form, prepared)]
    const completion = progress(form, prepared)
    if (targetStatus === 'complete' && completion.count < completion.total) {
      errors.push(`Còn ${completion.total - completion.count} mục thiếu. Hãy bổ sung hoặc lưu bản nháp.`)
    }
    if (errors.length) {
      notify(errors[0])
      return
    }
    save({
      ...original, id: recordId, person: code, patient: subject, group: form.group, form: form.id,
      unit: field('unit'), date: field('date'), source: original?.source || 'Thủ công', status: targetStatus,
      conclusion: field('conclusion'), note: field('note'), answers: prepared,
    }, Boolean(original))
  }

  return <Modal title={original ? 'Chỉnh sửa thông tin đối tượng & phiếu' : 'Nhập phiếu khảo sát'} size="wide" close={close}
    footer={<>
      <p id="editor-progress">Đã trả lời {counts.count} / {counts.total} mục áp dụng</p>
      <button type="button" className="right" onClick={close}>Hủy</button>
      <button type="button" disabled={busy} onClick={() => submit('draft')}>Lưu bản nháp</button>
      <button type="button" className="primary" disabled={busy} onClick={() => submit(status)}><Icon name="check" /><span>Lưu thông tin</span></button>
    </>}>
    <div className="modal-toolbar">
      <span className={`pill ${form.group === 'youth' ? 'blue' : ''}`}>{GROUP[form.group]}</span>
      <span className="sub">{form.id} · {form.code}</span>
      {original?.hasOriginal && <button type="button" className="smallbtn right" onClick={() => viewOriginal(original)}>
        <Icon name="file" /><span>Xem phiếu gốc</span></button>}
      <button type="button" className={`smallbtn ${original?.hasOriginal ? '' : 'right'}`} onClick={showSource}>Xem mẫu phiếu trống</button>
    </div>
    <form ref={editor} className="survey-editor" onSubmit={event => { event.preventDefault(); submit('complete') }}>
      <div className="editor-section">Thông tin đối tượng <span>Dùng chung cho các phiếu cùng mã</span></div>
      <div className="fieldgrid">
        <div className="field"><label htmlFor="ed-person">{fieldLabels.person}</label>
          <input id="ed-person" name="person" required readOnly={Boolean(original)} maxLength={120}
            placeholder={`VD: ${form.group === 'youth' ? 'PT.CK.001' : 'QK1.01'}`} value={person}
            onBlur={fillKnownPatient} onChange={event => setPerson(event.target.value)} /></div>
        {subjectFields.map(key => <div className="field" key={key}><label htmlFor={`ed-${key}`}>{fieldLabels[key]}</label>
          <input id={`ed-${key}`} name={key} value={patient[key]} onChange={event => setPatient({ ...patient, [key]: event.target.value })}
            type={key === 'birthDate' ? 'date' : key === 'birthYear' ? 'number' : 'text'}
            min={key === 'birthYear' ? '1900' : undefined} max={key === 'birthYear' ? today().slice(0, 4) : key === 'birthDate' ? today() : undefined}
            maxLength={255} /></div>)}
        <div className="field"><label htmlFor="ed-unit">{fieldLabels.unit}</label>
          <input id="ed-unit" name="unit" maxLength={255} defaultValue={original?.unit} /></div>
      </div>
      <div className="editor-section">Thông tin phiếu khảo sát</div>
      <div className="fieldgrid">
        <div className="field"><label htmlFor="ed-recordId">{fieldLabels.id}</label>
          <input id="ed-recordId" name="id" defaultValue={id} required maxLength={120} readOnly={Boolean(original)} /></div>
        <div className="field"><label htmlFor="ed-date">{fieldLabels.date}</label>
          <input id="ed-date" name="date" type="date" required defaultValue={original?.date || today()} /></div>
        <div className="field"><label htmlFor="ed-status">Trạng thái</label>
          <select id="ed-status" name="status" value={status} onChange={event => setStatus(event.target.value as Status)}>
            {Object.entries(STATUS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></div>
        <div className="field full"><label htmlFor="ed-conclusion">Kết luận về bệnh / nhận xét chuyên môn</label>
          <textarea id="ed-conclusion" name="conclusion" maxLength={20000} defaultValue={original?.conclusion}
            placeholder="Nhập kết luận đã được cán bộ chuyên môn ghi nhận; để trống nếu chưa có." /></div>
      </div>
      <div className="editor-section">Nội dung phiếu <span>{form.title}</span></div>
      {form.id === 'F01' && <div className="notice">Áp dụng chuyển câu theo Câu 5, 7a, 8, 16. Câu 20a–20d luôn phải trả lời. Thông tin định danh được giữ ở hồ sơ riêng.</div>}
      {form.id === 'F09' && <div className="notice">Phần D: nếu D0 = Không thì D1–D4 không bắt buộc; câu trả lời đã đánh vẫn được giữ. Phiếu giấy in nhầm câu D0 thành “D1”.</div>}
      <div className="questions-panel">{form.questions.map(question => {
        const { id: key, label, options, multi } = question
        const value = answers[key]
        const skipped = isSkipped(answers, question)
        const optional = skipped && keepsSkippedAnswer(question)
        const disabled = skipped && !optional
        return <div className={`question ${disabled ? 'is-skipped' : optional ? 'is-optional' : ''}`} key={key}>
          <div className="qtitle"><span className="qindex">{key}</span>{label}</div>
          {options.length ? <div className="choices">{options.map((option, index) => {
            const values = Array.isArray(value) ? value : []
            return <label className="choice" key={index}><input name={key} type={multi ? 'checkbox' : 'radio'} value={option}
              disabled={disabled} checked={multi ? values.includes(option) : value === option}
              onChange={event => setAnswers(previous => ({
                ...previous, [key]: multi ? event.target.checked ? [...values, option] : values.filter(item => item !== option) : option,
              }))} />{option}</label>
          })}</div> : <textarea name={key} aria-label={label} disabled={disabled} maxLength={20000}
            placeholder="Nhập câu trả lời theo phiếu gốc..." value={answerText(value) || ''}
            onChange={event => setAnswers({ ...answers, [key]: event.target.value })} />}
          {skipped && <div className="skip-note hint">{optional ? 'Không bắt buộc theo chỉ dẫn chuyển câu; câu trả lời đã đánh vẫn được giữ.'
            : 'Không áp dụng theo chỉ dẫn chuyển câu.'}</div>}
        </div>
      })}</div>
      <div className="field spaced"><label htmlFor="ed-note">Ghi chú đối soát</label>
        <textarea id="ed-note" name="note" maxLength={20000} defaultValue={original?.note} placeholder="Các thông tin còn thiếu hoặc cần kiểm tra..." /></div>
      {original?.ocr && <details className="notice"><summary>Xem kết quả trích xuất OCR</summary><OCRContent record={original} /></details>}
    </form>
  </Modal>
}

export type DetailTab = 'survey' | 'related' | 'ocr'

function OCRContent({ record }: { record: Survey }) {
  return <p className="source-text">{record.ocr}</p>
}

export function RecordDetail({ record, form, related, forms, initialTab, close, showSource, viewOriginal, edit, view, exportRecord }: {
  record: Survey
  form: SurveyForm
  related: Survey[]
  forms: SurveyForm[]
  initialTab: DetailTab
  close: () => void
  showSource: () => void
  viewOriginal: (record: Survey) => void
  edit: () => void
  view: (row: Survey) => void
  exportRecord: () => void
}) {
  const [tab, setTab] = useState(initialTab)
  const { patient } = record
  const fields = [
    ['Ngày sinh', birthLabel(patient)], ['Quê quán', patient.hometown || '—'],
    ['Ngày khảo sát', formatDate(record.date)], ['Loại phiếu', form.title], ['Mã phiếu', record.id], ['Nguồn nhập', record.source],
  ]
  const tabs: [DetailTab, string][] = [['survey', 'Nội dung phiếu'], ['related', `Các phiếu cùng đối tượng (${related.length})`]]
  if (record.ocr) tabs.push(['ocr', 'Dữ liệu OCR'])
  return <Modal title="Thông tin phiếu khảo sát" size="wide" close={close} footer={<>
    <button onClick={showSource}>Xem mẫu phiếu trống</button>
    {record.hasOriginal && <button onClick={() => viewOriginal(record)}><Icon name="file" /><span>Xem phiếu gốc</span></button>}
    <button className="right" onClick={exportRecord}><Icon name="download" /><span>Xuất dữ liệu</span></button>
    <button className="primary" onClick={edit}><Icon name="edit" /><span>Chỉnh sửa thông tin</span></button>
  </>}>
    <div className="profile-banner"><span className="personavatar">{initials(patient.fullName)}</span><div>
      <h3>{patient.fullName || 'Chưa có họ tên'}</h3><div className="profiletags">
        <span>{record.person}</span><span>{GROUP[record.group]}</span><span>{record.unit || 'Chưa có đơn vị'}</span></div>
    </div><span style={{ marginLeft: 'auto' }}><Badge status={record.status} /></span></div>
    <div className="view-grid" aria-label="Thông tin đối tượng và phiếu">{fields.map(([label, value]) =>
      <div className="view-item" key={label}><label>{label}</label><strong>{value}</strong></div>)}</div>
    <div className="notice"><b>Kết luận về bệnh:</b> {record.conclusion || 'Chưa có kết luận chuyên môn.'}</div>
    <div className="detail-tabs">{tabs.map(([value, label]) => <button key={value} className={tab === value ? 'active' : ''}
      onClick={() => setTab(value)}>{label}</button>)}</div>
    {tab === 'survey' && <>
      <div className="tablewrap"><table className="viewtable"><thead><tr><th>CÂU HỎI</th><th>CÂU TRẢ LỜI</th></tr></thead>
        <tbody>{form.questions.map(question => {
          const answer = record.answers[question.id]
          const skipped = isSkipped(record.answers, question)
          const display = !hasAnswer(answer) ? skipped ? 'Không áp dụng theo chuyển câu' : 'Chưa trả lời' : undefined
          return <tr key={question.id}><td title={question.label}><span className="qindex">{question.id}</span>{question.label}</td>
            <td title={display || answerText(answer)}>{display ? <span className="answer-empty">{display}</span>
              : <>{answerText(answer)}{skipped && <span className="answer-empty"> (không bắt buộc)</span>}</>}</td></tr>
        })}</tbody></table></div>
      <div className="notice"><b>Ghi chú:</b> {record.note || 'Chưa có ghi chú.'}</div>
    </>}
    {tab === 'related' && <div className="tablewrap"><table><thead><tr>
      <th>MÃ PHIẾU</th><th>LOẠI PHIẾU</th><th>NGÀY</th><th>TRẠNG THÁI</th><th></th></tr></thead>
      <tbody>{related.map(row => <tr key={row.id}><td className="code">{row.id}</td>
        <td>{forms.find(item => item.id === row.form)?.title}</td><td>{formatDate(row.date)}</td>
        <td><Badge status={row.status} /></td><td><button className="rowlink" onClick={() => {
          setTab('survey')
          if (row.id !== record.id) view(row)
        }}>Xem phiếu</button></td></tr>)}</tbody></table></div>}
    {tab === 'ocr' && <OCRContent record={record} />}
  </Modal>
}

export function SourceDialog({ form, close }: { form: SurveyForm; close: () => void }) {
  return <Modal title={form.title} close={close} overlay>
    <a href={form.source} download className="primary smallbtn source-download">
      <Icon name="download" /><span>Tải Word gốc</span>
    </a>
    <p className="hint spaced">Bản xem nội dung trích xuất. Tệp Word giữ đầy đủ định dạng và hướng dẫn chuyển câu.</p>
    {form.blocks.map((block, index) => 'text' in block ? <p className="source-text" key={index}>{block.text}</p>
      : <div className="tablewrap" key={index}><table className="source-table"><tbody>{block.rows.map((row, rowIndex) =>
        <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex} title={cell}>{cell}</td>)}</tr>)}</tbody></table></div>)}
  </Modal>
}
