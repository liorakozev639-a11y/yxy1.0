# 留白计划网页版上线指南

本文档用于把当前项目部署成可以分享链接访问的网页版 / PWA App。

## 1. 最小上线结构

推荐先使用一台服务器承载三部分：

- PostgreSQL：保存会话、问卷、画像、计划、执行记录和反馈。
- FastAPI 后端：监听本机 `127.0.0.1:8000`，由 Nginx 反向代理出去。
- 静态前端：直接由 Nginx 托管 `frontend` 目录。

浏览器访问顺序：

```text
用户浏览器
-> https://你的域名
-> Nginx
-> 静态前端或 FastAPI 后端
-> PostgreSQL
```

## 2. 服务器需要具备的条件

- 一台公网服务器，例如 `148.113.16.140`。
- 可以登录服务器的 SSH 账号，或者服务器面板账号。
- Python 3.12。
- PostgreSQL。
- Nginx。
- 一个域名，正式上线推荐准备；只有 IP 也能先测试。
- HTTPS 证书，正式 PWA 安装体验需要 HTTPS。

## 3. 后端环境变量

复制模板：

```powershell
Copy-Item deploy\.env.production.example .env.production
```

把 `.env.production` 中的值改成真实配置：

```text
SESSION_DATABASE_URL=postgresql://postgres:<database_password>@127.0.0.1:5432/free_time_agent
FRONTEND_ORIGINS=https://<your-domain>,http://148.113.16.140
```

不要把真实 `.env.production` 提交到 GitHub。

## 4. 前端公网 API 配置

复制模板覆盖正式前端配置：

```powershell
Copy-Item deploy\frontend-config.production.example frontend\config.js
```

把里面的地址改成正式后端地址：

```javascript
window.FREE_TIME_API_BASE_URL = 'https://<your-domain>';
```

如果后端和前端在同一个域名下，并用 Nginx 代理 `/api` 与 `/health`，可以设置成：

```javascript
window.FREE_TIME_API_BASE_URL = 'https://<your-domain>';
```

如果使用独立服务器或 Render 这种前后端分离部署，不要在正式生产环境留空。留空时，本地域名会默认请求当前主机的 `:8000` 端口；Vercel 等线上同域名部署会默认请求当前线上域名。

## 5. 本地一键启动

在 Windows 本机开发时，可以执行：

```powershell
Set-Location D:\yxy1.0
.\deploy\start-local-product.ps1
```

启动后访问：

- 前端：`http://127.0.0.1:5173/`
- Swagger：`http://127.0.0.1:8000/docs`

检查本地服务：

```powershell
.\deploy\check-local-product.ps1
```

## 6. Nginx 配置

参考 `deploy/nginx-free-time-agent.conf`。

部署时需要替换：

- `<your-domain>`：你的域名。
- `/srv/free-time-agent/frontend`：服务器上的前端目录。

完成后测试：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 7. 上线验收清单

- 打开 `https://你的域名`，可以看到像素风首页。
- 首页可以创建会话，并进入问卷。
- 问卷提交后可以看到偏好画像解释页。
- 可以生成 10 个推荐任务和计划时间线。
- 可以开始、完成、跳过、替换任务。
- 可以进入历史计划与偏好学习视图。
- `https://你的域名/manifest.json?v=pwa-v1` 返回 200。
- `https://你的域名/service-worker.js` 返回 200。
- 手机浏览器可以添加到桌面。

## 8. 当前还需要你提供的信息

如果要由 Codex 继续帮你真正部署到 `148.113.16.140`，需要提供其中一种方式：

- SSH 地址、用户名、密码或密钥登录方式。
- 宝塔、1Panel、Plesk 等服务器面板登录方式。
- 已经部署好的服务器目录和你希望使用的域名。

没有服务器登录权限时，只能完成本地仓库的部署准备，不能直接把进程运行到公网服务器上。

## 9. 免费方案一：Supabase + Vercel 操作步骤

如果没有服务器，并且 Render 要求绑定银行卡，优先使用 Vercel。Vercel 可以把当前仓库中的静态前端和 FastAPI 后端放在同一个域名下，PostgreSQL 仍使用 Supabase。

完整步骤见：

```text
deploy/README-vercel.md
```

关键点：

- Vercel 读取根目录 `vercel.json`。
- `api/index.py` 是 Vercel 的 FastAPI Serverless 入口。
- `frontend/config.js` 可以保持为空，线上会自动使用当前 Vercel 域名作为 API 地址。
- 只需要在 Vercel 环境变量中填写 `SESSION_DATABASE_URL`。

## 10. 免费方案二：Supabase + Render 操作步骤

这个方案不需要你购买服务器，适合先让别人通过链接体验 MVP。

### 10.1 申请 Supabase 数据库

1. 打开 `https://supabase.com/`。
2. 使用 GitHub 或邮箱注册。
3. 点击 `New project`。
4. 项目名填写 `free-time-agent`。
5. 保存你自己设置的数据库密码。
6. 创建完成后进入 `Project Settings -> Database`。
7. 复制 PostgreSQL connection string。

最终你需要拿到类似这样的地址：

```text
postgresql://postgres.xxx:<你的数据库密码>@aws-xxx.pooler.supabase.com:6543/postgres
```

### 10.2 申请 Render 后端

1. 打开 `https://render.com/`。
2. 使用 GitHub 登录。
3. 连接仓库 `liorakozev639-a11y/yxy1.0`。
4. 选择 `New -> Blueprint`。
5. 选择仓库根目录中的 `render.yaml`。
6. 创建 `free-time-agent-api` 和 `free-time-agent-web` 两个服务。
7. 在 `free-time-agent-api` 的 Environment 中填写：

```text
SESSION_DATABASE_URL=Supabase 给你的 PostgreSQL 地址
FRONTEND_ORIGINS=https://free-time-agent-web.onrender.com
```

### 10.3 检查 Render 后端

部署完成后打开：

```text
https://free-time-agent-api.onrender.com/health
```

成功时应返回：

```json
{
  "data": {
    "status": "ok",
    "service": "api"
  },
  "error": null
}
```

再打开：

```text
https://free-time-agent-api.onrender.com/api/v1/health/database
```

成功时 `data.status` 应为 `ok`。

### 10.4 检查 Render 前端

打开：

```text
https://free-time-agent-web.onrender.com/
```

能进入像素风首页，并且可以完成问卷和生成计划，说明前端、后端和 Supabase 已经连通。

### 10.5 如果服务名被占用

如果 Render 提示 `free-time-agent-api` 或 `free-time-agent-web` 名称不可用，需要改两个地方：

1. `render.yaml` 中对应服务名。
2. `FREE_TIME_API_BASE_URL` 和 `FRONTEND_ORIGINS` 中的 `.onrender.com` 地址。

改完后提交到 GitHub，再重新部署。
