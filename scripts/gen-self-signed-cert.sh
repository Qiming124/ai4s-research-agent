#!/usr/bin/env bash
# 生成 Nginx / uvicorn 用的自签名 TLS 证书（含 IP SAN，便于 https://公网IP 访问）
#
# 用法（在仓库根目录）：
#   ./scripts/gen-self-signed-cert.sh                 # 默认 CN=localhost
#   ./scripts/gen-self-signed-cert.sh 47.112.10.62    # 按公网 IP 生成
#   CERT_DAYS=825 ./scripts/gen-self-signed-cert.sh 47.112.10.62
#
# 产物：
#   conf/ssl/cert.pem  — 证书（可公开）
#   conf/ssl/key.pem   — 私钥（勿提交 Git）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSL_DIR="${ROOT}/conf/ssl"
HOST_IP="${1:-localhost}"
DAYS="${CERT_DAYS:-825}"

mkdir -p "${SSL_DIR}"

if [[ ! -f "${SSL_DIR}/.gitignore" ]]; then
  cat > "${SSL_DIR}/.gitignore" << 'EOF'
# 私钥与本地生成的证书勿入库
*.pem
*.key
*.crt
!.gitignore
!README.md
EOF
fi

# OpenSSL 3 / 1.1.1+：用 -addext 写 SAN；旧版回退到临时 openssl.cnf
SAN="DNS:localhost,IP:127.0.0.1"
if [[ "${HOST_IP}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="${SAN},IP:${HOST_IP}"
  CN="${HOST_IP}"
elif [[ "${HOST_IP}" != "localhost" ]]; then
  SAN="${SAN},DNS:${HOST_IP}"
  CN="${HOST_IP}"
else
  CN="localhost"
fi

echo "生成自签名证书 → ${SSL_DIR}/"
echo "  CN=${CN}"
echo "  SAN=${SAN}"
echo "  有效期=${DAYS} 天"

if openssl req -x509 -newkey rsa:2048 -sha256 -nodes \
  -keyout "${SSL_DIR}/key.pem" \
  -out "${SSL_DIR}/cert.pem" \
  -days "${DAYS}" \
  -subj "/CN=${CN}/O=AI4S Research Agent/C=CN" \
  -addext "subjectAltName=${SAN}" 2>/dev/null; then
  :
else
  TMP_CFG="$(mktemp)"
  cat > "${TMP_CFG}" << EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = ${CN}
O = AI4S Research Agent
C = CN

[v3_req]
subjectAltName = ${SAN}
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes \
    -keyout "${SSL_DIR}/key.pem" \
    -out "${SSL_DIR}/cert.pem" \
    -days "${DAYS}" \
    -config "${TMP_CFG}"
  rm -f "${TMP_CFG}"
fi

chmod 600 "${SSL_DIR}/key.pem"
chmod 644 "${SSL_DIR}/cert.pem"

echo "完成："
echo "  证书: ${SSL_DIR}/cert.pem"
echo "  私钥: ${SSL_DIR}/key.pem"
echo
echo "下一步（Nginx）："
echo "  1. 编辑 conf/nginx/ai4s.conf 中的 ssl_certificate 路径（默认可直接用）"
echo "  2. cp conf/nginx/ai4s.conf /etc/nginx/sites-available/ai4s"
echo "  3. nginx -t && systemctl reload nginx"
echo "  4. 安全组放行 443，浏览器访问 https://${HOST_IP}"
echo "  （首次会提示「不安全」，点高级 → 继续访问即可）"
