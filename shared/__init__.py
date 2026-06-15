"""
shared 包：服务端与客户端共用的数据结构。

在架构中的位置：
    - 被 server/api/chat.py 用于请求/响应校验
    - 被 client/cli.py 用于构造 HTTP 请求体

类比 C++：类似放在 common/ 目录下的 protobuf message 或 nlohmann::json 结构体定义，
         确保 client 与 server 对同一数据格式有一致理解。
"""
