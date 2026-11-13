import { useEffect, useRef, useState } from 'react'
import { surveyError } from './api'
import { GROUP, type Survey, type SurveyForm } from './model'
import { Badge, Icon, Modal } from './ui'
import { downloadTemplate, readWorkbook, type ImportRow } from './workbook'

export function ExcelDialog({ form, records, busy, close, save, notify }: {
  form: SurveyForm
  records: Survey[]
  busy: boolean
  close: () => void
  save: (rows: Survey[]) => void
  notify: (message: string) => void
}) {
  const [rows, setRows] = useState<ImportRow[]>([])
  const [reading, setReading] = useState(false)
  const [error, setError] = useState('')
  const generation = useRef(0)
  useEffect(() => () => { generation.current++ }, [])
  const good = rows.filter(row => !row.errors.length)

  async function read(file?: File) {
    const current = ++generation.current
    setRows([])
    setError('')
    setReading(Boolean(file))
    if (!file) return
    try {
      const result = await readWorkbook(file, form, records)
      if (generation.current === current) setRows(result)
    } catch (error) {
      if (generation.current === current) setError(surveyError(error))
    } finally {
      if (generation.current === current) setReading(false)
    }
  }
  async function template() {
    try {
      await downloadTemplate(form)
      notify('Đã tải mẫu Excel và từ điển câu hỏi.')
    } catch (error) { notify(surveyError(error)) }
  }
  return <Modal title="Tải dữ liệu Excel" close={close} footer={<>
    <p>Kiểm tra mã trùng, ngày sinh, ngày khảo sát và đáp án trước khi lưu.</p>
    <button className="right" onClick={close}>Đóng</button>
    <button className="primary" disabled={!good.length || busy || reading} onClick={() => save(good.map(row => row.record))}>
      {busy ? 'Đang lưu vào cơ sở dữ liệu…' : rows.length ? `Nhập ${good.length} hàng hợp lệ` : 'Nhập dữ liệu hợp lệ'}
    </button>
  </>}>
    <div className="modal-toolbar"><span className={`pill ${form.group === 'youth' ? 'blue' : ''}`}>{GROUP[form.group]}</span>
      <p>{form.title}</p><button className="smallbtn right" onClick={template}><Icon name="download" /><span>Tải mẫu Excel</span></button></div>
    <div className="flow">{['Chọn tệp', 'Kiểm tra dữ liệu', 'Xác nhận nhập'].map((step, index) =>
      <div className={`step ${index === (busy ? 2 : rows.length || reading || error ? 1 : 0) ? 'active' : ''}`} key={step}><span>{index + 1}</span>{step}</div>)}</div>
    <div className="dropzone modal-drop"><div className="upload-icon"><Icon name="excel" /></div>
      <h3>Chọn tệp dữ liệu khảo sát</h3><p className="sub">.xlsx, .xls, .csv · Tối đa 10 MB · Dùng mẫu Excel của {form.id}</p>
      <input aria-label="Chọn tệp Excel" type="file" accept=".xlsx,.xls,.csv" disabled={busy} onChange={event => {
        void read(event.target.files?.[0])
        event.target.value = ''
      }} /></div>
    {reading && <p className="sub">Đang đọc và kiểm tra dữ liệu…</p>}
    {error && <div className="notice amber">{error}</div>}
    {rows.length > 0 && <>
      <div className="upload-summary"><strong>{good.length} / {rows.length} hàng hợp lệ</strong> · {rows.length - good.length} hàng lỗi. Chỉ các hàng hợp lệ được nhập.</div>
      <div className="import-result"><table><thead><tr><th>HÀNG</th><th>HỌ VÀ TÊN / MÃ PHIẾU</th><th>KẾT QUẢ</th></tr></thead>
        <tbody>{rows.slice(0, 100).map(row => <tr key={row.row}>
          <td title={String(row.row)}>{row.row}</td>
          <td title={`${row.record.patient.fullName || 'Chưa có họ tên'} ${row.record.id}`}>
            {row.record.patient.fullName || 'Chưa có họ tên'}<div className="patient-code">{row.record.id}</div></td>
          <td title={(row.errors.length ? row.errors : row.warnings).join('; ')}>{row.errors.length
            ? <span style={{ color: '#a26c56' }}>{row.errors.join('; ')}</span>
            : <><Badge status={row.record.status} />{row.warnings.length > 0 && <div className="hint">{row.warnings.join('; ')}</div>}</>}</td>
        </tr>)}</tbody></table></div>
      {rows.length > 100 && <p className="hint">Hiển thị 100 hàng đầu. Đã kiểm tra toàn bộ tệp.</p>}
    </>}
  </Modal>
}
