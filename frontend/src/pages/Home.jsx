import { useState } from 'react'
import { get } from '../api.js'
import { useApp } from '../App.jsx'
import { Badge, Btn, Card, Empty, ErrorBox, Loading, Notice, Page, useLoad } from '../ui.jsx'
import { SHIFT, dm, dmy, money, num, todayIso, weekday, shiftMonth } from '../fmt.js'

function OwnerHome() {
  const { currentMonth } = useApp()
  const prevMonth = shiftMonth(currentMonth, -1)

  const rev = useLoad(() => get('/revenue/daily?month=' + currentMonth), [currentMonth])
  const pnl = useLoad(() => get('/pnl/' + currentMonth), [currentMonth])
  const prevPnl = useLoad(() => get('/pnl/' + prevMonth), [prevMonth])
  const swaps = useLoad(() => get('/swap-requests?status=pending'), [])
  const stock = useLoad(() => get('/ingredient-status/open'), [])
  const ho = useLoad(() => get('/handovers?month=' + currentMonth), [currentMonth])

  const waitingHandovers = (ho.data || []).filter(h => h.status === 'submitted' || h.shortage_refund !== 0 || h.extra !== 0).length
  const maxRev = Math.max(1, ...(rev.data?.days || []).map(d => d.revenue))
  const today = todayIso()

  // Tính biên lãi
  const profitMargin = pnl.data && pnl.data.revenue > 0
    ? ((pnl.data.profit / pnl.data.revenue) * 100).toFixed(1)
    : '0.0'

  // Cơ cấu 4 nhóm chi phí
  const totalCost = pnl.data?.total_cost || 1
  const costItems = [
    { label: '1. Chi phí nguyên liệu', amount: pnl.data?.ingredients || 0, color: 'var(--primary)' },
    { label: '2. Lương nhân viên', amount: pnl.data?.payroll || 0, color: 'var(--accent)' },
    { label: '3. Mặt bằng / điện / nước', amount: pnl.data?.fixed || 0, color: 'var(--info)' },
    { label: '4. Chi phí phát sinh', amount: pnl.data?.other || 0, color: 'var(--warn)' },
  ]

  return (
    <div className="stack" style={{ gap: 16 }}>
      {/* TẦNG 1: 4 THẺ KPI */}
      <div className="grid4">
        <Card className="tight">
          <div className="kpi">
            <span className="l">Doanh thu (POS)</span>
            <span className="v">{pnl.data ? money(pnl.data.revenue) : '…'}</span>
            <span className="small muted">{rev.data?.orders ? `${num(rev.data.orders)} hóa đơn` : 'Chưa có đơn'}</span>
          </div>
        </Card>

        <Card className="tight">
          <div className="kpi">
            <span className="l">Tổng chi phí</span>
            <span className="v">{pnl.data ? money(pnl.data.total_cost) : '…'}</span>
            <span className="small muted">Gồm 4 nhóm chi phí</span>
          </div>
        </Card>

        <Card className="tight">
          <div className={'kpi ' + (pnl.data ? (pnl.data.profit >= 0 ? 'good' : 'bad') : '')}>
            <span className="l">{pnl.data && pnl.data.profit < 0 ? 'Lỗ ròng' : 'Lãi ròng'}</span>
            <span className="v">{pnl.data ? money(Math.abs(pnl.data.profit)) : '…'}</span>
            <span className="small muted">
              Tháng trước: {prevPnl.data ? money(prevPnl.data.profit) : '…'}
            </span>
          </div>
        </Card>

        <Card className="tight">
          <div className={'kpi ' + (parseFloat(profitMargin) >= 0 ? 'good' : 'bad')}>
            <span className="l">Biên lãi</span>
            <span className="v">{profitMargin}%</span>
            <span className="small muted">Lãi / doanh thu</span>
          </div>
        </Card>
      </div>

      {/* D1: Nhãn tạm tính tháng đang diễn ra */}
      {pnl.data?.prorated_label && (
        <Notice kind="info">
          ℹ️ <b>{pnl.data.prorated_label}</b>: Doanh thu, lương và chi phí cố định được tính theo số ngày đã qua ({pnl.data.as_of_day}/{pnl.data.total_days} ngày).
        </Notice>
      )}

      {/* TẦNG 2: BIỂU ĐỒ DOANH THU THEO NGÀY ▾ */}
      <Card title="Doanh thu theo ngày ▾" collapsible defaultOpen={true}>
        {rev.loading && !rev.data ? <Loading /> : rev.error ? <ErrorBox message={rev.error} onRetry={rev.reload} /> :
          rev.data?.total === 0 ? <Empty title="Chưa có dữ liệu doanh thu tháng này" /> : (
            <>
              <div className="chart" role="img" aria-label="Biểu đồ doanh thu theo ngày">
                {rev.data.days.map(d => (
                  <div
                    key={d.date}
                    className={'b ' + (d.date === today ? 'today' : '')}
                    style={{ height: Math.max(3, (d.revenue / maxRev) * 100) + '%' }}
                    title={`${dm(d.date)}: ${money(d.revenue)} (${d.orders} đơn)`}
                  />
                ))}
              </div>
              <div className="axis">
                <span>{dm(rev.data.days[0].date)}</span>
                <span>{num(rev.data.orders)} hóa đơn · Tổng: {money(rev.data.total)}</span>
                <span>{dm(rev.data.days.at(-1).date)}</span>
              </div>
            </>
          )}
      </Card>

      {/* TẦNG 3: CƠ CẤU CHI PHÍ ▾ */}
      <Card title="Cơ cấu chi phí ▾" collapsible defaultOpen={true}>
        {pnl.loading && !pnl.data ? <Loading /> : (
          <div className="stack" style={{ gap: 12 }}>
            {costItems.map((c, i) => {
              const pct = totalCost > 0 ? ((c.amount / totalCost) * 100).toFixed(1) : 0
              return (
                <div key={i} className="stack-sm">
                  <div className="row spread" style={{ fontSize: '.88rem' }}>
                    <span><b>{c.label}</b></span>
                    <span><b>{money(c.amount)}</b> <span className="muted">({pct}%)</span></span>
                  </div>
                  <div className="progress-bar-wrap">
                    <div className="progress-bar-fill" style={{ width: `${Math.min(100, pct)}%`, background: c.color }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* TẦNG 4: LƯỚI 2 CỘT (Cần đặt hàng ▾ | Việc đang chờ ▾) */}
      <div className="grid2">
        <Card
          title="Cần đặt hàng ▾"
          collapsible
          defaultOpen={true}
          action={<a href="#/ingredients" className="small" style={{ textDecoration: 'none' }}>Xem tất cả →</a>}
        >
          {stock.loading && !stock.data ? <Loading /> : (stock.data || []).length === 0 ? (
            <span className="muted small">Tất cả nguyên liệu đều đủ.</span>
          ) : (
            <div className="stack-sm">
              {stock.data.slice(0, 4).map((it, idx) => (
                <div key={idx} className="row spread card flat tight">
                  <div>
                    <b>{it.ingredient}</b>
                    <div className="muted small">{it.note || 'Cần đặt thêm'}</div>
                  </div>
                  <Badge kind={it.status === 'het' ? 'bad' : it.status === 'sap_het' ? 'warn' : 'info'}>
                    {it.status === 'het' ? 'Đã hết' : it.status === 'sap_het' ? 'Sắp hết' : 'Đã đặt'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Việc đang chờ ▾"
          collapsible
          defaultOpen={true}
          action={<span className="small muted">Hệ thống</span>}
        >
          <div className="stack-sm">
            <a className="row spread card flat tight" href="#/handover" style={{ textDecoration: 'none', color: 'inherit' }}>
              <span><b>{waitingHandovers}</b> biên bản giao ca chờ nhận / xem xét</span>
              <Badge kind={waitingHandovers > 0 ? 'warn' : 'ok'}>{waitingHandovers > 0 ? 'Xử lý' : 'Xong'}</Badge>
            </a>

            <a className="row spread card flat tight" href="#/schedule" style={{ textDecoration: 'none', color: 'inherit' }}>
              <span><b>{swaps.data?.length || 0}</b> yêu cầu đổi ca đang chờ duyệt</span>
              <Badge kind={(swaps.data?.length || 0) > 0 ? 'warn' : 'ok'}>{(swaps.data?.length || 0) > 0 ? 'Duyệt' : 'Xong'}</Badge>
            </a>

            <a className="row spread card flat tight" href="#/payroll" style={{ textDecoration: 'none', color: 'inherit' }}>
              <span>Bảng lương tháng {currentMonth}</span>
              <Badge kind={pnl.data?.payroll_locked ? 'ok' : 'warn'}>{pnl.data?.payroll_locked ? 'Đã chốt' : 'Chưa chốt'}</Badge>
            </a>
          </div>
        </Card>
      </div>
    </div>
  )
}

function StaffHome() {
  const { me, currentMonth } = useApp()
  const sch = useLoad(() => get('/schedules/' + currentMonth), [currentMonth])
  const ho = useLoad(() => get('/handovers?month=' + currentMonth), [currentMonth])
  const today = todayIso()
  const mine = (sch.data?.assignments || [])
    .filter(a => a.employee_id === me.employee_id && a.work_date >= today)
    .slice(0, 5)
  const isMineHo = h => h && (h.giver_id === me.id || h.giver_name === me.display_name)
  const pendingConfirm = (ho.data || []).filter(h => h.status === 'submitted' && !isMineHo(h))
  const unlockedForMe = (ho.data || []).filter(h => isMineHo(h) && h.unlocked_by_owner)

  return (
    <div className="stack" style={{ gap: 16 }}>
      {pendingConfirm.length > 0 && (
        <Notice kind="info">
          <div className="row spread" style={{ width: '100%' }}>
            <span>
              🤝 Có <b>{pendingConfirm.length}</b> biên bản giao ca từ đồng nghiệp ca trước đang chờ bạn kiểm đếm tiền mặt và xác nhận ({pendingConfirm.map(p => `${dm(p.business_date)} Ca ${SHIFT[p.shift_code]} - ${p.giver_name}`).join(', ')}).
            </span>
            <a className="btn sm primary" href="#/handover">Xem &amp; nhận ca →</a>
          </div>
        </Notice>
      )}

      {unlockedForMe.length > 0 && (
        <Notice kind="warn">
          <div className="row spread" style={{ width: '100%' }}>
            <span>
              🔓 Chủ quán đã mở khóa <b>{unlockedForMe.length}</b> biên bản giao ca để bạn chỉnh sửa lại ({unlockedForMe.map(p => `${dm(p.business_date)} Ca ${SHIFT[p.shift_code]}`).join(', ')}).
            </span>
            <a className="btn sm" href="#/handover">Sửa phiếu →</a>
          </div>
        </Notice>
      )}

      <div className="card">
        <h2>Xin chào, {me.display_name} 👋</h2>
        <p className="muted small" style={{ margin: '4px 0 14px' }}>Hôm nay là {dmy(today)} · Chi nhánh Cửa hàng A</p>
        <div className="grid3">
          <a className="btn primary" href="#/handover">🤝 Giao ca</a>
          <a className="btn" href="#/purchases">🧾 Ghi nhận nhập hàng</a>
          <a className="btn" href="#/ingredients">🥛 Báo nguyên liệu</a>
          <a className="btn" href="#/schedule">🗓️ Lịch ca &amp; Đổi ca</a>
          <a className="btn" href="#/payroll">💰 Bảng lương của tôi</a>
          <a className="btn" href="#/settings">👤 Hồ sơ &amp; Mật khẩu</a>
        </div>
      </div>

      <Card title="Ca sắp tới của bạn ▾" collapsible defaultOpen={true}>
        {sch.loading ? <Loading /> : sch.error ? <ErrorBox message={sch.error} onRetry={sch.reload} /> :
          !me.employee_id ? <Notice kind="warn">Tài khoản chưa liên kết với nhân viên. Nhờ chủ quán kết nối trong mục Tài khoản.</Notice> :
            sch.data.status !== 'published' ? <Empty title="Lịch tháng này chưa công bố">Chủ quán sẽ công bố lịch làm việc sau khi hoàn tất sắp xếp.</Empty> :
              mine.length === 0 ? <Empty title="Bạn không có ca nào trong những ngày tới" /> : (
                <div className="stack-sm">
                  {mine.map(a => (
                    <div key={a.id} className="row spread card flat tight">
                      <span><b>{weekday(a.work_date)} {dm(a.work_date)}</b></span>
                      <Badge kind={a.work_date === today ? 'ok' : ''}>
                        Ca {SHIFT[a.shift_code]}{a.work_date === today ? ' · Hôm nay' : ''}
                      </Badge>
                    </div>
                  ))}
                  <div style={{ marginTop: 8 }}>
                    <a href="#/schedule" className="small">Xem toàn bộ lịch tháng →</a>
                  </div>
                </div>
              )}
      </Card>
    </div>
  )
}

export default function Home() {
  return useApp().me.role === 'owner' ? <OwnerHome /> : <StaffHome />
}
