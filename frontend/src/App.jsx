import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { get, post } from './api.js'
import { BottomSheet, Btn, Card, Field, Loading, Modal, Notice, PasswordRulesHint, ToastProvider, useToast } from './ui.jsx'
import { checkPasswordRules, thisMonth, shiftMonth, monthLabel } from './fmt.js'
import Home from './pages/Home.jsx'
import Revenue from './pages/Revenue.jsx'
import Handover from './pages/Handover.jsx'
import Purchases from './pages/Purchases.jsx'
import Ingredients from './pages/Ingredients.jsx'
import Schedule from './pages/Schedule.jsx'
import Swaps from './pages/Swaps.jsx'
import Payroll from './pages/Payroll.jsx'
import Finance from './pages/Finance.jsx'
import Settings from './pages/Settings.jsx'
import { Audit, AttendanceQr, AttendanceScan, AttendanceLogs, KioskScreen } from './pages/Extras.jsx'

export const AppCtx = createContext(null)
export const useApp = () => useContext(AppCtx)

// Các trang KHÔNG hiển thị thanh chọn tháng dưới Header
const NO_PERIOD_PAGES = ['ingredients', 'settings', 'audit']

// Toàn bộ các trang có thể điều hướng
const PAGES = {
  home: { label: 'Tổng quan', ico: '⌂', component: Home, role: 'os' },
  revenue: { label: 'Doanh thu POS', ico: '▤', component: Revenue, role: 'o' },
  purchases: { label: 'Nhập hàng', ico: '❐', component: Purchases, role: 'os' },
  finance: { label: 'Chi phí & lãi/lỗ', ico: '₫', component: Finance, role: 'o' },
  handover: { label: 'Giao ca', ico: '⇄', component: Handover, role: 'os' },
  ingredients: { label: 'Nguyên liệu', ico: '▤', component: Ingredients, role: 'os' },
  schedule: { label: 'Lịch ca & đổi ca', ico: '☷', component: Schedule, role: 'os' },
  swaps: { label: 'Đổi ca', ico: '🔁', component: Swaps, role: 'os' },
  attendance_logs: { label: 'Nhật ký chấm công', ico: '◷', component: AttendanceLogs, role: 'o' },
  payroll: { label: 'Lương tháng', ico: '₫', component: Payroll, role: 'os' },
  settings: { label: 'Tài khoản', ico: '⚙', component: Settings, role: 'os' },
  attendance: { label: 'Chấm công QR', ico: '📱', component: AttendanceQr, role: 'o', flag: 'E09_QR_ATTENDANCE' },
  audit: { label: 'Nhật ký thao tác', ico: '🕘', component: Audit, role: 'o', flag: 'E03_AUDIT' },
}

function useHashPath() {
  const read = () => (window.location.hash.replace(/^#\/?/, '') || 'home').split('?')[0]
  const [p, setP] = useState(read)
  useEffect(() => {
    const h = () => setP(read())
    window.addEventListener('hashchange', h)
    return () => window.removeEventListener('hashchange', h)
  }, [])
  return p
}

/* ================= III.3 LOGIN ================= */
function Login({ meta, onDone }) {
  const toast = useToast()
  const setup = meta.needs_setup
  const isQrScan = typeof window !== 'undefined' && window.location.pathname.startsWith('/attendance/scan')
  const [f, setF] = useState({ username: '', display_name: '', password: '', remember: true })
  const [showPassword, setShowPassword] = useState(false)
  const [showForgotModal, setShowForgotModal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  const submit = async e => {
    e?.preventDefault()
    if (setup && !checkPasswordRules(f.password).ok) {
      setErrorMsg('Mật khẩu phải trên 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt.')
      return
    }
    setBusy(true)
    setErrorMsg('')
    try {
      if (setup) {
        await post('/auth/setup', { username: f.username, display_name: f.display_name, password: f.password })
      } else {
        await post('/auth/login', { username: f.username, password: f.password })
      }
      onDone()
    } catch (err) {
      setErrorMsg(err.message)
      toast(err.message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  const quickLogin = async username => {
    setBusy(true)
    setErrorMsg('')
    try {
      await post('/auth/quick-login', { username })
      onDone()
    } catch (err) {
      setErrorMsg(err.message)
      toast(err.message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-brand-logo">T06</div>
        <div className="login-title">
          <h1>{meta.shop_name || 'Cửa hàng A'}</h1>
          <p>Tích hợp dữ liệu và báo cáo lãi/lỗ · Demo v1</p>
        </div>

        {isQrScan && (
          <Notice kind="info" style={{ marginBottom: 14 }}>
            <b>📱 Xác nhận Chấm công QR:</b> Vui lòng đăng nhập tài khoản nhân viên trên điện thoại (chỉ cần 1 lần) để tiếp tục xác nhận Vào ca / Ra ca.
          </Notice>
        )}

        {meta.is_live && (
          <Notice kind="bad" style={{ marginBottom: 14 }}>
            <b>DỮ LIỆU THẬT</b>. Mọi thao tác đều tác động trực tiếp số liệu của quán.
          </Notice>
        )}

        {errorMsg && (
          <Notice kind="bad" style={{ marginBottom: 14 }}>
            {errorMsg}
          </Notice>
        )}

        <form className="stack" onSubmit={submit}>
          <Field label="Tên đăng nhập">
            <input
              className="input"
              autoFocus
              autoComplete="username"
              value={f.username}
              onChange={set('username')}
              required
              minLength={3}
              placeholder="Nhập tên đăng nhập"
            />
          </Field>

          {setup && (
            <Field label="Tên hiển thị (chủ quán)">
              <input
                className="input"
                value={f.display_name}
                onChange={set('display_name')}
                required
                placeholder="Ví dụ: Chủ quán"
              />
            </Field>
          )}

          <Field label="Mật khẩu">
            <div className="pw-field-wrap">
              <input
                className="input"
                type={showPassword ? 'text' : 'password'}
                autoComplete={setup ? 'new-password' : 'current-password'}
                value={f.password}
                onChange={set('password')}
                required
                minLength={setup ? 9 : 1}
                placeholder="Nhập mật khẩu"
              />
              <button
                type="button"
                className="pw-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex="-1"
              >
                {showPassword ? 'Ẩn' : 'Hiện'}
              </button>
            </div>
          </Field>

          {setup && <PasswordRulesHint password={f.password} />}

          {!setup && (
            <div className="row spread" style={{ fontSize: '.88rem' }}>
              <label className="row" style={{ gap: 6, cursor: 'pointer' }}>
                <input type="checkbox" checked={f.remember} onChange={set('remember')} />
                <span>Ghi nhớ đăng nhập</span>
              </label>
              <button
                type="button"
                className="btn ghost sm"
                style={{ padding: 0, color: 'var(--primary)', height: 'auto', minHeight: 0 }}
                onClick={() => setShowForgotModal(true)}
              >
                Quên mật khẩu?
              </button>
            </div>
          )}

          <Btn kind="primary" busy={busy} type="submit" style={{ width: '100%', marginTop: 8 }}>
            {setup ? 'Tạo tài khoản chủ quán' : 'Đăng nhập'}
          </Btn>

          <p className="muted small" style={{ textAlign: 'center', margin: '4px 0 0' }}>
            Chưa có tài khoản? Liên hệ chủ quán để được cấp.
          </p>
        </form>

        {!meta.is_live && !setup && (
          <div className="quick-login-wrap">
            <span className="muted small" style={{ fontWeight: 600 }}>Đăng nhập nhanh (Chỉ Demo):</span>
            <div className="quick-login-btns">
              <Btn size="sm" onClick={() => quickLogin('chuquan')} disabled={busy}>👤 Chủ quán</Btn>
              <Btn size="sm" onClick={() => quickLogin('nvA')} disabled={busy}>👤 NV A</Btn>
              <Btn size="sm" onClick={() => quickLogin('nvB')} disabled={busy}>👤 NV B</Btn>
            </div>
            <div style={{ marginTop: 10 }}>
              <Btn size="sm" kind="ghost" onClick={() => { window.location.pathname !== '/kiosk' && (window.location.href = '/kiosk') }}>
                🖥️ Chế độ Máy quầy (Demo)
              </Btn>
            </div>
          </div>
        )}
      </div>

      {showForgotModal && (
        <Modal title="Quên mật khẩu" onClose={() => setShowForgotModal(false)}>
          <div className="stack">
            <p>Hệ thống không lưu trữ mật khẩu dạng rõ để đảm bảo an toàn.</p>
            <Notice kind="info">
              Nếu bạn là <b>nhân viên</b>, hãy liên hệ trực tiếp Chủ quán để được cấp lại mật khẩu tạm thời trong mục Tài khoản.
              <br /><br />
              Nếu bạn là <b>chủ quán</b>, hãy đăng nhập bằng tài khoản quản trị hệ thống hoặc liên hệ kỹ thuật để reset qua terminal.
            </Notice>
            <div className="row" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
              <Btn kind="primary" onClick={() => setShowForgotModal(false)}>Đã hiểu</Btn>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

/* Modal đổi mật khẩu */
function ChangePasswordModal({ onClose }) {
  const toast = useToast()
  const [f, setF] = useState({ old_password: '', new_password: '', confirm_password: '' })
  const [busy, setBusy] = useState(false)
  const submit = async e => {
    e.preventDefault()
    if (!checkPasswordRules(f.new_password).ok) {
      toast('Mật khẩu mới phải trên 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt', 'bad')
      return
    }
    if (f.new_password !== f.confirm_password) {
      toast('Mật khẩu mới và xác nhận mật khẩu không khớp', 'bad')
      return
    }
    setBusy(true)
    try {
      await post('/auth/change-password', { old_password: f.old_password, new_password: f.new_password })
      toast('Đổi mật khẩu thành công')
      onClose()
    } catch (err) {
      toast(err.message, 'bad')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal title="Đổi mật khẩu" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <Field label="Mật khẩu hiện tại">
          <input className="input" type="password" required value={f.old_password} onChange={e => setF({ ...f, old_password: e.target.value })} />
        </Field>
        <Field label="Mật khẩu mới">
          <input className="input" type="password" required minLength={9} value={f.new_password} onChange={e => setF({ ...f, new_password: e.target.value })} />
        </Field>
        <PasswordRulesHint password={f.new_password} />
        <Field label="Xác nhận mật khẩu mới">
          <input className="input" type="password" required minLength={9} value={f.confirm_password} onChange={e => setF({ ...f, confirm_password: e.target.value })} />
        </Field>
        <div className="row" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
          <Btn type="button" onClick={onClose}>Hủy</Btn>
          <Btn kind="primary" busy={busy} disabled={!checkPasswordRules(f.new_password).ok} type="submit">Lưu mật khẩu mới</Btn>
        </div>
      </form>
    </Modal>
  )
}

/* Modal kết thúc ca làm việc (Ra ca bằng QR hoặc PIN) */
function EndShiftModal({ me, onClose, onDone }) {
  const toast = useToast()
  const [qr, setQr] = useState(null)
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const getKioskId = () => {
    let id = localStorage.getItem('t06_kiosk_id')
    if (!id) {
      id = 'kiosk-' + Math.random().toString(36).slice(2, 10)
      localStorage.setItem('t06_kiosk_id', id)
    }
    return id
  }

  useEffect(() => {
    let timer
    let pollTimer
    const kioskId = getKioskId()

    const load = async () => {
      try {
        const r = await post('/attendance/kiosk/qr', {
          kiosk_id: kioskId,
          base_url: window.location.origin,
          purpose: 'out',
        })
        setQr(r)
        if (pollTimer) clearInterval(pollTimer)
        pollTimer = setInterval(async () => {
          try {
            const st = await get(`/attendance/kiosk/qr/status?token=${r.token}&kiosk_id=${kioskId}`)
            if (st.confirmed && st.kind === 'out') {
              clearInterval(pollTimer)
              toast(`Đã ghi nhận RA CA cho ${st.employee_name || me.display_name}`)
              onDone()
            }
          } catch {}
        }, 2500)
      } catch (e) {
        setError(e.message)
      }
    }

    load()
    timer = setInterval(load, 110000)

    return () => {
      clearInterval(timer)
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [me, onDone, toast])

  const confirmWithPin = async () => {
    if (!/^\d{4,6}$/.test(pin)) {
      toast('Mã PIN phải từ 4 đến 6 chữ số', 'bad')
      return
    }
    setBusy(true)
    try {
      const kioskId = getKioskId()
      const r = await post('/attendance/kiosk/end-shift', { kiosk_id: kioskId, pin })
      toast(`Đã ghi nhận RA CA cho ${r.employee_name || me.display_name}`)
      onDone()
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Kết thúc ca làm việc (Ra ca)" onClose={onClose}>
      <div className="stack" style={{ textAlign: 'center' }}>
        <p>Quét mã QR bằng điện thoại để xác nhận ra ca, hoặc nhập mã PIN bên dưới.</p>

        {qr?.svg ? (
          <div className="stack-sm" style={{ alignItems: 'center' }}>
            <div style={{ display: 'inline-block', margin: '0 auto', padding: 12, background: '#fff', borderRadius: 12, border: '1px solid var(--line)' }}>
              <div dangerouslySetInnerHTML={{ __html: qr.svg }} />
            </div>
            {qr?.url && (
              <span className="small muted" style={{ fontSize: '.75rem', wordBreak: 'break-all' }}>
                Liên kết quét: <code>{qr.url.split('/attendance')[0]}</code>
              </span>
            )}
          </div>
        ) : error ? (
          <Notice kind="bad">{error}</Notice>
        ) : (
          <Loading />
        )}

        <div style={{ margin: '16px 0 8px', borderTop: '1px dashed var(--line)', paddingTop: 16 }}>
          <Field label="Hoặc xác nhận nhanh bằng mã PIN">
            <div className="row" style={{ gap: 8, maxWidth: 300, margin: '0 auto' }}>
              <input
                className="input"
                type="password"
                inputMode="numeric"
                maxLength={6}
                value={pin}
                onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="Nhập PIN (4–6 số)"
                style={{ textAlign: 'center', letterSpacing: '0.2em', fontSize: '1.2rem' }}
              />
              <Btn kind="primary" busy={busy} disabled={!/^\d{4,6}$/.test(pin)} onClick={confirmWithPin}>
                Ra ca
              </Btn>
            </div>
          </Field>
        </div>

        <div className="row" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
          <Btn onClick={onClose}>Hủy / Tiếp tục làm việc</Btn>
        </div>
      </div>
    </Modal>
  )
}

/* ================= CHUÔNG THÔNG BÁO ================= */
function NotificationBell({ me }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const uid = me?.id || me?.username || 'user'
  const seenKey = `t06_notif_seen_${uid}`
  const readIdsKey = `t06_notif_read_ids_${uid}`

  const loadReadIds = key => {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || '[]')
      return Array.isArray(parsed) ? parsed : []
    } catch { return [] }
  }

  const [seenAt, setSeenAt] = useState(() => localStorage.getItem(seenKey) || '')
  const [readIds, setReadIds] = useState(() => loadReadIds(readIdsKey))

  const load = useCallback(async () => {
    try {
      const data = await get('/notifications')
      if (Array.isArray(data)) setItems(data)
    } catch {}
  }, [])

  useEffect(() => {
    setSeenAt(localStorage.getItem(seenKey) || '')
    setReadIds(loadReadIds(readIdsKey))
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [load, seenKey, readIdsKey])

  useEffect(() => {
    if (!open) return
    const close = () => setOpen(false)
    window.addEventListener('click', close)
    return () => window.removeEventListener('click', close)
  }, [open])

  const isItemUnread = n => {
    if (readIds.includes(n.id)) return false
    if (!seenAt) return true
    return Boolean(n.at && n.at > seenAt)
  }

  const unreadCount = items.filter(isItemUnread).length

  const markOneRead = id => {
    if (readIds.includes(id)) return
    const next = [...readIds, id].slice(-100)
    setReadIds(next)
    localStorage.setItem(readIdsKey, JSON.stringify(next))
  }

  const markAllRead = () => {
    const newest = items.reduce((acc, i) => (i.at && i.at > acc ? i.at : acc), new Date().toISOString())
    localStorage.setItem(seenKey, newest)
    setSeenAt(newest)
    const allIds = Array.from(new Set([...readIds, ...items.map(i => i.id)])).slice(-100)
    setReadIds(allIds)
    localStorage.setItem(readIdsKey, JSON.stringify(allIds))
  }

  const fmtTime = iso => {
    if (!iso) return ''
    try {
      const d = new Date(iso)
      return d.toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
    } catch { return '' }
  }

  return (
    <div className="notif-wrap" onClick={e => e.stopPropagation()}>
      <button
        type="button"
        className="notif-btn"
        title="Thông báo hoạt động"
        aria-label="Thông báo"
        onClick={() => {
          const next = !open
          setOpen(next)
          if (next) load()
        }}
      >
        <span>🔔</span>
        {unreadCount > 0 && <span className="notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-head">
            <b style={{ fontSize: '.9rem' }}>
              {unreadCount > 0 ? `Thông báo (${unreadCount} chưa đọc)` : 'Thông báo (Đã đọc hết)'}
            </b>
            {unreadCount > 0 && (
              <button
                type="button"
                className="btn ghost sm"
                style={{ minHeight: 26, padding: '0 8px', fontSize: '.78rem' }}
                onClick={markAllRead}
              >
                Đánh dấu tất cả đã đọc
              </button>
            )}
          </div>
          <div className="notif-list">
            {items.length === 0 ? (
              <div className="empty" style={{ padding: '24px 12px', fontSize: '.85rem' }}>
                Chưa có thông báo hoạt động nào.
              </div>
            ) : items.map(n => {
              const isUnread = isItemUnread(n)
              return (
                <button
                  key={n.id}
                  type="button"
                  className={'notif-item' + (isUnread ? ' unread' : '')}
                  onClick={() => {
                    markOneRead(n.id)
                    setOpen(false)
                    if (n.link) window.location.hash = n.link
                  }}
                >
                  <span className="notif-ico">{n.icon || '🔔'}</span>
                  <div className="notif-content">
                    <div className="notif-title">{n.title}</div>
                    {n.detail && <div className="notif-detail">{n.detail}</div>}
                    {n.at && <div className="notif-time">{fmtTime(n.at)}</div>}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

/* ================= III.1 & III.2 APP SHELL ================= */
function Shell({ me, meta, logout, currentMonth, setCurrentMonth }) {
  const path = useHashPath()
  const [menuOpen, setMenuOpen] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [changePwOpen, setChangePwOpen] = useState(false)
  const [endShiftOpen, setEndShiftOpen] = useState(false)

  const isOwner = me.role === 'owner'
  const roleChar = isOwner ? 'o' : 's'
  const isAllowedPage = key => {
    const p = PAGES[key]
    if (!p) return false
    if (!p.role.includes(roleChar)) return false
    if (p.flag && !meta?.flags?.[p.flag]) return false
    return true
  }

  // Tìm trang hiện tại (kiểm tra chặt quyền theo vai trò chủ quán / nhân viên)
  const curKey = isAllowedPage(path) ? path : 'home'
  const CurrentComponent = PAGES[curKey].component
  const showPeriodBar = !NO_PERIOD_PAGES.includes(curKey)

  useEffect(() => {
    if (!isAllowedPage(path)) {
      window.location.hash = '#/home'
    }
  }, [path, isOwner])

  useEffect(() => {
    const close = () => setMenuOpen(false)
    if (menuOpen) window.addEventListener('click', close)
    return () => window.removeEventListener('click', close)
  }, [menuOpen])

  // Tự khóa sau 15 phút không tương tác nếu là nhân viên
  useEffect(() => {
    if (isOwner) return
    let lastActive = Date.now()
    const IDLE_LIMIT = 15 * 60 * 1000 // 15 phút
    const onActivity = () => { lastActive = Date.now() }
    const evts = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll']
    evts.forEach(e => window.addEventListener(e, onActivity, { passive: true }))
    const iv = setInterval(() => {
      if (Date.now() - lastActive >= IDLE_LIMIT) {
        clearInterval(iv)
        logout()
      }
    }, 10000)
    return () => {
      clearInterval(iv)
      evts.forEach(e => window.removeEventListener(e, onActivity))
    }
  }, [isOwner, logout])

  return (
    <div className="app-shell">
      {/* III.1 Header */}
      <header className="app-header">
        <div className="header-top">
          <a href="#/home" className="header-brand" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="brand-badge">T06</div>
            <div className="brand-info">
              <h1>{meta.shop_name || 'Cửa hàng A'}</h1>
              <p>Tích hợp dữ liệu và báo cáo lãi/lỗ · Demo v1</p>
            </div>
          </a>

          <div className="header-actions">
            {!meta.is_live ? (
              <span className="demo-badge">DEMO – MÔ PHỎNG</span>
            ) : (
              <span className="live-badge">DỮ LIỆU THẬT</span>
            )}

            {!isOwner && meta?.flags?.E09_QR_ATTENDANCE && (
              <button
                type="button"
                className="btn sm end-shift-btn"
                style={{ background: '#e53e3e', color: '#fff', borderColor: '#e53e3e', fontWeight: 600 }}
                onClick={() => setEndShiftOpen(true)}
                title="Kết thúc ca làm việc (ra ca)"
              >
                <span className="hide-mobile">🏁 Kết thúc ca</span>
                <span className="show-mobile">🏁 Ra ca</span>
              </button>
            )}

            <NotificationBell me={me} />

            <button
              className="user-menu-btn"
              onClick={e => {
                e.stopPropagation()
                setMenuOpen(!menuOpen)
              }}
              title="Tùy chọn người dùng"
            >
              <span className="hide-mobile">{isOwner ? '👤 Chủ quán' : '👤 Nhân viên'}</span>
              <span className="show-mobile">👤</span>
              <span style={{ fontSize: '1.1rem' }}>≡</span>
            </button>
          </div>
        </div>

        {menuOpen && (
          <div className="menu-dropdown" onClick={e => e.stopPropagation()}>
            <div className="menu-dropdown-header">
              <b>{me.display_name}</b>
              <div className="muted small">{isOwner ? 'Chủ quán (Toàn quyền)' : 'Nhân viên cửa hàng'}</div>
            </div>
            <button className="menu-dropdown-item" onClick={() => { setMenuOpen(false); setChangePwOpen(true) }}>
              <span>🔑</span> Đổi mật khẩu
            </button>
            <button className="menu-dropdown-item danger" onClick={() => { setMenuOpen(false); logout() }}>
              <span>🚪</span> Đăng xuất
            </button>
          </div>
        )}

        {/* Chỉ hiện thanh chọn kỳ ở các trang làm việc theo tháng */}
        {showPeriodBar && (
          <div className="header-period">
            <div className="period-bar">
              <button className="period-btn" onClick={() => setCurrentMonth(shiftMonth(currentMonth, -1))} title="Tháng trước">◀</button>
              <span>{monthLabel(currentMonth)}</span>
              <button className="period-btn" onClick={() => setCurrentMonth(shiftMonth(currentMonth, 1))} title="Tháng sau">▶</button>
            </div>
          </div>
        )}
      </header>

      {/* Thân trang: Sidebar trái trên Desktop + Nội dung chính */}
      <div className="desktop-layout">
        <aside className="desktop-sidebar" aria-label="Điều hướng chính">
          {isOwner ? (
            <>
              <div className="sidebar-group-title">TỔNG HỢP & TÀI CHÍNH</div>
              <a href="#/home" className={'sidebar-item ' + (curKey === 'home' ? 'on' : '')}><span>⌂</span><span>Tổng quan</span></a>
              <a href="#/revenue" className={'sidebar-item ' + (curKey === 'revenue' ? 'on' : '')}><span>▤</span><span>Doanh thu POS</span></a>
              <a href="#/purchases" className={'sidebar-item ' + (curKey === 'purchases' ? 'on' : '')}><span>❐</span><span>Nhập hàng</span></a>
              <a href="#/finance" className={'sidebar-item ' + (curKey === 'finance' ? 'on' : '')}><span>₫</span><span>Chi phí & lãi/lỗ</span></a>

              <div className="sidebar-group-title">VẬN HÀNH</div>
              <a href="#/handover" className={'sidebar-item ' + (curKey === 'handover' ? 'on' : '')}><span>⇄</span><span>Giao ca</span></a>
              <a href="#/ingredients" className={'sidebar-item ' + (curKey === 'ingredients' ? 'on' : '')}><span>▤</span><span>Nguyên liệu</span></a>
              {meta.flags?.E09_QR_ATTENDANCE && (
                <a href="#/attendance" className={'sidebar-item ' + (curKey === 'attendance' ? 'on' : '')}><span>📱</span><span>Chấm công QR</span></a>
              )}

              <div className="sidebar-group-title">NHÂN SỰ & QUẢN TRỊ</div>
              <a href="#/schedule" className={'sidebar-item ' + (curKey === 'schedule' || curKey === 'swaps' ? 'on' : '')}><span>📅</span><span>Lịch ca & đổi</span></a>
              <a href="#/attendance_logs" className={'sidebar-item ' + (curKey === 'attendance_logs' ? 'on' : '')}><span>◷</span><span>Nhật ký công</span></a>
              <a href="#/payroll" className={'sidebar-item ' + (curKey === 'payroll' ? 'on' : '')}><span>₫</span><span>Lương tháng</span></a>
              <a href="#/settings" className={'sidebar-item ' + (curKey === 'settings' ? 'on' : '')}><span>⚙</span><span>Tài khoản & Cài đặt</span></a>
              {meta.flags?.E03_AUDIT && (
                <a href="#/audit" className={'sidebar-item ' + (curKey === 'audit' ? 'on' : '')}><span>🕘</span><span>Nhật ký thao tác</span></a>
              )}
            </>
          ) : (
            <>
              <div className="sidebar-group-title">CÔNG VIỆC CỦA TÔI</div>
              <a href="#/home" className={'sidebar-item ' + (curKey === 'home' ? 'on' : '')}><span>⌂</span><span>Tổng quan</span></a>
              <a href="#/schedule" className={'sidebar-item ' + (curKey === 'schedule' || curKey === 'swaps' ? 'on' : '')}><span>📅</span><span>Lịch ca & Đổi ca</span></a>
              <a href="#/handover" className={'sidebar-item ' + (curKey === 'handover' ? 'on' : '')}><span>⇄</span><span>Giao ca</span></a>
              <a href="#/purchases" className={'sidebar-item ' + (curKey === 'purchases' ? 'on' : '')}><span>❐</span><span>Nhập hàng</span></a>
              <a href="#/ingredients" className={'sidebar-item ' + (curKey === 'ingredients' ? 'on' : '')}><span>▤</span><span>Nguyên liệu</span></a>
              <div className="sidebar-group-title">CÁ NHÂN</div>
              <a href="#/payroll" className={'sidebar-item ' + (curKey === 'payroll' ? 'on' : '')}><span>₫</span><span>Bảng lương</span></a>
              <a href="#/settings" className={'sidebar-item ' + (curKey === 'settings' ? 'on' : '')}><span>👤</span><span>Tài khoản & Mật khẩu</span></a>
            </>
          )}
        </aside>

        <main className="app-main">
          <CurrentComponent key={curKey + currentMonth} />
        </main>
      </div>

      {/* III.2 Điều hướng đáy (Floating Dock - Chỉ hiện trên điện thoại/màn hình nhỏ) */}
      <nav className="bottom-dock">
        <div className="dock-container">
          {isOwner ? (
            <>
              <a href="#/home" className={'dock-item ' + (curKey === 'home' ? 'on' : '')}>
                <span className="dock-ico">⌂</span>
                <span>Tổng quan</span>
              </a>
              <a href="#/revenue" className={'dock-item ' + (curKey === 'revenue' ? 'on' : '')}>
                <span className="dock-ico">▤</span>
                <span>Doanh thu</span>
              </a>
              <a href="#/purchases" className={'dock-item ' + (curKey === 'purchases' ? 'on' : '')}>
                <span className="dock-ico">❐</span>
                <span>Nhập hàng</span>
              </a>
              <a href="#/finance" className={'dock-item ' + (curKey === 'finance' ? 'on' : '')}>
                <span className="dock-ico">₫</span>
                <span>Chi phí</span>
              </a>
              <button
                type="button"
                className={'dock-item ' + (!['home', 'revenue', 'purchases', 'finance'].includes(curKey) ? 'on' : '')}
                onClick={() => setSheetOpen(true)}
              >
                <span className="dock-ico">•••</span>
                <span>Thêm</span>
              </button>
            </>
          ) : (
            <>
              <a href="#/home" className={'dock-item ' + (curKey === 'home' ? 'on' : '')}>
                <span className="dock-ico">⌂</span>
                <span>Tổng quan</span>
              </a>
              <a href="#/schedule" className={'dock-item ' + (curKey === 'schedule' || curKey === 'swaps' ? 'on' : '')}>
                <span className="dock-ico">📅</span>
                <span>Lịch ca</span>
              </a>
              <a href="#/handover" className={'dock-item ' + (curKey === 'handover' ? 'on' : '')}>
                <span className="dock-ico">⇄</span>
                <span>Giao ca</span>
              </a>
              <a href="#/purchases" className={'dock-item ' + (curKey === 'purchases' ? 'on' : '')}>
                <span className="dock-ico">❐</span>
                <span>Nhập hàng</span>
              </a>
              <button
                type="button"
                className={'dock-item ' + (!['home', 'schedule', 'swaps', 'handover', 'purchases'].includes(curKey) ? 'on' : '')}
                onClick={() => setSheetOpen(true)}
              >
                <span className="dock-ico">•••</span>
                <span>Thêm</span>
              </button>
            </>
          )}
        </div>
      </nav>

      {/* Bottom Sheet "Tính năng mở rộng" cho Chủ quán & Nhân viên trên mobile */}
      {sheetOpen && (
        <BottomSheet title="Tính năng mở rộng" onClose={() => setSheetOpen(false)}>
          {isOwner ? (
            <>
              <div className="bottom-sheet-section-title">VẬN HÀNH</div>
              <div className="sheet-grid">
                <a href="#/handover" className={'sheet-item ' + (curKey === 'handover' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">⇄</span>
                  <span>Giao ca</span>
                </a>
                <a href="#/ingredients" className={'sheet-item ' + (curKey === 'ingredients' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">▤</span>
                  <span>Nguyên liệu</span>
                </a>
                {meta.flags?.E09_QR_ATTENDANCE && (
                  <a href="#/attendance" className={'sheet-item ' + (curKey === 'attendance' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                    <span className="sheet-ico">📱</span>
                    <span>Chấm công QR</span>
                  </a>
                )}
              </div>

              <div className="bottom-sheet-section-title">NHÂN SỰ & QUẢN TRỊ</div>
              <div className="sheet-grid">
                <a href="#/schedule" className={'sheet-item ' + (curKey === 'schedule' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">☷</span>
                  <span>Lịch ca & đổi</span>
                </a>
                <a href="#/attendance_logs" className={'sheet-item ' + (curKey === 'attendance_logs' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">◷</span>
                  <span>Nhật ký công</span>
                </a>
                <a href="#/payroll" className={'sheet-item ' + (curKey === 'payroll' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">₫</span>
                  <span>Lương tháng</span>
                </a>
                <a href="#/settings" className={'sheet-item ' + (curKey === 'settings' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">⚙</span>
                  <span>Tài khoản</span>
                </a>
                {meta.flags?.E03_AUDIT && (
                  <a href="#/audit" className={'sheet-item ' + (curKey === 'audit' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                    <span className="sheet-ico">🕘</span>
                    <span>Nhật ký thao tác</span>
                  </a>
                )}
              </div>
            </>
          ) : (
            <>
              <div className="bottom-sheet-section-title">CÔNG VIỆC & CÁ NHÂN</div>
              <div className="sheet-grid">
                <a href="#/ingredients" className={'sheet-item ' + (curKey === 'ingredients' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">▤</span>
                  <span>Nguyên liệu</span>
                </a>
                <a href="#/payroll" className={'sheet-item ' + (curKey === 'payroll' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">₫</span>
                  <span>Bảng lương</span>
                </a>
                <a href="#/settings" className={'sheet-item ' + (curKey === 'settings' ? 'on' : '')} onClick={() => setSheetOpen(false)}>
                  <span className="sheet-ico">👤</span>
                  <span>Tài khoản</span>
                </a>
              </div>
            </>
          )}
        </BottomSheet>
      )}

      {changePwOpen && <ChangePasswordModal onClose={() => setChangePwOpen(false)} />}
      {endShiftOpen && <EndShiftModal me={me} onClose={() => setEndShiftOpen(false)} onDone={() => { setEndShiftOpen(false); logout() }} />}
    </div>
  )
}

function Root() {
  const [meta, setMeta] = useState(null)
  const [me, setMe] = useState(undefined)
  const [fatal, setFatal] = useState(null)
  const [currentMonth, setCurrentMonth] = useState('2026-11')

  const loadMe = useCallback(async () => {
    try {
      const [m, u] = await Promise.all([get('/meta'), get('/auth/me').catch(() => null)])
      setMeta(m)
      setMe(u)
    } catch (e) {
      setFatal(e.message)
    }
  }, [])

  useEffect(() => {
    loadMe()
  }, [loadMe])

  useEffect(() => {
    const h = () => setMe(null)
    window.addEventListener('t06:unauth', h)
    return () => window.removeEventListener('t06:unauth', h)
  }, [])

  const logout = async () => {
    try {
      await post('/auth/logout')
    } catch {
      /* phiên hết hạn */
    }
    window.location.hash = '#/home'
    setMe(null)
  }

  if (fatal) {
    return (
      <div className="login-screen">
        <Card title="Không kết nối được hệ thống">
          <p>{fatal}</p>
          <Btn onClick={() => window.location.reload()}>Tải lại</Btn>
        </Card>
      </div>
    )
  }

  if (!meta || me === undefined) return <Loading />

  // Truyền cả currentMonth và period để tương thích 100% với mọi trang con
  const ctxVal = {
    me,
    meta,
    reloadMe: loadMe,
    currentMonth,
    setCurrentMonth,
    period: currentMonth,
    setPeriod: setCurrentMonth,
  }

  if (window.location.pathname.startsWith('/attendance/scan')) {
    return me ? (
      <AppCtx.Provider value={ctxVal}>
        <AttendanceScan />
      </AppCtx.Provider>
    ) : (
      <Login meta={meta} onDone={loadMe} />
    )
  }

  if (window.location.pathname === '/kiosk') {
    return (
      <AppCtx.Provider value={ctxVal}>
        <KioskScreen />
      </AppCtx.Provider>
    )
  }

  if (!me) return <Login meta={meta} onDone={loadMe} />

  return (
    <AppCtx.Provider value={ctxVal}>
      <Shell me={me} meta={meta} logout={logout} currentMonth={currentMonth} setCurrentMonth={setCurrentMonth} />
    </AppCtx.Provider>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <Root />
    </ToastProvider>
  )
}