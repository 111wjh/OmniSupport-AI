// VITE_API_BASE_URL 是公开的服务地址，不能放 API 密钥等秘密。
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(
  /\/$/,
  '',
)
