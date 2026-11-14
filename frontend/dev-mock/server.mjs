// API GIẢ để chạy/kiểm thử giao diện khi chưa có backend: `node dev-mock/server.mjs` (cổng 8010).
// Chỉ phục vụ phát triển giao diện; không phải backend thật, dữ liệu là giả lập và nằm trong bộ nhớ.
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'

const PORT = Number(process.env.PORT || 8010)
const STATIC = process.env.STATIC_DIR || ''
const pad = n => String(n).padStart(2, '0')
const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const now = new Date(), TODAY = iso(now), MONTH = TODAY.slice(0, 7)
const daysOf = m => { const [y, mo] = m.split('-').map(Number); return Array.from({ length: new Date(y, mo, 0).getDate() }, (_, i) => `${m}-${pad(i + 1)}`) }
const SH = ['sang', 'trua', 'toi']
const emps = [1, 2, 3, 4].map(i => ({ id: i, display_name: 'Nhân viên ' + 'ABCD'[i - 1], is_active: true }))
const users = [{ id: 1, username: 'chuquan', display_name: 'Chủ quán (demo)', role: 'owner', is_active: true, employee_id: null },
  ...emps.map(e => ({ id: e.id + 1, username: 'nv' + 'ABCD'[e.id - 1], display_name: e.display_name, role: 'staff', is_active: true, employee_id: e.id }))]
const S = { settings: { duty_require_schedule: false, cluster_fairness_slack: 1, max_shifts_per_day: 2, shop_name: 'Cửa hàng A' },
  published: { [MONTH]: true }, assigns: [], nextId: 100, handovers: [], purchases: [], expenses: [], swaps: [], ings: [], ingHistory: [], rates: { rate_a: 22000, rate_b: 25000 }, locked: {},
  shifts: [{ code: 'sang', name: 'Sáng', hours: 5.5, start_time: '06:30', end_time: '12:00', capacity: 1 }, { code: 'trua', name: 'Trưa', hours: 5.5, start_time: '12:00', end_time: '17:30', capacity: 1 }, { code: 'toi', name: 'Tối', hours: 4, start_time: '17:30', end_time: '21:30', capacity: 1 }] }
daysOf(MONTH).forEach((d, i) => SH.forEach((s, j) => S.assigns.push({ id: S.nextId++, work_date: d, shift_code: s, employee_id: ((i + j) % 4) + 1, source: 'import' })))
;['Sữa tươi:hộp:31000', 'Trà nhài:kg:180000', 'Đường:kg:22000'].forEach((x, i) => { const [n, u, p] = x.split(':'); S.ings.push({ id: i + 1, name: n, unit: u, is_active: true, last_price: +p, last_price_unit: u, last_purchase_date: TODAY, status: i === 0 ? 'sap_het' : 'du', status_note: i === 0 ? 'Còn 4 hộp tại tủ mát' : '', status_at: now.toISOString(), status_by_name: i === 0 ? 'Nhân viên A' : '' }) })
S.ingHistory.push({ id: 1, ingredient_id: 1, ingredient: 'Sữa tươi', ingredient_name: 'Sữa tươi', unit: 'hộp', status: 'sap_het', note: 'Còn 4 hộp tại tủ mát', reported_by_name: 'Nhân viên A', created_by_name: 'Nhân viên A', reported_at: now.toISOString(), created_at: now.toISOString() })
S.expenses.push({ id: 1, expense_date: `${MONTH}-01`, category: 'co_dinh', item: 'Tiền thuê mặt bằng', amount: 8000000, note: '' })
S.purchases.push({ id: 1, purchase_date: TODAY, supplier: 'NCC Sữa Mẫu', doc_type: 'hoa_don', discount: 0, total_amount: 744000, note: '', created_by: 2, created_by_name: 'Nhân viên A', shift_code: null, out_of_schedule: false, items: [{ ingredient: 'Sữa tươi', quantity: 24, unit: 'hộp', unit_price: 31000, line_total: 744000 }], attachments: [] })
S.swaps.push({ id: 1, kind: 'full_swap', work_date: TODAY, shift_code: 'toi', from_employee_id: 3, from_name: 'Nhân viên C', to_employee_id: 4, to_name: 'Nhân viên D', counter_date: null, counter_shift: null, from_time: null, to_time: null, reason: 'Việc gia đình', status: 'pending', requested_at: now.toISOString(), decision_note: '', decided_at: null })
S.swaps.push({ id: 2, kind: 'partial_cover', work_date: TODAY, shift_code: 'sang', from_employee_id: 1, from_name: 'Nhân viên A', to_employee_id: 2, to_name: 'Nhân viên B', counter_date: null, counter_shift: null, from_time: '09:00', to_time: '11:00', reason: 'Đi khám', status: 'approved', requested_at: now.toISOString(), decision_note: '', decided_at: now.toISOString() })

const who = req => { const m = /t06_session=(\w+)/.exec(req.headers.cookie || ''); return m ? users.find(u => u.username === ({ owner: 'chuquan', staff: 'nvA' })[m[1]]) : null }
const send = (res, code, data, headers = {}) => { const body = typeof data === 'string' || Buffer.isBuffer(data) ? data : JSON.stringify(data); res.writeHead(code, { 'Content-Type': typeof data === 'string' || Buffer.isBuffer(data) ? (headers.ct || 'text/plain') : 'application/json', ...headers }); res.end(body) }
const readBody = req => new Promise(r => { const c = []; req.on('data', x => c.push(x)); req.on('end', () => r(Buffer.concat(c))) })
const sum = (a, f) => a.reduce((s, x) => s + f(x), 0)
const dailyRevenue = month => daysOf(month).map((d, i) => ({ date: d, revenue: d <= TODAY ? 1200000 + ((i * 137) % 9) * 150000 : 0, orders: d <= TODAY ? 18 + (i % 7) : 0 }))
const pnl = month => { const rev = sum(dailyRevenue(month), d => d.revenue), ing = sum(S.purchases, p => p.total_amount), exp = sum(S.expenses, e => e.amount), pay = payroll(month).total
  return { month, revenue: rev, ingredients: ing, payroll: pay, fixed: exp, other: 0, total_cost: ing + pay + exp, profit: rev - ing - pay - exp, complete: rev > 0, missing: rev > 0 ? [] : ['doanh thu POS (chưa đồng bộ/nạp)'], payroll_locked: !!S.locked[month] } }
const payroll = month => { const rows = emps.map(e => { const a = S.assigns.filter(x => x.employee_id === e.id && x.work_date.startsWith(month)); const n = k => a.filter(x => x.shift_code === k).length
  return { employee_id: e.id, name: e.display_name, n_sang: n('sang'), n_trua: n('trua'), n_toi: n('toi'), amount: Math.round(S.rates.rate_a * 5.5 * n('sang') + S.rates.rate_b * 5.5 * n('trua') + S.rates.rate_b * 4 * n('toi')) } }).filter(r => r.n_sang + r.n_trua + r.n_toi)
  return { rows, total: sum(rows, r => r.amount) } }

async function route(req, res, url) {
  const p = url.pathname.replace(/^\/api/, ''), q = url.searchParams, m = req.method, me = who(req)
  const body = ['POST', 'PUT', 'PATCH'].includes(m) ? await readBody(req) : null
  const json = () => { try { return JSON.parse(body.toString() || '{}') } catch { return {} } }
  if (p === '/meta') return send(res, 200, { app_mode: process.env.MOCK_LIVE ? 'live' : 'demo', is_live: !!process.env.MOCK_LIVE, flags: { E01_ROLES: true, E02_AUTH: true, E03_AUDIT: true, E04_SHIFT_TAG: true, E05_EXPORT: true, E09_QR_ATTENDANCE: true, E13_AUTO_DRAFT: true }, needs_setup: !!process.env.MOCK_SETUP, shop_name: 'Cửa hàng A', pos365_configured: false })
  if (p === '/auth/quick-login' && m === 'POST') { const b = json(); const u = users.find(x => x.username === b.username); if (!u) return send(res, 404, { detail: 'Không tìm thấy tài khoản' }); const role = u.role === 'owner' ? 'owner' : 'staff'; return send(res, 200, u, { 'Set-Cookie': `t06_session=${role}; Path=/; HttpOnly` }) }
  if (p === '/auth/login' && m === 'POST') { const b = json(); const role = b.username === 'chuquan' ? 'owner' : b.username === 'nvA' ? 'staff' : null
    if (!role || b.password !== 'demo12345') return send(res, 401, { detail: 'Sai tên đăng nhập hoặc mật khẩu' }); return send(res, 200, users.find(u => u.username === b.username), { 'Set-Cookie': `t06_session=${role}; Path=/; HttpOnly` }) }
  if (p === '/auth/setup' && m === 'POST') return send(res, 200, { id: 1 }, { 'Set-Cookie': 't06_session=owner; Path=/' })
  if (p === '/auth/logout') return send(res, 200, { ok: true }, { 'Set-Cookie': 't06_session=; Path=/; Max-Age=0' })
  if (!me) return send(res, 401, { detail: 'Chưa đăng nhập' })
  const owner = me.role === 'owner'
  if (p === '/auth/me') return send(res, 200, me)
  if (p === '/revenue/daily') { const d = dailyRevenue(q.get('month')); return send(res, 200, { month: q.get('month'), days: d, total: sum(d, x => x.revenue), orders: sum(d, x => x.orders) }) }
  if (p === '/pnl/' + MONTH || /^\/pnl\/\d{4}-\d{2}$/.test(p)) return send(res, 200, pnl(p.split('/')[2]))
  if (/\/pnl\/.*\/reconcile/.test(p)) { const r = pnl(p.split('/')[2]); return send(res, 200, { rows: Object.fromEntries(['revenue', 'ingredients', 'payroll', 'fixed', 'other'].map(k => [k, { system: r[k], manual: null, diff: null }])) }) }
  if (p === '/pos/sync-logs') return send(res, 200, [{ id: 1, kind: 'file', file_name: 'chi_tiet_doanh_thu_mock.xlsx', started_at: now.toISOString(), rows_read: 248, rows_inserted: 248, rows_duplicate: 0, reconcile_ok: true, status: 'ok' }])
  if (p === '/pos/import-sample') return send(res, 200, { status: 'ok', rows_read: 248, rows_inserted: 0, rows_updated: 0, rows_duplicate: 248, rows_skipped_total: 2, reconcile_ok: true, reconcile: { ok: true }, warnings: ['File này đã từng được nạp (kết quả không bị nhân đôi nhờ chống trùng mã chứng từ)'] })
  if (p === '/swap-requests' && m === 'GET') { let r = S.swaps; if (q.get('status')) r = r.filter(x => x.status === q.get('status')); if (!owner) r = r.filter(x => x.from_employee_id === me.employee_id || x.to_employee_id === me.employee_id); return send(res, 200, r) }
  if (p === '/swap-requests' && m === 'POST') { const b = json(); const r = { id: S.nextId++, kind: b.kind, work_date: b.work_date, shift_code: b.shift_code, from_employee_id: me.employee_id, from_name: me.display_name, to_employee_id: b.to_employee_id, to_name: emps.find(e => e.id === b.to_employee_id)?.display_name, counter_date: b.counter_date || null, counter_shift: b.counter_shift || null, from_time: b.from_time, to_time: b.to_time, reason: b.reason, status: 'pending', requested_at: new Date().toISOString(), decision_note: '', decided_at: null }; S.swaps.unshift(r); return send(res, 200, r) }
  let mm = /^\/swap-requests\/(\d+)\/(approve|reject|cancel)$/.exec(p)
  if (mm) { const r = S.swaps.find(x => x.id === +mm[1]); if (r.status !== 'pending') return send(res, 409, { detail: 'Yêu cầu đã ở trạng thái ' + r.status }); r.status = { approve: 'approved', reject: 'rejected', cancel: 'cancelled' }[mm[2]]
    if (mm[2] === 'approve' && r.kind === 'full_swap') { const a = S.assigns.find(x => x.work_date === r.work_date && x.shift_code === r.shift_code); if (a) a.employee_id = r.to_employee_id } return send(res, 200, r) }
  if (p === '/ingredient-status/open') return send(res, 200, S.ings.filter(i => i.status !== 'du').map(i => ({ ingredient_id: i.id, ingredient: i.name, ingredient_name: i.name, unit: i.unit, status: i.status, note: i.status_note, reported_by_name: i.status_by_name || 'Nhân viên A', created_by_name: i.status_by_name || 'Nhân viên A', reported_at: i.status_at, created_at: i.status_at, out_of_schedule: false })))
  if (p === '/ingredient-status/history') return send(res, 200, S.ingHistory)
  if (p === '/ingredient-status' && m === 'POST') { const b = json(); const i = S.ings.find(x => x.id === b.ingredient_id); i.status = b.status; i.status_note = b.note || ''; i.status_at = new Date().toISOString(); i.status_by_name = me.display_name; S.ingHistory.unshift({ id: S.nextId++, ingredient_id: i.id, ingredient: i.name, ingredient_name: i.name, unit: i.unit, status: b.status, note: b.note || '', reported_by_name: me.display_name, created_by_name: me.display_name, reported_at: i.status_at, created_at: i.status_at }); return send(res, 200, { ok: true, out_of_schedule: false }) }
  if (p === '/ingredients' && m === 'GET') return send(res, 200, S.ings)
  if (p === '/ingredients' && m === 'POST') { const b = json(); const id = S.nextId++; S.ings.push({ id, name: b.name, unit: b.unit, is_active: true, last_price: null, last_price_unit: null, last_purchase_date: null, status: 'du', status_note: '', status_at: null, status_by_name: '' }); return send(res, 200, { id }) }
  mm = /^\/ingredients\/(\d+)$/.exec(p)
  if (mm && m === 'PUT') { const b = json(); const i = S.ings.find(x => x.id === +mm[1]); if (i) { i.name = b.name; i.unit = b.unit }; return send(res, 200, { ok: true }) }
  if (mm && m === 'DELETE') { S.ings = S.ings.filter(x => x.id !== +mm[1]); return send(res, 200, { ok: true }) }
  if (p === '/handovers/ref') return send(res, 200, { date: q.get('date'), pos_revenue_ref: 1850000 })
  if (p === '/handovers' && m === 'GET') return send(res, 200, S.handovers)
  if (p === '/handovers' && m === 'POST') { const b = json(); const h = { id: S.nextId++, ...b, status: b.submit ? 'submitted' : 'draft', pos_revenue_ref: 1850000, giver_id: me.id, giver_name: me.display_name, receiver_name: '', expected_receiver_name: 'Chủ quán', unlocked_by_owner: false, out_of_schedule: me.role === 'staff' && !S.assigns.some(a => a.work_date === b.business_date && a.employee_id === me.employee_id) }; S.handovers.unshift(h); return send(res, 200, h) }
  mm = /^\/handovers\/(\d+)$/.exec(p)
  if (mm && m === 'PUT') { const b = json(); const h = S.handovers.find(x => x.id === +mm[1]); if (h) { Object.assign(h, b); if (b.submit) { h.status = 'submitted'; h.unlocked_by_owner = false } } return send(res, 200, h) }
  mm = /^\/handovers\/(\d+)\/(confirm|unlock|submit)$/.exec(p)
  if (mm) { const h = S.handovers.find(x => x.id === +mm[1]); const b = json(); if (mm[2] === 'confirm') { if (b.action === 'review') { h.status = 'draft'; h.unlocked_by_owner = true; h.receiver_name = '' } else { h.status = 'confirmed'; h.receiver_name = me.display_name } } if (mm[2] === 'submit') { h.status = 'submitted'; h.unlocked_by_owner = false } if (mm[2] === 'unlock') { h.unlocked_by_owner = true; h.status = 'draft'; h.receiver_name = '' } return send(res, 200, h) }
  if (p === '/purchases/summary') return send(res, 200, { month: q.get('month'), total: sum(S.purchases, x => x.total_amount), count: S.purchases.length, by_supplier: [{ supplier: 'NCC Sữa Mẫu', total: sum(S.purchases, x => x.total_amount), count: S.purchases.length }] })
  if (p === '/purchases' && m === 'GET') return send(res, 200, S.purchases)
  if (p === '/purchases' && m === 'POST') { const b = json(); const items = b.items.map(i => ({ ingredient: i.ingredient_name, quantity: i.quantity, unit: i.unit, unit_price: i.unit_price, line_total: Math.round(i.quantity * i.unit_price) })); const r = { id: S.nextId++, purchase_date: b.purchase_date, supplier: b.supplier_name, doc_type: b.doc_type, discount: b.discount, total_amount: sum(items, i => i.line_total) - b.discount, note: b.note, created_by: me.id, created_by_name: me.display_name, out_of_schedule: false, items, attachments: [], warnings: [] }; S.purchases.unshift(r); return send(res, 200, r) }
  mm = /^\/purchases\/(\d+)$/.exec(p)
  if (mm && m === 'PUT') { const b = json(); const r = S.purchases.find(x => x.id === +mm[1]); if (r) { const items = b.items.map(i => ({ ingredient: i.ingredient_name, quantity: i.quantity, unit: i.unit, unit_price: i.unit_price, line_total: Math.round(i.quantity * i.unit_price) })); Object.assign(r, { purchase_date: b.purchase_date, supplier: b.supplier_name, doc_type: b.doc_type, discount: b.discount, total_amount: sum(items, i => i.line_total) - b.discount, note: b.note, items }) } return send(res, 200, r) }
  if (mm && m === 'DELETE') { S.purchases = S.purchases.filter(x => x.id !== +mm[1]); return send(res, 200, { ok: true }) }
  if (p === '/schedules/template.xlsx') return send(res, 200, Buffer.from('PK-mock'), { ct: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename="mau.xlsx"' })
  mm = /^\/schedules\/(\d{4}-\d{2})$/.exec(p)
  if (mm) { const pub = !!S.published[mm[1]]; const rows = owner || pub ? S.assigns.filter(a => a.work_date.startsWith(mm[1])).map(a => ({ ...a, employee_name: emps.find(e => e.id === a.employee_id).display_name })) : []
    return send(res, 200, { month: mm[1], status: pub ? 'published' : 'draft', my_employee_id: me.employee_id, shift_types: S.shifts, employees: emps, assignments: rows }) }
  mm = /^\/schedules\/(\d{4}-\d{2})\/(publish|unpublish|auto-draft|cell|import)$/.exec(p)
  if (mm) { if (mm[2] === 'publish') S.published[mm[1]] = true; if (mm[2] === 'unpublish') S.published[mm[1]] = false
    if (mm[2] === 'auto-draft') return send(res, 200, { assigned: 12, unassigned: [{ date: TODAY, shift: 'toi' }], counts: {} })
    if (mm[2] === 'import') { const txt = body.toString('latin1'); if (txt.includes('Ngoc Anh') && !txt.includes('"Ngoc Anh":')) return send(res, 200, { needs_mapping: true, unmapped: [{ name: 'Ngoc Anh', suggestions: [2] }], employees: emps, layout: 'grid' }); return send(res, 200, { needs_mapping: false, layout: 'grid', imported: 90, skipped_other_month: 0, errors: [], over_capacity: [] }) }
    if (mm[2] === 'cell') { const b = json(); S.assigns = S.assigns.filter(a => !(a.work_date === b.work_date && a.shift_code === b.shift_code)); b.employee_ids.forEach(id => S.assigns.push({ id: S.nextId++, work_date: b.work_date, shift_code: b.shift_code, employee_id: id, source: 'owner' })); return send(res, 200, { ok: true, warning: null }) }
    return send(res, 200, { ok: true }) }
  if (p === '/availability') return send(res, 200, p && m === 'PUT' ? { ok: true, saved: 1 } : { month: q.get('month'), locked: false, items: [] })
  mm = /^\/payroll\/(\d{4}-\d{2})$/.exec(p)
  if (mm) { const r = payroll(mm[1]); const rows = owner ? r.rows : r.rows.filter(x => x.employee_id === me.employee_id); return send(res, 200, { month: mm[1], locked: !!S.locked[mm[1]], rate_a: S.rates.rate_a, rate_b: S.rates.rate_b, rate_a_at_lock: S.locked[mm[1]] ? S.rates.rate_a : null, rate_b_at_lock: S.locked[mm[1]] ? S.rates.rate_b : null, rate_configured: true, rows, total: sum(rows, x => x.amount), flags: S.swaps.filter(s => s.kind === 'partial_cover' && s.status === 'approved').map(s => ({ work_date: s.work_date, shift_code: s.shift_code, from_employee_id: s.from_employee_id, from_name: s.from_name, cover_employee_id: s.to_employee_id, cover_name: s.to_name, from_time: s.from_time, to_time: s.to_time, reason: s.reason })) }) }
  mm = /^\/payroll\/(\d{4}-\d{2})\/lock$/.exec(p); if (mm) { S.locked[mm[1]] = m === 'POST'; return send(res, 200, { ok: true }) }
  if (p === '/expenses' && m === 'GET') return send(res, 200, S.expenses)
  if (p === '/expenses' && m === 'POST') { const b = json(); const e = { id: S.nextId++, ...b }; S.expenses.unshift(e); return send(res, 200, e) }
  if (p === '/settings') return m === 'PUT' ? (Object.assign(S.settings, json()), send(res, 200, { ok: true })) : send(res, 200, S.settings)
  if (p === '/shift-types') return m === 'PUT' ? (S.shifts = json(), send(res, 200, { ok: true })) : send(res, 200, S.shifts)
  if (p === '/pay-rates') return (m === 'PUT' || m === 'POST') ? (Object.assign(S.rates, json()), send(res, 200, { ok: true, ...S.rates })) : send(res, 200, S.rates)
  if (p === '/employees') return send(res, 200, emps)
  if (p === '/users') return send(res, 200, users)
  if (p === '/audit') return send(res, 200, [{ id: 1, at: now.toISOString(), username: 'chuquan', action: 'approve', entity: 'swap_request', entity_id: '2', old_value: { status: 'pending' }, new_value: { status: 'approved', kind: 'partial_cover' } }])
  if (p === '/attendance/qr') return send(res, 200, { token: 't', url: 'http://x/attendance/scan?t=t', svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#fff"/><rect x="1" y="1" width="3" height="3"/><rect x="6" y="1" width="3" height="3"/><rect x="1" y="6" width="3" height="3"/></svg>', refresh_seconds: 50 })
  if (p === '/attendance/scan') return send(res, 200, { kind: 'in', out_of_schedule: true })
  if (p === '/attendance') return send(res, 200, [])
  return send(res, 200, { ok: true })
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x')
  try {
    if (url.pathname.startsWith('/api/')) return await route(req, res, url)
    if (STATIC) { let f = path.join(STATIC, url.pathname === '/' ? 'index.html' : url.pathname); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(STATIC, 'index.html')
      const ext = path.extname(f); return send(res, 200, fs.readFileSync(f), { ct: { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css' }[ext] || 'application/octet-stream' }) }
    send(res, 404, 'not found')
  } catch (e) { send(res, 500, { detail: String(e) }) }
}).listen(PORT, () => console.log('Mock API http://localhost:' + PORT))
