import { useEffect, useRef, useState } from 'react'
import { get, post, put, upload } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Loading, Modal, Notice, Page, Tabs, useLoad, useToast } from '../ui.jsx'
import { SHIFT, SHIFTS, daysOfMonth, dm, isWeekend, todayIso, weekday } from '../fmt.js'
import Swaps from './Swaps.jsx'

/* ---------- Thời khóa biểu ---------- */
function CellModal({ cell, employees, onClose, onSaved, month }) {
  const toast = useToast()
  const [ids, setIds] = useState(cell.ids)
  const toggle = id => setIds(x => x.includes(id) ? x.filter(i => i !== id) : [...x, id])
  const save = async () => {
    try { const r = await put(`/schedules/${month}/cell`, { work_date: cell.date, shift_code: cell.shift, employee_ids: ids }); if (r.warning) toast(r.warning, 'bad'); else toast('Đã lưu'); onSaved() }
    catch (e) { toast(e.message, 'bad') }
  }
  return (
    <Modal title={`${weekday(cell.date)} ${dm(cell.date)} · Ca ${SHIFT[cell.shift]}`} onClose={onClose}>
      <div className="stack">
        <div className="stack-sm">{employees.map(e => (
          <label key={e.id} className="row card flat tight" style={{ cursor: 'pointer' }}>
            <input type="checkbox" checked={ids.includes(e.id)} onChange={() => toggle(e.id)} style={{ width: 20, height: 20 }} /><span>{e.display_name}</span>
          </label>
        ))}</div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Btn kind="ghost" onClick={() => setIds([])}>Bỏ trống ca</Btn><Btn onClick={onClose}>Hủy</Btn><Btn kind="primary" onClick={save}>Lưu</Btn></div>
      </div>
    </Modal>
  )
}

function View({ month }) {
  const { me, meta } = useApp()
  const toast = useToast()
  const owner = me.role === 'owner'
  const s = useLoad(() => get('/schedules/' + month), [month])
  const [cell, setCell] = useState(null)
  const today = todayIso()
  const by = {}
  ;(s.data?.assignments || []).forEach(a => { (by[a.work_date + a.shift_code] ||= []).push(a) })
  const act = (fn, msg) => async () => { try { const r = await fn(); toast(typeof msg === 'function' ? msg(r) : msg); s.reload() } catch (e) { toast(e.message, 'bad') } }
  const published = s.data?.status === 'published'
  return (
    <div className="stack">
      <div className="row spread">
        <div className="row">{s.data && <Badge kind={published ? 'ok' : 'warn'}>{published ? 'Đã công bố' : 'Bản nháp'}</Badge>}</div>
        {owner && s.data && <div className="row">
          {meta.flags.E13_AUTO_DRAFT && <Btn onClick={act(() => post(`/schedules/${month}/auto-draft`), r => `Đã xếp ${r.assigned} ca, còn ${r.unassigned.length} ô trống`)}>Gợi ý lịch nháp</Btn>}
          {published ? <Btn onClick={act(() => post(`/schedules/${month}/unpublish`), 'Đã chuyển về bản nháp')}>Hủy công bố</Btn>
            : <Btn kind="primary" onClick={act(() => post(`/schedules/${month}/publish`), 'Đã công bố lịch cho nhân viên')}>Công bố lịch</Btn>}
        </div>}
      </div>
      {owner && s.data && !published && <Notice kind="info">Bản nháp chỉ chủ quán thấy. Bấm vào ô để chọn người, xếp xong bấm “Công bố lịch”.</Notice>}
      {s.loading && !s.data ? <Loading /> : s.error ? <ErrorBox message={s.error} onRetry={s.reload} /> :
        !owner && !published ? <Card><Empty title="Lịch tháng này chưa công bố">Chủ quán sẽ công bố sau khi xếp xong.</Empty></Card> : (
          <div className="table-wrap"><table className="t sched">
            <thead><tr><th>Ngày</th>{SHIFTS.map(k => <th key={k}>Ca {SHIFT[k]}</th>)}</tr></thead>
            <tbody>{daysOfMonth(month).map(d => (
              <tr key={d} className={(d === today ? 'today ' : '') + (isWeekend(d) ? 'wk' : '')}>
                <td><b>{weekday(d)}</b> {dm(d)}</td>
                {SHIFTS.map(k => {
                  const list = by[d + k] || []
                  if (owner) return <td key={k}><button className={'cellbtn ' + (list.length ? 'filled' : '')} onClick={() => setCell({ date: d, shift: k, ids: list.map(a => a.employee_id) })}>
                    {list.length ? list.map(a => a.employee_name).join(', ') : '+'}{list.some(a => a.source === 'auto_draft') && <span className="muted small"> ·nháp</span>}</button></td>
                  return <td key={k}><span className="cell">{list.length ? list.map(a => <span key={a.id} className={'pill ' + (a.employee_id === me.employee_id ? 'mine' : '')}>{a.employee_name}</span>) : <span className="muted">—</span>}</span></td>
                })}
              </tr>
            ))}</tbody></table></div>
        )}
      {cell && <CellModal cell={cell} month={month} employees={s.data.employees} onClose={() => setCell(null)} onSaved={() => { setCell(null); s.reload() }} />}
    </div>
  )
}

/* ---------- Lịch rảnh ---------- */
function Availability({ month }) {
  const { me } = useApp()
  const toast = useToast()
  const owner = me.role === 'owner'
  const emps = useLoad(() => owner ? get('/employees') : Promise.resolve([]), [])
  const [emp, setEmp] = useState('')
  useEffect(() => { if (owner && emps.data?.length && !emp) setEmp(String(emps.data[0].id)) }, [emps.data, owner, emp])
  const q = useLoad(() => (owner && !emp) ? Promise.resolve(null) : get(`/availability?month=${month}${owner ? '&employee_id=' + emp : ''}`), [month, emp])
  const [state, setState] = useState({})
  useEffect(() => { const m = {}; (q.data?.items || []).forEach(i => { m[i.work_date + i.shift_code] = i.available }); setState(m) }, [q.data])
  const toggle = (d, k) => setState(x => ({ ...x, [d + k]: !x[d + k] }))
  const setAll = v => { const m = {}; daysOfMonth(month).forEach(d => SHIFTS.forEach(k => { m[d + k] = v })); setState(m) }
  const save = async () => {
    const items = daysOfMonth(month).flatMap(d => SHIFTS.map(k => ({ work_date: d, shift_code: k, available: Boolean(state[d + k]) })))
    try { await put('/availability', { month, items, employee_id: owner ? Number(emp) : null }); toast('Đã lưu lịch rảnh'); q.reload() } catch (e) { toast(e.message, 'bad') }
  }
  const locked = q.data?.locked && !owner
  return (
    <div className="stack">
      {owner && emps.data && (
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <select className="select" style={{ width: 'auto' }} value={emp} onChange={e => setEmp(e.target.value)} aria-label="Nhân viên">
            {emps.data.map(e => <option key={e.id} value={e.id}>{e.display_name}</option>)}
          </select>
        </div>
      )}
      {!owner && !me.employee_id && <Notice kind="warn">Tài khoản chưa gắn với nhân viên. Nhờ chủ quán liên kết ở Cài đặt.</Notice>}
      <Notice kind="info">Tick vào ca bạn <b>có thể làm</b>. Ca không tick được hiểu là bận. Chủ quán dựa vào đây để xếp lịch.</Notice>
      {locked && <Notice kind="warn">Lịch tháng này đã công bố nên không khai báo thêm được.</Notice>}
      {q.loading && !q.data ? <Loading /> : q.error ? <ErrorBox message={q.error} onRetry={q.reload} /> : (
        <>
          <div className="row no-print"><Btn size="sm" onClick={() => setAll(true)} disabled={locked}>Chọn tất cả</Btn><Btn size="sm" onClick={() => setAll(false)} disabled={locked}>Bỏ chọn tất cả</Btn></div>
          <div className="table-wrap"><table className="t sched"><thead><tr><th>Ngày</th>{SHIFTS.map(k => <th key={k}>Ca {SHIFT[k]}</th>)}</tr></thead>
            <tbody>{daysOfMonth(month).map(d => (
              <tr key={d} className={isWeekend(d) ? 'wk' : ''}><td><b>{weekday(d)}</b> {dm(d)}</td>
                {SHIFTS.map(k => <td key={k}><input type="checkbox" style={{ width: 22, height: 22 }} aria-label={`${dm(d)} ca ${SHIFT[k]}`} checked={Boolean(state[d + k])} disabled={locked} onChange={() => toggle(d, k)} /></td>)}</tr>
            ))}</tbody></table></div>
          <div><Btn kind="primary" onClick={save} disabled={locked || (!owner && !me.employee_id)}>Lưu lịch rảnh</Btn></div>
        </>
      )}
    </div>
  )
}

/* ---------- Nạp file lịch ca (F06-B) ---------- */
function ImportTab({ month }) {
  const toast = useToast()
  const file = useRef()
  const [pending, setPending] = useState(null)
  const [map, setMap] = useState({})
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const send = async (f, mapping) => {
    setBusy(true); setResult(null)
    try {
      const r = await upload(`/schedules/${month}/import`, f, mapping ? { mapping: JSON.stringify(mapping) } : {})
      if (r.needs_mapping) {
        setPending({ file: f, unmapped: r.unmapped, employees: r.employees })
        setMap(Object.fromEntries(r.unmapped.map(u => [u.name, u.suggestions[0] ? String(u.suggestions[0]) : ''])))
      } else { setPending(null); setResult(r); toast(`Đã nạp ${r.imported} ca`) }
    } catch (e) { toast(e.message, 'bad') } finally { setBusy(false) }
  }
  const ready = pending && pending.unmapped.every(u => map[u.name])
  return (
    <div className="stack">
      <div className="grid2">
        <Card title="Định dạng 1 · Lưới của quán">
          <p className="muted" style={{ marginTop: 0 }}>Cột <b>Ngày</b> (hoặc <b>Thứ</b>) rồi 3 cột <b>Ca Sáng</b>, <b>Ca Trưa</b>, <b>Ca Tối</b>. Mỗi ô là tên nhân viên.</p>
          <div className="table-wrap"><table className="t small"><thead><tr><th>Ngày</th><th>Ca Sáng</th><th>Ca Trưa</th><th>Ca Tối</th></tr></thead><tbody><tr><td>02/11/2026</td><td>Lan</td><td>Minh</td><td>Lan</td></tr></tbody></table></div>
          <div style={{ marginTop: 12 }}><a className="btn" href={`/api/schedules/template.xlsx?kind=grid&month=${month}`} download>⬇ Tải file mẫu .xlsx</a></div>
        </Card>
        <Card title="Định dạng 2 · Danh sách phẳng">
          <p className="muted" style={{ marginTop: 0 }}>Mỗi dòng một phân công: <b>Ngày</b> (YYYY-MM-DD hoặc DD/MM/YYYY), <b>Mã ca</b> (Sáng/Trưa/Tối), <b>Tên nhân viên</b>.</p>
          <div className="table-wrap"><table className="t small"><thead><tr><th>Ngày</th><th>Mã ca</th><th>Tên nhân viên</th></tr></thead><tbody><tr><td>2026-11-02</td><td>Sáng</td><td>Lan</td></tr></tbody></table></div>
          <div style={{ marginTop: 12 }}><a className="btn" href={`/api/schedules/template.xlsx?kind=flat&month=${month}`} download>⬇ Tải file mẫu .xlsx</a></div>
        </Card>
      </div>
      <Card title="Nạp lịch ca">
        <p className="muted" style={{ marginTop: 0 }}>Nạp lại cùng tháng sẽ thay các ca đã nạp từ file trước đó, không nhân đôi; ca bạn xếp tay hoặc đã duyệt đổi ca được giữ nguyên. Tên không khớp danh sách nhân viên sẽ được hỏi ghép tay.</p>
        <input ref={file} type="file" accept=".xlsx,.xlsm,.csv" hidden onChange={e => { const f = e.target.files[0]; e.target.value = ''; if (f) send(f) }} />
        <Btn kind="primary" busy={busy} onClick={() => file.current.click()}>Chọn file .xlsx / .csv…</Btn>
      </Card>
      {pending && <Card title="Ghép tên chưa khớp">
        <Notice kind="warn">Có tên trong file không trùng nhân viên nào. Chọn người tương ứng; hệ thống không tự đoán.</Notice>
        <div className="stack-sm" style={{ marginTop: 12 }}>{pending.unmapped.map(u => (
          <div key={u.name} className="row"><b style={{ minWidth: 140 }}>“{u.name}”</b>
            <select className="select" style={{ maxWidth: 260 }} value={map[u.name] || ''} onChange={e => setMap({ ...map, [u.name]: e.target.value })}>
              <option value="">— chọn nhân viên —</option>{pending.employees.map(e => <option key={e.id} value={e.id}>{e.display_name}</option>)}</select>
            {u.suggestions.length > 0 && <span className="muted small">gợi ý theo chữ gần giống</span>}</div>
        ))}</div>
        <div className="row" style={{ marginTop: 12 }}><Btn onClick={() => setPending(null)}>Hủy</Btn><Btn kind="primary" disabled={!ready} busy={busy} onClick={() => send(pending.file, map)}>Nạp lịch</Btn></div>
      </Card>}
      {result && <Notice kind={result.errors.length || result.over_capacity.length ? 'warn' : 'ok'}><div>
        <b>Đã nạp {result.imported} ca</b> (bố cục {result.layout === 'grid' ? 'lưới' : 'phẳng'}){result.skipped_other_month ? ` · bỏ ${result.skipped_other_month} dòng ngoài tháng này` : ''}
        {result.errors.map((e, i) => <div key={i}>• Dòng {e.row}: {e.reason}</div>)}
        {result.over_capacity.map((o, i) => <div key={i}>• {dm(o.date)} ca {SHIFT[o.shift]}: vượt sức chứa ca</div>)}
      </div></Notice>}
    </div>
  )
}

export default function Schedule() {
  const { me, currentMonth: month } = useApp()
  const [tab, setTab] = useState('view')
  const items = [
    ['view', 'Thời khóa biểu'],
    ['avail', 'Đăng ký rảnh/bận'],
    ['swaps', 'Đổi ca'],
    ...(me.role === 'owner' ? [['import', 'Nạp file']] : [])
  ]
  return (
    <Page title="Lịch ca làm việc" sub="Thời khóa biểu ca làm, khai báo lịch rảnh/bận, duyệt đổi ca và nạp lịch từ file Excel.">
      <Tabs value={tab} onChange={setTab} items={items} />
      {tab === 'view' && <View month={month} />}
      {tab === 'avail' && <Availability month={month} />}
      {tab === 'swaps' && <Swaps />}
      {tab === 'import' && <ImportTab month={month} />}
    </Page>
  )
}