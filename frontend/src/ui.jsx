import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { checkPasswordRules, monthLabel, shiftMonth } from './fmt.js'

/* ---------- thông báo nhanh ---------- */
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((text, kind = 'ok') => {
    const id = Math.random()
    setItems(x => [...x, { id, text, kind }])
    setTimeout(() => setItems(x => x.filter(i => i.id !== id)), kind === 'bad' ? 6000 : 3200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map(i => <div key={i.id} className={'toast ' + i.kind}>{i.text}</div>)}
      </div>
    </ToastCtx.Provider>
  )
}

/* ---------- tải dữ liệu ---------- */
export function useLoad(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const seq = useRef(0)
  const reload = useCallback(async () => {
    const my = ++seq.current
    setState(s => ({ ...s, loading: true, error: null }))
    try { const data = await fn(); if (my === seq.current) setState({ data, error: null, loading: false }) }
    catch (e) { if (my === seq.current) setState({ data: null, error: e.message, loading: false }) }
  }, deps) // eslint-disable-line
  useEffect(() => { reload() }, [reload])
  return { ...state, reload }
}

/* ---------- thành phần Card có nút thu gọn/mở rộng ▾ ---------- */
export const Card = ({ title, action, children, className = '', defaultOpen = true, collapsible = false }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  // Nếu có title và bật collapsible hoặc có dấu ▾ trong title
  const hasCollapse = collapsible || (typeof title === 'string' && (title.includes('▾') || title.includes('▼')))
  const displayTitle = typeof title === 'string' ? title.replace(/[▾▼]/g, '').trim() : title

  return (
    <section className={'card ' + className}>
      {(title || action) && (
        <div className="card-header row spread" style={{ marginBottom: isOpen ? 12 : 0 }}>
          <div className="row" style={{ gap: 8, cursor: hasCollapse ? 'pointer' : 'default' }} onClick={() => hasCollapse && setIsOpen(!isOpen)}>
            {title && <h2>{displayTitle}</h2>}
            {hasCollapse && (
              <span className="card-toggle" title={isOpen ? 'Thu gọn' : 'Mở rộng'} style={{ fontSize: '0.9rem', color: 'var(--muted)', userSelect: 'none' }}>
                {isOpen ? '▾' : '▸'}
              </span>
            )}
          </div>
          {action}
        </div>
      )}
      {(!hasCollapse || isOpen) && <div className="card-body">{children}</div>}
    </section>
  )
}

export const Btn = ({ kind = '', size = '', busy, children, ...p }) => (
  <button className={`btn ${kind} ${size}`} disabled={busy || p.disabled} {...p}>{busy ? 'Đang xử lý…' : children}</button>
)

export const Field = ({ label, hint, children }) => (
  <div className="field">{label && <label>{label}</label>}{children}{hint && <span className="hint">{hint}</span>}</div>
)

export const Badge = ({ kind = '', children }) => <span className={'badge ' + kind}>{children}</span>

export function PasswordRulesHint({ password = '' }) {
  const r = checkPasswordRules(password)
  const items = [
    [r.minLen, 'Trên 8 ký tự (tối thiểu 9 ký tự)'],
    [r.hasUpper, 'Có ít nhất 1 chữ hoa (A-Z)'],
    [r.hasLower, 'Có ít nhất 1 chữ thường (a-z)'],
    [r.hasDigit, 'Có ít nhất 1 chữ số (0-9)'],
    [r.hasSpecial, 'Có ít nhất 1 ký tự đặc biệt (!@#$%...)'],
  ]
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '4px 10px', fontSize: '.78rem', padding: '8px 10px', borderRadius: 10, background: 'var(--soft)', border: '1px solid var(--line)' }}>
      {items.map(([ok, label]) => (
        <div key={label} style={{ color: ok ? 'var(--ok)' : 'var(--muted)', fontWeight: ok ? 650 : 400 }}>
          {ok ? '✓' : '○'} {label}
        </div>
      ))}
    </div>
  )
}

/* C1: Khắc phục khoảng trắng thừa và tách cột flex trong hộp ghi chú / notice */
export const Notice = ({ kind = 'info', children, className = '', style }) => (
  <div className={`notice ${kind} ${className}`} style={style}>
    <div className="notice-body">{children}</div>
  </div>
)

export const Empty = ({ title, children }) => <div className="empty"><b>{title}</b>{children}</div>
export const Loading = () => <div className="empty">Đang tải…</div>
export const ErrorBox = ({ message, onRetry }) => (
  <Notice kind="bad">
    <div className="row spread" style={{ gap: 10 }}>
      <div className="grow">{message}</div>
      {onRetry && <Btn size="sm" onClick={onRetry}>Thử lại</Btn>}
    </div>
  </Notice>
)

export const Tabs = ({ value, onChange, items }) => (
  <div className="tabs" role="tablist">{items.map(([k, label]) => (
    <button key={k} role="tab" aria-selected={value === k} className={value === k ? 'on' : ''} onClick={() => onChange(k)}>{label}</button>
  ))}</div>
)

export function Page({ title, sub, actions, children }) {
  return (
    <div className="page">
      <div className="page-head">
        <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
        {actions && <div className="row no-print page-actions">{actions}</div>}
      </div>
      <div className="stack">{children}</div>
    </div>
  )
}

export function MonthPicker({ value, onChange }) {
  return (
    <div className="month-picker row no-print" style={{ gap: 4 }}>
      <Btn size="sm" kind="ghost" aria-label="Tháng trước" onClick={() => onChange(shiftMonth(value, -1))}>◀</Btn>
      <b style={{ minWidth: 120, textAlign: 'center' }}>{monthLabel(value)}</b>
      <Btn size="sm" kind="ghost" aria-label="Tháng sau" onClick={() => onChange(shiftMonth(value, 1))}>▶</Btn>
    </div>
  )
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const h = e => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div className="modal-back" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="row spread modal-header" style={{ marginBottom: 14 }}>
          <h2>{title}</h2>
          <Btn size="sm" kind="ghost" onClick={onClose} aria-label="Đóng">✕</Btn>
        </div>
        <div className="modal-content">{children}</div>
      </div>
    </div>
  )
}

/* Bottom Sheet trượt từ dưới lên cho tính năng mở rộng theo Wireframe III.2 */
export function BottomSheet({ title, onClose, children }) {
  useEffect(() => {
    const h = e => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div className="bottom-sheet-back" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bottom-sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="bottom-sheet-header row spread">
          <h2>{title}</h2>
          <Btn size="sm" kind="ghost" onClick={onClose} aria-label="Đóng">✕</Btn>
        </div>
        <div className="bottom-sheet-body">{children}</div>
      </div>
    </div>
  )
}

export const Toggle = ({ checked, onChange, children }) => (
  <label className="toggle"><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} /><span className="sw" />{children}</label>
)

/* Ô nhập tiền tự động định dạng VNĐ */
export function MoneyInput({ value, onChange, big, ...p }) {
  const shown = value === '' || value === null || value === undefined ? '' : new Intl.NumberFormat('vi-VN').format(value)
  return (
    <input
      className={'input ' + (big ? 'big-input' : '')}
      inputMode="numeric"
      value={shown}
      placeholder="0"
      onChange={e => {
        const raw = e.target.value.replace(/[^\d-]/g, '')
        onChange(raw === '' || raw === '-' ? '' : Number(raw))
      }}
      {...p}
    />
  )
}

export function Table({ head, children, foot, empty }) {
  return (
    <div className="table-wrap">
      <table className="t">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i} className={h?.num ? 'num' : ''}>{h?.label ?? h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
        {foot && <tfoot>{foot}</tfoot>}
      </table>
      {empty}
    </div>
  )
}
