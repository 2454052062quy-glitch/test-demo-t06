import { useState } from 'react'
import { get, post, put, del } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Loading, Modal, MoneyInput, Notice, Page, Table, useLoad, useToast } from '../ui.jsx'
import { dmy, money, todayIso } from '../fmt.js'

const CAT = { co_dinh: 'Cố định (mặt bằng, điện, nước…)', phat_sinh: 'Phát sinh' }
const FIELDS = [
  ['revenue', 'Doanh thu (POS)'],
  ['ingredients', 'Chi phí nguyên liệu'],
  ['payroll', 'Chi phí nhân công (Lương)'],
  ['fixed', 'Chi phí cố định'],
  ['other', 'Chi phí phát sinh']
]

function ReconcileModal({ month, onClose }) {
  const toast = useToast()
  const r = useLoad(() => get(`/pnl/${month}/reconcile`), [month])
  const [vals, setVals] = useState(null)
  const cur = vals || Object.fromEntries(FIELDS.map(([k]) => [k, r.data?.rows[k].manual ?? '']))

  const save = async () => {
    try {
      await put(`/pnl/${month}/manual-reference`, Object.fromEntries(FIELDS.map(([k]) => [k, cur[k] === '' ? null : Number(cur[k])])))
      toast('Đã lưu số liệu đối chiếu tay')
      setVals(null)
      r.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  return (
    <Modal title={`Đối chiếu với sổ sách Excel · Tháng ${month}`} onClose={onClose}>
      <div className="stack">
        <Notice kind="info">Nhập số bạn tính tay bằng Excel để hệ thống tự động kiểm tra chênh lệch. Ô để trống nghĩa là chưa đối chiếu.</Notice>
        {r.loading && !r.data ? <Loading /> : r.error ? <ErrorBox message={r.error} onRetry={r.reload} /> : (
          <Table head={['Khoản mục', { label: 'Hệ thống', num: 1 }, { label: 'Bạn tính tay', num: 1 }, { label: 'Chênh lệch', num: 1 }]}>
            {FIELDS.map(([k, label]) => {
              const row = r.data.rows[k]
              const diff = cur[k] === '' ? null : row.system - Number(cur[k])
              return (
                <tr key={k}>
                  <td><b>{label}</b></td>
                  <td className="num">{money(row.system)}</td>
                  <td style={{ minWidth: 150 }}>
                    <MoneyInput value={cur[k]} onChange={v => setVals({ ...cur, [k]: v })} />
                  </td>
                  <td className="num">
                    {diff === null ? '—' : diff === 0 ? <Badge kind="ok">Khớp</Badge> : <Badge kind={diff > 0 ? 'info' : 'warn'}>{diff > 0 ? '+' : '−'}{money(Math.abs(diff))}</Badge>}
                  </td>
                </tr>
              )
            })}
          </Table>
        )}
        <div className="row spread" style={{ marginTop: 12 }}>
          <Btn onClick={onClose}>Đóng</Btn>
          <Btn kind="primary" onClick={save}>Lưu số liệu đối chiếu</Btn>
        </div>
      </div>
    </Modal>
  )
}

export default function Finance() {
  const { currentMonth: month } = useApp()
  const toast = useToast()
  const maxDate = todayIso()
  const [showReconcile, setShowReconcile] = useState(false)
  const [expenseForm, setExpenseForm] = useState(null)
  const [newExp, setNewExp] = useState({ expense_date: maxDate, category: 'co_dinh', item: '', amount: '', note: '' })
  const [busyAdd, setBusyAdd] = useState(false)

  const pnl = useLoad(() => get('/pnl/' + month), [month])
  const expList = useLoad(() => get('/expenses?month=' + month), [month])

  const totalExp = (expList.data || []).reduce((s, e) => s + e.amount, 0)

  const addExpenseQuick = async () => {
    if (!newExp.item.trim() || !(Number(newExp.amount) > 0)) return
    if (newExp.expense_date > maxDate) {
      toast('Ngày chi phí không được vượt quá ngày hiện tại', 'bad')
      return
    }
    setBusyAdd(true)
    try {
      await post('/expenses', { ...newExp, amount: Number(newExp.amount) })
      toast('Đã ghi nhận khoản chi')
      setNewExp({ expense_date: maxDate, category: 'co_dinh', item: '', amount: '', note: '' })
      expList.reload()
      pnl.reload()
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusyAdd(false)
    }
  }

  const saveEditedExpense = async () => {
    if (expenseForm.expense_date > maxDate) {
      toast('Ngày chi phí không được vượt quá ngày hiện tại', 'bad')
      return
    }
    try {
      const body = { ...expenseForm, amount: Number(expenseForm.amount) }
      await put('/expenses/' + expenseForm.id, body)
      toast('Đã cập nhật khoản chi')
      setExpenseForm(null)
      expList.reload()
      pnl.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const removeExpense = async e => {
    if (!confirm('Xóa khoản chi này?')) return
    try {
      await del('/expenses/' + e.id)
      toast('Đã xóa')
      expList.reload()
      pnl.reload()
    } catch (x) {
      toast(x.message, 'bad')
    }
  }

  const d = pnl.data
  const totalCost = d ? (d.ingredients + d.payroll + d.fixed + d.other) : 0

  return (
    <Page
      title="Quản lý Tài chính & Lãi/Lỗ"
      sub="Báo cáo lãi/lỗ tự động hợp nhất từ Doanh thu POS, Nhập hàng, Lịch ca lương và Chi phí cố định/phát sinh."
      actions={
        <div className="row" style={{ gap: 8 }}>
          <Btn onClick={() => setShowReconcile(true)}>🔍 Đối chiếu với Excel</Btn>
        </div>
      }
    >
      <div className="grid2" style={{ alignItems: 'start' }}>
        {/* CỘT TRÁI: ẨN KHI IN PDF (no-print) */}
        <div className="stack no-print">
          <Card title="Ghi nhận chi phí" subtitle="Chỉ ghi chi phí cố định (thuê mặt bằng, điện nước...) và phát sinh">
            <div className="stack-sm">
              <div className="grid2">
                <Field label="Ngày">
                  <input
                    className="input"
                    type="date"
                    max={maxDate}
                    value={newExp.expense_date}
                    onChange={e => setNewExp({ ...newExp, expense_date: e.target.value })}
                  />
                </Field>
                <Field label="Nhóm chi phí">
                  <select className="select" value={newExp.category} onChange={e => setNewExp({ ...newExp, category: e.target.value })}>
                    {Object.entries(CAT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </Field>
              </div>
              <Field label="Nội dung khoản chi">
                <input className="input" value={newExp.item} onChange={e => setNewExp({ ...newExp, item: e.target.value })} placeholder="Ví dụ: Tiền thuê mặt bằng, sửa máy pha cà phê" />
              </Field>
              <div className="grid2">
                <Field label="Số tiền"><MoneyInput value={newExp.amount} onChange={v => setNewExp({ ...newExp, amount: v })} placeholder="Số tiền (VNĐ)" /></Field>
                <Field label="Ghi chú"><input className="input" value={newExp.note} onChange={e => setNewExp({ ...newExp, note: e.target.value })} placeholder="Tùy chọn" /></Field>
              </div>
              <Btn
                kind="primary"
                busy={busyAdd}
                disabled={!newExp.item.trim() || !(Number(newExp.amount) > 0)}
                onClick={addExpenseQuick}
                style={{ width: '100%', padding: '10px' }}
              >
                + Lưu khoản chi
              </Btn>
            </div>
          </Card>

          <Card title="Sổ chi phí trong tháng" subtitle={`Tổng chi phí ghi nhận: ${money(totalExp)}`}>
            {expList.loading && !expList.data ? <Loading /> : expList.error ? <ErrorBox message={expList.error} onRetry={expList.reload} /> :
              expList.data.length === 0 ? <Empty title="Chưa có khoản chi nào trong tháng này" /> : (
                <Table
                  head={['Ngày', 'Nhóm', 'Nội dung', { label: 'Số tiền', num: 1 }, '']}
                  foot={<tr><td colSpan="3"><b>Tổng cộng</b></td><td className="num"><b>{money(totalExp)}</b></td><td /></tr>}
                >
                  {expList.data.map(e => (
                    <tr key={e.id}>
                      <td>{dmy(e.expense_date)}</td>
                      <td><Badge kind={e.category === 'co_dinh' ? 'info' : 'warn'}>{e.category === 'co_dinh' ? 'Cố định' : 'Phát sinh'}</Badge></td>
                      <td>
                        <b>{e.item}</b>
                        {e.note && <div className="muted small">{e.note}</div>}
                      </td>
                      <td className="num">{money(e.amount)}</td>
                      <td>
                        <div className="row" style={{ gap: 4 }}>
                          <Btn size="sm" onClick={() => setExpenseForm({ ...e })}>Sửa</Btn>
                          <Btn size="sm" kind="danger" onClick={() => removeExpense(e)}>Xóa</Btn>
                        </div>
                      </td>
                    </tr>
                  ))}
                </Table>
              )}
          </Card>
        </div>

        {/* CỘT PHẢI: BÁO CÁO LÃI/LỖ 7 DÒNG CHUẨN (HIỂN THỊ TRỌN VẸN KHI IN PDF) */}
        <div className="stack">
          {pnl.loading && !pnl.data ? <Loading /> : pnl.error ? <ErrorBox message={pnl.error} onRetry={pnl.reload} /> : (
            <Card
              title={`Báo cáo Lãi / Lỗ tháng ${month}`}
              subtitle={d.is_prorated ? `⚡ ${d.prorated_label} (Ước tính theo ${d.days_passed}/${d.total_days} ngày đã qua)` : 'Số liệu chốt đầy đủ cả tháng'}
            >
              {!d.complete && <Notice kind="warn">Chưa đủ dữ liệu: {d.missing.join(', ')}. Số liệu đang được tạm tính.</Notice>}

              <div className={'kpi ' + (d.profit >= 0 ? 'good' : 'bad')} style={{ margin: '8px 0 16px', padding: '16px', borderRadius: '12px', background: d.profit >= 0 ? 'rgba(46,125,50,0.08)' : 'rgba(211,47,47,0.08)' }}>
                <span className="l" style={{ fontSize: '1rem', fontWeight: 600 }}>{d.profit >= 0 ? 'LÃI THUẦN DỰ KIẾN' : 'LỖ THUẦN DỰ KIẾN'}</span>
                <span className="v" style={{ fontSize: '2.2rem', fontWeight: 'bold' }}>{money(Math.abs(d.profit))}</span>
                <span className="muted small">{d.is_prorated ? d.prorated_label : 'Đã kết chuyển'}</span>
              </div>

              <Table head={['#', 'Khoản mục tài chính', { label: 'Số tiền (VNĐ)', num: 1 }]}>
                <tr>
                  <td><b>1</b></td>
                  <td><b>Doanh thu (POS)</b></td>
                  <td className="num" style={{ color: 'var(--ok)', fontWeight: 'bold' }}>{money(d.revenue)}</td>
                </tr>
                <tr>
                  <td>2</td>
                  <td>Chi phí nguyên liệu (nhập hàng)</td>
                  <td className="num">− {money(d.ingredients)}</td>
                </tr>
                <tr>
                  <td>3</td>
                  <td>
                    Chi phí nhân công (Lương)
                    <div className="muted small">{d.payroll_locked ? 'Đã chốt lương' : (d.is_prorated ? 'Tạm tính pro-rate theo lịch ca' : 'Tạm tính từ lịch ca')}</div>
                  </td>
                  <td className="num">− {money(d.payroll)}</td>
                </tr>
                <tr>
                  <td>4</td>
                  <td>
                    Chi phí cố định (mặt bằng, điện, nước)
                    {d.is_prorated && <div className="muted small">Phân bổ theo số ngày đã qua</div>}
                  </td>
                  <td className="num">− {money(d.fixed)}</td>
                </tr>
                <tr>
                  <td>5</td>
                  <td>Chi phí phát sinh</td>
                  <td className="num">− {money(d.other)}</td>
                </tr>
                <tr style={{ background: 'var(--bg-subtle)', fontWeight: 'bold' }}>
                  <td><b>6</b></td>
                  <td><b>Tổng chi phí (2 + 3 + 4 + 5)</b></td>
                  <td className="num" style={{ color: 'var(--bad)' }}>− {money(totalCost)}</td>
                </tr>
                <tr style={{ background: d.profit >= 0 ? 'rgba(46,125,50,0.1)' : 'rgba(211,47,47,0.1)', fontWeight: 'bold', fontSize: '1.05rem' }}>
                  <td><b>7</b></td>
                  <td><b>LỢI NHUẬN THUẦN (1 − 6)</b></td>
                  <td className="num" style={{ color: d.profit >= 0 ? 'var(--ok)' : 'var(--bad)', fontSize: '1.15rem' }}>
                    {d.profit >= 0 ? '+' : '−'} {money(Math.abs(d.profit))}
                  </td>
                </tr>
              </Table>

              <div className="row spread no-print" style={{ marginTop: 16 }}>
                <div className="row" style={{ gap: 6 }}>
                  <a className="btn" href={`/api/export/pnl?month=${month}&fmt=xlsx`}>⬇ Xuất Excel</a>
                  <a className="btn" href={`/api/export/pnl?month=${month}&fmt=csv`}>⬇ Xuất CSV</a>
                </div>
                <Btn onClick={() => window.print()}>🖨 In / PDF</Btn>
              </div>
            </Card>
          )}
        </div>
      </div>

      {expenseForm && (
        <Modal title="Sửa khoản chi" onClose={() => setExpenseForm(null)}>
          <div className="stack">
            <div className="grid2">
              <Field label="Ngày">
                <input
                  className="input"
                  type="date"
                  max={maxDate}
                  value={expenseForm.expense_date}
                  onChange={e => setExpenseForm({ ...expenseForm, expense_date: e.target.value })}
                />
              </Field>
              <Field label="Nhóm"><select className="select" value={expenseForm.category} onChange={e => setExpenseForm({ ...expenseForm, category: e.target.value })}>{Object.entries(CAT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
            </div>
            <Field label="Nội dung"><input className="input" value={expenseForm.item} onChange={e => setExpenseForm({ ...expenseForm, item: e.target.value })} /></Field>
            <Field label="Số tiền"><MoneyInput big value={expenseForm.amount} onChange={v => setExpenseForm({ ...expenseForm, amount: v })} /></Field>
            <Field label="Ghi chú"><input className="input" value={expenseForm.note || ''} onChange={e => setExpenseForm({ ...expenseForm, note: e.target.value })} /></Field>
            <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
              <Btn onClick={() => setExpenseForm(null)}>Hủy</Btn>
              <Btn kind="primary" disabled={!expenseForm.item.trim() || !(Number(expenseForm.amount) > 0)} onClick={saveEditedExpense}>Lưu thay đổi</Btn>
            </div>
          </div>
        </Modal>
      )}

      {showReconcile && <ReconcileModal month={month} onClose={() => setShowReconcile(false)} />}
    </Page>
  )
}