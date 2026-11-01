# 工单接口并发验证

本记录对应 2026-11-01 在本地专用测试库完成的一轮接口验证，不是性能压测报告。

## 测试环境

- 工具：Apifox 普通 HTTP 请求及后置自定义脚本。
- 并发方式：pm.sendRequest 配合 Promise.all。
- 服务地址：http://127.0.0.1:8001。
- 专用数据库：omnisupport_concurrency_test。
- 身份：一个测试客户、两名不同的 customer_support 员工。
- 本轮工单：469e0cab-422f-4d18-bb40-8de4df17cbe5。
- 本轮测试客户：fa2f97cf-313f-4867-b057-55f445aecc9c。
- 客服邮箱：race.a@example.com、race.b@example.com。
- 本轮领取成功者：race.a@example.com。

测试服务使用 evaluations/ticket_api_test.py 启动。该入口仅在当前进程内切换数据库配置，不修改项目 .env。

在项目根目录初始化并启动：

    .\.venv\Scripts\python.exe -m evaluations.ticket_api_test init
    .\.venv\Scripts\python.exe -m evaluations.ticket_api_test serve

初始化成功后再执行启动命令，并保持服务终端运行。测试账号及新工单需在该测试服务中准备，不能直接使用业务库中的账号和工单。

## Apifox 环境变量

| 变量 | 含义 |
|---|---|
| race_ticket_id | 本轮新建测试工单编号 |
| race_customer_id | 测试客户编号 |
| race_customer_token | 测试客户登录取得的原始 Token |
| race_staff_a_token | 员工 A 登录取得的原始 Token |
| race_staff_b_token | 员工 B 登录取得的原始 Token |

Token 值保留在操作者本地的 Apifox 环境中，不写入脚本或提交到仓库。Token 变量不包含 Bearer 前缀，脚本发送请求时自行添加。

## 场景与脚本

三份文件都是完整的后置脚本，包含入口调用及异常处理，应分别放在对应请求的“后置操作 → 自定义脚本”中。

主请求均使用客户身份：Auth 选择 Bearer Token，Token 填写 {{race_customer_token}}，Body 选择 none。

| 场景 | 后置脚本 | 主请求 |
|---|---|---|
| 两名员工领取同一工单 | [ticket_claim.js](../evaluations/apifox/ticket_claim.js) | GET http://127.0.0.1:8001/api/v1/tickets/{{race_ticket_id}} |
| 客户与处理员工并发回复 | [ticket_replies.js](../evaluations/apifox/ticket_replies.js) | GET http://127.0.0.1:8001/api/v1/tickets/{{race_ticket_id}}/messages?limit=100&offset=0 |
| 客户回复与员工关闭并发 | [ticket_close_race.js](../evaluations/apifox/ticket_close_race.js) | GET http://127.0.0.1:8001/api/v1/tickets/{{race_ticket_id}} |

按表格顺序使用一张新工单验证：

1. 抢单前工单必须为 open，且没有处理员工。脚本先通过员工资料接口确认两名不同员工，再发起两个领取请求。
2. 并发回复前工单必须为 in_progress，且消息数为零。客户、处理员工各发五条，核对返回码、内容、身份及持久化序号。
3. 关闭争用前工单必须为 in_progress。脚本先保存历史，再并发提交客户回复和员工关闭，并在关闭完成后分别尝试客户、员工回复。
4. 当前工单完成后为 closed，下一轮需创建新工单。中途发生网络错误时先查询实际状态，不直接重复执行写入脚本。

本轮获胜者是员工 A，因此后两份脚本读取 race_staff_a_token。若新一轮由员工 B 领取，应将后两份脚本中 staffToken 的读取变量改为 race_staff_b_token。脚本会核对所用 Token 是否属于当前处理员工。

主请求 Body 展示的是后置脚本执行前的查询快照。子请求响应及最终查询结果需看控制台和断言区域。

## 本轮结果

| 场景 | 实际结果 |
|---|---|
| 两名员工领取同一工单 | A 返回 200，B 返回 409，最终分配给 A |
| 客户与处理员工并发回复 | 各提交 5 条，全部返回 201，保存 10 条，序号连续且唯一 |
| 客户回复与员工关闭并发 | 回复返回 201，关闭返回 200，消息从 10 条增至 11 条 |
| 关闭后双方再次回复 | 均返回 409，未新增消息，已有记录保留 |

最终数据库记录经只读核对：

- 工单状态为 closed，关闭时间非空。
- 消息数为 11，唯一消息序号数为 11，最小序号 1，最大序号 11。
- 客户消息 6 条、员工消息 5 条。
- 两条“关闭后应被拒绝”的测试回复没有写入。

409 在抢单冲突和关闭后回复场景中是预期业务拒绝，不能直接算作服务器故障。

## 实现机制

领取、回复和关闭操作均通过 SELECT FOR UPDATE 锁定对应工单行。回复在持有工单锁时读取最大消息序号、生成下一序号，并在同一事务中写入消息及更新工单活动时间。数据库通过工单编号与消息序号的唯一约束进一步保护序号。

回复与关闭存在两种合法顺序：

| 业务顺序 | 并发回复 | 关闭 | 新增消息 |
|---|---|---|---|
| 回复先完成，随后关闭 | 201 | 200 | 1 条 |
| 关闭先完成，回复被拒绝 | 409 | 200 | 0 条 |

本轮只实际观测到了第一种结果。不能通过请求发出或响应到达的先后，直接判断数据库获取锁的先后。

## 覆盖范围与限制

- 本轮属于小规模、单轮 HTTP 接口并发验证。
- Promise.all 不保证请求在数据库内发生重叠；本轮未控制或观察实际锁等待。
- 关闭先完成、并发回复被拒绝的争用分支尚未实际观测到。
- 关闭完成后双方回复被拒绝的行为已验证。
- 未测试创建幂等。
- 未开展吞吐量、延迟分位数或长时间稳定性压测。
- 未据此证明所有并发交错情况均已覆盖。
- 本记录只对应所列场景和本轮数据，不代表整个应用已通过全面并发测试。
