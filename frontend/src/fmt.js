export const money = (n) => (n === null || n === undefined) ? '—' : new Intl.NumberFormat('vi-VN').format(Math.round(n)) + ' ₫'
export const num = (n) => new Intl.NumberFormat('vi-VN').format(n)
export const pad = (n) => String(n).padStart(2, '0')
export const isoDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
export const todayIso = () => isoDate(new Date())
export const monthOf = (iso) => iso.slice(0, 7)
export const thisMonth = () => monthOf(todayIso())
export const shiftMonth = (m, delta) => { const [y, mo] = m.split('-').map(Number); const d = new Date(y, mo - 1 + delta, 1); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}` }
export const monthLabel = (m) => { const [y, mo] = m.split('-'); return `Tháng ${Number(mo)}/${y}` }
export const dmy = (iso) => { if (!iso) return ''; const [y, m, d] = iso.slice(0, 10).split('-'); return `${d}/${m}/${y}` }
export const dm = (iso) => { const [, m, d] = iso.slice(0, 10).split('-'); return `${d}/${m}` }
const WD = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7']
export const weekday = (iso) => { const [y, m, d] = iso.split('-').map(Number); return WD[new Date(y, m - 1, d).getDay()] }
export const isWeekend = (iso) => { const w = weekday(iso); return w === 'CN' || w === 'T7' }
export const dateTime = (iso) => { if (!iso) return ''; const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}` }
export const SHIFT = { sang: 'Sáng', trua: 'Trưa', toi: 'Tối' }
export const SHIFTS = ['sang', 'trua', 'toi']
export const DOC_TYPES = { hoa_don: 'Hóa đơn', bien_lai_viet_tay: 'Biên lai viết tay', khong_chung_tu: 'Không chứng từ' }
export const daysOfMonth = (m) => { const [y, mo] = m.split('-').map(Number); const n = new Date(y, mo, 0).getDate(); return Array.from({ length: n }, (_, i) => `${m}-${pad(i + 1)}`) }
export const digits = (s) => Number(String(s).replace(/[^\d-]/g, '')) || 0
export const checkPasswordRules = (pw = '') => {
  const minLen = pw.length > 8
  const hasUpper = /[A-Z]/.test(pw)
  const hasLower = /[a-z]/.test(pw)
  const hasDigit = /[0-9]/.test(pw)
  const hasSpecial = /[^A-Za-z0-9]/.test(pw)
  return { minLen, hasUpper, hasLower, hasDigit, hasSpecial, ok: minLen && hasUpper && hasLower && hasDigit && hasSpecial }
}
