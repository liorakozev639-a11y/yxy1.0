# Vercel + Supabase 免费上线指南

本方案用于把“留白计划”部署为一个可分享的网页。前端和 FastAPI 后端放在同一个 Vercel 项目里，PostgreSQL 使用 Supabase。

## 1. 准备条件

- GitHub 仓库已经包含最新代码：`https://github.com/liorakozev639-a11y/yxy1.0`
- Supabase 项目已经创建，并且能拿到 PostgreSQL 连接串。
- Vercel 账号可以使用 GitHub 登录。

## 2. Supabase 数据库连接串

进入 Supabase 项目：

```text
Project Settings -> Database -> Connection string -> Transaction pooler
```

复制形如下面的地址，并把 `[YOUR-PASSWORD]` 替换成你创建 Supabase 项目时设置的数据库密码：

```text
postgresql://postgres.umdhznohzbflvhwqryut:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

注意：数据库密码只粘贴到 Vercel 环境变量，不要写入代码、README 或聊天记录。

## 3. 在 Vercel 导入 GitHub 仓库

1. 打开 `https://vercel.com/new`。
2. 选择 GitHub 登录。
3. Import `liorakozev639-a11y/yxy1.0` 仓库。
4. Framework Preset 选择 `Other`。
5. Root Directory 保持仓库根目录。
6. Build and Output Settings 保持默认，项目会读取根目录的 `vercel.json`。

## 4. 配置环境变量

在 Vercel 项目的 Environment Variables 中添加：

```text
SESSION_DATABASE_URL=你的 Supabase Transaction pooler PostgreSQL 连接串
FRONTEND_ORIGINS=https://你的-vercel-域名.vercel.app
```

如果第一次还不知道 Vercel 域名，可以先只设置 `SESSION_DATABASE_URL` 完成部署；拿到域名后再补 `FRONTEND_ORIGINS` 并 Redeploy。

## 5. 部署后验证

部署成功后访问：

```text
https://你的-vercel-域名.vercel.app/
https://你的-vercel-域名.vercel.app/health
https://你的-vercel-域名.vercel.app/docs
```

期望结果：

- 首页显示像素风“留白计划”产品页面。
- `/health` 返回后端状态 JSON。
- `/docs` 能打开 FastAPI Swagger。
- 完成问卷后可以生成计划、替换任务、调整任务、查看历史洞察。

## 6. 本地与线上 API 的区别

本地开发时，前端默认调用：

```text
http://127.0.0.1:8000
```

线上部署时，前端默认调用当前 Vercel 同源域名：

```text
https://你的-vercel-域名.vercel.app
```

因此线上不需要单独配置 `FREE_TIME_API_BASE_URL`，也不会再错误请求 `:8000` 端口。
