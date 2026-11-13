import { useEffect, useMemo, useRef, useState } from 'react'
import { birthLabel, GROUP, initials, SHORT, STATUS, type Group, type ImportAction, type Survey, type SurveyForm } from './model'
import { Badge, Icon, Title } from './ui'

const columns = [
  ['fullName', 'HỌ VÀ TÊN', 'Tìm họ và tên'], ['birthDate', 'NGÀY SINH', 'YYYY-MM hoặc năm'],
  ['hometown', 'QUÊ QUÁN', 'Tìm quê quán'], ['conclusion', 'KẾT LUẬN VỀ BỆNH', 'Tìm kết luận'],
  ['form', 'LOẠI PHIẾU KHẢO SÁT', ''],
] as const
const initialFilters = { search: '', fullName: '', birthDate: '', hometown: '', conclusion: '', form: 'all', status: 'all', unit: 'all' }
type SortKey = typeof columns[number][0] | 'status'
type Sort = { key: SortKey; direction: number }
const collator = new Intl.Collator('vi', { numeric: true, sensitivity: 'base' })
const lower = (text: string) => text.toLocaleLowerCase('vi')

export function SurveyList({ rows, forms, group, form, openImport, view, edit, remove, exportRows, pageSize, setPageSize, sort, setSort }: {
  rows: Survey[]
  forms: SurveyForm[]
  group: Group
  form?: string
  openImport: (action: ImportAction) => void
  view: (row: Survey) => void
  edit: (row: Survey) => void
  remove: (rows: Survey[]) => void
  exportRows: (rows: Survey[]) => void
  pageSize: number
  setPageSize: (size: number) => void
  sort: Sort
  setSort: (sort: Sort) => void
}) {
  const [filters, setFilters] = useState(initialFilters)
  const [selected, setSelected] = useState(new Set<string>())
  const [page, setPage] = useState(1)
  const checkAll = useRef<HTMLInputElement>(null)
  const formsById = useMemo(() => new Map(forms.map(form => [form.id, form])), [forms])
  const scoped = useMemo(() => rows.filter(row => row.group === group && (!form || row.form === form)), [rows, group, form])
  const units = [...new Set(scoped.map(row => row.unit))].sort()
  const titleOf = (row: Survey) => formsById.get(row.form)?.title || row.form
  const valueOf = (row: Survey, key: SortKey) => {
    switch (key) {
      case 'form': return titleOf(row)
      case 'birthDate': return row.patient.birthDate || row.patient.birthYear
      case 'fullName':
      case 'hometown': return row.patient[key]
      default: return row[key]
    }
  }
  const filtered = scoped.filter(row => {
    const { patient } = row
    const searchable = [
      patient.fullName, patient.birthDate, patient.birthYear, patient.hometown, row.conclusion,
      row.person, row.id, titleOf(row), row.unit,
    ].join(' ')
    return lower(searchable).includes(lower(filters.search))
      && columns.slice(0, 4).every(([key]) => lower(valueOf(row, key)).includes(lower(filters[key])))
      && (filters.form === 'all' || row.form === filters.form)
      && (filters.status === 'all' || row.status === filters.status)
      && (filters.unit === 'all' || row.unit === filters.unit)
  }).sort((first, second) =>
    sort.direction * collator.compare(valueOf(first, sort.key), valueOf(second, sort.key)) || first.id.localeCompare(second.id),
  )
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const current = Math.min(page, pages)
  const visible = filtered.slice((current - 1) * pageSize, current * pageSize)
  const selectedRows = rows.filter(row => selected.has(row.id))
  const visibleSelected = visible.filter(row => selected.has(row.id)).length
  const allSelected = visible.length > 0 && visibleSelected === visible.length
  const indeterminate = visibleSelected > 0 && !allSelected
  useEffect(() => {
    if (checkAll.current) checkAll.current.indeterminate = indeterminate
  }, [indeterminate])
  useEffect(() => {
    setPage(previous => Math.min(previous, pages))
  }, [pages])

  function filter(key: keyof typeof filters, value: string) {
    setFilters(previous => ({ ...previous, [key]: value }))
    setSelected(new Set())
    setPage(1)
  }
  function toggle(ids: string[], checked: boolean) {
    setSelected(previous => {
      const next = new Set(previous)
      ids.forEach(id => checked ? next.add(id) : next.delete(id))
      return next
    })
  }
  function sortBy(key: SortKey) {
    setSort({ key, direction: sort.key === key ? -sort.direction : 1 })
    setPage(1)
  }
  function sortIcon(key: SortKey) {
    return sort.key === key ? sort.direction === 1 ? '↑' : '↓' : '↕'
  }
  return <>
    <Title actions={<>
      <button onClick={() => openImport('excel')}><Icon name="excel" /><span>Tải dữ liệu Excel</span></button>
      <button onClick={() => openImport('ocr')}><Icon name="image" /><span>Tải file khảo sát</span></button>
      <button className="primary" onClick={() => openImport('manual')}><Icon name="plus" /><span>Nhập dữ liệu</span></button>
    </>}>Dữ liệu đối tượng {GROUP[group].toLowerCase()}</Title>
    <div className="mini-stats">
      <span><b>{scoped.length}</b>phiếu khảo sát</span>
      <span><b>{new Set(scoped.map(row => row.person)).size}</b>đối tượng</span>
      <span><b>{scoped.filter(row => row.status === 'complete').length}</b>đã hoàn tất</span>
      <span><b>{scoped.filter(row => row.status !== 'complete').length}</b>cần đối soát / bổ sung</span>
    </div>
    <div className="data-count"><h2>{form ? SHORT[form] : 'Danh sách khảo sát'}</h2>
      <span className="count-badge">{filtered.length} phiếu</span><span className="searchstat">{form ? 1 : forms.filter(item => item.group === group).length} loại biểu mẫu</span>
    </div>
    <section className="panel list-panel">
      <div className="list-controls">
        <div className="searchbox"><span><Icon name="search" /></span><input aria-label="Tìm kiếm khảo sát"
          value={filters.search} placeholder="Tìm họ tên, mã đối tượng, quê quán, kết luận..." onChange={event => filter('search', event.target.value)} /></div>
        <select aria-label="Lọc đơn vị" value={filters.unit} onChange={event => filter('unit', event.target.value)}>
          <option value="all">Tất cả đơn vị / địa bàn</option>
          {units.map(unit => <option key={unit} value={unit}>{unit || 'Chưa có đơn vị'}</option>)}
        </select>
        <select aria-label="Lọc trạng thái" value={filters.status} onChange={event => filter('status', event.target.value)}>
          <option value="all">Tất cả trạng thái</option>
          {(['complete', 'review', 'draft'] as const).map(status => <option key={status} value={status}>{STATUS[status]}</option>)}
        </select>
        <button className="smallbtn" onClick={() => { setFilters(initialFilters); setSelected(new Set()); setPage(1) }}>Đặt lại bộ lọc</button>
      </div>
      <div className="bulkbar"><strong>{selectedRows.length} đã chọn</strong><div className="bulk-actions">
        <button disabled={!selectedRows.length} onClick={() => exportRows(selectedRows)}><Icon name="download" /><span>Xuất dữ liệu</span></button>
        <button className="dangerbtn" disabled={!selectedRows.length} onClick={() => remove(selectedRows)}><Icon name="trash" /><span>Xóa đã chọn</span></button>
      </div></div>
      <div className="tablewrap"><table className="survey-table">
        <colgroup>{[48, 240, 160, 190, 280, 280, 180, 180].map((width, index) => <col key={index} style={{ width }} />)}</colgroup>
        <thead><tr>
          <th className="checkcol"><input ref={checkAll} type="checkbox" aria-label="Chọn tất cả dòng trên trang" checked={allSelected}
            onChange={event => toggle(visible.map(row => row.id), event.target.checked)} /></th>
          {columns.map(([key, label, placeholder]) => <th key={key}>
            <button onClick={() => sortBy(key)} aria-label={`Sắp xếp ${label.toLowerCase()}`}>{label}<span>{sortIcon(key)}</span></button>
            {key === 'form' ? <select aria-label="Lọc loại phiếu" value={filters.form} onChange={event => filter('form', event.target.value)}>
              <option value="all">Tất cả loại phiếu</option>
              {forms.filter(item => item.group === group && (!form || item.id === form))
                .map(item => <option key={item.id} value={item.id}>{SHORT[item.id]}</option>)}
            </select> : <input aria-label={placeholder} placeholder={placeholder} value={filters[key]} onChange={event => filter(key, event.target.value)} />}
          </th>)}
          <th style={{ minWidth: 112 }}><button onClick={() => sortBy('status')}>TRẠNG THÁI <span>{sortIcon('status')}</span></button></th>
          <th className="actions-col"><span className="actions-heading">THAO TÁC</span></th>
        </tr></thead>
        <tbody>{visible.length ? visible.map(row => <tr key={row.id} className={selected.has(row.id) ? 'selected-row' : undefined}>
          <td className="checkcol"><input aria-label={`Chọn phiếu ${row.id}`} type="checkbox" checked={selected.has(row.id)}
            onChange={event => toggle([row.id], event.target.checked)} /></td>
          <td><div className="namecell"><span className="personavatar">{initials(row.patient.fullName)}</span><div>
            <div className="patient-name" title={row.patient.fullName}>{row.patient.fullName || 'Chưa có họ tên'}</div>
            <div className="patient-code">{row.person}{row.sample && <span className="sample-tag">Mẫu</span>}</div>
          </div></div></td>
          <td className="dobcell">{birthLabel(row.patient)}</td>
          <td className="hometowncell" title={row.patient.hometown}>{row.patient.hometown || '—'}</td>
          <td className="conclusioncell">{row.conclusion ? <span className="conclusion-text" title={row.conclusion}>{row.conclusion}</span>
            : <span className="conclusion-empty">Chưa có kết luận</span>}</td>
          <td><div className="formname" title={titleOf(row)}>{titleOf(row)}</div><div className="patient-code">{row.form} · {row.source}</div></td>
          <td><Badge status={row.status} /></td>
          <td className="actions-col"><div className="row-actions">
            <button title="View · Xem phiếu" aria-label={`View ${row.id}`} onClick={() => view(row)}><Icon name="eye" /></button>
            <button title="Edit · Sửa thông tin" aria-label={`Edit ${row.id}`} onClick={() => edit(row)}><Icon name="edit" /></button>
            <button className="delete" title="Delete · Xóa phiếu" aria-label={`Delete ${row.id}`} onClick={() => remove([row])}><Icon name="trash" /></button>
          </div></td>
        </tr>) : <tr><td colSpan={8}><div className="empty"><div className="empty-icon"><Icon name="file" /></div>
          <strong>Không có phiếu khảo sát phù hợp</strong>
          {scoped.length ? 'Thử thay đổi từ khóa hoặc đặt lại bộ lọc.' : 'Nhập dữ liệu thủ công, tải Excel hoặc tải ảnh khảo sát để bắt đầu.'}
        </div></td></tr>}</tbody>
      </table></div>
      <div className="pagination"><span>Hiển thị {filtered.length ? (current - 1) * pageSize + 1 : 0}–{Math.min(current * pageSize, filtered.length)} / {filtered.length} phiếu</span>
        <div className="pagination-right"><span>Số dòng</span><select aria-label="Số dòng trên trang" value={pageSize}
          onChange={event => { setPageSize(Number(event.target.value)); setPage(1) }}>
          {[15, 30, 50, 100].map(size => <option key={size}>{size}</option>)}
        </select>
        <button aria-label="Trang trước" disabled={current === 1} onClick={() => setPage(current - 1)}>‹</button>
        <span>{current} / {pages}</span>
        <button aria-label="Trang sau" disabled={current === pages} onClick={() => setPage(current + 1)}>›</button></div>
      </div>
    </section>
  </>
}
