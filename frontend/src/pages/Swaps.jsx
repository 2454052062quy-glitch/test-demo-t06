import { useState } from 'react'
import { get, post } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Loading, Modal, Notice, Page, Tabs, useLoad, useToast } from '../ui.jsx'
import { SHIFT, dateTime, dm, shiftMonth, thisMonth, todayIso, weekday } from '../fmt.js'

const ST = { pending: ['warn', 'Chờ duyệt'], approved: ['ok', 'Đã duyệt'], rejected: ['bad', 'Từ chối'], cancelled: ['', 'Đã hủy'] }
const KIND = { full_swap: 'Đổi nguyên ca', partial_cover: 'Nhờ phụ giữa ca / vắng nửa ca' }

const SHIFT_WINDOWS = {
  sang: { start: '06:30', end: '12:00', defFrom: '09:00', defTo: '11:00' },
  trua: { start: '12:00', end: '17:30', defFrom: '13:30', defTo: '15:00' },
  toi: { start: '17:30', end: '21:30', defFrom: '18:30', defTo: '20:00' },
}

function NewRequest({ onClose, onSaved }) {
  const { me } = useApp()
  const toast = useToast()
  const m1 = thisMonth(), m2 = shiftMonth(m1, 1)
  const s1 = useLoad(() => get('/schedules/' + m1), [])
  const s2 = useLoad(() => get('/schedules/' + m2), [])
  const emps = useLoad(() => get('/employees'), [])
  const [f, setF] = useState({ kind: 'full_swap', shift: '', to: '', counter: '', from_time: '', to_time: '', reason: '' })
  const [busy, setBusy] = useState(false)
  const all = [...(s1.data?.assignments || []), ...(s2.data?.assignments || [])]
  const today = todayIso()

  // Khung giờ của các ca (lấy từ cấu hình ca nếu có, dự phòng SHIFT_WINDOWS)
  const shiftTypes = s1.data?.shift_types || []
  const getWindow = code => {
    const st = shiftTypes.find(x => x.code === code)
    const fallback = SHIFT_WINDOWS[code] || { start: '06:30', end: '21:30', defFrom: '09:00', defTo: '11:00' }
    return {
      start: st?.start_time || fallback.start,
      end: st?.end_time || fallback.end,
      defFrom: fallback.defFrom,
      defTo: fallback.defTo,
    }
  }

  // Đổi nguyên ca: chỉ chọn từ hôm nay trở đi; Nhờ phụ / vắng giữa ca: không cho chọn tương lai (<= hôm nay)
  const mine = all.filter(a => a.employee_id === me.employee_id && (f.kind === 'full_swap' ? a.work_date >= today : a.work_date <= today))
  const theirs = all.filter(a => String(a.employee_id) === f.to && a.work_date >= today)
  const selectedShiftCode = f.shift ? f.shift.split('|')[1] : ''
  const curWin = selectedShiftCode ? getWindow(selectedShiftCode) : null

  const set = k => e => setF({ ...f, [k]: e.target.value })
  const onShiftChange = e => {
    const val = e.target.value
    const code = val ? val.split('|')[1] : ''
    const win = code ? getWindow(code) : null
    if (f.kind === 'partial_cover' && win) {
      setF({ ...f, shift: val, from_time: win.defFrom, to_time: win.defTo })
    } else {
      setF({ ...f, shift: val })
    }
  }

  const send = async () => {
    const [work_date, shift_code] = f.shift.split('|')
    if (f.kind === 'partial_cover') {
      if (work_date > today) {
        toast('Khai báo nhờ phụ / vắng giữa ca không được chọn ngày trong tương lai', 'bad')
        return
      }
      const win = getWindow(shift_code)
      const ft = f.from_time || win.defFrom
      const tt = f.to_time || win.defTo
      if (ft >= tt) {
        toast('Giờ bắt đầu phải trước giờ kết thúc', 'bad')
        return
      }
      if (ft < win.start || tt > win.end) {
        toast(`Khung giờ (${ft}–${tt}) không hợp lệ! Ca ${SHIFT[shift_code]} chỉ nằm trong khung giờ ${win.start}–${win.end}.`, 'bad')
        return
      }
    } else if (work_date < today) {
      toast('Chỉ đổi được ca từ hôm nay trở đi', 'bad')
      return
    }
    const body = { kind: f.kind, work_date, shift_code, to_employee_id: Number(f.to), reason: f.reason }
    if (f.kind === 'full_swap' && f.counter) { const [cd, cs] = f.counter.split('|'); body.counter_date = cd; body.counter_shift = cs }
    if (f.kind === 'partial_cover') {
      const win = getWindow(shift_code)
      body.from_time = f.from_time || win.defFrom
      body.to_time = f.to_time || win.defTo
    }
    setBusy(true)
    try { await post('/swap-requests', body); toast('Đã gửi yêu cầu cho chủ quán'); onSaved() } catch (e) { toast(e.message, 'bad') } finally { setBusy(false) }
  }
  const loading = s1.loading || s2.loading || emps.loading
  return (
    <Modal title="Tạo yêu cầu" onClose={onClose}>
      {loading ? <Loading /> : (
        <div className="stack">
          <div className="grid2">{Object.entries(KIND).map(([k, label]) => (
            <label key={k} className="card flat tight row" style={{ cursor: 'pointer', borderColor: f.kind === k ? 'var(--primary)' : undefined, background: f.kind === k ? 'var(--primary-soft)' : undefined }}>
              <input type="radio" name="kind" checked={f.kind === k} onChange={() => setF({ ...f, kind: k, shift: '', counter: '', from_time: '', to_time: '' })} /><b>{label}</b></label>
          ))}</div>
          {f.kind === 'partial_cover'
            ? <Notice kind="info">Khi chủ quán duyệt, <b>lịch ca và lương không đổi</b>. Chỉ áp dụng cho các ca từ hôm nay trở về trước (không chọn tương lai) và khung giờ phải nằm trong ca đã chọn.</Notice>
            : <Notice kind="info">Khi chủ quán duyệt, lịch ca và lương của hai bạn đổi ngay (áp dụng cho các ca từ hôm nay trở đi).</Notice>}
          <Field label={f.kind === 'full_swap' ? 'Ca của bạn muốn đổi (Từ hôm nay trở đi)' : 'Ca bạn bị vắng / cần người phụ (Không chọn tương lai)'}>
            <select className="select" value={f.shift} onChange={onShiftChange}><option value="">— chọn ca —</option>
              {mine.map(a => {
                const w = getWindow(a.shift_code)
                return <option key={a.id} value={a.work_date + '|' + a.shift_code}>{weekday(a.work_date)} {dm(a.work_date)} · Ca {SHIFT[a.shift_code]} ({w.start}–{w.end})</option>
              })}</select></Field>
          <Field label={f.kind === 'full_swap' ? 'Người nhận ca' : 'Người làm phụ'}>
            <select className="select" value={f.to} onChange={e => setF({ ...f, to: e.target.value, counter: '' })}><option value="">— chọn nhân viên —</option>
              {(emps.data || []).filter(e => e.is_active && e.id !== me.employee_id).map(e => <option key={e.id} value={e.id}>{e.display_name}</option>)}</select></Field>
          {f.kind === 'full_swap' && f.to && <Field label="Đổi lấy ca của họ (tùy chọn)" hint="Bỏ trống nếu chỉ nhường ca">
            <select className="select" value={f.counter} onChange={set('counter')}><option value="">Không, chỉ nhường ca</option>
              {theirs.map(a => <option key={a.id} value={a.work_date + '|' + a.shift_code}>{weekday(a.work_date)} {dm(a.work_date)} · Ca {SHIFT[a.shift_code]}</option>)}</select></Field>}
          {f.kind === 'partial_cover' && (
            <div className="stack-sm">
              <div className="grid2">
                <Field label={`Từ giờ ${curWin ? `(Trong ca: ${curWin.start}–${curWin.end})` : ''}`}>
                  <input className="input" type="time" min={curWin?.start} max={curWin?.end} value={f.from_time} onChange={set('from_time')} />
                </Field>
                <Field label={`Đến giờ ${curWin ? `(Trong ca: ${curWin.start}–${curWin.end})` : ''}`}>
                  <input className="input" type="time" min={curWin?.start} max={curWin?.end} value={f.to_time} onChange={set('to_time')} />
                </Field>
              </div>
              {curWin && (
                <span className="hint">
                  Khung giờ của <b>Ca {SHIFT[selectedShiftCode]}</b> là <b>{curWin.start}–{curWin.end}</b>. Hệ thống sẽ chặn nếu nhập giờ ngoài ca này.
                </span>
              )}
            </div>
          )}
          <Field label="Lý do"><textarea className="input" value={f.reason} onChange={set('reason')} placeholder="Ví dụ: bận việc gia đình" /></Field>
          <div className="row" style={{ justifyContent: 'flex-end' }}><Btn onClick={onClose}>Hủy</Btn><Btn kind="primary" busy={busy} disabled={!f.shift || !f.to} onClick={send}>Gửi yêu cầu</Btn></div>
        </div>
      )}
    </Modal>
  )
}

function Row({ r, owner, me, onDone }) {
  const toast = useToast()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const act = path => async () => { setBusy(true); try { await post(`/swap-requests/${r.id}/${path}`, { note }); toast(path === 'approve' ? 'Đã duyệt' : path === 'reject' ? 'Đã từ chối' : 'Đã hủy'); onDone() } catch (e) { toast(e.message, 'bad') } finally { setBusy(false) } }
  const [k, label] = ST[r.status]
  return (
    <Card className="tight">
      <div className="row spread"><div><b>{r.from_name}</b> → <b>{r.to_name}</b> <Badge kind={k}>{label}</Badge></div><span className="muted small">{dateTime(r.requested_at)}</span></div>
      <div style={{ margin: '6px 0' }}><Badge kind="info">{KIND[r.kind]}</Badge> {weekday(r.work_date)} {dm(r.work_date)} · Ca {SHIFT[r.shift_code]}
        {r.counter_date && <> ⇄ {weekday(r.counter_date)} {dm(r.counter_date)} · Ca {SHIFT[r.counter_shift]}</>}
        {r.kind === 'partial_cover' && (r.from_time || r.to_time) && <> · {r.from_time || '…'}–{r.to_time || '…'}</>}</div>
      {r.reason && <div className="muted">“{r.reason}”</div>}
      {r.decision_note && <div className="muted small">Ghi chú chủ quán: {r.decision_note}</div>}
      {r.status === 'pending' && owner && <div className="row" style={{ marginTop: 10 }}>
        <input className="input" style={{ maxWidth: 260 }} placeholder="Ghi chú (tùy chọn)" value={note} onChange={e => setNote(e.target.value)} />
        <Btn kind="primary" size="sm" busy={busy} onClick={act('approve')}>Duyệt</Btn><Btn size="sm" kind="danger" busy={busy} onClick={act('reject')}>Từ chối</Btn></div>}
      {r.status === 'pending' && !owner && r.from_employee_id === me.employee_id && <div style={{ marginTop: 10 }}><Btn size="sm" busy={busy} onClick={act('cancel')}>Hủy yêu cầu</Btn></div>}
    </Card>
  )
}

export default function Swaps() {
  const { me } = useApp()
  const owner = me.role === 'owner'
  const [tab, setTab] = useState('pending')
  const [open, setOpen] = useState(false)
  const list = useLoad(() => get('/swap-requests' + (tab === 'pending' ? '?status=pending' : '')), [tab])
  return (
    <Page title="Đổi ca" sub={owner ? 'Duyệt yêu cầu đổi ca. Duyệt xong lịch và lương cập nhật ngay.' : 'Gửi yêu cầu đổi ca hoặc nhờ người làm phụ; chủ quán duyệt trên hệ thống.'}
      actions={!owner && <Btn kind="primary" onClick={() => setOpen(true)}>+ Tạo yêu cầu</Btn>}>
      <Tabs value={tab} onChange={setTab} items={[['pending', 'Chờ duyệt'], ['all', 'Tất cả']]} />
      {!owner && !me.employee_id && <Notice kind="warn">Tài khoản chưa gắn với nhân viên. Nhờ chủ quán liên kết ở Cài đặt.</Notice>}
      {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> :
        list.data.length === 0 ? <Card><Empty title={tab === 'pending' ? 'Không có yêu cầu nào chờ duyệt' : 'Chưa có yêu cầu nào'} /></Card> :
          <div className="stack-sm">{list.data.map(r => <Row key={r.id} r={r} owner={owner} me={me} onDone={list.reload} />)}</div>}
      {open && <NewRequest onClose={() => setOpen(false)} onSaved={() => { setOpen(false); list.reload() }} />}
    </Page>
  )
}
