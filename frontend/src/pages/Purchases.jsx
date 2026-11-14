import { useRef, useState } from 'react'
import { get, post, put, del, upload } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Loading, Modal, MoneyInput, Notice, Page, Table, useLoad, useToast } from '../ui.jsx'
import { DOC_TYPES, dmy, money, todayIso } from '../fmt.js'

const newItem = () => ({ ingredient_name: '', quantity: '', unit: '', unit_price: '' })
const lineTotal = it => Math.round((Number(it.quantity) || 0) * (Number(it.unit_price) || 0))

function PurchaseFormInline({ ingredients, suppliers, onSaved }) {
  const toast = useToast()
  const photo = useRef()
  const maxDate = todayIso()
  const blank = () => ({ purchase_date: maxDate, supplier_name: '', doc_type: 'hoa_don', discount: '', note: '', items: [newItem()] })
  const [f, setF] = useState(blank())
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const set = k => v => setF(x => ({ ...x, [k]: v }))
  const setItem = (i, k, v) => setF(x => ({ ...x, items: x.items.map((it, j) => j === i ? { ...it, [k]: v } : it) }))
  const pickIngredient = (i, name) => {
    const ing = ingredients.find(g => g.name.toLowerCase() === name.trim().toLowerCase())
    setF(x => ({ ...x, items: x.items.map((it, j) => j === i ? { ...it, ingredient_name: name, unit: it.unit || ing?.unit || '', unit_price: it.unit_price === '' && ing?.last_price ? ing.last_price : it.unit_price } : it) }))
  }
  const sum = f.items.reduce((s, it) => s + lineTotal(it), 0)
  const total = sum - (Number(f.discount) || 0)
  const valid = f.items.every(it => it.ingredient_name.trim() && Number(it.quantity) > 0 && it.unit_price !== '') && total >= 0 && f.purchase_date <= maxDate

  const save = async () => {
    if (f.purchase_date > maxDate) {
      toast('Ngày nhập hàng không được vượt quá ngày hiện tại', 'bad')
      return
    }
    setBusy(true)
    const body = {
      purchase_date: f.purchase_date,
      supplier_name: f.supplier_name,
      doc_type: f.doc_type,
      discount: Number(f.discount) || 0,
      note: f.note,
      items: f.items.map(it => ({ ingredient_name: it.ingredient_name.trim(), quantity: Number(it.quantity), unit: it.unit, unit_price: Number(it.unit_price) }))
    }
    try {
      const r = await post('/purchases', body)
      for (const file of files) {
        const a = await upload(`/purchases/${r.id}/attachments`, file)
        if (a.warning) toast(a.warning, 'bad')
      }
      ;(r.warnings || []).forEach(w => toast(w, 'bad'))
      toast('Đã ghi nhận phiếu nhập hàng')
      setF(blank())
      setFiles([])
      if (photo.current) photo.current.value = ''
      onSaved()
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Ghi nhận phiếu nhập hàng" subtitle="Nhân viên nhận hàng thực tế và ghi ngay vào ca">
      <div className="stack">
        <div className="grid2">
          <Field label="Ngày nhập">
            <input
              className="input"
              type="date"
              max={maxDate}
              value={f.purchase_date}
              onChange={e => set('purchase_date')(e.target.value)}
            />
          </Field>
          <Field label="Loại chứng từ"><select className="select" value={f.doc_type} onChange={e => set('doc_type')(e.target.value)}>{Object.entries(DOC_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        </div>
        <Field label="Nhà cung cấp"><input className="input" list="sup-list-inline" value={f.supplier_name} onChange={e => set('supplier_name')(e.target.value)} placeholder="Để trống nếu mua lẻ tại chợ/siêu thị" />
          <datalist id="sup-list-inline">{suppliers.map(s => <option key={s} value={s} />)}</datalist>
        </Field>
        <div className="stack-sm">
          <div className="row spread"><span className="lbl">Danh mục hàng nhập</span><span className="muted small">Tạm tính: {money(sum)}</span></div>
          {f.items.map((it, i) => (
            <div key={i} className="card flat tight stack-sm" style={{ background: 'var(--bg-subtle)' }}>
              <input className="input" list="ing-list-inline" placeholder="Tên nguyên liệu (hạt cà phê, sữa tươi...)" value={it.ingredient_name} onChange={e => pickIngredient(i, e.target.value)} />
              <div className="grid3">
                <input className="input" inputMode="decimal" placeholder="Số lượng" value={it.quantity} onChange={e => setItem(i, 'quantity', e.target.value.replace(',', '.'))} />
                <input className="input" placeholder="Đơn vị (kg, hộp...)" value={it.unit} onChange={e => setItem(i, 'unit', e.target.value)} />
                <MoneyInput value={it.unit_price} onChange={v => setItem(i, 'unit_price', v)} placeholder="Đơn giá" />
              </div>
              <div className="row spread">
                <span className="muted small">Thành tiền: <b>{money(lineTotal(it))}</b></span>
                {f.items.length > 1 && <Btn size="sm" kind="ghost" onClick={() => setF(x => ({ ...x, items: x.items.filter((_, j) => j !== i) }))}>Xóa món</Btn>}
              </div>
            </div>
          ))}
          <datalist id="ing-list-inline">{ingredients.map(g => <option key={g.id} value={g.name} />)}</datalist>
          <Btn size="sm" onClick={() => setF(x => ({ ...x, items: [...x.items, newItem()] }))}>+ Thêm dòng hàng</Btn>
        </div>
        <div className="grid2">
          <Field label="Chiết khấu (nếu có)"><MoneyInput value={f.discount} onChange={set('discount')} /></Field>
          <Field label="Tổng thanh toán"><div className="big-input input" style={{ display: 'flex', alignItems: 'center', fontWeight: 'bold', color: 'var(--pri)' }}>{money(total)}</div></Field>
        </div>
        <Field label="Ghi chú"><input className="input" value={f.note} onChange={e => set('note')(e.target.value)} placeholder="Ví dụ: Giao hàng đợt 1, thiếu 2 hộp" /></Field>
        <Field label="Ảnh hóa đơn / biên lai nhận hàng" hint="JPG, PNG hoặc WEBP, tối đa 8 MB">
          <input ref={photo} className="input" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={e => setFiles([...e.target.files])} />
        </Field>
        <Btn kind="primary" busy={busy} disabled={!valid} onClick={save} style={{ width: '100%', padding: '12px' }}>Lưu phiếu nhập</Btn>
      </div>
    </Card>
  )
}

function FormModal({ initial, ingredients, suppliers, onClose, onSaved }) {
  const toast = useToast()
  const photo = useRef()
  const maxDate = todayIso()
  const [f, setF] = useState(initial)
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const set = k => v => setF(x => ({ ...x, [k]: v }))
  const setItem = (i, k, v) => setF(x => ({ ...x, items: x.items.map((it, j) => j === i ? { ...it, [k]: v } : it) }))
  const pickIngredient = (i, name) => {
    const ing = ingredients.find(g => g.name.toLowerCase() === name.trim().toLowerCase())
    setF(x => ({ ...x, items: x.items.map((it, j) => j === i ? { ...it, ingredient_name: name, unit: it.unit || ing?.unit || '', unit_price: it.unit_price === '' && ing?.last_price ? ing.last_price : it.unit_price } : it) }))
  }
  const sum = f.items.reduce((s, it) => s + lineTotal(it), 0)
  const total = sum - (Number(f.discount) || 0)
  const valid = f.items.every(it => it.ingredient_name.trim() && Number(it.quantity) > 0 && it.unit_price !== '') && total >= 0 && f.purchase_date <= maxDate

  const save = async () => {
    if (f.purchase_date > maxDate) {
      toast('Ngày nhập hàng không được vượt quá ngày hiện tại', 'bad')
      return
    }
    setBusy(true)
    const body = {
      purchase_date: f.purchase_date,
      supplier_name: f.supplier_name,
      doc_type: f.doc_type,
      discount: Number(f.discount) || 0,
      note: f.note,
      items: f.items.map(it => ({ ingredient_name: it.ingredient_name.trim(), quantity: Number(it.quantity), unit: it.unit, unit_price: Number(it.unit_price) }))
    }
    try {
      const r = f.id ? await put('/purchases/' + f.id, body) : await post('/purchases', body)
      for (const file of files) {
        const a = await upload(`/purchases/${r.id}/attachments`, file)
        if (a.warning) toast(a.warning, 'bad')
      }
      ;(r.warnings || []).forEach(w => toast(w, 'bad'))
      toast('Đã lưu phiếu nhập')
      onSaved()
    } catch (e) {
      toast(e.message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={f.id ? 'Sửa phiếu nhập' : 'Phiếu nhập hàng'} onClose={onClose}>
      <div className="stack">
        <div className="grid2">
          <Field label="Ngày nhập">
            <input
              className="input"
              type="date"
              max={maxDate}
              value={f.purchase_date}
              onChange={e => set('purchase_date')(e.target.value)}
            />
          </Field>
          <Field label="Loại chứng từ"><select className="select" value={f.doc_type} onChange={e => set('doc_type')(e.target.value)}>{Object.entries(DOC_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        </div>
        <Field label="Nhà cung cấp"><input className="input" list="sup-list" value={f.supplier_name} onChange={e => set('supplier_name')(e.target.value)} placeholder="Để trống nếu mua lẻ" />
          <datalist id="sup-list">{suppliers.map(s => <option key={s} value={s} />)}</datalist></Field>
        <div className="stack-sm">
          <span className="lbl">Hàng nhập</span>
          {f.items.map((it, i) => (
            <div key={i} className="card flat tight stack-sm">
              <input className="input" list="ing-list" placeholder="Tên nguyên liệu" value={it.ingredient_name} onChange={e => pickIngredient(i, e.target.value)} />
              <div className="grid3">
                <input className="input" inputMode="decimal" placeholder="Số lượng" value={it.quantity} onChange={e => setItem(i, 'quantity', e.target.value.replace(',', '.'))} />
                <input className="input" placeholder="Đơn vị" value={it.unit} onChange={e => setItem(i, 'unit', e.target.value)} />
                <MoneyInput value={it.unit_price} onChange={v => setItem(i, 'unit_price', v)} placeholder="Đơn giá" />
              </div>
              <div className="row spread"><span className="muted small">Thành tiền: <b>{money(lineTotal(it))}</b></span>
                {f.items.length > 1 && <Btn size="sm" kind="ghost" onClick={() => setF(x => ({ ...x, items: x.items.filter((_, j) => j !== i) }))}>Xóa dòng</Btn>}</div>
            </div>
          ))}
          <datalist id="ing-list">{ingredients.map(g => <option key={g.id} value={g.name} />)}</datalist>
          <Btn size="sm" onClick={() => setF(x => ({ ...x, items: [...x.items, newItem()] }))}>+ Thêm dòng hàng</Btn>
        </div>
        <div className="grid2">
          <Field label="Chiết khấu (nếu có)"><MoneyInput value={f.discount} onChange={set('discount')} /></Field>
          <Field label="Tổng thanh toán"><div className="big-input input" style={{ display: 'flex', alignItems: 'center' }}>{money(total)}</div></Field>
        </div>
        <Field label="Ghi chú"><textarea className="input" value={f.note} onChange={e => set('note')(e.target.value)} /></Field>
        <Field label="Ảnh hóa đơn / biên lai (tùy chọn)" hint="JPG, PNG hoặc WEBP, tối đa 8 MB mỗi ảnh">
          <input ref={photo} className="input" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={e => setFiles([...e.target.files])} />
        </Field>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Btn onClick={onClose}>Hủy</Btn><Btn kind="primary" busy={busy} disabled={!valid} onClick={save}>Lưu phiếu</Btn></div>
      </div>
    </Modal>
  )
}

function PurchaseDetailModal({ purchase, onClose, onEdit, onDelete, canManage }) {
  if (!purchase) return null
  return (
    <Modal title={`Chi tiết phiếu nhập #${purchase.id}`} onClose={onClose}>
      <div className="stack">
        <div className="grid2">
          <div><span className="muted small">Ngày nhập:</span> <b>{dmy(purchase.purchase_date)}</b></div>
          <div><span className="muted small">Loại chứng từ:</span> <Badge>{DOC_TYPES[purchase.doc_type]}</Badge></div>
          <div><span className="muted small">Nhà cung cấp:</span> <b>{purchase.supplier || 'Mua lẻ'}</b></div>
          <div><span className="muted small">Người lập:</span> <b>{purchase.created_by_name || '—'}</b></div>
        </div>

        {purchase.out_of_schedule && <Notice kind="warn">Phiếu được lập ngoài lịch phân công.</Notice>}
        {purchase.note && <div className="card flat tight" style={{ background: 'var(--bg-subtle)' }}><span className="muted small">Ghi chú:</span> {purchase.note}</div>}

        <Table head={['Mặt hàng', { label: 'Số lượng', num: 1 }, { label: 'Đơn giá', num: 1 }, { label: 'Thành tiền', num: 1 }]}>
          {purchase.items.map((it, idx) => (
            <tr key={idx}>
              <td><b>{it.ingredient}</b></td>
              <td className="num">{it.quantity} {it.unit}</td>
              <td className="num">{money(it.unit_price)}</td>
              <td className="num"><b>{money(it.quantity * it.unit_price)}</b></td>
            </tr>
          ))}
          {purchase.discount > 0 && (
            <tr>
              <td colSpan="3" className="num">Chiết khấu:</td>
              <td className="num">− {money(purchase.discount)}</td>
            </tr>
          )}
          <tr style={{ fontWeight: 'bold' }}>
            <td colSpan="3">Tổng thanh toán:</td>
            <td className="num" style={{ color: 'var(--pri)', fontSize: '1.1rem' }}>{money(purchase.total_amount)}</td>
          </tr>
        </Table>

        {purchase.attachments && purchase.attachments.length > 0 && (
          <div className="stack-sm">
            <span className="lbl">Ảnh chứng từ ({purchase.attachments.length})</span>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              {purchase.attachments.map(a => (
                <a key={a.id} href={`/api/purchases/${purchase.id}/attachments/${a.id}`} target="_blank" rel="noreferrer">
                  <img alt="Chứng từ" src={`/api/purchases/${purchase.id}/attachments/${a.id}`} style={{ height: 80, borderRadius: 8, border: '1px solid var(--line)' }} />
                </a>
              ))}
            </div>
          </div>
        )}

        <div className="row spread" style={{ marginTop: 12 }}>
          {canManage ? (
            <div className="row" style={{ gap: 8 }}>
              <Btn size="sm" onClick={() => { onClose(); onEdit(purchase) }}>Sửa phiếu</Btn>
              <Btn size="sm" kind="danger" onClick={() => { onClose(); onDelete(purchase) }}>Xóa</Btn>
            </div>
          ) : <div />}
          <Btn onClick={onClose}>Đóng</Btn>
        </div>
      </div>
    </Modal>
  )
}

export default function Purchases() {
  const { me, currentMonth: month } = useApp()
  const toast = useToast()
  const owner = me.role === 'owner'
  const [form, setForm] = useState(null)
  const [selectedPurchase, setSelectedPurchase] = useState(null)
  const [ocrNotice, setOcrNotice] = useState(false)

  const list = useLoad(() => get('/purchases?month=' + month), [month])
  const sum = useLoad(() => get('/purchases/summary?month=' + month), [month])
  const ings = useLoad(() => get('/ingredients'), [])
  const suppliers = [...new Set((list.data || []).map(p => p.supplier).filter(Boolean))]

  const blank = () => ({ purchase_date: todayIso(), supplier_name: '', doc_type: 'hoa_don', discount: '', note: '', items: [newItem()] })
  const edit = p => setForm({
    id: p.id,
    purchase_date: p.purchase_date,
    supplier_name: p.supplier,
    doc_type: p.doc_type,
    discount: p.discount || '',
    note: p.note,
    items: p.items.map(i => ({ ingredient_name: i.ingredient, quantity: i.quantity, unit: i.unit, unit_price: i.unit_price }))
  })

  const remove = async p => {
    if (!confirm('Xóa phiếu nhập này?')) return
    try {
      await del('/purchases/' + p.id)
      toast('Đã xóa phiếu nhập')
      list.reload()
      sum.reload()
    } catch (e) {
      toast(e.message, 'bad')
    }
  }

  const handleOcrClick = () => {
    toast('Chưa triển khai, chờ nhóm thống nhất', 'bad')
    setOcrNotice(true)
  }

  return (
    <Page
      title="Nhập hàng & Kho"
      sub="Ghi nhận từng lần nhập ngay khi nhận hàng. Chi phí tự động tổng hợp vào báo cáo lãi/lỗ."
      actions={
        <div className="row" style={{ gap: 8 }}>
          {owner && <Btn kind="primary" onClick={() => setForm(blank())}>+ Thêm phiếu nhập</Btn>}
          <Btn onClick={handleOcrClick} title="Tính năng thử nghiệm">📷 Quét hóa đơn AI</Btn>
        </div>
      }
    >
      {ocrNotice && (
        <Notice kind="warn">
          Tính năng <b>quét hóa đơn bằng AI (OCR)</b> chưa triển khai, chờ nhóm thống nhất. Vui lòng ghi nhận phiếu nhập bằng biểu mẫu thủ công.
          <div style={{ marginTop: 6 }}><Btn size="sm" onClick={() => setOcrNotice(false)}>Đã hiểu</Btn></div>
        </Notice>
      )}

      {owner && sum.data && (
        <div className="grid3">
          <Card className="tight">
            <div className="kpi">
              <span className="l">Chi phí nguyên liệu tháng</span>
              <span className="v" style={{ color: 'var(--pri)' }}>{money(sum.data.total)}</span>
            </div>
          </Card>
          <Card className="tight">
            <div className="kpi">
              <span className="l">Số phiếu nhập</span>
              <span className="v">{sum.data.count}</span>
            </div>
          </Card>
          <Card className="tight">
            <div className="kpi">
              <span className="l">Nhà cung cấp lớn nhất</span>
              <span className="v" style={{ fontSize: '1.05rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {sum.data.by_supplier[0]?.supplier || '—'}
              </span>
            </div>
          </Card>
        </div>
      )}

      {!owner ? (
        <div className="grid2" style={{ alignItems: 'start' }}>
          <div>
            <PurchaseFormInline
              ingredients={ings.data || []}
              suppliers={suppliers}
              onSaved={() => { list.reload(); sum.reload(); ings.reload() }}
            />
          </div>
          <div>
            <Card title="Các lần nhập gần đây" subtitle="Bấm vào để xem chi tiết, hoặc Sửa / Xóa phiếu do bạn lập">
              {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> :
                list.data.length === 0 ? <Empty title="Chưa có phiếu nhập trong tháng" /> : (
                  <div className="stack-sm">
                    {list.data.slice(0, 10).map(p => {
                      const canManage = owner || p.created_by === me.id || p.created_by_name === me.display_name
                      return (
                        <div
                          key={p.id}
                          className="card flat tight stack-sm"
                          style={{ cursor: 'pointer', border: '1px solid var(--line)' }}
                          onClick={() => setSelectedPurchase(p)}
                        >
                          <div className="row spread">
                            <div>
                              <b>{dmy(p.purchase_date)}</b> · {p.supplier || 'Mua lẻ'}
                              <div className="muted small">Người lập: <b>{p.created_by_name || '—'}</b></div>
                              <div style={{ marginTop: 2 }}>
                                <Badge>{DOC_TYPES[p.doc_type]}</Badge>
                                {p.out_of_schedule && <Badge kind="warn">Ngoài lịch</Badge>}
                                {p.attachments.length > 0 && <Badge kind="info">📷 {p.attachments.length}</Badge>}
                              </div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              <b className="num" style={{ fontSize: '1.05rem', display: 'block' }}>{money(p.total_amount)}</b>
                              {canManage && (
                                <div className="row" style={{ gap: 6, marginTop: 6, justifyContent: 'flex-end' }} onClick={e => e.stopPropagation()}>
                                  <Btn size="sm" onClick={() => edit(p)}>Sửa</Btn>
                                  <Btn size="sm" kind="danger" onClick={() => remove(p)}>Xóa</Btn>
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="muted small" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {p.items.map(i => `${i.ingredient} (${i.quantity} ${i.unit})`).join(' · ')}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
            </Card>
          </div>
        </div>
      ) : (
        <Card title="Danh sách phiếu nhập hàng" subtitle="Bấm vào dòng để xem chi tiết, mặt hàng và ảnh chứng từ">
          {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> :
            list.data.length === 0 ? <Empty title="Chưa có phiếu nhập trong tháng này" /> : (
              <Table head={['Ngày', 'Nhà cung cấp / Nguồn', 'Chứng từ', 'Mặt hàng chính', { label: 'Tổng tiền', num: 1 }, 'Thao tác']}>
                {list.data.map(p => (
                  <tr key={p.id} style={{ cursor: 'pointer' }} onClick={() => setSelectedPurchase(p)}>
                    <td><b>{dmy(p.purchase_date)}</b></td>
                    <td>
                      <b>{p.supplier || 'Mua lẻ'}</b>
                      <div className="muted small">Lập bởi: {p.created_by_name || '—'}</div>
                    </td>
                    <td>
                      <Badge>{DOC_TYPES[p.doc_type]}</Badge>
                      {p.out_of_schedule && <Badge kind="warn">Ngoài lịch</Badge>}
                      {p.attachments.length > 0 && <Badge kind="info">📷 {p.attachments.length}</Badge>}
                    </td>
                    <td style={{ maxWidth: 260, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {p.items.map(i => `${i.ingredient} (${i.quantity} ${i.unit})`).join(', ')}
                    </td>
                    <td className="num"><b>{money(p.total_amount)}</b></td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="row" style={{ gap: 6 }}>
                        <Btn size="sm" onClick={() => edit(p)}>Sửa</Btn>
                        <Btn size="sm" kind="danger" onClick={() => remove(p)}>Xóa</Btn>
                      </div>
                    </td>
                  </tr>
                ))}
              </Table>
            )}
        </Card>
      )}

      {selectedPurchase && (
        <PurchaseDetailModal
          purchase={selectedPurchase}
          onClose={() => setSelectedPurchase(null)}
          onEdit={p => edit(p)}
          onDelete={p => remove(p)}
          canManage={owner || selectedPurchase.created_by === me.id || selectedPurchase.created_by_name === me.display_name}
        />
      )}

      {form && (
        <FormModal
          initial={form}
          ingredients={ings.data || []}
          suppliers={suppliers}
          onClose={() => setForm(null)}
          onSaved={() => { setForm(null); list.reload(); sum.reload(); ings.reload() }}
        />
      )}
    </Page>
  )
}