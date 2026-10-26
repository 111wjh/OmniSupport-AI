
from mcp.server.mcpserver import MCPServer


# 创建 MCP Server 实例
mcp = MCPServer("OmniSupport MCP Server")


@mcp.tool()
def get_product_info(product_name: str) -> dict:
    """查询演示商品的基础信息，不涉及客户个人数据。"""

    products = {
        "蓝牙无线耳机 Pro": {
            "name": "蓝牙无线耳机 Pro",
            "category": "耳机",
            "warranty": "一年有限保修",
        },
    }

    product = products.get(product_name)

    if product is None:
        return {
            "success": False,
            "message": "没有找到该商品",
        }

    return {
        "success": True,
        "data": product,
    }


@mcp.tool()
def list_products() -> dict:
    """查询演示商品目录中支持的商品列表。"""

    products = [
        "蓝牙无线耳机 Pro",
    ]

    return {
        "success": True,
        "data": {
            "products": products,
            "total": len(products),
        },
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
