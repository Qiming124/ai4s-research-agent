# 部署指南

## 一、本地开发

### 后端

```bash
cd /path/to/ai4s-research-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp conf/.env.example conf/.env   # 编辑 DEEPSEEK_API_KEY、ENABLE_MCP 等
mkdir -p data/mcp_files data/chroma log
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir app
```

### Web 开发模式

```bash
cd app/web && npm install && npm run dev
# http://localhost:5173（Vite 代理 API 到 8000）
```

### Web 生产模式（与 API 同端口）

```bash
cd app/web && npm run build
cd ../../ && uvicorn server.main:app --host 0.0.0.0 --port 8000 --app-dir app
# http://localhost:8000
```

---

## 二、Docker Compose

详见 [docker.md](docker.md)。

```bash
cp conf/.env.example conf/.env
mkdir -p data/mcp_files data/chroma log
docker compose -f docker/docker-compose.yml up -d --build
```

旧版 Compose：

```bash
docker-compose -f docker/docker-compose.yml up -d --build
```

访问 `http://<主机>:8000`。

---

## 三、云服务器：拉取阿里云镜像

### 1. 准备 `.env`

```bash
mkdir -p ~/ai4s-research-agent/data/mcp_files ~/ai4s-research-agent/data/chroma
# 创建 .env，至少包含：
# DEEPSEEK_API_KEY=...
# ENABLE_MCP=true
```

### 2. 登录并拉取

```bash
docker login --username=<用户名> crpi-xxx.cn-shenzhen.personal.cr.aliyuncs.com
docker pull crpi-xxx.cn-shenzhen.personal.cr.aliyuncs.com/<命名空间>/research-agent:v2.2
```

### 3. 启动

```bash
docker run -d \
  --name ai4s \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file ~/ai4s-research-agent/conf/.env \
  -v ~/ai4s-research-agent/data:/repo/data \
  -v ~/ai4s-research-agent/conf:/repo/conf:ro \
  -e SESSION_DB_PATH=/repo/data/sessions.db \
  -e MCP_ALLOWED_DIRS=/repo/data/mcp_files:/repo/data/theory:/repo/data/experiments \
  -e RAG_CHROMA_PATH=/repo/data/chroma \
  -e MCP_CONFIG_PATH=/repo/conf/mcp_servers.json \
  -e THEORY_WORKSPACE_PATH=/repo/data/theory \
  -e EXPERIMENTS_PATH=/repo/data/experiments \
  -e LOG_FORMAT=json \
  crpi-xxx.cn-shenzhen.personal.cr.aliyuncs.com/<命名空间>/research-agent:v2.2
```

> 镜像 `WORKDIR` 为 `/repo`（见 `docker/Dockerfile`）。优先使用 Compose：`docker compose -f docker/docker-compose.yml up -d`。

### 4. 验证

```bash
docker logs ai4s --tail 30
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/mcp/status
```

云安全组需放行 **8000**（或 Nginx 反代 80/443）。

---

## 四、Nginx 反代（可选）

SSE 必须关闭代理缓冲：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 600s;
}
```

仓库内完整示例：[`conf/nginx/ai4s.conf`](../conf/nginx/ai4s.conf)（含 HTTP→HTTPS 与自签名证书）。

---

## 四-B、自签名 HTTPS（公网 IP 访问推荐）

纯 `http://公网IP` 不是浏览器安全上下文，`crypto.randomUUID` 会报错导致白屏。启用 HTTPS（即使自签名）可解决；前端也已内置 UUID 回退。

### 1. 生成证书

```bash
cd /root/ai4s-research-agent   # 按实际路径
chmod +x scripts/gen-self-signed-cert.sh
./scripts/gen-self-signed-cert.sh 47.112.10.62   # 换成你的公网 IP
```

产物：`conf/ssl/cert.pem`、`conf/ssl/key.pem`（私钥已被 gitignore）。

### 2. 安装 Nginx 配置

```bash
# 确认 conf/nginx/ai4s.conf 里 ssl_certificate* 指向本机绝对路径
cp conf/nginx/ai4s.conf /etc/nginx/sites-available/ai4s
ln -sf /etc/nginx/sites-available/ai4s /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### 3. 安全组

放行 **443/TCP**（以及可选保留 80，用于跳转 HTTPS）。

### 4. 访问

浏览器打开 **https://公网IP** → 出现「您的连接不是私密连接」→ 高级 → 继续访问。

重建前端（若刚拉了含 UUID 回退的代码）：

```bash
cd app/web && npm run build && cd ../..
systemctl restart ai4s-agent
```

---

## 五、常见问题

| 现象 | 处理 |
|------|------|
| MCP 未启用 | `.env` 设 `ENABLE_MCP=true` 且启动时带 `--env-file` |
| 页面 404 | 确认镜像含 `app/web/dist`（build 阶段在 `app/web` 执行 `npm run build`） |
| 会话丢失 | 挂载 `data/` 卷；`SESSION_STORE_BACKEND=sqlite` |
| Docker Hub 超时 | 配置 `registry-mirrors`，见 doc/docker.md |
| `crypto.randomUUID is not a function` | 用 HTTPS（见「四-B」）或拉取含 UUID 回退的前端并重新 `npm run build` |
| 浏览器提示证书不受信任 | 自签名正常现象：高级 → 继续访问；或换 Let's Encrypt |
