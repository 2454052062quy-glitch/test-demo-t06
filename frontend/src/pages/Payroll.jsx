import { useState } from 'react'
import { get, post, put, del } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Loading, Modal, MoneyInput, Notice, Page, Table, useLoad, useToast } from '../ui.jsx'
import { SHIFT, dateTime, dm, money, weekday } from '../fmt.js'

export default function Payroll() {
  const { me, currentMonth: month } = useApp()
  const toast = useToast()
  const owner = me.role === 'owner'
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [rateA, setRateA] = useState('')
  const [rateB, setRateB] = useState('')

  const p = useLoad(() => get('/payroll/' + month), [month])

  const act = (fn, msg) => async () => {
    try {
      await fn()
      toast(msg)
      p.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const openConfig = () => {
    setRateA(p.data?.rate_a ?? '')
    setRateB(p.data?.rate_b ?? '')
    setShowConfigModal(true)
  }

  const saveRates = async () => {
    const aVal = Number(rateA) || 0
    const bVal = Number(rateB) || 0
    if (aVal <= 0 || bVal <= 0) {
      toast('Vui lòng nhập mức lương a và b lớn hơn 0', 'bad')
      return
    }
    try {
      await put('/pay-rates', { rate_a: aVal, rate_b: bVal })
      toast('Đã cập nhật đơn giá lương a & b')
      setShowConfigModal(false)
      p.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const d = p.data
  const activeRateA = d?.locked ? (d?.rate_a_at_lock || d?.rate_a) : d?.rate_a
  const activeRateB = d?.locked ? (d?.rate_b_at_lock || d?.rate_b) : d?.rate_b

  return (
    <Page
      title={owner ? 'Bảng tính Lương theo Ca' : 'Bảng Lương của tôi'}
      sub="Công thức: Lương = (a × 5,5h × ca sáng) + (b × 5,5h × ca trưa) + (b × 4,0h × ca tối). Tự động tính từ lịch ca phân công."
      actions={
        owner && (
          <div className="row" style={{ gap: 8 }}>
            <Btn onClick={openConfig}>⚙ Cấu hình đơn giá a & b</Btn>
          </div>
        )
      }
    >
      {p.loading && !p.data ? <Loading /> : p.error ? <ErrorBox message={p.error} onRetry={p.reload} /> : (
        <div className="stack">
          {d.note && <Notice kind="info">{d.note}</Notice>}
          {owner && d.rate_configured === false && (
            <Notice kind="warn">
              Chưa thiết lập mức lương a, b. Vui lòng bấm vào nút <b>"⚙ Cấu hình đơn giá a & b"</b> bên trên để nhập đơn giá.
            </Notice>
          )}

          <div className="card flat tight row spread" style={{ background: 'var(--bg-subtle)' }}>
            <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
              <Badge kind={d.locked ? 'ok' : 'warn'}>
                {d.locked ? `🔒 Đã chốt lương (${dateTime(d.locked_at)})` : '⚡ Đang tạm tính từ lịch ca'}
              </Badge>
              <span className="small">
                Đơn giá áp dụng: <b>a (sáng) = {money(activeRateA || 0)}/h</b> · <b>b (trưa/tối) = {money(activeRateB || 0)}/h</b>
                {d.locked && d.rate_a_at_lock && <span className="muted"> (đã khóa theo thời điểm chốt)</span>}
              </span>
            </div>

            {owner && (
              <div className="row" style={{ gap: 8 }}>
                {d.locked ? (
                  <Btn size="sm" onClick={act(() => del(`/payroll/${month}/lock`), 'Đã mở khóa bảng lương')}>
                    Mở khóa tính lại
                  </Btn>
                ) : (
                  <Btn
                    size="sm"
                    kind="primary"
                    disabled={!d.rows || d.rows.length === 0}
                    onClick={() => {
                      if (confirm('Chốt lương tháng này? Sau khi chốt, các đơn giá và lịch phân công của tháng sẽ được khóa cố định.')) {
                        act(() => post(`/payroll/${month}/lock`), 'Đã chốt bảng lương tháng')()
                      }
                    }}
                  >
                    🔒 Chốt bảng lương tháng
                  </Btn>
                )}
              </div>
            )}
          </div>

          {d.rows.length === 0 ? (
            <Card><Empty title="Chưa có ca làm việc nào được phân công trong tháng này" /></Card>
          ) : (
            <Card title={`Chi tiết lương nhân viên · Tháng ${month}`}>
              <Table
                head={[
                  'Nhân viên',
                  { label: 'Ca sáng (5,5h)', num: 1 },
                  { label: 'Ca trưa (5,5h)', num: 1 },
                  { label: 'Ca tối (4,0h)', num: 1 },
                  { label: 'Tổng giờ công', num: 1 },
                  { label: 'Đơn giá áp dụng', num: 1 },
                  { label: 'Thành tiền lương', num: 1 }
                ]}
                foot={
                  owner && (
                    <tr style={{ fontWeight: 'bold' }}>
                      <td>Tổng cộng ({d.rows.length} người)</td>
                      <td className="num">{d.rows.reduce((s, r) => s + r.n_sang, 0)} ca</td>
                      <td className="num">{d.rows.reduce((s, r) => s + r.n_trua, 0)} ca</td>
                      <td className="num">{d.rows.reduce((s, r) => s + r.n_toi, 0)} ca</td>
                      <td className="num">{d.rows.reduce((s, r) => s + (r.hours || (r.n_sang * 5.5 + r.n_trua * 5.5 + r.n_toi * 4.0)), 0)}h</td>
                      <td className="num">—</td>
                      <td className="num" style={{ color: 'var(--pri)', fontSize: '1.15rem' }}>{money(d.total)}</td>
                    </tr>
                  )
                }
              >
                {d.rows.map(r => {
                  const totalHours = r.hours || (r.n_sang * 5.5 + r.n_trua * 5.5 + r.n_toi * 4.0)
                  return (
                    <tr key={r.employee_id}>
                      <td><b>{r.name}</b></td>
                      <td className="num">{r.n_sang} ca</td>
                      <td className="num">{r.n_trua} ca</td>
                      <td className="num">{r.n_toi} ca</td>
                      <td className="num"><b>{totalHours}h</b></td>
                      <td className="num small muted">a={money(activeRateA)} | b={money(activeRateB)}</td>
                      <td className="num" style={{ fontSize: '1.05rem', color: 'var(--pri)' }}><b>{money(r.amount)}</b></td>
                    </tr>
                  )
                })}
              </Table>
            </Card>
          )}

          {d.flags && d.flags.length > 0 && (
            <Card title="Ghi chú điều chỉnh lương (Nhờ phụ giữa ca / vắng nửa ca)">
              <Notice kind="warn">
                Các sự vụ dưới đây đã được chủ quán duyệt nhưng <b>không tự động trừ lương trên hệ thống</b>.
                {owner ? ' Chủ quán vui lòng cộng/trừ chuyển khoản thủ công nếu có thỏa thuận.' : ' Chủ quán sẽ đối soát khi thanh toán lương.'}
              </Notice>
              <div className="stack-sm" style={{ marginTop: 12 }}>
                {d.flags.map((f, i) => (
                  <div key={i} className="card flat tight" style={{ border: '1px solid var(--line)' }}>
                    <b>{weekday(f.work_date)} {dm(f.work_date)} · Ca {SHIFT[f.shift_code]}</b>: {f.from_name} vắng
                    {(f.from_time || f.to_time) ? ` (${f.from_time || '…'}–${f.to_time || '…'})` : ''}, {f.cover_name} làm phụ thay.
                    {f.reason && <span className="muted"> Lý do: “{f.reason}”</span>}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {showConfigModal && (
        <Modal title="Cấu hình mức lương a & b theo giờ" onClose={() => setShowConfigModal(false)}>
          <div className="stack">
            <Notice kind="info">
              Mức lương áp dụng cho toàn quán. Ca sáng tính theo mức <b>a</b>; ca trưa và ca tối tính theo mức <b>b</b>.
            </Notice>
            <Field label="Mức lương a (₫/giờ, áp dụng cho ca sáng)">
              <MoneyInput big value={rateA} onChange={setRateA} placeholder="Ví dụ: 25.000" />
            </Field>
            <Field label="Mức lương b (₫/giờ, áp dụng cho ca trưa & tối)">
              <MoneyInput big value={rateB} onChange={setRateB} placeholder="Ví dụ: 28.000" />
            </Field>
            <div className="row spread" style={{ marginTop: 12 }}>
              <Btn onClick={() => setShowConfigModal(false)}>Hủy</Btn>
              <Btn kind="primary" onClick={saveRates}>Lưu thiết lập</Btn>
            </div>
          </div>
        </Modal>
      )}
    </Page>
  )
}