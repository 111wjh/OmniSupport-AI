// 主请求：GET http://127.0.0.1:8001/api/v1/tickets/{{race_ticket_id}}
// 主请求 Auth：Bearer {{race_customer_token}}；用作完整后置脚本。
// 本轮处理员工为 A；若由 B 领取，将 staffToken 改读 race_staff_b_token。
const BASE_URL = "http://127.0.0.1:8001";

function check(condition, name) {
    pm.test(name, function () {
        pm.expect(condition).to.equal(true);
    });

    if (!condition) {
        throw new Error(name);
    }
}

// payload 存在时，发送 JSON 请求体
function sendRequest(method, path, token, payload) {
    const request = {
        url: BASE_URL + path,
        method: method,
        header: {
            Authorization: "Bearer " + token,
            Accept: "application/json"
        }
    };

    if (payload !== undefined) {
        request.header["Content-Type"] = "application/json";
        request.body = {
            mode: "raw",
            raw: JSON.stringify(payload)
        };
    }

    return new Promise(function (resolve, reject) {
        pm.sendRequest(request, function (error, response) {
            if (error) {
                reject(new Error(method + " " + path + " 请求失败"));
                return;
            }

            try {
                resolve({
                    code: response.code,
                    data: response.json()
                });
            } catch (error) {
                reject(new Error(path + " 返回内容不是 JSON"));
            }
        });
    });
}

async function run() {
    const ticketId = pm.environment.get("race_ticket_id");
    const customerId = pm.environment.get("race_customer_id");
    const customerToken = pm.environment.get("race_customer_token");
    const staffToken = pm.environment.get("race_staff_a_token");

    check(
        Boolean(ticketId && customerId && customerToken && staffToken),
        "本轮变量已配置"
    );
    check(pm.response.code === 200, "工单查询成功");

    const initial = pm.response.json();

    check(
        initial.id === ticketId && initial.customer_id === customerId,
        "查询的是测试客户的工单"
    );
    check(
        initial.status === "in_progress" && initial.closed_at === null,
        "工单尚未关闭"
    );

    const staffResult = await sendRequest(
        "GET", "/api/v1/staff/me", staffToken
    );

    check(staffResult.code === 200, "员工 Token 有效");
    check(
        staffResult.data.id === initial.assigned_staff_id,
        "关闭操作由当前处理员工执行"
    );

    const customerPath = "/api/v1/tickets/" + ticketId;
    const staffPath = "/api/v1/staff/tickets/" + ticketId;
    const messagesPath = customerPath + "/messages?limit=100&offset=0";

    // 保存本轮开始前的历史记录
    const before = await sendRequest(
        "GET", messagesPath, customerToken
    );

    check(before.code === 200, "历史消息查询成功");
    check(
        before.data.total === before.data.items.length &&
        before.data.total <= 99,
        "本轮历史消息已完整读取，且有空间检查新增消息"
    );

    const baselineCount = before.data.total;
    const content = "关闭争用测试-" + Date.now() + "-" +
        Math.random().toString(16).slice(2, 8);

    // 同时提交客户回复和员工关闭
    const [replyResult, closeResult] = await Promise.all([
        sendRequest(
            "POST",
            customerPath + "/messages",
            customerToken,
            { content: content }
        ),
        sendRequest(
            "POST",
            staffPath + "/close",
            staffToken
        )
    ]);

    console.log("并发回复结果：", replyResult);
    console.log("并发关闭结果：", closeResult);

    check(closeResult.code === 200, "工单关闭成功");
    check(
        replyResult.code === 201 || replyResult.code === 409,
        "并发回复成功，或因工单关闭而被拒绝"
    );

    const [finalTicket, after] = await Promise.all([
        sendRequest("GET", customerPath, customerToken),
        sendRequest("GET", messagesPath, customerToken)
    ]);

    check(
        finalTicket.code === 200 && after.code === 200,
        "关闭后仍可查询工单和历史消息"
    );
    check(
        finalTicket.data.status === "closed" &&
        finalTicket.data.closed_at !== null,
        "最终状态为已关闭，且记录关闭时间"
    );
    check(
        finalTicket.data.assigned_staff_id === initial.assigned_staff_id,
        "处理员工保持正确"
    );

    const added = replyResult.code === 201 ? 1 : 0;
    const messages = after.data.items;

    check(
        after.data.total === baselineCount + added &&
        messages.length === after.data.total,
        "最终消息数量与并发回复结果一致"
    );

    const byId = new Map(messages.map(item => [item.id, item]));

    check(
        before.data.items.every(function (oldMessage) {
            const saved = byId.get(oldMessage.id);
            return saved && Object.keys(oldMessage).every(
                key => saved[key] === oldMessage[key]
            );
        }),
        "原有消息全部保留，内容未被改变"
    );
    check(
        messages.every((item, index) => item.message_seq === index + 1),
        "最终消息序号仍连续"
    );

    const matching = messages.filter(item => item.content === content);

    check(
        matching.length === added,
        "本轮回复成功则存在，拒绝则没有写入"
    );

    if (added === 1) {
        check(
            matching[0].id === replyResult.data.id &&
            matching[0].sender_type === "customer" &&
            matching[0].sender_customer_id === customerId &&
            matching[0].message_seq === baselineCount + 1,
            "本轮成功回复的身份、编号和序号正确"
        );
    }

    // 明确在关闭完成之后，再尝试双方回复
    const lateResults = await Promise.all([
        sendRequest(
            "POST",
            customerPath + "/messages",
            customerToken,
            { content: "关闭后的客户回复，应被拒绝" }
        ),
        sendRequest(
            "POST",
            staffPath + "/messages",
            staffToken,
            { content: "关闭后的员工回复，应被拒绝" }
        )
    ]);

    console.log("关闭后双方回复状态码：", lateResults.map(item => item.code));

    check(
        lateResults.every(item => item.code === 409),
        "关闭后客户和员工回复都被拒绝"
    );

    const confirmed = await sendRequest(
        "GET", messagesPath, customerToken
    );

    check(confirmed.code === 200, "可以再次查询历史");
    check(
        confirmed.data.total === after.data.total &&
        JSON.stringify(confirmed.data.items) === JSON.stringify(messages),
        "关闭后的拒绝请求没有新增或改变消息"
    );

    console.log("最终工单状态：", finalTicket.data.status);
    console.log("原有消息数量：", baselineCount);
    console.log("最终消息数量：", confirmed.data.total);
}

console.log("开始执行关闭与回复并发验证");

run().catch(function (error) {
    console.error(error.message);
    pm.test("并发验证流程正常完成", function () {
        throw error;
    });
});
