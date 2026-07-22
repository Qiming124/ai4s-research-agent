# =============================================================================
# server.api 包：HTTP 路由层。
#
# 职责：
#     1. 各子模块定义 APIRouter（chat、projects 等）
#     2. server/main.py 通过 include_router 统一挂载
#     3. 层内只做参数校验与 Store/Agent 委派，不含核心业务图逻辑
#
# 架构位置：
#     - 被调用：server/main.py
#     - 调用：server/agents/、server/memory/、server/export/ 等
#
# 阅读提示：
#     - 新人从 chat.py 入口开始，再按功能浏览各路由文件
#
# Debug：
#     - 404 路由未注册 → main.py 是否 include 对应 router
# =============================================================================
