import { formatDate, GROUP, GROUPS, nf, SHORT, STATUS, today, type Group, type Survey, type SurveyForm } from './model'
import { Icon, Title, type Icons } from './ui'

const STATUS_COLORS = { complete: '#3ba6a3', review: '#e7ad55', draft: '#c6d2df' }
const statusOrder = ['complete', 'review', 'draft'] as const

function Chart({ rows }: { rows: Survey[] }) {
  const end = rows.reduce((latest, row) => row.date > latest ? row.date : latest, '') || today()
  const dates = Array.from({ length: 8 }, (_, index) => {
    const date = new Date(`${end}T00:00:00Z`)
    date.setUTCDate(date.getUTCDate() - 7 + index)
    return date.toISOString().slice(0, 10)
  })
  const counts = dates.map(date => GROUPS.map(group => rows.filter(row => row.date === date && row.group === group).length))
  const highest = Math.max(0, ...counts.flat())
  const step = Math.max(1, Math.ceil(highest / 4))
  const base = 235
  const plotHeight = 196
  const slot = (760 - 40 - 12) / dates.length
  const barWidth = Math.min(24, slot * 0.26)
  return <svg className="dash-chart" viewBox="0 0 760 280" role="img" aria-label="Số phiếu khảo sát theo ngày, thanh niên và quân nhân">
    <title>Phiếu khảo sát theo ngày</title>
    {Array.from({ length: 5 }, (_, index) => {
      const y = base - index * plotHeight / 4
      return <g key={index}>
        <line x1={40} x2={748} y1={y} y2={y} stroke="#e7edf2" strokeDasharray={index ? '4 5' : '0'} />
        <text x={26} y={y + 4} textAnchor="end" className="chart-tick">{nf(step * index)}</text>
      </g>
    })}
    {dates.map((date, index) => {
      const x = 40 + slot * (index + 0.5)
      return <g key={date}>
        {counts[index].map((count, groupIndex) => {
          const height = count / (step * 4) * plotHeight
          return <rect key={groupIndex} x={x + (groupIndex ? 3 : -barWidth - 3)} y={base - height}
            width={barWidth} height={height} rx={5} fill={groupIndex ? '#254c70' : '#3ba6a3'}>
            <title>{GROUP[GROUPS[groupIndex]]} · {formatDate(date)}: {count} phiếu</title>
          </rect>
        })}
        <text x={x} y={265} textAnchor="middle" className="chart-tick">{date.slice(8)}/{date.slice(5, 7)}</text>
      </g>
    })}
    {!highest && <text x="400" y="129" textAnchor="middle" className="chart-empty">Chưa có dữ liệu khảo sát</text>}
  </svg>
}

export function Dashboard({ rows, forms, navigate, add, exportAll, analyze }: {
  rows: Survey[]
  forms: SurveyForm[]
  navigate: (group: Group, form?: string) => void
  add: () => void
  exportAll: () => void
  analyze: (form: string) => void
}) {
  const total = rows.length
  const people = new Set(rows.map(row => JSON.stringify([row.group, row.person]))).size
  const statusCounts = Object.fromEntries(statusOrder.map(status => [status, rows.filter(row => row.status === status).length]))
  const done = statusCounts.complete
  const completion = total ? Math.round(done / total * 100) : 0
  const formCounts = forms.map(form => ({ form, count: rows.filter(row => row.form === form.id).length }))
  const maxForm = Math.max(1, ...formCounts.map(({ count }) => count))
  const stats: [string, number, keyof typeof Icons, string][] = [
    ['Tổng phiếu khảo sát', total, 'file', 'navy'], ['Đối tượng tham gia', people, 'users', 'blue'],
    ['Đã hoàn tất', done, 'check', 'teal'], ['Cần đối soát', total - done, 'search', 'amber'],
  ]
  const percent = (count: number) => `${total ? count / total * 100 : 0}%`
  return <div className="dash-workspace">
    <Title actions={<>
      <button onClick={exportAll}><Icon name="download" /><span>Xuất dữ liệu</span></button>
      <button className="primary" onClick={add}><Icon name="plus" /><span>Nhập dữ liệu</span></button>
    </>}>Dashboard</Title>
    <section className="dash-kpis" aria-label="Chỉ số tổng quan">
      {stats.map(([label, value, icon, tone]) => <article key={label} className={`dash-kpi ${tone}`}>
        <div className="dash-kpi-label">{label}<span><Icon name={icon} /></span></div>
        <strong>{nf(value)}</strong><div className="dash-kpi-rule" />
      </article>)}
    </section>
    <div className="dash-top-grid">
      <section className="dash-card dash-collection">
        <div className="dash-card-heading"><h2>Phiếu khảo sát theo ngày</h2>
          <div className="dash-chart-legend"><span><i className="teal" />Thanh niên</span><span><i className="navy" />Quân nhân</span></div>
        </div>
        <div className="dash-plot"><Chart rows={rows} /></div>
      </section>
      <section className="dash-card dash-populations">
        <div className="dash-card-heading"><h2>Nhóm đối tượng</h2></div>
        <div className="dash-population-list">
          {GROUPS.map(group => {
            const groupRows = rows.filter(row => row.group === group)
            const persons = new Set(groupRows.map(row => row.person)).size
            return <button key={group} className={`dash-population ${group}`} onClick={() => navigate(group)}
              aria-label={`Mở dữ liệu ${GROUP[group].toLowerCase()}`}>
              <div className="dash-population-top"><span className="dash-population-icon"><Icon name={group === 'youth' ? 'users' : 'shield'} /></span>
                <h3>{GROUP[group]}</h3><span className="dash-open">Xem dữ liệu</span>
              </div>
              <div className="dash-population-numbers">
                <strong>{nf(groupRows.length)}<span>phiếu khảo sát</span></strong><div><b>{nf(persons)}</b> đối tượng</div>
              </div>
              <div className="dash-population-track"><span style={{ width: percent(groupRows.length) }} /></div>
            </button>
          })}
        </div>
      </section>
    </div>
    <div className="dash-bottom-grid">
      <section className="dash-card dash-form-card">
        <div className="dash-card-heading"><h2>Phân bố theo loại phiếu</h2><span className="dash-total-tag">{forms.length} biểu mẫu</span></div>
        <div className="dash-form-list">
          {formCounts.map(({ form, count }) => <button key={form.id} className={`dash-form-row ${form.group}`}
            onClick={() => navigate(form.group, form.id)} aria-label={`Xem ${form.title}`}>
            <span className="dash-form-code">{form.id}</span><span className="dash-form-label" title={form.title}>{SHORT[form.id]}</span>
            <span className="dash-form-bar"><span style={{ width: `${count / maxForm * 100}%` }} /></span><b>{nf(count)}</b>
          </button>)}
        </div>
      </section>
      <div className="dash-side-stack">
        <section className="dash-card dash-progress-card">
          <div className="dash-card-heading"><h2>Tiến độ xử lý</h2></div>
          <div className="dash-completion"><strong>{completion}<span>%</span></strong><span>đã hoàn tất</span></div>
          <div className="dash-status-meter" role="img" aria-label={`${done} đã hoàn tất, ${statusCounts.review} chờ đối soát, ${statusCounts.draft} bản nháp`}>
            {statusOrder.map(status => <span key={status} title={STATUS[status]} style={{ width: percent(statusCounts[status]), background: STATUS_COLORS[status] }} />)}
          </div>
          <div className="dash-status-list">
            {statusOrder.map(status => <div key={status}><span><i style={{ background: STATUS_COLORS[status] }} />{STATUS[status]}</span><b>{nf(statusCounts[status])}</b></div>)}
          </div>
        </section>
        <form className="dash-analysis" onSubmit={event => {
          event.preventDefault()
          analyze(String(new FormData(event.currentTarget).get('form')))
        }}>
          <span className="dash-analysis-icon"><Icon name="search" /></span><h2>Phân tích câu trả lời</h2>
          <select id="dash-form" name="form" aria-label="Chọn biểu mẫu phân tích">
            {forms.map(form => <option key={form.id} value={form.id}>{GROUP[form.group]} · {form.title}</option>)}
          </select>
          <button>Mở phân tích</button>
        </form>
      </div>
    </div>
  </div>
}
