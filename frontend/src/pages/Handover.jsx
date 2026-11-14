import { useEffect, useState } from 'react'
import { get, post, put } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Loading, Modal, MoneyInput, Notice, Page, Table, useLoad, useToast } from '../ui.jsx'
import { SHIFT, SHIFTS, dateTime, dm, dmy, money, todayIso } from '../fmt.js'

const STATUS = {
  draft: ['', 'Nháp'],
  submitted: ['info', 'Chờ nhận'],
  confirmed: ['ok', 'Đã xác nhận'],
  needs_review: ['warn', 'Cần xem lại'],
}

/* ================= VIEW CHỦ QUÁN ================= */
function OwnerHandover() {
  const { currentMonth } = useApp()
  const toast = useToast()

  const [fromDate, setFromDate] = useState(`${currentMonth}-01`)
  const [toDate, setToDate] = useState(`${currentMonth}-30`)
  const [shiftFilter, setShiftFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedTicket, setSelectedTicket] = useState(null)

  const list = useLoad(() => get(`/handovers?month=${currentMonth}`), [currentMonth])

  // Lọc phiếu
  const filtered = (list.data || []).filter(h => {
    if (fromDate && h.business_date < fromDate) return false
    if (toDate && h.business_date > toDate) return false
    if (shiftFilter && h.shift_code !== shiftFilter) return false
    if (statusFilter && h.status !== statusFilter) return false
    return true
  })

  // Mở khóa phiếu để nhân viên sửa lại
  const unlockTicket = async id => {
    try {
      const updated = await post(`/handovers/${id}/unlock`)
      toast('Đã mở khóa phiếu giao ca cho nhân viên chỉnh sửa')
      list.reload()
      if (selectedTicket?.id === id) {
        setSelectedTicket(updated)
      }
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  // Chủ quán xác nhận nhận bàn giao (ví dụ ca tối bàn giao cho chủ quán)
  const confirmByOwner = async id => {
    try {
      const updated = await post(`/handovers/${id}/confirm`, { action: 'confirm' })
      toast('Chủ quán đã xác nhận nhận bàn giao ca')
      list.reload()
      if (selectedTicket?.id === id) {
        setSelectedTicket(updated)
      }
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  // Tự động chọn phiếu đầu tiên nếu chưa chọn
  useEffect(() => {
    if (filtered.length > 0 && !selectedTicket) {
      setSelectedTicket(filtered[0])
    }
  }, [filtered, selectedTicket])

  return (
    <div className="stack" style={{ gap: 16 }}>
      {/* Bộ lọc */}
      <Card className="tight">
        <div className="row spread" style={{ gap: 10 }}>
          <div className="row" style={{ gap: 8 }}>
            <Field label="Từ ngày">
              <input type="date" className="input" style={{ width: 'auto', minHeight: 36 }} value={fromDate} onChange={e => setFromDate(e.target.value)} />
            </Field>
            <Field label="Đến ngày">
              <input type="date" className="input" style={{ width: 'auto', minHeight: 36 }} value={toDate} onChange={e => setToDate(e.target.value)} />
            </Field>
            <Field label="Ca">
              <select className="select" style={{ width: 'auto', minHeight: 36 }} value={shiftFilter} onChange={e => setShiftFilter(e.target.value)}>
                <option value="">Tất cả ca</option>
                {SHIFTS.map(s => <option key={s} value={s}>Ca {SHIFT[s]}</option>)}
              </select>
            </Field>
            <Field label="Trạng thái">
              <select className="select" style={{ width: 'auto', minHeight: 36 }} value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
                <option value="">Tất cả trạng thái</option>
                <option value="submitted">Chờ nhận</option>
                <option value="confirmed">Đã xác nhận</option>
                <option value="draft">Nháp</option>
              </select>
            </Field>
          </div>
          <Btn size="sm" kind="ghost" onClick={() => { setFromDate(`${currentMonth}-01`); setToDate(`${currentMonth}-30`); setShiftFilter(''); setStatusFilter('') }}>Đặt lại</Btn>
        </div>
      </Card>

      {/* Bảng danh sách phiếu giao ca */}
      <Card title="Danh sách biên bản giao ca ▾" collapsible defaultOpen={true}>
        {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> :
          filtered.length === 0 ? <Empty title="Không tìm thấy biên bản giao ca nào" /> : (
            <Table head={['Ngày', 'Ca', 'Người giao', 'Người nhận', { label: 'Hệ thống (POS)', num: 1 }, { label: 'Chuyển khoản', num: 1 }, { label: 'Thực tế giao', num: 1 }, 'Trạng thái', '']}>
              {filtered.map(h => {
                const [badgeKind, badgeText] = STATUS[h.status] || ['', h.status]
                const isOver10 = h.pos_revenue_ref > 0 && Math.abs(h.pos_revenue_entered - h.pos_revenue_ref) > 0.10 * h.pos_revenue_ref
                const isSelected = selectedTicket?.id === h.id

                return (
                  <tr key={h.id} style={{ background: isSelected ? 'var(--primary-soft)' : undefined }}>
                    <td><b>{dmy(h.business_date)}</b></td>
                    <td>Ca {SHIFT[h.shift_code]}</td>
                    <td>{h.giver_name}</td>
                    <td>
                      {h.receiver_name ? (
                        <b>{h.receiver_name}</b>
                      ) : h.expected_receiver_name ? (
                        <span className="muted small" title="Người nhận dự kiến theo lịch phân công">
                          Chờ: {h.expected_receiver_name}
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="num">
                      <span style={{ color: isOver10 ? 'var(--warn)' : 'inherit', fontWeight: isOver10 ? 700 : 400 }}>
                        {money(h.pos_revenue_entered)}
                      </span>
                      {isOver10 && <span title="Lệch quá 10% so với POS tham chiếu" style={{ marginLeft: 4 }}>⚠️</span>}
                    </td>
                    <td className="num">{money(h.transfer_total)}</td>
                    <td className="num"><b>{money(h.cash_handed)}</b></td>
                    <td>
                      <Badge kind={badgeKind}>{badgeText}</Badge>
                      {h.unlocked_by_owner && <div style={{ marginTop: 2 }}><Badge kind="warn">🔓 Đã mở khóa sửa</Badge></div>}
                      {isOver10 && <div style={{ marginTop: 2 }}><Badge kind="warn">Lệch &gt;10%</Badge></div>}
                    </td>
                    <td>
                      <Btn size="sm" kind={isSelected ? 'primary' : 'ghost'} onClick={() => setSelectedTicket(h)}>
                        {isSelected ? 'Đang xem' : 'Mở phiếu'}
                      </Btn>
                    </td>
                  </tr>
                )
              })}
            </Table>
          )}
      </Card>

      {/* Chi tiết phiếu (Chỉ đọc – số do nhân viên đếm và nhập) */}
      {selectedTicket && (
        <Card title={`Chi tiết phiếu: Ngày ${dmy(selectedTicket.business_date)} · Ca ${SHIFT[selectedTicket.shift_code]} ▾`} collapsible defaultOpen={true}>
          <div className="stack" style={{ gap: 14 }}>
            {selectedTicket.pos_revenue_ref > 0 && Math.abs(selectedTicket.pos_revenue_entered - selectedTicket.pos_revenue_ref) > 0.10 * selectedTicket.pos_revenue_ref && (
              <Notice kind="warn">
                ⚠️ <b>Cảnh báo chênh lệch &gt; 10%:</b> Doanh thu nhân viên nhập ({money(selectedTicket.pos_revenue_entered)}) lệch đáng kể so với POS tham chiếu của ca ({money(selectedTicket.pos_revenue_ref)}).
              </Notice>
            )}

            <div className="grid3">
              <div className="card flat tight">
                <span className="lbl">Doanh thu hệ thống (POS)</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{money(selectedTicket.pos_revenue_entered)}</div>
                {selectedTicket.pos_revenue_ref !== null && (
                  <span className="muted small">POS đối chiếu: {money(selectedTicket.pos_revenue_ref)}</span>
                )}
              </div>
              <div className="card flat tight">
                <span className="lbl">Tổng chuyển khoản (Bill CK)</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{money(selectedTicket.transfer_total)}</div>
              </div>
              <div className="card flat tight">
                <span className="lbl">Thực tế giao (Tiền mặt đã đếm)</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--primary)' }}>{money(selectedTicket.cash_handed)}</div>
              </div>
            </div>

            <div className="grid2">
              <div className="card flat tight">
                <span className="lbl">Thiếu / Trả</span>
                <div style={{ fontWeight: 600 }}>{selectedTicket.shortage_refund ? money(selectedTicket.shortage_refund) : '0 đ'}</div>
              </div>
              <div className="card flat tight">
                <span className="lbl">Phát sinh</span>
                <div style={{ fontWeight: 600 }}>{selectedTicket.extra ? money(selectedTicket.extra) : '0 đ'}</div>
              </div>
            </div>

            {selectedTicket.note && (
              <div className="card flat tight">
                <span className="lbl">Ghi chú chênh lệch / Cách xử lý</span>
                <p style={{ margin: '4px 0 0', fontStyle: 'italic' }}>"{selectedTicket.note}"</p>
              </div>
            )}

            {/* Dòng chữ ký */}
            <div className="card flat tight" style={{ background: 'var(--soft)' }}>
              <div className="stack-sm">
                <div>
                  ☑ <b>Nhân viên đã ký giao ca:</b> {selectedTicket.giver_name} · {dateTime(selectedTicket.submitted_at || selectedTicket.created_at)}
                </div>
                <div>
                  {selectedTicket.receiver_name ? (
                    <>☑ <b>Nhân viên đã ký nhận ca:</b> {selectedTicket.receiver_name} · {dateTime(selectedTicket.confirmed_at)}</>
                  ) : (
                    <>☐ <span className="muted">Chưa có người ký nhận ca (dự kiến bàn giao cho: <b>{selectedTicket.expected_receiver_name || 'Ca tiếp theo / Chủ quán'}</b>)</span></>
                  )}
                </div>
              </div>
            </div>

            {/* Nút hành động của chủ quán */}
            <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
              {selectedTicket.status === 'submitted' && (
                <Btn kind="primary" size="sm" onClick={() => confirmByOwner(selectedTicket.id)}>
                  ✓ Chủ quán xác nhận nhận ca
                </Btn>
              )}
              {(selectedTicket.status !== 'draft' || !selectedTicket.unlocked_by_owner) && (
                <Btn kind="ghost" size="sm" onClick={() => unlockTicket(selectedTicket.id)}>
                  🔓 Mở khóa cho nhân viên sửa lại
                </Btn>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

/* ================= VIEW NHÂN VIÊN ================= */
function StaffHandover() {
  const { me, currentMonth } = useApp()
  const toast = useToast()

  const blankForm = (d = todayIso(), s = 'sang') => ({
    business_date: d,
    shift_code: s,
    pos_revenue_entered: '',
    transfer_total: '',
    shortage_refund: '',
    extra: '',
    cash_handed: '',
    note: '',
  })

  const [f, setF] = useState(() => blankForm())
  const [editingId, setEditingId] = useState(null)
  const [refAmount, setRefAmount] = useState(null)
  const [busy, setBusy] = useState(false)
  const [itemsList, setItemsList] = useState([]) // Bảng động Thiếu / Trả, Phát sinh
  const [reviewModal, setReviewModal] = useState(null) // Modal xem & nhận ca trước
  const [reviewNote, setReviewNote] = useState('')

  // Tải danh sách biên bản của quán và lịch ca tháng để kiểm tra ca phân công
  const list = useLoad(() => get(`/handovers?month=${currentMonth}`), [currentMonth])
  const sched = useLoad(() => get(`/schedule/${currentMonth}`), [currentMonth])

  // Tìm biên bản đã tồn tại của đúng ngày + ca đang chọn
  const existingForSlot = (list.data || []).find(
    h => h.business_date === f.business_date && h.shift_code === f.shift_code
  )
  const isMine = h => h && (h.giver_id === me.id || h.giver_name === me.display_name)
  const canEditExisting = existingForSlot && isMine(existingForSlot) && (existingForSlot.status === 'draft' || existingForSlot.unlocked_by_owner)

  // Load dữ liệu phiếu cần sửa vào form
  const loadTicketIntoForm = t => {
    setEditingId(t.id)
    setF({
      business_date: t.business_date,
      shift_code: t.shift_code,
      pos_revenue_entered: t.pos_revenue_entered ?? '',
      transfer_total: t.transfer_total ?? '',
      shortage_refund: t.shortage_refund ?? '',
      extra: t.extra ?? '',
      cash_handed: t.cash_handed ?? '',
      note: t.note || '',
    })
    setItemsList([])
  }

  // Khi đổi ngày/ca: nếu ca đó có phiếu nháp hoặc phiếu đã được Chủ quán mở khóa của mình thì tự nạp vào form để sửa
  useEffect(() => {
    if (!list.data) return
    const match = list.data.find(h => h.business_date === f.business_date && h.shift_code === f.shift_code)
    if (match && isMine(match) && (match.status === 'draft' || match.unlocked_by_owner)) {
      if (editingId !== match.id) {
        loadTicketIntoForm(match)
      }
    } else if (editingId !== null) {
      setEditingId(null)
    }
  }, [f.business_date, f.shift_code, list.data])

  // Lấy POS tham chiếu khi đổi ngày hoặc ca (D3)
  const fetchPosRef = async (d, s) => {
    if (!d || d > todayIso()) {
      setRefAmount(0)
      return 0
    }
    try {
      const res = await get(`/handovers/ref?date=${d}&shift=${s}`)
      setRefAmount(res.pos_revenue_ref)
      return res.pos_revenue_ref
    } catch {
      setRefAmount(null)
      return null
    }
  }

  useEffect(() => {
    fetchPosRef(f.business_date, f.shift_code)
  }, [f.business_date, f.shift_code])

  const setField = k => v => {
    setF(prev => ({ ...prev, [k]: v }))
  }

  // Bảng động Thiếu / Trả / Phát sinh
  const addItem = () => setItemsList([...itemsList, { type: 'thieu', amount: '', note: '' }])
  const updateItem = (idx, field, val) => {
    const next = [...itemsList]
    next[idx][field] = val
    setItemsList(next)
  }
  const removeItem = idx => setItemsList(itemsList.filter((_, i) => i !== idx))

  // Kiểm tra phân công lịch ca của ngày + ca đang chọn
  const slotAssignments = (sched.data?.assignments || []).filter(
    a => a.work_date === f.business_date && a.shift_code === f.shift_code
  )
  const assignedWrongPerson = slotAssignments.length > 0 && me.employee_id && !slotAssignments.some(a => a.employee_id === me.employee_id)
  const assignedNames = slotAssignments.map(a => a.employee_name).join(', ')

  // Kiểm tra độ lệch > 10%
  const isOver10 = refAmount > 0 && Math.abs((Number(f.pos_revenue_entered) || 0) - refAmount) > 0.10 * refAmount
  const needNote = isOver10 || itemsList.length > 0 || (Number(f.shortage_refund) || 0) !== 0 || (Number(f.extra) || 0) !== 0

  // Lưu hoặc Gửi biên bản
  const handleSave = async (submitNow) => {
    if (assignedWrongPerson) {
      toast(`Ca ${SHIFT[f.shift_code]} ngày ${dmy(f.business_date)} theo lịch là của ${assignedNames}. Bạn không đứng ca này nên không thể giao ca.`, 'bad')
      return
    }

    const posVal = Number(f.pos_revenue_entered) || 0
    const ckVal = Number(f.transfer_total) || 0
    const cashVal = Number(f.cash_handed) || 0

    if (f.pos_revenue_entered === '' && f.cash_handed === '' && f.transfer_total === '') {
      toast('Vui lòng nhập số liệu doanh thu POS và tiền mặt thực tế kiểm đếm trước khi tạo phiếu', 'bad')
      return
    }
    if (posVal <= 0 && ckVal <= 0 && cashVal <= 0 && !f.note.trim()) {
      toast('Số tiền giao ca đang bằng 0 đ. Vui lòng nhập số tiền thực tế hoặc ghi rõ lý do nếu ca không phát sinh doanh thu.', 'bad')
      return
    }

    // Kiểm tra các dòng Thiếu/Trả/Phát sinh
    for (const it of itemsList) {
      if ((Number(it.amount) || 0) <= 0) {
        toast('Vui lòng nhập số tiền lớn hơn 0 cho dòng Thiếu / Trả / Phát sinh (hoặc xóa dòng trống)', 'bad')
        return
      }
    }

    // Tính tổng phát sinh/thiếu trả từ bảng động
    let calcShortage = Number(f.shortage_refund) || 0
    let calcExtra = Number(f.extra) || 0
    const itemNotes = []
    itemsList.forEach(it => {
      const a = Number(it.amount) || 0
      const label = it.type === 'thieu' ? 'Thiếu' : it.type === 'tra' ? 'Trả khách' : 'Phát sinh'
      if (it.type === 'thieu' || it.type === 'tra') calcShortage -= a
      else if (it.type === 'phat_sinh') calcExtra += a
      if (it.note?.trim()) itemNotes.push(`${label} ${money(a)}: ${it.note.trim()}`)
    })

    const combinedNote = [f.note.trim(), ...itemNotes].filter(Boolean).join('; ')

    if ((needNote || calcShortage !== 0 || calcExtra !== 0) && !combinedNote) {
      toast('Doanh thu lệch >10% hoặc có khoản thiếu/trả/phát sinh, bắt buộc ghi rõ lý do', 'bad')
      return
    }

    setBusy(true)
    const payload = {
      business_date: f.business_date,
      shift_code: f.shift_code,
      pos_revenue_entered: posVal,
      transfer_total: ckVal,
      shortage_refund: calcShortage,
      extra: calcExtra,
      cash_handed: cashVal,
      note: combinedNote,
      submit: submitNow,
    }

    const targetId = editingId || (canEditExisting ? existingForSlot.id : null)

    try {
      if (targetId) {
        await put(`/handovers/${targetId}`, payload)
        toast(submitNow ? 'Đã cập nhật và ký gửi lại biên bản giao ca' : 'Đã lưu cập nhật biên bản nháp')
      } else {
        await post('/handovers', payload)
        toast(submitNow ? 'Đã ký giao ca thành công' : 'Đã lưu nháp biên bản')
      }
      await list.reload()
      if (submitNow) {
        setEditingId(null)
        setF(blankForm(f.business_date, f.shift_code))
        setItemsList([])
      }
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  // Xác nhận hoặc Yêu cầu xem lại phiếu ca trước
  const handleConfirmTicket = async (id, statusAction) => {
    if (statusAction === 'review' && !reviewNote.trim()) {
      toast('Vui lòng nhập lý do cần xem lại vào ô ghi chú trước khi gửi phản hồi', 'bad')
      return
    }
    try {
      await post(`/handovers/${id}/confirm`, { action: statusAction, note: reviewNote })
      toast(statusAction === 'confirm' ? 'Đã xác nhận nhận ca thành công' : 'Đã gửi yêu cầu xem lại (phiếu đã mở khóa để người giao sửa)')
      setReviewModal(null)
      setReviewNote('')
      list.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  // Lọc phiếu chờ bạn nhận (submitted và người giao != bạn)
  const pendingForMe = (list.data || []).filter(h => h.status === 'submitted' && !isMine(h))
  // Phiếu của tôi gần đây
  const myRecent = (list.data || []).filter(h => isMine(h))

  return (
    <div className="grid2" style={{ gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 16 }}>
      {/* CỘT TRÁI (60% Desktop): FORM PHIẾU GIAO CA */}
      <Card title={editingId ? `Sửa phiếu giao ca #${editingId} ▾` : 'Phiếu giao ca ▾'} collapsible defaultOpen={true}>
        <div className="stack" style={{ gap: 14 }}>
          {editingId && (
            <Notice kind="info">
              <div className="row spread" style={{ width: '100%' }}>
                <span>
                  📝 Đang chỉnh sửa biên bản <b>Ca {SHIFT[f.shift_code]} · {dmy(f.business_date)}</b>
                  {existingForSlot?.unlocked_by_owner ? ' (Đã được Chủ quán mở khóa cho phép sửa lại)' : ' (Bản nháp)'}.
                </span>
                <Btn size="sm" kind="ghost" onClick={() => { setEditingId(null); setF(blankForm()) }}>Tạo mới</Btn>
              </div>
            </Notice>
          )}

          {!editingId && existingForSlot && !canEditExisting && (
            <Notice kind="warn">
              Biên bản <b>Ca {SHIFT[f.shift_code]} · {dmy(f.business_date)}</b> đã được lập bởi <b>{existingForSlot.giver_name}</b> ({STATUS[existingForSlot.status]?.[1] || existingForSlot.status}).
              {isMine(existingForSlot) && ' Nếu cần sửa số liệu, vui lòng nhờ Chủ quán bấm "Mở khóa cho nhân viên sửa lại".'}
            </Notice>
          )}

          {assignedWrongPerson && (
            <Notice kind="bad">
              ⚠️ Theo lịch phân công đã công bố, <b>Ca {SHIFT[f.shift_code]} ngày {dmy(f.business_date)}</b> là của <b>{assignedNames}</b> (không phải ca của bạn).
            </Notice>
          )}

          <div className="grid2">
            <Field label="Ngày kinh doanh">
              <input
                type="date"
                className="input"
                value={f.business_date}
                onChange={e => setField('business_date')(e.target.value)}
              />
            </Field>
            <Field label="Ca làm việc">
              <select className="select" value={f.shift_code} onChange={e => setField('shift_code')(e.target.value)}>
                {SHIFTS.map(s => <option key={s} value={s}>Ca {SHIFT[s]}</option>)}
              </select>
            </Field>
          </div>

          {slotAssignments.length > 0 && !assignedWrongPerson && (
            <div className="muted small" style={{ marginTop: -6 }}>
              ✓ Lịch phân công ca này: <b>{assignedNames}</b>
            </div>
          )}

          {/* Doanh thu hệ thống kèm nút "Lấy từ POS365" (D3) */}
          <Field label="Doanh thu hệ thống của ca *">
            <div className="row" style={{ gap: 8 }}>
              <div className="grow">
                <MoneyInput big value={f.pos_revenue_entered} onChange={setField('pos_revenue_entered')} placeholder="Nhập doanh thu POS hoặc bấm Lấy từ POS365" />
              </div>
              <Btn type="button" onClick={() => fetchPosRef(f.business_date, f.shift_code).then(v => v !== null && setField('pos_revenue_entered')(v))}>
                Lấy từ POS365
              </Btn>
            </div>
            {refAmount !== null && (
              <span className="hint">
                Tham chiếu POS ca này: <b>{money(refAmount)}</b>
                {isOver10 && <span style={{ color: 'var(--warn)', fontWeight: 700 }}> (Lệch &gt;10% - Cần ghi rõ lý do)</span>}
              </span>
            )}
          </Field>

          <Field label="Tổng tiền chuyển khoản (Bill CK)">
            <MoneyInput big value={f.transfer_total} onChange={setField('transfer_total')} placeholder="0" />
          </Field>

          <Field label="Tiền mặt thực tế đã kiểm đếm *">
            <MoneyInput big value={f.cash_handed} onChange={setField('cash_handed')} placeholder="Nhập số tiền mặt thực tế bàn giao" />
          </Field>

          {/* Bảng động: Thiếu / Trả, Phát sinh */}
          <div className="stack-sm">
            <div className="row spread">
              <span className="lbl">Thiếu / Trả, Phát sinh</span>
              <Btn size="sm" kind="ghost" type="button" onClick={addItem}>+ Thêm dòng</Btn>
            </div>
            {itemsList.map((item, idx) => (
              <div key={idx} className="row" style={{ gap: 8, background: 'var(--soft)', padding: 8, borderRadius: 10 }}>
                <select className="select" style={{ width: 110 }} value={item.type} onChange={e => updateItem(idx, 'type', e.target.value)}>
                  <option value="thieu">Thiếu</option>
                  <option value="tra">Trả khách</option>
                  <option value="phat_sinh">Phát sinh</option>
                </select>
                <div style={{ width: 130 }}>
                  <MoneyInput value={item.amount} onChange={v => updateItem(idx, 'amount', v)} placeholder="Số tiền" />
                </div>
                <input className="input grow" placeholder="Ghi chú lý do..." value={item.note} onChange={e => updateItem(idx, 'note', e.target.value)} />
                <Btn size="sm" kind="danger" type="button" onClick={() => removeItem(idx)}>🗑</Btn>
              </div>
            ))}
          </div>

          <Field label={'Ghi chú lý do' + (needNote ? ' (BẮT BUỘC khi lệch >10% hoặc có phát sinh)' : '')}>
            <textarea
              className="input"
              value={f.note}
              onChange={e => setField('note')(e.target.value)}
              placeholder="Giải trình chênh lệch tiền mặt, hoàn tiền khách hàng..."
            />
          </Field>

          <div className="row spread" style={{ paddingTop: 8, borderTop: '1px solid var(--line)' }}>
            <Btn busy={busy} disabled={assignedWrongPerson} onClick={() => handleSave(false)}>
              {editingId ? 'Lưu cập nhật nháp' : 'Lưu nháp'}
            </Btn>
            <Btn kind="primary" busy={busy} disabled={assignedWrongPerson} onClick={() => handleSave(true)}>
              {editingId ? 'Cập nhật & Ký giao ca →' : 'Ký giao ca →'}
            </Btn>
          </div>
        </div>
      </Card>

      {/* CỘT PHẢI (40% Desktop): PHIẾU CHỜ BẠN NHẬN & PHIẾU GẦN ĐÂY */}
      <div className="stack" style={{ gap: 16 }}>
        {/* Phiếu chờ bạn nhận */}
        <Card title="Phiếu chờ bạn nhận ▾" collapsible defaultOpen={true}>
          {pendingForMe.length === 0 ? (
            <span className="muted small">Không có phiếu nào đang chờ bạn nhận.</span>
          ) : (
            <div className="stack-sm">
              {pendingForMe.map(p => (
                <div key={p.id} className="row spread card flat tight" style={{ background: 'var(--primary-soft)' }}>
                  <div>
                    <b>Ngày {dm(p.business_date)} · Ca {SHIFT[p.shift_code]}</b>
                    <div className="muted small">
                      Người giao: <b>{p.giver_name}</b> · Tiền mặt: <b>{money(p.cash_handed)}</b>
                    </div>
                  </div>
                  <Btn size="sm" kind="primary" onClick={() => setReviewModal(p)}>Xem &amp; nhận</Btn>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Phiếu của tôi gần đây */}
        <Card title="Phiếu của tôi gần đây ▾" collapsible defaultOpen={true}>
          {myRecent.length === 0 ? (
            <span className="muted small">Bạn chưa lập phiếu nào trong tháng.</span>
          ) : (
            <div className="stack-sm">
              {myRecent.slice(0, 8).map(p => {
                const [bKind, bText] = STATUS[p.status] || ['', p.status]
                const editable = p.status === 'draft' || p.unlocked_by_owner
                return (
                  <div key={p.id} className="row spread card flat tight" style={{ border: editingId === p.id ? '2px solid var(--primary)' : undefined }}>
                    <div>
                      <b>Ngày {dm(p.business_date)} · Ca {SHIFT[p.shift_code]}</b>
                      <div className="muted small">
                        Thực tế giao: <b>{money(p.cash_handed)}</b>
                        {p.receiver_name ? ` · Nhận: ${p.receiver_name}` : p.expected_receiver_name ? ` · Chờ: ${p.expected_receiver_name}` : ''}
                      </div>
                      {p.unlocked_by_owner && (
                        <div style={{ marginTop: 4 }}>
                          <Badge kind="warn">🔓 Đã mở khóa - Bấm Sửa lại</Badge>
                        </div>
                      )}
                    </div>
                    <div className="row" style={{ gap: 6 }}>
                      <Badge kind={bKind}>{bText}</Badge>
                      {editable && (
                        <Btn size="sm" kind="primary" onClick={() => loadTicketIntoForm(p)}>
                          ✏️ Sửa lại
                        </Btn>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      </div>

      {/* Modal Phiếu chờ xác nhận */}
      {reviewModal && (
        <Modal title="Xác nhận nhận bàn giao ca" onClose={() => setReviewModal(null)}>
          <div className="stack" style={{ gap: 12 }}>
            <div className="grid2">
              <div className="card flat tight">
                <span className="lbl">Ca &amp; Ngày</span>
                <div><b>Ca {SHIFT[reviewModal.shift_code]} · {dmy(reviewModal.business_date)}</b></div>
              </div>
              <div className="card flat tight">
                <span className="lbl">Người bàn giao</span>
                <div><b>{reviewModal.giver_name}</b></div>
              </div>
            </div>

            <div className="grid2">
              <div className="card flat tight">
                <span className="lbl">Doanh thu POS</span>
                <div>{money(reviewModal.pos_revenue_entered)}</div>
              </div>
              <div className="card flat tight">
                <span className="lbl">Chuyển khoản</span>
                <div>{money(reviewModal.transfer_total)}</div>
              </div>
            </div>

            <div className="card flat tight" style={{ background: 'var(--soft)' }}>
              <span className="lbl">Tiền mặt thực tế bàn giao (Cần đếm kỹ)</span>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--primary)' }}>
                {money(reviewModal.cash_handed)}
              </div>
            </div>

            {reviewModal.note && (
              <div className="card flat tight">
                <span className="lbl">Ghi chú của người giao</span>
                <p style={{ margin: '2px 0 0', fontStyle: 'italic' }}>"{reviewModal.note}"</p>
              </div>
            )}

            <Field label="Lý do xem lại (nếu có chênh lệch chưa khớp)">
              <textarea
                className="input"
                placeholder="Nhập ghi chú nếu phát hiện thiếu tiền két..."
                value={reviewNote}
                onChange={e => setReviewNote(e.target.value)}
              />
            </Field>

            <div className="row spread" style={{ marginTop: 10 }}>
              <Btn type="button" onClick={() => setReviewModal(null)}>Đóng</Btn>
              <div className="row" style={{ gap: 8 }}>
                <Btn kind="danger" size="sm" onClick={() => handleConfirmTicket(reviewModal.id, 'review')}>
                  Cần xem lại
                </Btn>
                <Btn kind="primary" onClick={() => handleConfirmTicket(reviewModal.id, 'confirm')}>
                  Xác nhận nhận ca
                </Btn>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default function Handover() {
  const { me } = useApp()
  return (
    <Page
      title="Giao ca"
      sub="Biên bản bàn giao ca: ghi nhận doanh thu, bill chuyển khoản, kiểm đếm tiền mặt thực tế và xác nhận tiếp quản."
    >
      {me.role === 'owner' ? <OwnerHandover /> : <StaffHandover />}
    </Page>
  )
}
