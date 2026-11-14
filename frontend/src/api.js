// Gọi API: JSON, thông báo lỗi tiếng Việt từ `detail` của FastAPI, tự báo khi hết phiên (401).
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

function messageFrom(data, status) {
  const d = data && data.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map(e => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ')
  if (status === 401) return 'Phiên đăng nhập đã hết hạn'
  if (status === 403) return 'Bạn không có quyền thực hiện thao tác này'
  if (status >= 500) return 'Máy chủ gặp lỗi. Thử lại sau ít phút'
  return 'Có lỗi xảy ra'
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const opt = { method, credentials: 'same-origin', headers: {} }
  if (form) opt.body = form
  else if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body) }
  let res
  try { res = await fetch('/api' + path, opt) } catch { throw new ApiError('Không kết nối được máy chủ', 0) }
  const type = res.headers.get('content-type') || ''
  const data = type.includes('json') ? await res.json().catch(() => null) : null
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/login')) window.dispatchEvent(new Event('t06:unauth'))
    throw new ApiError(messageFrom(data, res.status), res.status)
  }
  return data
}

export const get = (p) => api(p)
export const post = (p, body) => api(p, { method: 'POST', body: body ?? {} })
export const put = (p, body) => api(p, { method: 'PUT', body })
export const patch = (p, body) => api(p, { method: 'PATCH', body })
export const del = (p) => api(p, { method: 'DELETE' })
export const upload = (p, file, extra = {}) => {
  const f = new FormData(); f.append('file', file)
  Object.entries(extra).forEach(([k, v]) => f.append(k, v))
  return api(p, { method: 'POST', form: f })
}
