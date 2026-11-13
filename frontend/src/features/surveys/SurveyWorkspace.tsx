import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createRecords, deleteRecords, getForms, getRecord, getRecords, surveyError, updateRecord } from './api'
import { Dashboard } from './Dashboard'
import { ExcelDialog } from './ExcelDialog'
import { PhotoDialog } from './PhotoDialog'
import { Editor, RecordDetail, SourceDialog, type DetailTab } from './RecordDialogs'
import { SurveyList } from './SurveyList'
import { Icon, Modal } from './ui'
import { exportWorkbook } from './workbook'
import { APP_NAME, GROUP, GROUPS, hasAnswer, isSkipped, persistSamples, readSamples, SHORT,
  type Group, type ImportAction, type Survey, type SurveyForm } from './model'
import styles from './workspace.css?url'

type Page = { group?: Group; form?: string }
type Dialog =
  | { type: 'group' }
  | { type: 'pick'; group: Group; action: ImportAction }
  | { type: 'manual'; form: SurveyForm; record?: Survey }
  | { type: 'excel' | 'ocr' | 'analysis'; form: SurveyForm }
  | { type: 'view'; form: SurveyForm; record: Survey; tab: DetailTab }
  | { type: 'delete'; rows: Survey[] }

const RECORDS_KEY = ['survey-records'] as const
const SIDEBAR_KEY = 'ta-sidebar-collapsed'

function readPage(): Page {
  const [group, form] = location.hash.slice(1).split('/')
  return group === 'youth' || group === 'military' ? { group, form } : {}
}

function Analysis({ form, rows, close }: { form: SurveyForm; rows: Survey[]; close: () => void }) {
  const [questionId, setQuestionId] = useState(form.questions[0].id)
  const question = form.questions.find(item => item.id === questionId)!
  const completed = rows.filter(row => row.form === form.id && row.status === 'complete')
  const valid = completed.filter(row => hasAnswer(row.answers[questionId]) && !isSkipped(form, row.answers, question))
  const counts = new Map<string, number>()
  for (const row of valid) {
    const answer = row.answers[questionId]
    for (const value of new Set(Array.isArray(answer) ? answer : [answer])) counts.set(value, (counts.get(value) || 0) + 1)
  }
  const entries = question.options.length ? question.options.map(option => [option, counts.get(option) || 0] as const)
    : [...counts].sort((first, second) => second[1] - first[1]).slice(0, 20)
  return <Modal title="Phân tích câu trả lời" close={close} footer={<button className="right" onClick={close}>Đóng</button>}>
    <p className="sub">{GROUP[form.group]} · {form.title} · Chỉ dùng phiếu đã hoàn tất.</p>
    <select className="analysis-select" aria-label="Chọn câu hỏi phân tích" value={questionId} onChange={event => setQuestionId(event.target.value)}>
      {form.questions.map(item => <option key={item.id} value={item.id}>{item.id} · {item.label}</option>)}
    </select>
    <div className="notice">{valid.length}/{completed.length} phiếu đã hoàn tất có trả lời câu này.</div>
    {valid.length ? <table><thead><tr><th>ĐÁP ÁN / GIÁ TRỊ</th><th>SỐ PHIẾU</th><th>TỶ LỆ</th></tr></thead>
      <tbody>{entries.map(([value, count], index) => <tr key={index}><td title={value}>{value}</td><td>{count}</td>
        <td>{(count / valid.length * 100).toFixed(1)}%</td></tr>)}</tbody></table>
      : <div className="empty"><strong>Chưa có câu trả lời để phân tích</strong></div>}
    <p className="scoring-note">{question.multi ? 'Câu nhiều lựa chọn: tổng tỷ lệ có thể vượt 100%.' : 'Tỷ lệ tính trên các phiếu có câu trả lời hợp lệ.'} Không chuyển các thống kê này thành kết luận bệnh.</p>
  </Modal>
}

export function SurveyWorkspace() {
  const forms = useQuery({ queryKey: ['survey-forms'], queryFn: getForms, staleTime: Infinity })
  const records = useQuery({ queryKey: RECORDS_KEY, queryFn: getRecords })
  return <>
    <link rel="stylesheet" href={styles} />
    {forms.data ? <Workspace forms={forms.data} records={records.data || []} recordError={records.error} reconnect={records.refetch} />
      : <main>
        {forms.error ? <div className="sync-warning">{surveyError(forms.error)} <button className="smallbtn" onClick={() => forms.refetch()}>Kết nối lại</button></div>
          : <p role="status">Đang tải biểu mẫu khảo sát…</p>}
      </main>}
  </>
}

function Workspace({ forms, records, recordError, reconnect }: {
  forms: SurveyForm[]
  records: Survey[]
  recordError: Error | null
  reconnect: () => Promise<unknown>
}) {
  const client = useQueryClient()
  const [page, setPage] = useState(readPage)
  const [samples, setSamples] = useState(() => readSamples(forms))
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) !== 'false')
  const [expanded, setExpanded] = useState({ youth: true, military: true })
  const [dialog, setDialog] = useState<Dialog>()
  const [source, setSource] = useState<SurveyForm>()
  const [toast, setToast] = useState('')
  const toastTimer = useRef<number>()
  const [busy, setBusy] = useState(false)
  const running = useRef(false)
  const detailRequest = useRef(0)
  const [pageSize, setPageSize] = useState(15)
  const [sort, setSort] = useState<Parameters<typeof SurveyList>[0]['sort']>({ key: 'fullName', direction: 1 })
  const [listVersion, setListVersion] = useState(0)
  const activeForm = forms.find(form => form.group === page.group && form.id === page.form)?.id
  const rows = [...records, ...samples]

  useEffect(() => {
    function onHash() {
      setPage(readPage())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHash)
    return () => {
      window.removeEventListener('hashchange', onHash)
      window.clearTimeout(toastTimer.current)
    }
  }, [])
  useEffect(() => {
    document.body.classList.toggle('sidebar-collapsed', collapsed)
    return () => document.body.classList.remove('sidebar-collapsed')
  }, [collapsed])
  useEffect(() => {
    document.title = `${APP_NAME} · ${page.group ? GROUP[page.group] : 'Dashboard'}`
    return () => { document.title = APP_NAME }
  }, [page.group])

  function notify(message: string) {
    setToast(message)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(''), 4800)
  }
  function navigate(group?: Group, form?: string) {
    if (group) setExpanded(previous => ({ ...previous, [group]: true }))
    if (page.group === group && activeForm === form) setListVersion(version => version + 1)
    setPage({ group, form })
    location.hash = group ? group + (form ? '/' + form : '') : 'dashboard'
    window.scrollTo(0, 0)
  }
  function toggleSidebar() {
    localStorage.setItem(SIDEBAR_KEY, String(!collapsed))
    setCollapsed(!collapsed)
  }
  function close() {
    if (running.current) {
      notify('Đang xử lý dữ liệu, vui lòng chờ hoàn tất.')
      return
    }
    detailRequest.current++
    setDialog(undefined)
  }
  function changeSamples(next: Survey[]) {
    persistSamples(next)
    setSamples(next)
  }
  async function reload() {
    await client.invalidateQueries({ queryKey: RECORDS_KEY })
  }
  async function perform(action: () => Promise<void>, message: string, reset = false) {
    if (running.current) return
    running.current = true
    setBusy(true)
    try {
      await action()
      setDialog(undefined)
      if (reset) setListVersion(version => version + 1)
      notify(message)
    } catch (error) {
      notify(surveyError(error))
    } finally {
      running.current = false
      setBusy(false)
    }
  }
  async function loadDetail(row: Survey, editing: boolean, tab: DetailTab = 'survey') {
    const request = ++detailRequest.current
    const form = forms.find(form => form.id === row.form)!
    try {
      const record = !row.sample && row.hasOCR ? await getRecord(row.id) : row
      if (request === detailRequest.current) {
        setDialog(editing ? { type: 'manual', form, record } : { type: 'view', form, record, tab })
      }
    } catch (error) {
      if (request === detailRequest.current) notify(surveyError(error))
    }
  }
  async function exportRows(selected: Survey[]) {
    if (!selected.length) return
    try {
      await exportWorkbook(selected, forms)
      notify(`Đã xuất ${selected.length} phiếu được chọn.`)
    } catch (error) { notify(surveyError(error)) }
  }
  function saveManual(record: Survey, editing: boolean) {
    void perform(async () => {
      if (record.sample) {
        changeSamples(samples.map(row => row.id === record.id ? record
          : row.group === record.group && row.person === record.person ? { ...row, patient: record.patient } : row))
      } else {
        if (editing) await updateRecord(record)
        else await createRecords([record])
        await reload()
      }
    }, 'Đã lưu thông tin đối tượng và phiếu khảo sát.')
  }
  function remove(selected: Survey[]) {
    void perform(async () => {
      const real = selected.filter(row => !row.sample).map(row => row.id)
      const sample = new Set(selected.filter(row => row.sample).map(row => row.id))
      if (real.length) {
        await deleteRecords(real)
        client.setQueryData<Survey[]>(RECORDS_KEY, previous => previous?.filter(row => !real.includes(row.id)))
      }
      if (sample.size) changeSamples(samples.filter(row => !sample.has(row.id)))
      if (real.length) await reload()
    }, `Đã xóa ${selected.length} phiếu khảo sát.`)
  }
  const pickerTitle = {
    manual: 'Chọn kiểu biểu mẫu khảo sát', excel: 'Chọn mẫu phiếu để tải Excel', ocr: 'Chọn mẫu phiếu để trích xuất từ ảnh',
  }

  return <>
    <aside className="sidebar">
      <div className="sidebar-brand-row">
        <a className="brand" href="#dashboard" onClick={event => { event.preventDefault(); navigate() }}>
          <img className="brandmark" src="/surveys/hospital-103.png" alt="Logo Bệnh viện Quân y 103" />
          <div className="brand-copy">Bệnh viện Quân y 103</div>
        </a>
        <button className="sidebar-toggle" aria-expanded={!collapsed} title={collapsed ? 'Mở rộng menu' : 'Thu gọn menu'}
          aria-label={collapsed ? 'Mở rộng menu' : 'Thu gọn menu'} onClick={toggleSidebar}><Icon name="menu" /></button>
      </div>
      <nav id="nav" aria-label="Điều hướng chính">
        <button className={`parent ${page.group ? '' : 'active'}`} title="Dashboard" aria-label="Dashboard" onClick={() => navigate()}>
          <span className="ni"><Icon name="dashboard" /></span><span className="nav-text">Dashboard</span>
        </button>
        {GROUPS.map(group => {
          const label = GROUP[group].toLowerCase()
          return <div className="nav-group" key={group}>
            <div className={`nav-parent-row ${page.group === group ? 'current-group' : ''}`}>
              <button className={`parent ${page.group === group && !activeForm ? 'active' : ''}`} title={`Dữ liệu đối tượng ${label}`}
                aria-label={`Dữ liệu đối tượng ${label}`} onClick={() => navigate(group)}>
                <span className="ni"><Icon name={group === 'youth' ? 'users' : 'shield'} /></span>
                <span className="nav-text">Dữ liệu đối tượng<br />{label}</span>
              </button>
              <button className={`submenu-toggle ${expanded[group] ? 'is-open' : ''}`} aria-label={`${expanded[group] ? 'Đóng' : 'Mở'} submenu ${label}`}
                aria-expanded={expanded[group]} aria-controls={`submenu-${group}`} onClick={() => setExpanded({ ...expanded, [group]: !expanded[group] })}><Icon name="chevron" /></button>
            </div>
            <div className="submenu" id={`submenu-${group}`} hidden={!expanded[group]}>
              {forms.filter(form => form.group === group).map(form => <button key={form.id} title={form.title}
                className={activeForm === form.id ? 'active' : ''} onClick={() => navigate(group, form.id)}>
                <span className="subdot" /><span>{SHORT[form.id]}</span>
              </button>)}
            </div>
          </div>
        })}
      </nav>
    </aside>
    <div className="shell">
      <header><div className="header-heading"><strong className="system-name">{APP_NAME}</strong></div></header>
      <main id="main">
        {recordError && <div className="sync-warning">{surveyError(recordError)} <button className="smallbtn" onClick={() => reconnect()}>Kết nối lại</button></div>}
        {page.group ? <SurveyList key={`${page.group}/${activeForm || 'all'}/${listVersion}`}
          rows={rows} forms={forms} group={page.group} form={activeForm} pageSize={pageSize} setPageSize={setPageSize} sort={sort} setSort={setSort}
          openImport={action => setDialog({ type: 'pick', group: page.group!, action })}
          view={row => void loadDetail(row, false)} edit={row => void loadDetail(row, true)}
          remove={rows => setDialog({ type: 'delete', rows })} exportRows={exportRows} />
          : <Dashboard rows={rows} forms={forms} navigate={navigate} add={() => setDialog({ type: 'group' })}
            exportAll={() => void exportRows(rows)} analyze={id => {
              const form = forms.find(form => form.id === id)
              if (form) setDialog({ type: 'analysis', form })
            }} />}
      </main>
    </div>
    {dialog?.type === 'group' && <Modal title="Chọn nhóm đối tượng" size="slim" close={close}>
      <div className="formpick">{GROUPS.map(group => <button key={group} onClick={() => {
        navigate(group)
        setDialog({ type: 'pick', group, action: 'manual' })
      }}><span className="pick-icon"><Icon name={group === 'youth' ? 'users' : 'shield'} /></span>
        <span>{GROUP[group]}<span className="pick-meta">{forms.filter(form => form.group === group).length} biểu mẫu khảo sát</span></span>
        <span className="arrow"><Icon name="chevron" /></span></button>)}</div>
    </Modal>}
    {dialog?.type === 'pick' && <Modal title={pickerTitle[dialog.action]} size="slim" close={close}>
      <p className="sub" style={{ marginBottom: 18 }}>Đối tượng {GROUP[dialog.group].toLowerCase()} · Chọn biểu mẫu tương ứng với dữ liệu cần nhập.</p>
      <div className="formpick">{forms.filter(form => form.group === dialog.group).map(form =>
        <button key={form.id} onClick={() => setDialog({ type: dialog.action, form })}>
          <span className="pick-icon"><Icon name="file" /></span><span>{form.title}
            <span className="pick-meta">{form.id} · {form.code} · {form.questions.length} mục nhập liệu</span></span>
          <span className="arrow"><Icon name="chevron" /></span>
        </button>)}</div>
    </Modal>}
    {dialog?.type === 'manual' && <Editor key={dialog.record?.id || dialog.form.id} form={dialog.form} original={dialog.record}
      records={records} busy={busy} close={close} save={saveManual} showSource={() => setSource(dialog.form)} notify={notify} />}
    {dialog?.type === 'excel' && <ExcelDialog form={dialog.form} records={records} busy={busy} close={close} notify={notify}
      save={selected => void perform(async () => {
        await createRecords(selected)
        await reload()
      }, `Đã nhập ${selected.length} phiếu khảo sát.`, true)} />}
    {dialog?.type === 'ocr' && <PhotoDialog form={dialog.form} records={records} close={close} notify={notify} save={async row => {
      await createRecords([row])
      await reload()
    }} open={row => {
      const saved = client.getQueryData<Survey[]>(RECORDS_KEY)?.find(record => record.id === row.id)
      void loadDetail(saved || { ...row, hasOCR: true }, false, 'ocr')
    }} />}
    {dialog?.type === 'view' && <RecordDetail key={dialog.record.id} record={dialog.record} form={dialog.form} forms={forms}
      related={rows.filter(row => row.group === dialog.record.group && row.person === dialog.record.person
        && Boolean(row.sample) === Boolean(dialog.record.sample))}
      initialTab={dialog.tab} close={close} showSource={() => setSource(dialog.form)}
      edit={() => setDialog({ type: 'manual', form: dialog.form, record: dialog.record })}
      view={row => void loadDetail(row, false)} exportRecord={() => void exportRows([dialog.record])} />}
    {dialog?.type === 'analysis' && <Analysis form={dialog.form} rows={rows} close={close} />}
    {dialog?.type === 'delete' && <Modal title={dialog.rows.length > 1 ? 'Xóa hàng loạt phiếu khảo sát' : 'Xóa phiếu khảo sát'}
      size="slim" close={close} footer={<>
        <button className="right" onClick={close}>Hủy</button>
        <button className="primary" style={{ background: '#a16c58', borderColor: '#a16c58' }} disabled={busy}
          onClick={() => remove(dialog.rows)}>Xác nhận xóa {dialog.rows.length} phiếu</button>
      </>}>
      <p style={{ color: '#5e7867' }}>Bạn đang chọn xóa <b>{dialog.rows.length} phiếu khảo sát</b>.</p>
      <div className="notice amber">Chỉ xóa các phiếu đã chọn. Các phiếu khác của cùng đối tượng vẫn được giữ lại.</div>
      <div className="hint">{dialog.rows.slice(0, 8).map(row => row.id).join(' · ')}{dialog.rows.length > 8 ? ' · …' : ''}</div>
    </Modal>}
    {source && <SourceDialog form={source} close={() => setSource(undefined)} />}
    <div id="toast" role="status" className={toast ? 'show' : ''}>{toast}</div>
  </>
}
