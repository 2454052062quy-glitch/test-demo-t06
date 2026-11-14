import { useRef, useState } from 'react'
import { get, post, upload } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Loading, Modal, Notice, Page, Table, Tabs, useLoad, useToast } from '../ui.jsx'
import { dateTime, dm, money, num, weekday } from '../fmt.js'

/* TAB 1: DOANH THU THEO NGÀY */
function DailyTab({ onSelectDay }) {
  const { currentMonth } = useApp()
  const r = useLoad(() => get('/revenue/daily?month=' + currentMonth), [currentMonth])

  return (
    <div className="stack" style={{ gap: 16 }}>
      {r.loading && !r.data ? <Loading /> : r.error ? <ErrorBox message={r.error} onRetry={r.reload} /> : (
        <>
          <div className="grid3">
            <Card className="tight">
              <div className="kpi">
                <span className="l">Doanh thu tháng</span>
                <span className="v">{money(r.data.total)}</span>
              </div>
            </Card>
            <Card className="tight">
              <div className="kpi">
                <span className="l">Số đơn</span>
                <span className="v">{num(r.data.orders)}</span>
              </div>
            </Card>
            <Card className="tight">
              <div className="kpi">
                <span className="l">Trung bình mỗi đơn</span>
                <span className="v">{r.data.orders ? money(r.data.total / r.data.orders) : '—'}</span>
              </div>
            </Card>
          </div>

          <Card title={`Doanh thu Tháng ${currentMonth} ▾`} collapsible defaultOpen={true}>
            <Table
              head={['Ngày', { label: 'Hóa đơn', num: 1 }, { label: 'Doanh thu', num: 1 }, { label: 'Thao tác', num: 1 }]}
              foot={
                <tr>
                  <td><b>Tổng tháng</b></td>
                  <td className="num"><b>{num(r.data.orders)}</b></td>
                  <td className="num"><b>{money(r.data.total)}</b></td>
                  <td></td>
                </tr>
              }
            >
              {r.data.days.map(d => (
                <tr key={d.date}>
                  <td><b>{weekday(d.date)}</b> {dm(d.date)}</td>
                  <td className="num">{d.orders ? num(d.orders) : '—'}</td>
                  <td className="num">{d.revenue ? money(d.revenue) : '—'}</td>
                  <td className="num">
                    {d.orders > 0 ? (
                      <Btn size="sm" kind="ghost" onClick={() => onSelectDay(d.date)}>Xem hóa đơn →</Btn>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </Table>
          </Card>
        </>
      )}
    </div>
  )
}

/* TAB 2: DANH SÁCH HÓA ĐƠN CHI TIẾT (A1 - A4) */
function OrdersTab({ initialDay }) {
  const { currentMonth } = useApp()
  const [dayFilter, setDayFilter] = useState(initialDay || '')
  const [searchKw, setSearchKw] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [page, setPage] = useState(1)

  const url = `/pos/orders?month=${currentMonth}${dayFilter ? `&day=${dayFilter}` : ''}${sourceFilter ? `&source=${sourceFilter}` : ''}${searchKw ? `&q=${encodeURIComponent(searchKw)}` : ''}&page=${page}&page_size=25`
  const r = useLoad(() => get(url), [currentMonth, dayFilter, sourceFilter, searchKw, page])

  const clearFilters = () => {
    setDayFilter('')
    setSearchKw('')
    setSourceFilter('')
    setPage(1)
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      {/* Bộ lọc & Tìm kiếm */}
      <Card className="tight">
        <div className="row spread" style={{ gap: 12 }}>
          <div className="row" style={{ flex: 1, minWidth: 260 }}>
            <input
              className="input"
              placeholder="🔍 Tìm mã đơn hoặc tên bàn..."
              value={searchKw}
              onChange={e => { setSearchKw(e.target.value); setPage(1) }}
              style={{ minHeight: 38 }}
            />
          </div>
          <div className="row" style={{ gap: 8 }}>
            <input
              type="date"
              className="input"
              style={{ width: 'auto', minHeight: 38 }}
              value={dayFilter}
              onChange={e => { setDayFilter(e.target.value); setPage(1) }}
              title="Lọc theo ngày kinh doanh"
            />
            <select
              className="select"
              style={{ width: 'auto', minHeight: 38 }}
              value={sourceFilter}
              onChange={e => { setSourceFilter(e.target.value); setPage(1) }}
            >
              <option value="">Tất cả nguồn</option>
              <option value="api">Nguồn API</option>
              <option value="file">Nguồn File</option>
            </select>
            {(dayFilter || searchKw || sourceFilter) && (
              <Btn size="sm" kind="ghost" onClick={clearFilters}>Đặt lại</Btn>
            )}
          </div>
        </div>
      </Card>

      {/* Bảng 7 cột theo A2 */}
      <Card title="Danh sách hóa đơn chi tiết ▾" collapsible defaultOpen={true}>
        {r.loading && !r.data ? <Loading /> : r.error ? <ErrorBox message={r.error} onRetry={r.reload} /> :
          r.data?.orders?.length === 0 ? <Empty title="Không tìm thấy hóa đơn nào" /> : (
            <>
              <Table
                head={[
                  'Mã chứng từ',
                  'Giờ tạo (VN)',
                  'Ngày kinh doanh',
                  'Phòng/Bàn',
                  { label: 'Tổng cộng', num: 1 },
                  { label: 'Chiết khấu', num: 1 },
                  { label: 'Thanh toán', num: 1 },
                ]}
              >
                {r.data.orders.map(o => {
                  // A2: Chiết khấu ưu tiên Discount; nếu không có thì tính Tổng - Thanh toán
                  const discountVal = o.discount !== null && o.discount !== undefined
                    ? o.discount
                    : Math.max(0, o.total - o.paid)
                  return (
                    <tr key={o.id}>
                      <td>
                        <b>{o.doc_code}</b>
                        <span style={{ marginLeft: 6 }}>
                          <Badge kind={o.source === 'api' ? 'ok' : 'info'}>{o.source === 'api' ? 'API' : 'File'}</Badge>
                        </span>
                      </td>
                      <td>{o.created_at_vn || (o.created_at ? dateTime(o.created_at).split(' ')[1] : '—')}</td>
                      <td>{dm(o.business_date)}</td>
                      <td>
                        {o.table_name || '—'}
                        {o.guests ? <span className="muted small"> ({o.guests}k)</span> : ''}
                      </td>
                      <td className="num">{money(o.total)}</td>
                      <td className="num" style={{ color: discountVal > 0 ? 'var(--warn)' : 'var(--muted)' }}>
                        {discountVal > 0 ? `-${money(discountVal)}` : '0 đ'}
                      </td>
                      <td className="num"><b>{money(o.paid)}</b></td>
                    </tr>
                  )
                })}
              </Table>

              {/* Phân trang */}
              <div className="row spread" style={{ marginTop: 12, fontSize: '.88rem' }}>
                <span className="muted">
                  Hiển thị {(page - 1) * 25 + 1}–{Math.min(page * 25, r.data.total)} trong tổng số <b>{num(r.data.total)}</b> hóa đơn
                </span>
                <div className="row" style={{ gap: 6 }}>
                  <Btn size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Trước</Btn>
                  <span style={{ padding: '0 4px', fontWeight: 600 }}>Trang {page} / {r.data.pages}</span>
                  <Btn size="sm" disabled={page >= r.data.pages} onClick={() => setPage(page + 1)}>Sau ›</Btn>
                </div>
              </div>
            </>
          )}
        <p className="muted small" style={{ marginTop: 10, fontSize: '.78rem' }}>
          * Ghi chú: Chiết khấu ưu tiên lấy từ trường Discount của POS365; đối với đơn nạp từ file không có trường này, chiết khấu được tính bằng (Tổng cộng − Thanh toán).
        </p>
      </Card>
    </div>
  )
}

/* TAB 3: ĐỒNG BỘ & NẠP FILE (B1 - B5) */
function SyncTab() {
  const { meta } = useApp()
  const toast = useToast()
  const fileRef = useRef()

  const [syncStatus, setSyncStatus] = useState('idle') // idle | syncing | success | error
  const [syncError, setSyncError] = useState('')
  const [syncInfo, setSyncInfo] = useState(null)
  const [mockModal, setMockModal] = useState(false)

  const logs = useLoad(() => get('/pos/sync-logs'), [])

  const handleSync = async () => {
    setSyncStatus('syncing')
    setSyncError('')
    setSyncInfo(null)
    try {
      const res = await post('/pos/sync')
      setSyncInfo(res)
      setSyncStatus('success')
      toast('Đồng bộ dữ liệu POS365 hoàn tất!')
      logs.reload()
    } catch (err) {
      setSyncError(err.message)
      setSyncStatus('error')
      toast(err.message, 'bad')
    }
  }

  const handleFileUpload = async file => {
    if (!file) return
    try {
      const res = await upload('/pos/import', file)
      setSyncInfo(res)
      toast('Nạp file doanh thu thành công')
      logs.reload()
    } catch (err) {
      toast(err.message, 'bad')
    }
  }

  const handleSampleImport = async () => {
    try {
      const res = await post('/pos/import-sample')
      setSyncInfo(res)
      toast('Đã nạp file dữ liệu mẫu thành công')
      logs.reload()
    } catch (err) {
      toast(err.message, 'bad')
    }
  }

  // Mẫu JSON POS365 Mock
  const sampleMockJson = {
    __count: 15829,
    results: [
      {
        Id: 101234,
        Code: "HDMOCK-001234",
        PurchaseDate: "2026-11-13T10:24:15.0000000Z",
        Status: 2,
        Total: 95000.0,
        TotalPayment: 90000.0,
        Discount: 5000.0,
        Pos: "Bàn 3",
        RoomId: 102,
        NumberOfGuests: 3
      },
      {
        Id: 101235,
        Code: "HDMOCK-001235",
        PurchaseDate: "2026-11-13T11:05:30.0000000Z",
        Status: 2,
        Total: 45000.0,
        TotalPayment: 45000.0,
        Discount: 0.0,
        Pos: "Mang về",
        RoomId: null,
        NumberOfGuests: 1
      }
    ]
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      {/* 2 Khung công cụ: Đồng bộ API / Nạp File */}
      <div className="grid2">
        {/* Khung 1: Đồng bộ API */}
        <Card title={!meta.is_live ? "1. Đồng bộ từ Mock API POS365" : "1. Đồng bộ từ POS365"}>
          <p className="muted small" style={{ marginTop: 0 }}>
            Tự động lấy đơn từ mốc ngày quy định (mặc định đầu tháng trước), dừng ngay khi gặp đơn cũ, chống trùng mã đơn.
          </p>

          {!meta.pos365_configured && meta.is_live && (
            <Notice kind="warn" style={{ marginBottom: 12 }}>
              Chưa cấu hình POS365_BASE_URL. Vui lòng khai báo trong file cấu hình .env.live.
            </Notice>
          )}

          {/* B5: Trạng thái & Lỗi hiển thị ngay trong thẻ */}
          {syncStatus === 'syncing' && (
            <Notice kind="info" style={{ marginBottom: 12 }}>
              ⏳ <b>Đang đồng bộ...</b> Đang kết nối và nạp các đơn mới từ POS365.
            </Notice>
          )}

          {syncStatus === 'error' && syncError && (
            <Notice kind="bad" style={{ marginBottom: 12 }}>
              ❌ <b>Lỗi đồng bộ:</b> {syncError}
            </Notice>
          )}

          {syncStatus === 'success' && syncInfo && (
            <Notice kind="ok" style={{ marginBottom: 12 }}>
              ✅ <b>Đồng bộ thành công:</b> Đọc {num(syncInfo.rows_read)} dòng · Thêm {num(syncInfo.rows_inserted)} đơn mới · Trùng {num(syncInfo.rows_duplicate)}.
              {syncInfo.stopped_early && <div>⚠️ Đã dừng vì đạt giới hạn trang tối đa. Bấm đồng bộ lại để tiếp tục.</div>}
            </Notice>
          )}

          <div className="row" style={{ marginTop: 12, gap: 8 }}>
            <Btn
              kind="primary"
              busy={syncStatus === 'syncing'}
              disabled={syncStatus === 'syncing' || (!meta.pos365_configured && meta.is_live)}
              onClick={handleSync}
            >
              {syncStatus === 'syncing' ? 'Đang đồng bộ…' : 'Đồng bộ doanh thu mới'}
            </Btn>

            {!meta.is_live && (
              <Btn size="sm" kind="ghost" onClick={() => setMockModal(true)}>
                Xem phản hồi Mock API
              </Btn>
            )}
          </div>
        </Card>

        {/* Khung 2: Nạp file xuất từ POS365 */}
        <Card title="2. Nạp file xuất từ POS365 (.xlsx / .csv)">
          <p className="muted small" style={{ marginTop: 0 }}>
            Phương án dự phòng: xuất file "Chi tiết doanh thu" từ trang quản trị POS365 rồi tải lên đây.
          </p>

          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm,.csv"
            hidden
            onChange={e => {
              const f = e.target.files[0]
              e.target.value = ''
              if (f) handleFileUpload(f)
            }}
          />

          <div className="row" style={{ marginTop: 18, gap: 10 }}>
            <Btn kind="primary" onClick={() => fileRef.current?.click()}>
              📁 Chọn file từ máy…
            </Btn>

            {!meta.is_live && (
              <Btn onClick={handleSampleImport}>
                Nạp dữ liệu mẫu có sẵn
              </Btn>
            )}
          </div>
        </Card>
      </div>

      {/* Thanh thông báo trạng thái đồng bộ gần nhất */}
      {logs.data?.length > 0 && (
        <Card className="tight">
          <div className="row spread" style={{ fontSize: '.88rem' }}>
            <span>
              Lần đồng bộ gần nhất: <b>{dateTime(logs.data[0].started_at)}</b> ({logs.data[0].kind === 'api' ? 'API' : 'File'})
            </span>
            <span>
              Trạng thái:{' '}
              <Badge kind={logs.data[0].status === 'ok' ? 'ok' : logs.data[0].status === 'partial' ? 'warn' : 'bad'}>
                {logs.data[0].status === 'ok' ? 'Thành công' : logs.data[0].status === 'partial' ? 'Đã lấy 1 phần' : 'Lỗi'}
              </Badge>
            </span>
          </div>
        </Card>
      )}

      {/* B4: Nhật ký đồng bộ / nạp file */}
      <Card title="Nhật ký đồng bộ / nhập ▾" collapsible defaultOpen={true}>
        {logs.loading && !logs.data ? <Loading /> : logs.error ? <ErrorBox message={logs.error} onRetry={logs.reload} /> :
          logs.data?.length === 0 ? <Empty title="Chưa có lần đồng bộ nào" /> : (
            <Table head={['Thời điểm', 'Nguồn', { label: 'Đọc', num: 1 }, { label: 'Thêm mới', num: 1 }, { label: 'Trùng', num: 1 }, 'Trạng thái', 'Ghi chú / Lỗi']}>
              {logs.data.map(l => (
                <tr key={l.id}>
                  <td>{dateTime(l.started_at)}</td>
                  <td><b>{l.kind === 'api' ? 'API POS365' : (l.file_name || 'File')}</b></td>
                  <td className="num">{num(l.rows_read)}</td>
                  <td className="num" style={{ color: l.rows_inserted > 0 ? 'var(--ok)' : 'inherit' }}>+{num(l.rows_inserted)}</td>
                  <td className="num muted">{num(l.rows_duplicate)}</td>
                  <td>
                    <Badge kind={l.status === 'ok' ? 'ok' : l.status === 'partial' ? 'warn' : 'bad'}>
                      {l.status === 'ok' ? 'Hoàn tất' : l.status === 'partial' ? 'Chạm giới hạn' : 'Lỗi'}
                    </Badge>
                  </td>
                  <td className="small muted" style={{ maxWidth: 300, wordBreak: 'break-word' }}>
                    {l.error || (l.warnings?.length ? l.warnings[0] : '—')}
                  </td>
                </tr>
              ))}
            </Table>
          )}
      </Card>

      {/* Modal phản hồi Mock API (chỉ Demo) */}
      {mockModal && (
        <Modal title="Phản hồi từ Mock API POS365" onClose={() => setMockModal(false)}>
          <div className="stack">
            <p className="small muted">
              Cấu trúc JSON chuẩn trả về từ endpoint <code>/api/orders</code> của POS365 theo tài liệu tích hợp v1.0:
            </p>
            <pre style={{ background: 'var(--soft)', padding: 12, borderRadius: 10, fontSize: '.8rem', overflowX: 'auto', maxHeight: 360 }}>
              {JSON.stringify(sampleMockJson, null, 2)}
            </pre>
            <div className="row" style={{ justifyContent: 'flex-end', marginTop: 10 }}>
              <Btn kind="primary" onClick={() => setMockModal(false)}>Đóng</Btn>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default function Revenue() {
  const [tab, setTab] = useState('daily')
  const [selectedDay, setSelectedDay] = useState('')

  const handleSelectDay = d => {
    setSelectedDay(d)
    setTab('orders')
  }

  return (
    <Page
      title="Doanh thu POS"
      sub="Doanh thu = tổng thanh toán các đơn hợp lệ từ POS365 theo ngày kinh doanh (Asia/Ho_Chi_Minh)."
    >
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          ['daily', 'Doanh thu theo ngày'],
          ['orders', 'Danh sách hóa đơn'],
          ['sync', 'Đồng bộ & nạp file'],
        ]}
      />

      {tab === 'daily' && <DailyTab onSelectDay={handleSelectDay} />}
      {tab === 'orders' && <OrdersTab initialDay={selectedDay} />}
      {tab === 'sync' && <SyncTab />}
    </Page>
  )
}
