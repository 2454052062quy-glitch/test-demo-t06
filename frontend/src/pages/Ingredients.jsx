import { useState } from 'react'
import { get, post, put, del } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Loading, Modal, Notice, Page, Table, useLoad, useToast } from '../ui.jsx'
import { dateTime, dmy, money } from '../fmt.js'

const ST = {
  du: ['ok', 'Đủ'],
  sap_het: ['warn', 'Sắp hết'],
  het: ['bad', 'Hết'],
  da_dat: ['info', 'Đã đặt hàng']
}

export default function Ingredients() {
  const { me } = useApp()
  const toast = useToast()
  const owner = me.role === 'owner'

  const list = useLoad(() => get('/ingredients'), [])
  const history = useLoad(() => get('/ingredient-status/history'), [])

  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [unit, setUnit] = useState('')

  // Sửa nguyên liệu (Chủ quán)
  const [editingIng, setEditingIng] = useState(null)
  const [editName, setEditName] = useState('')
  const [editUnit, setEditUnit] = useState('')

  // Nhân viên form state
  const [selectedIngId, setSelectedIngId] = useState('')
  const [reportStatus, setReportStatus] = useState('sap_het')
  const [reportNote, setReportNote] = useState('')
  const [busyReport, setBusyReport] = useState(false)

  // Chủ quán quick action report modal
  const [quickReport, setQuickReport] = useState(null)
  const [quickNote, setQuickNote] = useState('')

  const sendStatus = async (ingId, status, note = '') => {
    try {
      const r = await post('/ingredient-status', { ingredient_id: ingId, status, note })
      toast(r.out_of_schedule ? 'Đã ghi nhận (Ngoài lịch phân công)' : 'Đã cập nhật tình trạng nguyên liệu')
      list.reload()
      history.reload()
      setQuickReport(null)
      setQuickNote('')
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const handleStaffSubmit = async e => {
    e?.preventDefault()
    if (!selectedIngId) {
      toast('Vui lòng chọn nguyên liệu', 'bad')
      return
    }
    setBusyReport(true)
    try {
      await sendStatus(Number(selectedIngId), reportStatus, reportNote)
      setReportNote('')
      setSelectedIngId('')
    } finally {
      setBusyReport(false)
    }
  }

  const addIngredient = async () => {
    try {
      await post('/ingredients', { name, unit })
      toast('Đã thêm nguyên liệu')
      setAdding(false)
      setName('')
      setUnit('')
      list.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const openEditIngredient = ing => {
    setEditingIng(ing)
    setEditName(ing.name || '')
    setEditUnit(ing.unit || '')
  }

  const saveEditIngredient = async () => {
    if (!editingIng || !editName.trim()) return
    try {
      await put(`/ingredients/${editingIng.id}`, { name: editName.trim(), unit: editUnit.trim(), is_active: true })
      toast('Đã cập nhật thông tin nguyên liệu')
      setEditingIng(null)
      list.reload()
      history.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const removeIngredient = async ing => {
    if (!confirm(`Xóa nguyên liệu "${ing.name}" khỏi danh mục của quán?`)) return
    try {
      await del(`/ingredients/${ing.id}`)
      toast(`Đã xóa nguyên liệu "${ing.name}"`)
      list.reload()
      history.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const needOrder = (list.data || []).filter(i => i.status === 'sap_het' || i.status === 'het')
  const orderedWaiting = (list.data || []).filter(i => i.status === 'da_dat')

  return (
    <Page
      title="Tình trạng Nguyên liệu & Kho"
      sub="Báo nguyên liệu sắp hết để chủ quán kịp thời đặt hàng; theo dõi tiến độ hàng đã đặt và giá nhập gần nhất."
      actions={
        owner && (
          <Btn kind="primary" onClick={() => setAdding(true)}>+ Thêm nguyên liệu mới</Btn>
        )
      }
    >
      {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> : (
        <>
          {/* VIEW DÀNH CHO NHÂN VIÊN */}
          {!owner ? (
            <div className="stack">
              <Notice kind="info">
                <b>Quy tắc báo cáo tình trạng nguyên liệu:</b> Quán không theo dõi trừ kho tự động theo định lượng từng món. Nhân viên <b>kiểm tra trực tiếp bằng mắt tại quầy/tủ bảo quản</b> đầu hoặc cuối ca: nếu ước lượng chỉ còn đủ dùng dưới 1–2 ca thì báo <b>Sắp hết</b>, nếu đã cạn sạch thì báo <b>Hết hẳn</b>, hoặc khi nhận hàng mới về thì báo <b>Đã đủ</b>.
              </Notice>
              <div className="grid2" style={{ alignItems: 'start' }}>
                {/* CỘT TRÁI: FORM BÁO TÌNH TRẠNG NGUYÊN LIỆU */}
                <Card title="Báo cáo tình trạng nguyên liệu" subtitle="Kiểm tra thực tế tại quầy pha chế đầu ca / cuối ca">
                  <form onSubmit={handleStaffSubmit} className="stack">
                    <Field label="Chọn nguyên liệu" hint="Trạng thái hiển thị dựa trên lần kiểm tra/nhập hàng gần nhất">
                      <select
                        className="select"
                        value={selectedIngId}
                        onChange={e => setSelectedIngId(e.target.value)}
                        required
                      >
                        <option value="">-- Chọn nguyên liệu cần báo --</option>
                        {(list.data || []).map(i => (
                          <option key={i.id} value={i.id}>
                            {i.name} {i.unit ? `(${i.unit})` : ''} — Báo gần nhất: {ST[i.status]?.[1] || i.status}
                          </option>
                        ))}
                      </select>
                    </Field>

                  <Field label="Tình trạng hiện tại">
                    <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
                      <label className="row" style={{ cursor: 'pointer', gap: 6 }}>
                        <input
                          type="radio"
                          name="status"
                          value="sap_het"
                          checked={reportStatus === 'sap_het'}
                          onChange={() => setReportStatus('sap_het')}
                        />
                        <Badge kind="warn">Sắp hết</Badge>
                      </label>
                      <label className="row" style={{ cursor: 'pointer', gap: 6 }}>
                        <input
                          type="radio"
                          name="status"
                          value="het"
                          checked={reportStatus === 'het'}
                          onChange={() => setReportStatus('het')}
                        />
                        <Badge kind="bad">Hết hẳn</Badge>
                      </label>
                      <label className="row" style={{ cursor: 'pointer', gap: 6 }}>
                        <input
                          type="radio"
                          name="status"
                          value="du"
                          checked={reportStatus === 'du'}
                          onChange={() => setReportStatus('du')}
                        />
                        <Badge kind="ok">Đã đủ / Hàng về</Badge>
                      </label>
                    </div>
                  </Field>

                  <Field label="Ghi chú số lượng thực tế còn lại tại quầy">
                    <input
                      className="input"
                      value={reportNote}
                      onChange={e => setReportNote(e.target.value)}
                      placeholder="Ví dụ: Kiểm tại tủ mát còn đúng 2 hộp sữa, đủ dùng khoảng 1 ca"
                    />
                  </Field>

                  <Btn
                    kind="primary"
                    busy={busyReport}
                    disabled={!selectedIngId}
                    onClick={handleStaffSubmit}
                    style={{ width: '100%', padding: '10px' }}
                  >
                    Gửi báo cáo kho
                  </Btn>
                </form>
              </Card>

              {/* CỘT PHẢI: LỊCH SỬ BÁO GẦN ĐÂY */}
              <Card title="Lịch sử báo cáo gần đây" subtitle="Nhật ký các lần báo kho từ nhân viên & chủ quán">
                {history.loading && !history.data ? <Loading /> : history.error ? <ErrorBox message={history.error} onRetry={history.reload} /> :
                  (!history.data || history.data.length === 0) ? <Empty title="Chưa có lượt báo cáo nào gần đây" /> : (
                    <div className="stack-sm">
                      {history.data.slice(0, 10).map(h => (
                        <div key={h.id} className="card flat tight stack-sm" style={{ border: '1px solid var(--line)' }}>
                          <div className="row spread">
                            <div>
                              <b>{h.ingredient_name || h.ingredient}</b> <Badge kind={ST[h.status]?.[0] || 'info'}>{ST[h.status]?.[1] || h.status}</Badge>
                            </div>
                            <span className="muted small">{dateTime(h.reported_at || h.created_at)}</span>
                          </div>
                          {h.note && <div className="small">Ghi chú: <i>{h.note}</i></div>}
                          <div className="muted small">Người báo: <b>{h.reported_by_name || h.created_by_name || '—'}</b></div>
                        </div>
                      ))}
                    </div>
                  )}
              </Card>
            </div>
            </div>
          ) : (
            /* VIEW DÀNH CHO CHỦ QUÁN: 3 BẢNG THEO TIẾN ĐỘ */
            <div className="stack">
              {/* BẢNG 1: CẦN ĐẶT HÀNG (SẮP HẾT / HẾT) */}
              <Card
                title={`1. Danh mục cần đặt hàng (${needOrder.length})`}
                subtitle="Những nguyên liệu nhân viên báo thiếu, cần liên hệ nhà cung cấp"
              >
                {needOrder.length === 0 ? (
                  <div className="row" style={{ color: 'var(--ok)', gap: 8, padding: '12px 0' }}>
                    <span>✅ Tất cả nguyên liệu đang đủ hoặc đã được đặt.</span>
                  </div>
                ) : (
                  <Table head={['Nguyên liệu', 'Tình trạng', 'Ghi chú của ca', 'Thời gian báo', 'Thao tác']}>
                    {needOrder.map(i => (
                      <tr key={i.id}>
                        <td><b>{i.name}</b> {i.unit && <span className="muted small">({i.unit})</span>}</td>
                        <td><Badge kind={ST[i.status]?.[0] || 'warn'}>{ST[i.status]?.[1] || i.status}</Badge></td>
                        <td>{i.status_note || '—'}</td>
                        <td><span className="muted small">{dateTime(i.status_at)}</span></td>
                        <td>
                          <Btn
                            size="sm"
                            kind="primary"
                            onClick={() => sendStatus(i.id, 'da_dat', 'Chủ quán đã đặt hàng')}
                          >
                            Đánh dấu đã đặt
                          </Btn>
                        </td>
                      </tr>
                    ))}
                  </Table>
                )}
              </Card>

              {/* BẢNG 2: ĐÃ ĐẶT HÀNG - CHỜ HÀNG VỀ */}
              <Card
                title={`2. Danh mục đã đặt – chờ hàng về (${orderedWaiting.length})`}
                subtitle="Đã gọi NCC, chờ giao hàng tới quán và chuyển trạng thái sang Đủ"
              >
                {orderedWaiting.length === 0 ? (
                  <div className="muted small" style={{ padding: '8px 0' }}>Hiện không có nguyên liệu nào đang chờ giao.</div>
                ) : (
                  <Table head={['Nguyên liệu', 'Trạng thái', 'Ghi chú', 'Thời gian đặt', 'Thao tác khi hàng về']}>
                    {orderedWaiting.map(i => (
                      <tr key={i.id}>
                        <td><b>{i.name}</b> {i.unit && <span className="muted small">({i.unit})</span>}</td>
                        <td><Badge kind="info">Đã đặt hàng</Badge></td>
                        <td>{i.status_note || '—'}</td>
                        <td><span className="muted small">{dateTime(i.status_at)}</span></td>
                        <td>
                          <Btn
                            size="sm"
                            onClick={() => sendStatus(i.id, 'du', 'Hàng đã giao tới quán')}
                          >
                            ✓ Đã nhận đủ
                          </Btn>
                        </td>
                      </tr>
                    ))}
                  </Table>
                )}
              </Card>

              {/* BẢNG 3: TOÀN BỘ NGUYÊN LIỆU & GIÁ NHẬP GẦN NHẤT */}
              <Card
                title={`3. Toàn bộ danh mục nguyên liệu (${list.data.length})`}
                subtitle="Theo dõi giá nhập gần nhất từ phiếu nhập hàng, cập nhật trạng thái hoặc sửa/xóa nguyên liệu"
              >
                <Table head={['Nguyên liệu', 'Đơn vị', 'Tình trạng', { label: 'Giá nhập gần nhất', num: 1 }, 'Ngày nhập gần nhất', 'Báo trạng thái', 'Quản lý']}>
                  {list.data.map(i => (
                    <tr key={i.id}>
                      <td><b>{i.name}</b></td>
                      <td>{i.unit || '—'}</td>
                      <td>
                        <Badge kind={ST[i.status]?.[0] || 'info'}>{ST[i.status]?.[1] || i.status}</Badge>
                        {i.status_by_name && <div className="muted small" style={{ marginTop: 2 }}>Bởi: {i.status_by_name}</div>}
                      </td>
                      <td className="num">
                        {i.last_price !== null ? (
                          <b>{money(i.last_price)} {i.last_price_unit ? `/${i.last_price_unit}` : ''}</b>
                        ) : <span className="muted">—</span>}
                      </td>
                      <td>{i.last_purchase_date ? dmy(i.last_purchase_date) : <span className="muted">—</span>}</td>
                      <td>
                        <div className="row" style={{ gap: 6 }}>
                          {i.status !== 'sap_het' && (
                            <Btn size="sm" onClick={() => setQuickReport({ ing: i, status: 'sap_het' })}>Sắp hết</Btn>
                          )}
                          {i.status !== 'het' && (
                            <Btn size="sm" kind="danger" onClick={() => setQuickReport({ ing: i, status: 'het' })}>Hết</Btn>
                          )}
                          {i.status !== 'du' && (
                            <Btn size="sm" kind="ghost" onClick={() => sendStatus(i.id, 'du', 'Chủ quán cập nhật đủ')}>Đủ</Btn>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="row" style={{ gap: 6 }}>
                          <Btn size="sm" onClick={() => openEditIngredient(i)}>Sửa</Btn>
                          <Btn size="sm" kind="danger" onClick={() => removeIngredient(i)}>Xóa</Btn>
                        </div>
                      </td>
                    </tr>
                  ))}
                </Table>
              </Card>
            </div>
          )}
        </>
      )}

      {/* MODAL THÊM NGUYÊN LIỆU MỚI */}
      {adding && (
        <Modal title="Thêm nguyên liệu mới vào danh mục" onClose={() => setAdding(false)}>
          <div className="stack">
            <Field label="Tên nguyên liệu"><input className="input" autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="Ví dụ: Bột ca cao, Siro vani" /></Field>
            <Field label="Đơn vị tính"><input className="input" value={unit} onChange={e => setUnit(e.target.value)} placeholder="kg, hộp, chai, lon, gói…" /></Field>
            <div className="row spread" style={{ marginTop: 12 }}>
              <Btn onClick={() => setAdding(false)}>Hủy</Btn>
              <Btn kind="primary" disabled={!name.trim()} onClick={addIngredient}>Thêm nguyên liệu</Btn>
            </div>
          </div>
        </Modal>
      )}

      {/* MODAL SỬA NGUYÊN LIỆU */}
      {editingIng && (
        <Modal title={`Sửa nguyên liệu: ${editingIng.name}`} onClose={() => setEditingIng(null)}>
          <div className="stack">
            <Field label="Tên nguyên liệu">
              <input className="input" autoFocus value={editName} onChange={e => setEditName(e.target.value)} placeholder="Tên nguyên liệu" />
            </Field>
            <Field label="Đơn vị tính">
              <input className="input" value={editUnit} onChange={e => setEditUnit(e.target.value)} placeholder="kg, hộp, chai, lon, gói…" />
            </Field>
            <div className="row spread" style={{ marginTop: 12 }}>
              <Btn onClick={() => setEditingIng(null)}>Hủy</Btn>
              <Btn kind="primary" disabled={!editName.trim()} onClick={saveEditIngredient}>Lưu thay đổi</Btn>
            </div>
          </div>
        </Modal>
      )}

      {/* MODAL BÁO NHANH CHO CHỦ QUÁN */}
      {quickReport && (
        <Modal title={`${quickReport.status === 'het' ? 'Báo hết' : 'Báo sắp hết'}: ${quickReport.ing.name}`} onClose={() => setQuickReport(null)}>
          <div className="stack">
            <Field label="Ghi chú số lượng còn lại / chi tiết">
              <input className="input" autoFocus value={quickNote} onChange={e => setQuickNote(e.target.value)} placeholder="Ví dụ: Chỉ còn khoảng 2 túi" />
            </Field>
            <div className="row spread" style={{ marginTop: 12 }}>
              <Btn onClick={() => setQuickReport(null)}>Hủy</Btn>
              <Btn kind="primary" onClick={() => sendStatus(quickReport.ing.id, quickReport.status, quickNote)}>Xác nhận</Btn>
            </div>
          </div>
        </Modal>
      )}
    </Page>
  )
}
