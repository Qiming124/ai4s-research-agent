# TLS 证书目录（自签名）

本目录存放 Nginx / uvicorn 使用的 TLS 证书。

## 生成

在仓库根目录执行：

```bash
chmod +x scripts/gen-self-signed-cert.sh
./scripts/gen-self-signed-cert.sh 你的公网IP
# 例：./scripts/gen-self-signed-cert.sh 47.112.10.62
```

生成文件：

| 文件 | 说明 |
|------|------|
| `cert.pem` | 证书（公钥） |
| `key.pem` | 私钥（**勿提交 Git**） |

## 安全

- `*.pem` / `*.key` / `*.crt` 已在本目录 `.gitignore` 中忽略
- 自签名仅适合内网/演示；公网站点建议用 Let's Encrypt

## 与 HTTP 的关系

通过 `https://公网IP` 访问后，浏览器处于安全上下文，`crypto.randomUUID` 可用。
若仍用纯 HTTP，前端也会有 UUID 回退实现，但推荐启用 HTTPS。
