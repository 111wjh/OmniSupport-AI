# 客户与员工工作台

## 入口和角色

客户登录后顶部有智能会话、我的订单、退款进度、人工工单。
员工可从右上角进入，或直接访问前端地址加 /#staff。
员工账号由后端 create_staff 命令创建，没有公开员工注册页面。

- customer_support：待领取队列、我的工单、沟通记录、回复和关闭。
- refund_reviewer：退款待审队列、审核通过/拒绝、模拟执行。
- admin：两类入口。
- 客户与员工 Token 使用独立 sessionStorage 键。客户端角色显示只用于导航，服务端继续决定实际权限。

## 操作流程

### 客户订单和退款

我的订单支持分页，点击卡片查看详情，填写至少 5 字的退款原因后提交。
退款进度页面显示申请状态，点击查询执行结果查看模拟退款记录。
未审核或尚无执行记录时，接口会返回相应提示。
所有模拟结果均不代表真实资金变动。

### 客户工单

填写标题和至少 5 字的问题说明，可关联本人订单号及会话 UUID。
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
通过后将申请编号放入模拟执行表单，工作人员核对后单独执行。
其他已审核申请可粘贴 UUID 执行。当前接口未提供已审核队列，不在前端假造该列表。

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

test:business 启动独立 Vite 测试服务和无头 Edge，通过内存模拟 API 完成业务闭环，并产生 screenshots 下的业务页面截图。它不写入业务数据库，也不发送真实模型调用。

默认 Edge 路径为 C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe。其他环境设置 EDGE_EXECUTABLE 为已安装的 Chromium 浏览器可执行文件路径。

真实演示仍需运行后端、数据库和知识服务，准备客户、员工及模拟订单，按真实接口联调。测试截图与模拟流程不作为生产支付或安全审计证明。
