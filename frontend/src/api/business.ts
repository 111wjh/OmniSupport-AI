import { ApiError, isPage, isRecord, jsonRequest } from './http'
export interface Order {
  id: string
  order_number: string
  product_name: string
  total_amount: string
  status: string
  purchased_at: string
}
export interface Refund {
  id: string
  order_id: string
  reason: string
  status: string
  requested_at: string
  order_number?: string
  order_total_amount?: string
  customer_email?: string
  review_comment?: string | null
}
export interface Execution {
  id: string
  refund_request_id: string
  amount: string
  status: string
  executed_at: string | null
}
export interface Ticket {
  id: string
  subject: string
  description: string
  status: string
  customer_id: string
  assigned_staff_id: string | null
  order_id: string | null
  conversation_id: string | null
  created_at: string
}
export interface TicketMessage {
  id: string
  ticket_id: string
  sender_type: string
  message_seq: number
  content: string
  created_at: string
}
export interface Staff {
  id: string
  display_name: string
  email: string
  role: 'admin' | 'customer_support' | 'refund_reviewer'
  is_active: boolean
}
type Guard<T> = (value: unknown) => value is T
function strings(v: unknown, fields: string[]): v is Record<string, unknown> {
  return isRecord(v) && fields.every((k) => typeof v[k] === 'string')
}
export const isOrder: Guard<Order> = (v): v is Order =>
  strings(v, ['id', 'order_number', 'product_name', 'total_amount', 'status', 'purchased_at'])
export const isRefund: Guard<Refund> = (v): v is Refund =>
  strings(v, ['id', 'order_id', 'reason', 'status', 'requested_at'])
export const isTicket: Guard<Ticket> = (v): v is Ticket =>
  strings(v, ['id', 'subject', 'description', 'status', 'customer_id', 'created_at']) &&
  (v.assigned_staff_id === null || typeof v.assigned_staff_id === 'string')
export const isMessage: Guard<TicketMessage> = (v): v is TicketMessage =>
  strings(v, ['id', 'ticket_id', 'sender_type', 'content', 'created_at']) &&
  Number.isInteger(v.message_seq)
export const isExecution: Guard<Execution> = (v): v is Execution =>
  strings(v, ['id', 'refund_request_id', 'amount', 'status'])
export const isStaff: Guard<Staff> = (v): v is Staff =>
  strings(v, ['id', 'display_name', 'email']) &&
  ['admin', 'customer_support', 'refund_reviewer'].includes(String(v.role)) &&
  v.is_active === true
export async function record<T>(
  path: string,
  token: string,
  guard: Guard<T>,
  options: RequestInit = {},
) {
  const value = await jsonRequest(path, { ...options, token })
  if (!guard(value)) throw new ApiError('服务返回的数据格式异常，请刷新核对。')
  return value
}
export async function page<T>(
  path: string,
  token: string,
  guard: Guard<T>,
  offset = 0,
  signal?: AbortSignal,
) {
  const value = await jsonRequest(
    path +
      (path.includes('?') ? '&' : '?') +
      new URLSearchParams({ limit: '10', offset: String(offset) }),
    { token, signal },
  )
  if (!isPage(value) || !value.items.every(guard)) throw new ApiError('列表响应格式异常。')
  return { items: value.items, total: value.total }
}
export function post<T>(
  path: string,
  token: string,
  guard: Guard<T>,
  body?: unknown,
  headers: Record<string, string> = {},
) {
  return record(path, token, guard, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
}
export const label = (status: string) =>
  ({
    paid: '已支付',
    refunded: '已退款',
    pending: '待处理',
    approved: '审核通过',
    rejected: '已拒绝',
    open: '待领取',
    in_progress: '处理中',
    closed: '已关闭',
    succeeded: '执行成功',
    failed: '执行失败',
  })[status] || status
export function date(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}
export function money(value: string | undefined) {
  return value === undefined
    ? '—'
    : new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(Number(value))
}
