// 主请求：GET http://127.0.0.1:8001/api/v1/tickets/{{race_ticket_id}}
// 主请求 Auth：Bearer {{race_customer_token}}；用作完整后置脚本。
const BASE_URL = "http://127.0.0.1:8001";

function check(condition, name) {
    pm.test(name, function () {
        pm.expect(condition).to.equal(true);
    });
    if (!condition) {
        throw new Error(name);
    }
}

function sendRequest(method, path, token) {
    return new Promise(function (resolve, reject) {
        pm.sendRequest({
            url: BASE_URL + path,
            method: method,
            header: {
                Authorization: "Bearer " + token,
                Accept: "application/json"
            }
        }, function (error, response) {
            if (error) {
                reject(new Error(method + " " + path + " 请求发送失败"));
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
    const tokenA = pm.environment.get("race_staff_a_token");
    const tokenB = pm.environment.get("race_staff_b_token");

    check(
        Boolean(ticketId && customerId && customerToken && tokenA && tokenB),
        "测试所需变量已配置"
    );
    check(pm.response.code === 200, "主请求成功查询工单");

    const initial = pm.response.json();
    check(initial.id === ticketId, "查询的是本轮测试工单");
    check(initial.customer_id === customerId, "工单属于测试客户");
    check(
        initial.status === "open" && initial.assigned_staff_id === null,
        "工单尚未被领取"
    );

    const profiles = await Promise.all([
        sendRequest("GET", "/api/v1/staff/me", tokenA),
        sendRequest("GET", "/api/v1/staff/me", tokenB)
    ]);

    check(
        profiles.every(item => item.code === 200),
        "两个员工 Token 均有效"
    );
    check(
        profiles[0].data.email === "race.a@example.com" &&
        profiles[1].data.email === "race.b@example.com",
        "Token 分别属于测试员工 A 和 B"
    );
    check(
        profiles[0].data.id !== profiles[1].data.id,
        "两个领取者是不同员工"
    );

    const claimPath = "/api/v1/staff/tickets/" + ticketId + "/claim";
    const results = await Promise.all([
        sendRequest("POST", claimPath, tokenA),
        sendRequest("POST", claimPath, tokenB)
    ]);

    console.log("员工 A 领取结果：", results[0]);
    console.log("员工 B 领取结果：", results[1]);

    const codes = results.map(item => item.code).sort((a, b) => a - b);
    check(
        codes[0] === 200 && codes[1] === 409,
        "恰好一人领取成功，另一人发生业务冲突"
    );

    const winnerIndex = results.findIndex(item => item.code === 200);
    const winner = profiles[winnerIndex].data;
    check(
        results[winnerIndex].data.assigned_staff_id === winner.id,
        "成功响应中的处理员工正确"
    );

    const finalResult = await sendRequest(
        "GET",
        "/api/v1/tickets/" + ticketId,
        customerToken
    );

    check(finalResult.code === 200, "客户可以查询最终工单");
    check(finalResult.data.id === ticketId, "最终查询的工单编号正确");
    check(finalResult.data.status === "in_progress", "最终状态为处理中");
    check(
        finalResult.data.assigned_staff_id === winner.id,
        "最终处理员工与领取成功者一致"
    );

    pm.environment.set("race_winner_staff_id", winner.id);
    pm.environment.set("race_winner_email", winner.email);

    console.log("最终领取者：", winner.email);
    console.log("最终工单状态：", finalResult.data.status);
}

run().catch(function (error) {
    console.error(error.message);
    pm.test("并发验证流程正常完成", function () {
        throw error;
    });
});
