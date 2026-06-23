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

详见 [doc/docker.md](../doc/docker.md)。

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
docker pull crpi-xxx.cn-shenzhen.personal.cr.aliyuncs.com/<命名空间>/research-agent:v1.0
```

### 3. 启动

```bash
docker run -d \
  --name ai4s \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file ~/ai4s-research-agent/.env \
  -v ~/ai4s-research-agent/data:/app/data \
  -e SESSION_DB_PATH=/app/data/sessions.db \
  -e MCP_ALLOWED_DIRS=/app/data/mcp_files \
  -e RAG_CHROMA_PATH=/app/data/chroma \
  -e MCP_CONFIG_PATH=/app/mcp_servers.json \
  -e LOG_FORMAT=json \
  crpi-xxx.cn-shenzhen.personal.cr.aliyuncs.com/<命名空间>/research-agent:v1.0
```

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

---

## 五、常见问题

| 现象 | 处理 |
|------|------|
| MCP 未启用 | `.env` 设 `ENABLE_MCP=true` 且启动时带 `--env-file` |
| 页面 404 | 确认镜像含 `web/dist`（需 build 阶段 `npm run build`） |
| 会话丢失 | 挂载 `data/` 卷；`SESSION_STORE_BACKEND=sqlite` |
| Docker Hub 超时 | 配置 `registry-mirrors`，见 doc/docker.md |
