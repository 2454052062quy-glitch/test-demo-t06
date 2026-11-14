import { useEffect, useState } from 'react'
import { get, post, put, patch } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, ErrorBox, Field, Loading, Modal, MoneyInput, Notice, Page, PasswordRulesHint, Table, Toggle, useLoad, useToast } from '../ui.jsx'
import { SHIFT, SHIFTS, checkPasswordRules } from '../fmt.js'

function General() {
  const toast = useToast()
  const s = useLoad(() => get('/settings'), [])
  const [v, setV] = useState(null)
  useEffect(() => { if (s.data) setV(s.data) }, [s.data])
  if (!v) return s.error ? <ErrorBox message={s.error} onRetry={s.reload} /> : <Loading />
  const save = async patchBody => { try { await put('/settings', patchBody); toast('Đã lưu cài đặt'); s.reload() } catch (e) { toast(e.message, 'bad') } }
  return (
    <Card title="Cài đặt chung quán">
      <div className="stack">
        <Field label="Tên quán">
          <div className="row">
            <input className="input" style={{ maxWidth: 320 }} value={v.shop_name} onChange={e => setV({ ...v, shop_name: e.target.value })} />
            <Btn onClick={() => save({ shop_name: v.shop_name })}>Lưu tên</Btn>
          </div>
        </Field>
        <div className="stack-sm">
          <Toggle checked={v.duty_require_schedule} onChange={c => { setV({ ...v, duty_require_schedule: c }); save({ duty_require_schedule: c }) }}>
            Chặn nhân viên thao tác ngoài lịch phân công
          </Toggle>
          <span className="hint">Mặc định <b>tắt</b>: nhân viên vẫn giao ca, nhập hàng, báo nguyên liệu được kể cả ngày không có tên trong lịch (bản ghi gắn cờ “Ngoài lịch phân công” để chủ quán xem lại). Bật lên nếu muốn chặn cứng.</span>
        </div>
        <div className="grid2">
          <Field label="Ca tối đa mỗi người mỗi ngày (gợi ý lịch nháp)">
            <select className="select" value={v.max_shifts_per_day} onChange={e => { const n = Number(e.target.value); setV({ ...v, max_shifts_per_day: n }); save({ max_shifts_per_day: n }) }}>
              {[1, 2, 3].map(n => <option key={n} value={n}>{n} ca</option>)}
            </select>
          </Field>
          <Field label="Độ lệch số ca cho phép khi ghép cụm ca liền kề">
            <select className="select" value={v.cluster_fairness_slack} onChange={e => { const n = Number(e.target.value); setV({ ...v, cluster_fairness_slack: n }); save({ cluster_fairness_slack: n }) }}>
              {[0, 1, 2, 3].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </Field>
        </div>
      </div>
    </Card>
  )
}

function ShiftsAndRates() {
  const toast = useToast()
  const sh = useLoad(() => get('/shift-types'), [])
  const rt = useLoad(() => get('/pay-rates'), [])
  const [shifts, setShifts] = useState(null)
  const [rate, setRate] = useState(null)
  useEffect(() => { if (sh.data) setShifts(sh.data) }, [sh.data])
  useEffect(() => { if (rt.data) setRate(rt.data) }, [rt.data])
  if (!shifts || !rate) return <Loading />
  const setS = (code, k, val) => setShifts(shifts.map(s => {
    if (s.code !== code) return s
    const next = { ...s, [k]: val }
    if ((k === 'start_time' || k === 'end_time') && next.start_time && next.end_time) {
      const [sh, sm] = next.start_time.split(':').map(Number)
      const [eh, em] = next.end_time.split(':').map(Number)
      const diff = (eh * 60 + em) - (sh * 60 + sm)
      if (diff > 0) next.hours = Math.round((diff / 60) * 100) / 100
    }
    return next
  }))
  const save = async () => {
    try {
      await put('/shift-types', shifts.map(s => ({ ...s, hours: Number(s.hours), start_time: s.start_time || null, end_time: s.end_time || null, capacity: Number(s.capacity) })))
      await put('/pay-rates', { rate_a: Number(rate.rate_a) || 0, rate_b: Number(rate.rate_b) || 0 })
      toast('Đã lưu ca và mức lương')
      sh.reload()
      rt.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }
  return (
    <Card title="Khung ca làm việc & Đơn giá lương">
      <div className="stack">
        <Table head={['Ca làm việc', { label: 'Số giờ tính lương', num: 1 }, 'Từ giờ (bắt đầu)', 'Đến giờ (kết thúc)', { label: 'Số người/ca', num: 1 }]}>
          {shifts.map(s => (
            <tr key={s.code}>
              <td><b>Ca {SHIFT[s.code]}</b></td>
              <td><input className="input" style={{ width: 90, marginLeft: 'auto', display: 'block' }} inputMode="decimal" value={s.hours} onChange={e => setS(s.code, 'hours', e.target.value.replace(',', '.'))} /></td>
              <td><input className="input" type="time" style={{ width: 120 }} value={s.start_time || ''} onChange={e => setS(s.code, 'start_time', e.target.value)} /></td>
              <td><input className="input" type="time" style={{ width: 120 }} value={s.end_time || ''} onChange={e => setS(s.code, 'end_time', e.target.value)} /></td>
              <td><input className="input" style={{ width: 80, marginLeft: 'auto', display: 'block' }} inputMode="numeric" value={s.capacity} onChange={e => setS(s.code, 'capacity', e.target.value)} /></td>
            </tr>
          ))}
        </Table>
        <span className="hint">Giờ bắt đầu/kết thúc phải hợp lệ (bắt đầu trước kết thúc) để hệ thống tự động nhận diện ca khi giao ca và quét QR.</span>
        <div className="grid2">
          <Field label="Mức lương a (₫/giờ, ca sáng)"><MoneyInput value={rate.rate_a} onChange={v => setRate({ ...rate, rate_a: v })} /></Field>
          <Field label="Mức lương b (₫/giờ, ca trưa và tối)"><MoneyInput value={rate.rate_b} onChange={v => setRate({ ...rate, rate_b: v })} /></Field>
        </div>
        <div><Btn kind="primary" onClick={save}>Lưu thiết lập ca & đơn giá</Btn></div>
      </div>
    </Card>
  )
}

function People() {
  const { me } = useApp()
  const toast = useToast()
  const emps = useLoad(() => get('/employees'), [])
  const users = useLoad(() => get('/users'), [])
  const pinList = useLoad(() => get('/attendance/pin/list').catch(() => []), [])
  const [ename, setEname] = useState('')
  const [form, setForm] = useState(null)
  const [pinEditingUser, setPinEditingUser] = useState(null)
  const [pinValue, setPinValue] = useState('')
  const [pinBusy, setPinBusy] = useState(false)

  const pinMap = (pinList.data || []).reduce((acc, p) => { acc[p.user_id] = p.has_pin; return acc }, {})

  const addEmp = async () => {
    try {
      await post('/employees', { display_name: ename })
      setEname('')
      toast('Đã thêm nhân viên')
      emps.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }
  const addUser = async () => {
    try {
      await post('/users', { ...form, employee_id: form.employee_id ? Number(form.employee_id) : null })
      setForm(null)
      toast('Đã tạo tài khoản')
      users.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }
  const toggle = async u => {
    try {
      await patch('/users/' + u.id, { is_active: !u.is_active })
      users.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }
  const link = async (u, id) => {
    try {
      await patch('/users/' + u.id, { employee_id: id ? Number(id) : null })
      toast('Đã liên kết nhân viên')
      users.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }
  const reset = async u => {
    const pw = prompt('Mật khẩu mới cho ' + u.username + ' (trên 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt):')
    if (!pw) return
    if (!checkPasswordRules(pw).ok) {
      toast('Mật khẩu phải trên 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt', 'bad')
      return
    }
    try {
      await patch('/users/' + u.id, { new_password: pw })
      toast('Đã đổi mật khẩu thành công')
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const savePin = async () => {
    if (!/^\d{4,6}$/.test(pinValue)) {
      toast('Mã PIN phải từ 4 đến 6 chữ số', 'bad')
      return
    }
    setPinBusy(true)
    try {
      await put(`/attendance/pin/${pinEditingUser.id}`, { pin: pinValue })
      toast(`Đã lưu mã PIN cho ${pinEditingUser.display_name}`)
      setPinEditingUser(null)
      setPinValue('')
      pinList.reload()
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setPinBusy(false)
    }
  }

  return (
    <>
      <Card title="Danh sách Nhân viên">
        <div className="stack">
          <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
            {(emps.data || []).map(e => <Badge key={e.id} kind={e.is_active ? 'info' : 'bad'}>{e.display_name}</Badge>)}
          </div>
          <div className="row">
            <input className="input" style={{ maxWidth: 280 }} placeholder="Tên nhân viên mới" value={ename} onChange={e => setEname(e.target.value)} />
            <Btn disabled={!ename.trim()} onClick={addEmp}>+ Thêm nhân sự</Btn>
          </div>
        </div>
      </Card>
      <Card title="Quản lý Tài khoản Đăng nhập" action={<Btn size="sm" onClick={() => setForm({ username: '', display_name: '', password: '', role: 'staff', employee_id: '' })}>+ Tạo tài khoản</Btn>}>
        {users.error ? <ErrorBox message={users.error} /> : !users.data ? <Loading /> : (
          <Table head={['Tài khoản', 'Vai trò', 'Gắn với nhân viên', 'Trạng thái', 'Thao tác']}>
            {users.data.map(u => (
              <tr key={u.id}>
                <td><b>{u.username}</b><div className="muted small">{u.display_name}</div></td>
                <td>{u.role === 'owner' ? <Badge kind="ok">Chủ quán</Badge> : <Badge>Nhân viên</Badge>}</td>
                <td>
                  <select className="select" style={{ minWidth: 160 }} value={u.employee_id || ''} onChange={e => link(u, e.target.value)}>
                    <option value="">— chưa gắn —</option>
                    {(emps.data || []).map(e => <option key={e.id} value={e.id}>{e.display_name}</option>)}
                  </select>
                </td>
                <td><Badge kind={u.is_active ? 'ok' : 'bad'}>{u.is_active ? 'Đang dùng' : 'Đã khóa'}</Badge></td>
                <td>
                  <div className="row" style={{ gap: 6 }}>
                    <Btn size="sm" onClick={() => reset(u)}>Đặt lại MK</Btn>
                    {u.role !== 'owner' && (
                      <Btn size="sm" kind="ghost" onClick={() => { setPinEditingUser(u); setPinValue('') }}>
                        {pinMap[u.id] ? '🔑 Đổi PIN' : '🔑 Đặt PIN'}
                      </Btn>
                    )}
                    {u.id !== me.id && <Btn size="sm" kind="ghost" onClick={() => toggle(u)}>{u.is_active ? 'Khóa' : 'Mở'}</Btn>}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
        <p className="hint">Nhân viên cần được gắn với hồ sơ nhân sự để tự động liên kết dữ liệu giao ca, lịch làm việc và lương cá nhân. Mã PIN 4–6 số dùng để đăng nhập dự phòng tại máy quầy.</p>
      </Card>
      {pinEditingUser && (
        <Modal title={`Cài đặt mã PIN máy quầy · ${pinEditingUser.display_name}`} onClose={() => { setPinEditingUser(null); setPinValue('') }}>
          <div className="stack">
            <Field label="Mã PIN mới (4–6 chữ số)">
              <input
                className="input"
                type="password"
                inputMode="numeric"
                maxLength={6}
                value={pinValue}
                onChange={e => setPinValue(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="Nhập 4–6 số (ví dụ: 1111)"
                autoFocus
              />
            </Field>
            <Notice kind="info">
              Mã PIN này cho phép nhân viên đăng nhập nhanh tại Máy quầy khi điện thoại hết pin hoặc không có kết nối.
            </Notice>
            <div className="row" style={{ justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <Btn onClick={() => { setPinEditingUser(null); setPinValue('') }}>Hủy</Btn>
              <Btn kind="primary" busy={pinBusy} disabled={!/^\d{4,6}$/.test(pinValue)} onClick={savePin}>
                Lưu mã PIN
              </Btn>
            </div>
          </div>
        </Modal>
      )}
      {form && (
        <Modal title="Tạo tài khoản đăng nhập" onClose={() => setForm(null)}>
          <div className="stack">
            <Field label="Tên đăng nhập"><input className="input" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="VD: nhanvien_c" /></Field>
            <Field label="Tên hiển thị"><input className="input" value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} placeholder="VD: Nhân viên C" /></Field>
            <Field label="Mật khẩu khởi tạo">
              <input className="input" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="VD: Quancafe@2026" />
            </Field>
            <PasswordRulesHint password={form.password} />
            <div className="grid2">
              <Field label="Vai trò">
                <select className="select" value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
                  <option value="staff">Nhân viên</option>
                  <option value="owner">Chủ quán</option>
                </select>
              </Field>
              <Field label="Gắn với nhân sự">
                <select className="select" value={form.employee_id} onChange={e => setForm({ ...form, employee_id: e.target.value })}>
                  <option value="">— chưa gắn —</option>
                  {(emps.data || []).map(e => <option key={e.id} value={e.id}>{e.display_name}</option>)}
                </select>
              </Field>
            </div>
            <div className="row spread" style={{ marginTop: 12 }}>
              <Btn onClick={() => setForm(null)}>Hủy</Btn>
              <Btn kind="primary" disabled={form.username.length < 3 || !form.display_name || !checkPasswordRules(form.password).ok} onClick={addUser}>Tạo tài khoản</Btn>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}

function StaffProfile() {
  const { me } = useApp()
  return (
    <Card title="Hồ sơ tài khoản cá nhân">
      <div className="stack">
        <div className="grid2">
          <Field label="Tên đăng nhập"><input className="input" value={me.username} disabled /></Field>
          <Field label="Tên hiển thị"><input className="input" value={me.display_name} disabled /></Field>
        </div>
        <div className="grid2">
          <Field label="Vai trò hệ thống"><input className="input" value={me.role === 'owner' ? 'Chủ quán' : 'Nhân viên bán hàng'} disabled /></Field>
          <Field label="Nhân sự liên kết"><input className="input" value={me.employee_name || 'Đã liên kết hồ sơ'} disabled /></Field>
        </div>
        <div className="grid2">
          <Field label="Ngày sinh (tùy chọn)"><input className="input" type="date" defaultValue="2002-05-15" /></Field>
          <Field label="Số điện thoại liên hệ"><input className="input" placeholder="09xxxxxxxx" defaultValue="0912345678" /></Field>
        </div>
        <Notice kind="info">Thông tin hồ sơ liên kết giúp quán phân công ca làm và trả lương chính xác.</Notice>
      </div>
    </Card>
  )
}

function Password() {
  const toast = useToast()
  const [f, setF] = useState({ old_password: '', new_password: '', confirm_password: '' })
  const [busy, setBusy] = useState(false)
  const save = async () => {
    if (f.new_password !== f.confirm_password) {
      toast('Mật khẩu xác nhận không khớp', 'bad')
      return
    }
    setBusy(true)
    try {
      await post('/auth/change-password', { old_password: f.old_password, new_password: f.new_password })
      setF({ old_password: '', new_password: '', confirm_password: '' })
      toast('Đã đổi mật khẩu thành công')
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card title="Đổi mật khẩu">
      <div className="stack">
        <Field label="Mật khẩu hiện tại">
          <input className="input" type="password" autoComplete="current-password" value={f.old_password} onChange={e => setF({ ...f, old_password: e.target.value })} />
        </Field>
        <div className="grid2">
          <Field label="Mật khẩu mới (tối thiểu 8 ký tự)">
            <input className="input" type="password" autoComplete="new-password" value={f.new_password} onChange={e => setF({ ...f, new_password: e.target.value })} />
          </Field>
          <Field label="Xác nhận mật khẩu mới">
            <input className="input" type="password" autoComplete="new-password" value={f.confirm_password} onChange={e => setF({ ...f, confirm_password: e.target.value })} />
          </Field>
        </div>
        <div>
          <Btn kind="primary" busy={busy} disabled={!f.old_password || f.new_password.length < 8 || f.new_password !== f.confirm_password} onClick={save}>
            Cập nhật mật khẩu
          </Btn>
        </div>
      </div>
    </Card>
  )
}

function KioskManager() {
  const toast = useToast()
  const kiosks = useLoad(() => get('/attendance/kiosk/list'), [])
  const [busy, setBusy] = useState(false)

  const getMyKioskId = () => {
    let id = localStorage.getItem('t06_kiosk_id')
    if (!id) {
      id = 'kiosk-' + Math.random().toString(36).slice(2, 10)
      localStorage.setItem('t06_kiosk_id', id)
    }
    return id
  }

  const register = async () => {
    setBusy(true)
    try {
      const kiosk_id = getMyKioskId()
      await post('/attendance/kiosk/register', { kiosk_id, label: `Máy quầy (${kiosk_id.slice(-6)})` })
      toast('Đã đăng ký trình duyệt này làm Máy quầy')
      kiosks.reload()
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Đăng ký Máy quầy">
      <div className="stack">
        <p className="hint">Chỉ trình duyệt được đăng ký mới tạo được mã QR chấm công (ở bản Live). Bấm nút dưới để đăng ký trình duyệt hiện tại.</p>
        <div>
          <Btn kind="primary" busy={busy} onClick={register}>📱 Đăng ký trình duyệt này làm Máy quầy</Btn>
        </div>
        {kiosks.data && kiosks.data.length > 0 && (
          <Table head={['Kiosk ID', 'Nhãn']}>
            {kiosks.data.map(k => (
              <tr key={k.kiosk_id}>
                <td><code style={{ fontSize: '0.8em' }}>{k.kiosk_id}</code></td>
                <td>{k.label}</td>
              </tr>
            ))}
          </Table>
        )}
      </div>
    </Card>
  )
}

export default function Settings() {
  const { me, meta } = useApp()
  const owner = me.role === 'owner'
  const kioskEnabled = meta?.flags?.E09_QR_ATTENDANCE
  return (
    <Page
      title={owner ? 'Cài đặt hệ thống' : 'Hồ sơ cá nhân & Cài đặt'}
      sub={owner ? 'Cấu hình quán, khung giờ ca, đơn giá lương, quản lý nhân viên và tài khoản.' : 'Xem thông tin tài khoản và đổi mật khẩu đăng nhập.'}
    >
      {owner ? (
        <div className="stack">
          <General />
          <ShiftsAndRates />
          <People />
          {kioskEnabled && <KioskManager />}
          <Password />
        </div>
      ) : (
        <div className="stack">
          <StaffProfile />
          <Password />
        </div>
      )}
    </Page>
  )
}
