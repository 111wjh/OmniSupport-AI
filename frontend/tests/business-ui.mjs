import assert from 'node:assert/strict'
import { chromium } from '@playwright/test'
import { createServer } from 'vite'
import { mkdir } from 'node:fs/promises'
const server = await createServer({ server: { host: '127.0.0.1', port: 5188, strictPort: true } })
await server.listen()
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.EDGE_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
})
const id = '00000000-0000-4000-8000-000000000001',
  rid = '00000000-0000-4000-8000-000000000002',
  tid = '00000000-0000-4000-8000-000000000003'
let ticket = null,
  refund = null,
  seq = 0,
  messages = [],
  orderStatus = 'paid',
  failOrders = false,
  role = 'admin'
const order = () => ({
  id,
  order_number: 'OMNI-DEMO-001',
  product_name: '蓝牙无线耳机 Pro（模拟）',
  total_amount: '99.00',
  status: orderStatus,
  purchased_at: '2026-11-02T10:00:00+08:00',
})
const customer = { id, display_name: '演示客户', email: 'demo@example.com', is_active: true }
const staff = { ...customer, display_name: '演示员工', role: 'admin' }
const requests = []
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
await context.addInitScript(() =>
  sessionStorage.setItem('omnisupport.customer.token', 'test-customer'),
)
await context.route('**/*', async (route) => {
  const request = route.request(),
    url = new URL(request.url()),
    p = url.pathname
  if (!p.startsWith('/api/v1/') && p !== '/health') return route.continue()
  requests.push({ p, method: request.method(), headers: request.headers() })
  const ok = (data, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
  const list = (items) => ({ items, total: items.length, limit: 10, offset: 0 })
  if (p === '/health') return ok({ status: 'ok' })
  if (p === '/api/v1/customers/me') return ok(customer)
  if (p === '/api/v1/staff/login') return ok({ access_token: 'test-staff', token_type: 'bearer' })
  if (p === '/api/v1/staff/me') return ok({ ...staff, role })
  if (p === '/api/v1/conversations') return ok(list([]))
  if (p.startsWith('/api/v1/orders'))
    return failOrders
      ? ok({ detail: '测试：订单服务暂时不可用' }, 503)
      : ok(p === '/api/v1/orders' ? list([order()]) : order())
  if (p === '/api/v1/refunds' && request.method() === 'POST') {
    refund = {
      id: rid,
      order_id: id,
      reason: request.postDataJSON().reason,
      status: 'pending',
      requested_at: '2026-11-02T10:00:00+08:00',
    }
    return ok(refund, 201)
  }
  if (p === '/api/v1/refunds') return ok(list(refund ? [refund] : []))
  if (p === '/api/v1/refunds/pending')
    return ok(
      list(
        refund?.status === 'pending'
          ? [
              {
                ...refund,
                order_number: 'OMNI-DEMO-001',
                order_total_amount: '99.00',
                customer_email: customer.email,
              },
            ]
          : [],
      ),
    )
  if (p.endsWith('/review')) {
    refund = {
      ...refund,
      status: request.postDataJSON().decision,
      review_comment: request.postDataJSON().review_comment,
    }
    return ok(refund)
  }
  if (p.endsWith('/execute') || p.endsWith('/execution')) {
    orderStatus = 'refunded'
    return ok({
      id,
      refund_request_id: rid,
      amount: '99.00',
      status: 'succeeded',
      executed_at: '2026-11-02T11:00:00+08:00',
    })
  }
  if (p === '/api/v1/tickets' && request.method() === 'POST') {
    assert.ok(request.headers()['idempotency-key'])
    ticket = {
      ...request.postDataJSON(),
      id: tid,
      customer_id: id,
      status: 'open',
      assigned_staff_id: null,
      order_id: null,
      conversation_id: null,
      created_at: '2026-11-02T10:00:00+08:00',
    }
    return ok(ticket, 201)
  }
  if (p.endsWith('/claim')) {
    ticket = { ...ticket, status: 'in_progress', assigned_staff_id: id }
    return ok(ticket)
  }
  if (p.endsWith('/close')) {
    ticket = { ...ticket, status: 'closed' }
    return ok(ticket)
  }
  if (p.endsWith('/messages')) {
    if (request.method() === 'POST') {
      if (ticket.status === 'closed') return ok({ detail: '工单已关闭，不能继续回复' }, 409)
      const m = {
        id: crypto.randomUUID(),
        ticket_id: tid,
        sender_type: p.includes('/staff/') ? 'staff' : 'customer',
        message_seq: ++seq,
        content: request.postDataJSON().content,
        created_at: '2026-11-02T11:00:00+08:00',
      }
      messages.push(m)
      return ok(m, 201)
    }
    return ok({ ticket_id: tid, ...list(messages) })
  }
  if (p === '/api/v1/staff/tickets/queue')
    return ok(list(ticket?.status === 'open' ? [ticket] : []))
  if (p === '/api/v1/staff/tickets/mine') return ok(list(ticket?.assigned_staff_id ? [ticket] : []))
  if (p === '/api/v1/tickets') return ok(list(ticket ? [ticket] : []))
  if (p.includes('/tickets/')) return ok(ticket)
  return ok({ detail: 'Unexpected mock path ' + p }, 404)
})
const page = await context.newPage()
const { expect } = await import('@playwright/test')
try {
  await page.goto('http://127.0.0.1:5188')
  await page.getByRole('button', { name: '我的订单', exact: true }).click()
  await expect(page.getByText('蓝牙无线耳机 Pro（模拟）', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看详情与售后' }).click()
  await page.getByLabel('退款原因').fill('演示商品不符合使用需求')
  await page.getByRole('button', { name: '提交退款申请', exact: true }).click()
  await expect(page.getByText(/退款申请已提交，申请编号/)).toBeVisible()
  await mkdir('docs/screenshots', { recursive: true })
  await page.screenshot({ path: 'docs/screenshots/orders.png', fullPage: true })
  await page.getByRole('button', { name: '退款进度', exact: true }).click()
  await expect(page.getByText('待处理', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '人工工单', exact: true }).click()
  await page.getByRole('button', { name: /新建工单/ }).click()
  await page.getByLabel('问题标题').fill('电脑蓝牙连接排查')
  await page.getByLabel('问题描述').fill('耳机连接电脑失败，希望人工客服协助排查。')
  await page.getByRole('button', { name: '提交工单', exact: true }).click()
  await expect(page.getByText(/工单已创建，编号/)).toBeVisible()
  await page.getByRole('button', { name: '员工入口' }).click()
  await page.getByLabel('员工邮箱').fill('staff@example.com')
  await page.getByLabel('密码', { exact: true }).fill('mock-password')
  await page.getByRole('button', { name: '登录工作台' }).click()
  await page.getByRole('button', { name: '领取并开始处理' }).click()
  await expect(page.getByRole('heading', { name: '电脑蓝牙连接排查' })).toHaveCount(2)
  await page.getByLabel('补充回复').fill('已收到问题，请先确认电脑蓝牙是否开启。')
  await page.getByRole('button', { name: '发送回复', exact: true }).click()
  await expect(
    page.getByText('已收到问题，请先确认电脑蓝牙是否开启。', { exact: true }),
  ).toBeVisible()
  await page.locator('.service-desk').evaluate((el) => (el.scrollTop = 0))
  await page.screenshot({ path: 'docs/screenshots/staff-tickets.png', fullPage: true })
  await page.getByRole('button', { name: '关闭此工单' }).click()
  await expect(page.getByText('工单已关闭，沟通记录已保留。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('补充回复')).toHaveCount(0)
  await page.getByRole('button', { name: '退款审核', exact: true }).click()
  await page.getByRole('button', { name: '审核此申请' }).click()
  await page.getByLabel('审核意见').fill('演示审核通过，进入模拟执行。')
  await page.getByRole('button', { name: '审核通过', exact: true }).click()
  await expect(page.getByLabel('退款申请编号')).toHaveValue(rid)
  await page.getByRole('button', { name: '执行模拟退款', exact: true }).click()
  await expect(page.getByText(/执行成功 · ¥99.00/)).toBeVisible()
  await page.screenshot({ path: 'docs/screenshots/staff-refunds.png', fullPage: true })
  await page.getByRole('button', { name: '客户入口', exact: true }).click()
  await page.getByRole('button', { name: '退款进度', exact: true }).click()
  await page.getByRole('button', { name: '查询模拟执行结果' }).click()
  await expect(page.getByText(/执行成功 · ¥99.00/)).toBeVisible()
  await page.getByRole('button', { name: '人工工单', exact: true }).click()
  await page.getByRole('button', { name: '查看沟通记录' }).click()
  await expect(
    page.getByText('已收到问题，请先确认电脑蓝牙是否开启。', { exact: true }),
  ).toBeVisible()
  await expect(page.getByLabel('补充回复')).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'docs/screenshots/business-mobile.png', fullPage: true })
  assert.ok(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    '移动端页面横向溢出',
  )
  failOrders = true
  await page.getByRole('button', { name: '我的订单', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('订单服务暂时不可用')
  failOrders = false
  await page.getByRole('button', { name: '刷新订单', exact: true }).click()
  await expect(page.getByText('蓝牙无线耳机 Pro（模拟）', { exact: true })).toBeVisible()
  role = 'customer_support'
  await page.reload()
  await page.getByRole('button', { name: '员工入口' }).click()
  await expect(page.getByRole('button', { name: '工单服务', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '退款审核', exact: true })).toHaveCount(0)
  assert.ok(
    requests
      .filter((r) => r.p.includes('/staff/') && r.p !== '/api/v1/staff/login')
      .every((r) => r.headers.authorization === 'Bearer test-staff'),
  )
  console.log(
    'Business UI passed: orders/refund submission; ticket creation; staff login/claim/reply/close; review/execute; customer history; mobile layout; failure recovery; role navigation/token isolation.',
  )
} finally {
  await browser.close()
  await server.close()
}
