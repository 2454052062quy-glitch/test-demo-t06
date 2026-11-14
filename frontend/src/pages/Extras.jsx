import { useCallback, useEffect, useRef, useState } from 'react'
import { get, post } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Loading, Modal, Notice, Page, Table, Tabs, useLoad, useToast } from '../ui.jsx'
import { dateTime, dmy, money, weekday } from '../fmt.js'

const ACTIONS = {
  create: 'Tạo mới',
  update: 'Cập nhật',
  delete: 'Xóa',
  approve: 'Duyệt',
  reject: 'Từ chối',
  cancel: 'Hủy bỏ',
  submit: 'Gửi phiếu',
  confirm: 'Xác nhận nhận ca',
  unlock: 'Mở khóa',
  lock: 'Chốt dữ liệu',
  publish: 'Công bố',
  unpublish: 'Hủy công bố',
  set_cell: 'Xếp ca',
  import: 'Nạp từ file',
  sync: 'Đồng bộ POS365',
  auto_draft: 'Gợi ý lịch nháp',
  report: 'Báo tình trạng',
  attach: 'Đính kèm ảnh',
  availability: 'Đăng ký rảnh',
  change_password: 'Đổi mật khẩu',
  scan: 'Quét QR'
}

const ENTITIES = {
  pos_order: 'Đơn hàng POS',
  purchase: 'Phiếu nhập hàng',
  expense: 'Khoản chi phí',
  shift_handover: 'Phiếu giao ca',
  schedule: 'Lịch ca',
  schedule_cell: 'Phân công ca',
  swap_request: 'Yêu cầu đổi ca',
  payroll_month: 'Bảng lương tháng',
  ingredient: 'Nguyên liệu',
  ingredient_status: 'Báo cáo kho',
  attendance: 'Lượt chấm công',
  user: 'Tài khoản',
  employee: 'Nhân sự',
  settings: 'Cài đặt',
  kiosk: 'Máy quầy'
}

const FIELD_LABELS = {
  status: 'Trạng thái',
  cash_actual: 'Tiền mặt thực tế',
  pos_revenue_ref: 'Doanh thu POS tham chiếu',
  difference: 'Chênh lệch',
  note: 'Ghi chú',
  shift_code: 'Ca làm',
  work_date: 'Ngày làm',
  amount: 'Số tiền',
  total_amount: 'Tổng tiền',
  discount: 'Chiết khấu',
  is_active: 'Kích hoạt',
  rate_a: 'Lương ca sáng (a)',
  rate_b: 'Lương ca trưa/tối (b)',
  locked: 'Khóa sổ',
  closed_at: 'Thời điểm đóng',
  supplier: 'Nhà cung cấp',
  doc_type: 'Loại chứng từ'
}

function formatVal(k, val) {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'boolean') return val ? 'Bật / Có' : 'Tắt / Không'
  if (typeof val === 'number') {
    if (k.includes('amount') || k.includes('actual') || k.includes('revenue') || k.includes('difference') || k.includes('rate') || k.includes('price') || k.includes('discount')) {
      return money(val)
    }
    return String(val)
  }
  if (typeof val === 'string') {
    if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return dmy(val)
    if (/^\d{4}-\d{2}-\d{2}T/.test(val)) return dateTime(val)
  }
  return JSON.stringify(val)
}

function RenderDiff({ oldVal, newVal }) {
  if (!oldVal && !newVal) return <span className="muted">—</span>

  if (typeof oldVal === 'object' && typeof newVal === 'object' && oldVal !== null && newVal !== null) {
    const keys = Array.from(new Set([...Object.keys(oldVal), ...Object.keys(newVal)]))
    const changes = keys.filter(k => JSON.stringify(oldVal[k]) !== JSON.stringify(newVal[k]))
    if (changes.length > 0) {
      return (
        <div className="stack-sm" style={{ fontSize: '0.85rem' }}>
          {changes.map(k => (
            <div key={k} style={{ lineHeight: 1.4 }}>
              <span className="muted">{FIELD_LABELS[k] || k}:</span>{' '}
              <span style={{ textDecoration: 'line-through', color: 'var(--muted)' }}>{formatVal(k, oldVal[k])}</span>{' '}
              → <b style={{ color: 'var(--pri)' }}>{formatVal(k, newVal[k])}</b>
            </div>
          ))}
        </div>
      )
    }
  }

  return (
    <div className="stack-sm" style={{ fontSize: '0.85rem', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
      {oldVal && <div><span className="muted">Cũ:</span> {typeof oldVal === 'object' ? JSON.stringify(oldVal, null, 1) : String(oldVal)}</div>}
      {newVal && <div><span className="muted">Mới:</span> <b>{typeof newVal === 'object' ? JSON.stringify(newVal, null, 1) : String(newVal)}</b></div>}
    </div>
  )
}

export function Audit() {
  const [filterAction, setFilterAction] = useState('')
  const a = useLoad(() => get('/audit?limit=250'), [])

  const filtered = (a.data || []).filter(r => !filterAction || r.action === filterAction)

  return (
    <Page title="Nhật ký thao tác hệ thống" sub="Ghi nhận toàn bộ thao tác thêm, sửa, xóa, duyệt và chốt số liệu. Đảm bảo tính minh bạch và truy vết.">
      <div className="row spread" style={{ marginBottom: 12 }}>
        <div className="row" style={{ gap: 8 }}>
          <span className="small muted">Lọc theo hành động:</span>
          <select className="select" style={{ width: 'auto' }} value={filterAction} onChange={e => setFilterAction(e.target.value)}>
            <option value="">-- Tất cả thao tác --</option>
            {Object.entries(ACTIONS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </div>
        <span className="small muted">Hiển thị {filtered.length} bản ghi</span>
      </div>

      {a.loading && !a.data ? <Loading /> : a.error ? <ErrorBox message={a.error} onRetry={a.reload} /> : filtered.length === 0 ? (
        <Card><Empty title="Chưa có thao tác nào phù hợp" /></Card>
      ) : (
        <Card>
          <Table head={['Thời gian', 'Người thực hiện', 'Hành động', 'Đối tượng', 'Chi tiết thay đổi (Cũ → Mới)']}>
            {filtered.map(r => (
              <tr key={r.id}>
                <td style={{ whiteSpace: 'nowrap' }}><b>{dateTime(r.at)}</b></td>
                <td><b>{r.username}</b></td>
                <td><Badge kind={r.action === 'delete' ? 'bad' : r.action === 'approve' || r.action === 'lock' ? 'ok' : 'info'}>{ACTIONS[r.action] || r.action}</Badge></td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <b>{ENTITIES[r.entity] || r.entity}</b>
                  {r.entity_id && <div className="muted small">#{r.entity_id}</div>}
                </td>
                <td style={{ maxWidth: 420 }}>
                  <RenderDiff oldVal={r.old_value} newVal={r.new_value} />
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </Page>
  )
}

// ─── Nhật ký chấm công (trang riêng) ───
export function AttendanceLogs() {
  const { currentMonth: month } = useApp()
  const logs = useLoad(() => get('/attendance?month=' + month), [month])

  return (
    <Page title="Nhật ký chấm công thực tế" sub="Bảng theo dõi thời gian vào/ra thực tế của từng nhân viên">
      <Card title={`Nhật ký quét thực tế · Tháng ${month}`} subtitle="Thời gian quét thực tế theo giờ Việt Nam">
        {logs.loading && !logs.data ? <Loading /> : logs.error ? <ErrorBox message={logs.error} onRetry={logs.reload} /> : logs.data.length === 0 ? (
          <Empty title="Chưa có lượt chấm công nào trong tháng này" />
        ) : (
          <Table head={['Nhân viên', 'Ngày làm việc', 'Loại (Vào/Ra)', 'Giờ thực tế (giờ VN)', 'Cách vào ca', 'Trạng thái phân công']}>
            {logs.data.map(l => (
              <tr key={l.id}>
                <td><b>{l.employee}</b></td>
                <td><b>{weekday(l.work_date)}</b> {dmy(l.work_date)}</td>
                <td>
                  <Badge kind={l.kind === 'in' ? 'ok' : 'info'}>
                    {l.kind === 'in' ? '🟢 VÀO CA' : '🔵 RA CA'}
                  </Badge>
                </td>
                <td><b>{dateTime(l.at)}</b></td>
                <td>
                  <Badge kind={l.auto_closed ? 'warn' : 'info'}>
                    {l.method || 'Quét QR'}
                  </Badge>
                </td>
                <td>
                  {l.out_of_schedule ? (
                    <Badge kind="warn">⚠️ Ngoài lịch phân công</Badge>
                  ) : (
                    <Badge kind="ok">✓ Đúng lịch ca</Badge>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </Page>
  )
}

// ─── Màn hình Kiosk máy quầy ───

function getOrCreateKioskId() {
  let id = localStorage.getItem('t06_kiosk_id')
  if (!id) {
    id = 'kiosk-' + Math.random().toString(36).slice(2, 10)
    localStorage.setItem('t06_kiosk_id', id)
  }
  return id
}

// Màn hình chờ (hiển thị QR + chọn tên + nhập PIN)
function KioskIdle({ kioskId, onEntered }) {
  const toast = useToast()
  const [qrData, setQrData] = useState(null)
  const [qrErr, setQrErr] = useState('')
  const [pinMode, setPinMode] = useState(false)
  const [users, setUsers] = useState([])
  const [selUser, setSelUser] = useState(null)
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const pollRef = useRef(null)
  const qrTimerRef = useRef(null)

  // Lấy danh sách nhân viên để hiển thị chọn tên PIN
  useEffect(() => {
    get('/attendance/kiosk/employees').then(us => setUsers(us || [])).catch(() => {})
  }, [])

  // Tạo QR mới
  const loadQr = useCallback(async () => {
    try {
      const r = await post('/attendance/kiosk/qr', {
        kiosk_id: kioskId,
        base_url: window.location.origin,
        purpose: 'in',
      })
      setQrData(r)
      setQrErr('')
      return r.token
    } catch (e) {
      setQrErr(e.message)
      return null
    }
  }, [kioskId])

  // Poll xem điện thoại đã xác nhận chưa
  const startPoll = useCallback((token) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const r = await get(`/attendance/kiosk/qr/status?token=${token}&kiosk_id=${kioskId}`)
        if (r.expired) {
          // QR hết hạn → tạo mới
          clearInterval(pollRef.current)
          const newToken = await loadQr()
          if (newToken) startPoll(newToken)
        } else if (r.confirmed) {
          clearInterval(pollRef.current)
          if (qrTimerRef.current) clearTimeout(qrTimerRef.current)
          // Mở phiên kiosk
          try {
            const sess = await post('/attendance/kiosk/session/open', { kiosk_id: kioskId, token })
            onEntered({ ...sess, kind: r.kind })
          } catch (e) {
            toast(e.message, 'bad')
            const newToken = await loadQr()
            if (newToken) startPoll(newToken)
          }
        }
      } catch {}
    }, 3000)
  }, [kioskId, loadQr, onEntered, toast])

  useEffect(() => {
    let alive = true
    const init = async () => {
      const token = await loadQr()
      if (alive && token) {
        startPoll(token)
        // Tự refresh QR sau 110s (trước khi hết 120s)
        qrTimerRef.current = setInterval(async () => {
          const newToken = await loadQr()
          if (alive && newToken) {
            clearInterval(pollRef.current)
            startPoll(newToken)
          }
        }, 110000)
      }
    }
    init()
    return () => {
      alive = false
      if (pollRef.current) clearInterval(pollRef.current)
      if (qrTimerRef.current) clearInterval(qrTimerRef.current)
    }
  }, [loadQr, startPoll])

  const pinLogin = async () => {
    if (!selUser) { toast('Chọn nhân viên trước', 'bad'); return }
    if (!/^\d{4,6}$/.test(pin)) { toast('Mã PIN phải 4–6 chữ số', 'bad'); return }
    setBusy(true)
    try {
      const r = await post('/attendance/kiosk/pin-login', { kiosk_id: kioskId, user_id: selUser, pin })
      onEntered({ ...r, kind: r.kind })
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
      setPin('')
    }
  }

  return (
    <div className="kiosk-idle" style={{ textAlign: 'center' }}>
      <div className="kiosk-brand" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 16 }}>
        <div
          className="brand-badge"
          style={{
            width: 'auto',
            height: 'auto',
            minWidth: 68,
            minHeight: 68,
            fontSize: '1.75rem',
            padding: '10px 18px',
            borderRadius: 16,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1,
          }}
        >
          T06
        </div>
        <h1 style={{ margin: '10px 0 4px' }}>Máy quầy POS365</h1>
        <p className="muted" style={{ margin: 0 }}>Quét mã QR để vào ca / ra ca</p>
      </div>

      <div className="kiosk-qr-area">
        {qrErr ? (
          <Notice kind="bad">{qrErr}</Notice>
        ) : !qrData ? (
          <Loading />
        ) : (
          <div dangerouslySetInnerHTML={{ __html: qrData.svg }}
            style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid var(--line)', display: 'inline-block' }} />
        )}
        <p className="small muted" style={{ marginTop: 8 }}>Mã QR tự động cập nhật mỗi 2 phút</p>
        {qrData?.url && (
          <p className="small muted" style={{ marginTop: 2, fontSize: '.75rem', wordBreak: 'break-all' }}>
            Liên kết quét: <code>{qrData.url.split('/attendance')[0]}</code>
          </p>
        )}
      </div>

      <div style={{ marginTop: 20 }}>
        <Btn kind="ghost" size="sm" onClick={() => setPinMode(v => !v)}>
          🔐 {pinMode ? 'Ẩn đăng nhập PIN' : 'Dùng mã PIN dự phòng'}
        </Btn>
      </div>

      {pinMode && (
        <div className="kiosk-pin-area">
          <div className="stack" style={{ maxWidth: 320, margin: '0 auto', padding: 16, background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--line)' }}>
            <h3 style={{ margin: 0 }}>Đăng nhập bằng PIN</h3>
            <div>
              <label style={{ fontSize: '.85rem', color: 'var(--muted)' }}>Chọn nhân viên</label>
              <select className="select" style={{ width: '100%', marginTop: 4 }} value={selUser || ''} onChange={e => setSelUser(Number(e.target.value) || null)}>
                <option value="">— Chọn tên —</option>
                {users.map(u => <option key={u.id} value={u.id}>{u.display_name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: '.85rem', color: 'var(--muted)' }}>Mã PIN (4–6 số)</label>
              <input className="input" type="password" inputMode="numeric" maxLength={6}
                value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                style={{ width: '100%', marginTop: 4, letterSpacing: '0.3em', textAlign: 'center', fontSize: '1.4rem' }}
                placeholder="••••" />
            </div>
            <Btn kind="primary" busy={busy} disabled={!selUser || pin.length < 4} onClick={pinLogin}>
              Xác nhận
            </Btn>
          </div>
        </div>
      )}
    </div>
  )
}

// Màn hình chào sau khi vào ca
function KioskActive({ session, kioskId, onExited }) {
  const toast = useToast()
  const [showEndShift, setShowEndShift] = useState(false)
  const [pinMode, setPinMode] = useState(false)
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [idleSeconds, setIdleSeconds] = useState(0)
  const idleRef = useRef(null)

  // Đếm idle time, tự lock sau 15 phút
  useEffect(() => {
    const reset = () => setIdleSeconds(0)
    window.addEventListener('mousemove', reset)
    window.addEventListener('keydown', reset)
    window.addEventListener('touchstart', reset)
    idleRef.current = setInterval(() => {
      setIdleSeconds(s => {
        if (s >= 15 * 60) {
          // Tự khóa → quay về màn kiosk idle
          onExited({ reason: 'idle_lock' })
          return 0
        }
        return s + 1
      })
    }, 1000)
    return () => {
      window.removeEventListener('mousemove', reset)
      window.removeEventListener('keydown', reset)
      window.removeEventListener('touchstart', reset)
      clearInterval(idleRef.current)
    }
  }, [onExited])

  const endShiftPin = async () => {
    if (!/^\d{4,6}$/.test(pin)) { toast('Mã PIN không hợp lệ', 'bad'); return }
    setBusy(true)
    try {
      // Dùng pin-login để ghi ra ca (kind sẽ là "out" vì đang có phiên "in")
      const r = await post('/attendance/kiosk/pin-login', { kiosk_id: kioskId, user_id: session.user_id, pin })
      toast(`Đã ghi nhận RA CA · ${session.employee_name || session.display_name}`)
      onExited({ ...r, reason: 'end_shift' })
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
      setPin('')
    }
  }

  const idleMin = Math.floor(idleSeconds / 60)
  const idleSec = idleSeconds % 60

  return (
    <div className="kiosk-active">
      <div className="kiosk-active-header">
        <div style={{ fontSize: 48 }}>☕</div>
        <h1>Chào {session.employee_name || session.display_name}!</h1>
        <p>Đã ghi nhận <b>VÀO CA</b> lúc {session.opened_at ? new Date(session.opened_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '—'}</p>
        {session.out_of_schedule && (
          <Notice kind="warn" style={{ marginTop: 8 }}>⚠️ Hôm nay bạn không có trong lịch phân công chính thức.</Notice>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 24, flexWrap: 'wrap' }}>
        <Btn kind="primary" onClick={() => { window.location.href = '/#/home' }}>
          📋 Vào trang làm việc
        </Btn>
        <Btn onClick={() => setShowEndShift(true)}>
          🏁 Kết thúc ca
        </Btn>
      </div>

      {idleSeconds > 10 * 60 && (
        <Notice kind="warn" style={{ marginTop: 16 }}>
          Màn hình sẽ tự khóa sau {14 - idleMin} phút nếu không có thao tác.
        </Notice>
      )}

      {showEndShift && (
        <Modal title="Kết thúc ca làm việc" onClose={() => { setShowEndShift(false); setPinMode(false); setPin('') }}>
          <div className="stack">
            <p>Xác nhận <b>RA CA</b> cho <b>{session.employee_name || session.display_name}</b>?</p>
            <Notice kind="info">Quét mã QR trên điện thoại để xác nhận, hoặc dùng PIN bên dưới.</Notice>

            <Btn kind="ghost" size="sm" onClick={() => setPinMode(v => !v)}>
              🔐 {pinMode ? 'Ẩn PIN' : 'Dùng mã PIN để ra ca'}
            </Btn>

            {pinMode && (
              <div className="stack-sm">
                <input className="input" type="password" inputMode="numeric" maxLength={6}
                  value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="Nhập PIN để xác nhận ra ca"
                  style={{ letterSpacing: '0.3em', textAlign: 'center', fontSize: '1.3rem' }} autoFocus />
                <Btn kind="primary" busy={busy} disabled={pin.length < 4} onClick={endShiftPin}>
                  Xác nhận ra ca bằng PIN
                </Btn>
              </div>
            )}

            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <Btn onClick={() => { setShowEndShift(false); setPinMode(false); setPin('') }}>Đóng</Btn>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

// Màn hình Kiosk tổng hợp
export function KioskScreen() {
  const kioskId = getOrCreateKioskId()
  const [session, setSession] = useState(null) // null = chưa có phiên
  const [greeting, setGreeting] = useState(null) // { kind, employee_name, out_of_schedule }
  const [greetTimeout, setGreetTimeout] = useState(null)

  const handleEntered = (data) => {
    const withTime = { ...data, opened_at: data.opened_at || new Date().toISOString() }
    setSession(withTime)
    setGreeting(withTime)
    if (withTime.kind === 'in') {
      const t = setTimeout(() => {
        window.location.href = '/#/home'
      }, 2200)
      setGreetTimeout(t)
    } else {
      const t = setTimeout(() => setGreeting(null), 5000)
      setGreetTimeout(t)
    }
  }

  const handleExited = (data) => {
    setSession(null)
    if (greetTimeout) clearTimeout(greetTimeout)
    if (data.reason !== 'idle_lock') {
      setGreeting({ ...data, kind: 'out' })
      const t = setTimeout(() => setGreeting(null), 5000)
      setGreetTimeout(t)
    }
  }

  // Kiểm tra phiên đang chạy khi mount
  useEffect(() => {
    get(`/attendance/kiosk/session?kiosk_id=${kioskId}`)
      .then(r => { if (r.active) setSession(r) })
      .catch(() => {})
  }, [kioskId])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      {greeting && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999 }}>
          <div style={{ background: 'var(--surface)', borderRadius: 20, padding: 40, textAlign: 'center', maxWidth: 400, width: '90%' }}>
            <div style={{ fontSize: 64 }}>{greeting.kind === 'in' ? '☕' : '👋'}</div>
            <h2 style={{ margin: '12px 0 8px' }}>
              Chào {greeting.employee_name || ''}!
            </h2>
            <p style={{ fontSize: '1.15rem', margin: '8px 0' }}>
              Đã ghi nhận <b>{greeting.kind === 'in' ? 'VÀO CA' : 'RA CA'}</b> lúc{' '}
              <b>{new Date(greeting.opened_at || Date.now()).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</b>
            </p>
            {greeting.out_of_schedule && (
              <Notice kind="warn" style={{ marginTop: 12 }}>⚠️ Ngoài lịch phân công</Notice>
            )}
            {greeting.kind === 'in' && (
              <div style={{ marginTop: 18 }}>
                <p className="muted small" style={{ marginBottom: 10 }}>Đang tự động mở giao diện làm việc của bạn…</p>
                <Btn kind="primary" onClick={() => { window.location.href = '/#/home' }}>
                  📋 Vào trang làm việc ngay →
                </Btn>
              </div>
            )}
          </div>
        </div>
      )}

      {session ? (
        <KioskActive session={session} kioskId={kioskId} onExited={handleExited} />
      ) : (
        <KioskIdle kioskId={kioskId} onEntered={handleEntered} />
      )}
    </div>
  )
}

// ─── Trang chủ AttendanceQr (giữ cũ, bổ sung tab Kiosk) ───
export function AttendanceQr() {
  const { currentMonth: month } = useApp()
  const [tab, setTab] = useState('kiosk')
  const logs = useLoad(() => get('/attendance?month=' + month), [month])

  return (
    <Page
      title="Chấm công Máy quầy"
      sub="Nhân viên quét mã QR trên màn hình máy quầy hoặc nhập PIN để vào ca / tan ca."
    >
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          ['kiosk', '🖥️ Màn hình Máy quầy'],
          ['logs', '📋 Nhật ký chấm công'],
        ]}
      />

      {tab === 'kiosk' && (
        <Card title="Màn hình Máy quầy (chạy thử)">
          <Notice kind="info" style={{ marginBottom: 12 }}>
            Đây là màn hình mô phỏng máy quầy ngay trong trình duyệt. Trong thực tế, mở trang <code>/kiosk</code> trên máy tính ở quầy.
          </Notice>
          <KioskEmbedded />
        </Card>
      )}

      {tab === 'logs' && (
        <Card title={`Nhật ký chấm công · Tháng ${month}`}>
          {logs.loading && !logs.data ? <Loading /> : logs.error ? <ErrorBox message={logs.error} onRetry={logs.reload} /> : logs.data.length === 0 ? (
            <Empty title="Chưa có lượt chấm công nào trong tháng này" />
          ) : (
            <Table head={['Nhân viên', 'Ngày làm việc', 'Loại (Vào/Ra)', 'Giờ thực tế', 'Cách vào ca', 'Trạng thái']}>
              {logs.data.map(l => (
                <tr key={l.id}>
                  <td><b>{l.employee}</b></td>
                  <td><b>{weekday(l.work_date)}</b> {dmy(l.work_date)}</td>
                  <td>
                    <Badge kind={l.kind === 'in' ? 'ok' : 'info'}>
                      {l.kind === 'in' ? '🟢 VÀO CA' : '🔵 RA CA'}
                    </Badge>
                  </td>
                  <td><b>{dateTime(l.at)}</b></td>
                  <td><Badge kind={l.auto_closed ? 'warn' : 'info'}>{l.method || 'Quét QR'}</Badge></td>
                  <td>
                    {l.out_of_schedule ? (
                      <Badge kind="warn">⚠️ Ngoài lịch</Badge>
                    ) : (
                      <Badge kind="ok">✓ Đúng lịch</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </Page>
  )
}

// Kiosk thu nhỏ nhúng vào trang AttendanceQr để demo
function KioskEmbedded() {
  const kioskId = getOrCreateKioskId()
  const [session, setSession] = useState(null)
  const [greeting, setGreeting] = useState(null)

  const handleEntered = (data) => {
    const withTime = { ...data, opened_at: data.opened_at || new Date().toISOString() }
    setSession(withTime)
    setGreeting(withTime)
    if (withTime.kind === 'in') {
      setTimeout(() => { window.location.href = '/#/home' }, 2200)
    } else {
      setTimeout(() => setGreeting(null), 5000)
    }
  }

  const handleExited = (data) => {
    setSession(null)
    if (data.reason !== 'idle_lock') {
      setGreeting({ ...data, kind: 'out' })
      setTimeout(() => setGreeting(null), 5000)
    }
  }

  useEffect(() => {
    get(`/attendance/kiosk/session?kiosk_id=${kioskId}`)
      .then(r => { if (r.active) setSession(r) })
      .catch(() => {})
  }, [kioskId])

  return (
    <div style={{ position: 'relative', border: '2px solid var(--line)', borderRadius: 16, padding: 24, background: 'var(--bg)', minHeight: 320 }}>
      {greeting && (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)', borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
          <div style={{ background: 'var(--surface)', borderRadius: 16, padding: 32, textAlign: 'center' }}>
            <div style={{ fontSize: 48 }}>{greeting.kind === 'in' ? '☕' : '👋'}</div>
            <h2>Chào {greeting.employee_name || ''}!</h2>
            <p><b>{greeting.kind === 'in' ? 'VÀO CA' : 'RA CA'}</b> đã được ghi nhận</p>
            {greeting.out_of_schedule && <Notice kind="warn">⚠️ Ngoài lịch phân công</Notice>}
          </div>
        </div>
      )}
      {session ? (
        <KioskActive session={session} kioskId={kioskId} onExited={handleExited} />
      ) : (
        <KioskIdle kioskId={kioskId} onEntered={handleEntered} />
      )}
    </div>
  )
}

// ─── Màn hình điện thoại xác nhận QR ───
export function AttendanceScan() {
  const { me } = useApp() || {}
  const token = new URLSearchParams(window.location.search).get('t') || ''
  const [loading, setLoading] = useState(true)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [confirmed, setConfirmed] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  // 1. Kiểm tra QR trước
  useEffect(() => {
    if (!token) {
      setError('Mã QR không hợp lệ (thiếu token).')
      setLoading(false)
      return
    }
    get(`/attendance/mobile/preview?token=${encodeURIComponent(token)}`)
      .then(res => {
        setPreview(res)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [token])

  // 2. Nhân viên bấm nút xác nhận
  const handleConfirm = async () => {
    setSubmitting(true)
    setError('')
    try {
      const res = await post('/attendance/mobile/confirm', { token })
      setConfirmed(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-screen">
      <div className="card stack" style={{ width: 'min(420px, 94vw)', textAlign: 'center', padding: '28px 20px', margin: 'auto' }}>
        {loading ? (
          <Loading />
        ) : error ? (
          <>
            <div style={{ fontSize: 48, marginBottom: 8 }}>⚠️</div>
            <h2>Không thể xác nhận</h2>
            <p className="muted" style={{ margin: '8px 0 16px' }}>{error}</p>
            <div className="stack-sm">
              <a className="btn primary" href="/#/home" style={{ width: '100%' }}>
                Về màn hình chính
              </a>
              <Btn kind="ghost" onClick={async () => { try { await post('/auth/logout') } catch {} window.location.reload() }}>
                Đổi tài khoản nhân viên khác
              </Btn>
            </div>
          </>
        ) : confirmed ? (
          <>
            <div style={{ fontSize: 52, marginBottom: 8 }}>{confirmed.kind === 'in' ? '☕' : '👋'}</div>
            <h2>Đã ghi nhận {confirmed.kind === 'in' ? 'VÀO CA' : 'RA CA'}</h2>
            <p style={{ margin: '8px 0 12px' }}>
              Chào <b>{confirmed.employee_name || me?.display_name || 'bạn'}</b>, hệ thống đã ghi nhận thành công và tự động đồng bộ lên máy quầy.
            </p>
            {confirmed.out_of_schedule && (
              <Notice kind="warn" style={{ textAlign: 'left', marginBottom: 16 }}>
                ⚠️ Hôm nay bạn không có trong lịch phân công chính thức. Bản ghi được gắn cờ “Ngoài lịch phân công” để chủ quán đối chiếu.
              </Notice>
            )}
            <div style={{ marginTop: 12 }}>
              <a className="btn btn-primary" href="/#/home" style={{ width: '100%', display: 'inline-block' }}>
                Về màn hình chính
              </a>
            </div>
          </>
        ) : preview ? (
          <>
            <div style={{ fontSize: 48, marginBottom: 8 }}>{preview.kind === 'in' ? '☕' : '🏁'}</div>
            <h2 style={{ margin: '0 0 6px' }}>
              {preview.kind === 'in' ? 'Xác nhận Vào ca' : 'Xác nhận Ra ca'}
            </h2>
            <p style={{ fontSize: '1.05rem', margin: '0 0 16px' }}>
              Nhân viên: <b>{preview.employee_name}</b>
            </p>

            <Notice kind="info" style={{ textAlign: 'left', marginBottom: 14 }}>
              Bạn đang thực hiện <b>{preview.action_text}</b>. Bấm nút bên dưới để máy quầy tự động đăng nhập.
            </Notice>

            {preview.out_of_schedule && (
              <Notice kind="warn" style={{ textAlign: 'left', marginBottom: 16 }}>
                ⚠️ Hôm nay bạn không có trong lịch phân công chính thức.
              </Notice>
            )}

            <Btn
              kind="primary"
              busy={submitting}
              onClick={handleConfirm}
              style={{ width: '100%', padding: '12px 0', fontSize: '1.05rem', marginTop: 8 }}
            >
              {preview.kind === 'in' ? '✓ Xác nhận Đăng nhập Máy quầy' : '✓ Xác nhận Tan ca'}
            </Btn>
          </>
        ) : null}
      </div>
    </div>
  )
}
