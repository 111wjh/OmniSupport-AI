# 客户与员工工作台

## 入口和角色

客户登录后顶部有智能会话、我的订单、退款进度、人工工单。
员工可从右上角进入，或直接访问前端地址加 /#staff。
员工账号由后端 create_staff 命令创建，没有公开员工注册页面。

- customer_support：待领取队列、我的工单、沟通记录、回复和关闭。
- refund_reviewer：待审核和待执行队列、审核通过/拒绝、模拟执行。
- admin：两类入口。
- 客户与员工 Token 使用独立 sessionStorage 键。客户端角色显示只用于导航，服务端继续决定实际权限。

## 操作流程

### 客户订单和退款

我的订单支持分页，点击卡片查看详情，填写至少 5 字的退款原因后提交。
退款进度页面显示申请状态，点击查询执行结果查看模拟退款记录。
未审核或尚无执行记录时，接口会返回相应提示。
所有模拟结果均不代表真实资金变动。

### 客户工单

填写标题和至少 5 字的问题说明，页面会提示当前字数。关联本人订单号和会话 UUID 均为可选。
创建使用 Idempotency-Key，失败后相同输入保留请求号，成功后清理。
状态筛选及分页由后端执行。打开工单后可分页读历史、追加回复。
已关闭工单只展示历史。
追加回复尚未支持后端幂等；失败后先刷新沟通记录核对，避免重复。

### 员工工单

从待领取队列领取后进入本人处理列表；竞争失败会显示接口冲突提示，应刷新列表。
本人处理列表可按状态筛选，读取沟通记录后回复或关闭。
关闭后回复表单隐藏，最终业务校验仍在服务端。

### 退款审核

待审核列表展示订单号、客户、金额和原因。填写审核意见后选择通过或拒绝。
审核通过后，切到待执行队列。列表从 `GET /api/v1/refunds/ready-to-execute` 读取。
点击「选择执行」，核对订单、金额和申请编号，再点「确认模拟退款」。执行成功后刷新队列并显示模拟执行记录。

### 聊天回复方式

网页文字聊天默认使用普通回复，与 Apifox 的普通聊天接口一致。点击输入框旁的模式按钮可以切换流式回复，页面会显示当前选中的方式。

## 维护分工

api/business.ts：业务类型、运行时响应校验、分页与写入请求。
useBusiness.ts：分页、取消旧读取、错误与写入忙碌状态。
useStaffAuth.ts：员工登录、恢复、退出。
BusinessWorkspace.vue：角色页签。
OrdersView / RefundsView / TicketsView：领域页面。
PageControls.vue：共用分页。
business.css：与原深色客服界面一致的业务视觉及移动布局。

## 验证命令

```powershell
npm run typecheck
npm run build
npm run format:check
npm run test:chat-idempotency
npm run test:business
```

test:business 启动独立 Vite 测试服务和无头 Edge，通过内存模拟 API 验证业务闭环。设置 UPDATE_BUSINESS_SCREENSHOTS=1 时会更新 screenshots 下的业务截图。测试使用模拟业务数据和模型回复。

默认 Edge 路径为 C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe。其他环境设置 EDGE_EXECUTABLE 为已安装的 Chromium 浏览器可执行文件路径。

真实演示仍需运行后端、数据库和知识服务，准备客户、员工及模拟订单，按真实接口联调。测试截图与模拟流程不作为生产支付或安全审计证明。
