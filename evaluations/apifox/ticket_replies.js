// 主请求：GET http://127.0.0.1:8001/api/v1/tickets/{{race_ticket_id}}/messages?limit=100&offset=0
// 主请求 Auth：Bearer {{race_customer_token}}；用作完整后置脚本。
// 本轮处理员工为 A；若新一轮由 B 领取，将 staffToken 改读 race_staff_b_token。
const BASE_URL = "http://127.0.0.1:8001";

function check(condition, name) {
    pm.test(name, function () {
        pm.expect(condition).to.equal(true);
    });
    if (!condition) {
        throw new Error(name);
    }
}

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
    check(pm.response.code === 200, "消息查询成功");

    const baseline = pm.response.json();
    check(baseline.ticket_id === ticketId, "消息属于测试工单");
    check(baseline.total === 0, "本轮开始前没有消息");

    const ticketResult = await sendRequest(
        "GET", "/api/v1/tickets/" + ticketId, customerToken
    );
    const staffResult = await sendRequest(
        "GET", "/api/v1/staff/me", staffToken
    );

    check(
        ticketResult.code === 200 && staffResult.code === 200,
        "工单及处理员工查询成功"
    );
    check(
        ticketResult.data.status === "in_progress",
        "工单处于处理中"
    );
    check(
        ticketResult.data.assigned_staff_id === staffResult.data.id,
        "员工 Token 属于当前处理员工"
    );

    const runId = Date.now() + "-" + Math.random().toString(16).slice(2, 8);
    const jobs = [];

    for (let i = 1; i <= 5; i++) {
        jobs.push({
            path: "/api/v1/tickets/" + ticketId + "/messages",
            token: customerToken,
            senderType: "customer",
            content: runId + " 客户并发消息 " + i
        });
        jobs.push({
            path: "/api/v1/staff/tickets/" + ticketId + "/messages",
            token: staffToken,
            senderType: "staff",
            content: runId + " 员工并发消息 " + i
        });
    }

    const results = await Promise.all(
        jobs.map(function (job) {
            return sendRequest(
                "POST", job.path, job.token, { content: job.content }
            );
        })
    );

    console.log("10 个回复请求的状态码：", results.map(item => item.code));
    check(
        results.every(item => item.code === 201),
        "10 条回复全部创建成功"
    );
    check(
        results.every(function (item, index) {
            return item.data.ticket_id === ticketId &&
                item.data.content === jobs[index].content &&
                item.data.sender_type === jobs[index].senderType;
        }),
        "回复响应的工单、内容和发送者类型正确"
    );

    const finalResult = await sendRequest(
        "GET",
        "/api/v1/tickets/" + ticketId + "/messages?limit=100&offset=0",
        customerToken
    );

    check(finalResult.code === 200, "可以查询最终消息");
    check(
        finalResult.data.total === 10 &&
        finalResult.data.items.length === 10,
        "数据库中恰好保存 10 条消息"
    );

    const messages = finalResult.data.items;
    const sequences = messages.map(item => item.message_seq);

    check(
        sequences.every((value, index) => value === index + 1),
        "消息按序号排列，序号连续为 1 至 10"
    );
    check(
        new Set(messages.map(item => item.id)).size === 10,
        "10 条消息的 ID 不重复"
    );

    const expectedContents = jobs.map(item => item.content).sort();
    const actualContents = messages.map(item => item.content).sort();
    check(
        JSON.stringify(actualContents) === JSON.stringify(expectedContents),
        "发送的消息全部保存，无遗漏或重复"
    );
    check(
        messages.filter(item => item.sender_type === "customer").length === 5 &&
        messages.filter(item => item.sender_type === "staff").length === 5,
        "客户和员工各保存 5 条消息"
    );
    check(
        messages.every(function (item) {
            if (item.sender_type === "customer") {
                return item.sender_customer_id === customerId &&
                    item.sender_staff_id === null;
            }
            return item.sender_staff_id === staffResult.data.id &&
                item.sender_customer_id === null;
        }),
        "持久化消息的发送者身份正确"
    );

    console.log("最终消息数量：", finalResult.data.total);
    console.log("最终消息序号：", sequences);
}

run().catch(function (error) {
    console.error(error.message);
    pm.test("并发回复验证流程正常完成", function () {
        throw error;
    });
});
