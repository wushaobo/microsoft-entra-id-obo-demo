# Microsoft Entra ID OBO Demo — 实施计划

## Context

当前仓库 `/Users/wushaobo/Code/spike/microsoft_entra_id_obo_demo` 只有一个空的 `apps/` 目录。目标是搭建一个可运行的三服务 Demo，用于验证 Microsoft Entra ID 的登录、受保护 API 调用以及 **On-Behalf-Of (OBO)** 链路：

```
浏览器 SPA ──(A 的 access token)──> Service A ──(OBO 换 B 的 token)──> Service B
```

三个服务彼此独立，各自拥有一个 Entra 应用注册、独立的依赖与环境变量。不写测试、README、构建打包配置。

用户已确认：
- “get data from service B” 按钮走 **client → Service A OBO 端点 → Service B**，SPA 只申请 Service A 的 scope。
- SPA 使用 `loginPopup` / `logoutPopup`。
- React 使用 TypeScript（Vite）。

## 端口与服务

| 服务 | 技术栈 | 端口 | 鉴权 |
|---|---|---|---|
| `apps/client` | React 19 + TypeScript + Vite 8 + `@azure/msal-react` | 5173 | MSAL SPA 登录 |
| `apps/service_a` | FastAPI + Python 3.14 + uv + python-dotenv + msal + PyJWT | 8001 | 校验 Entra Bearer token |
| `apps/service_b` | FastAPI + Python 3.14 + uv + python-dotenv + PyJWT | 8002 | 校验 Entra Bearer token |

## Entra 应用注册（实现前需在 Entra 租户完成）

1. **SPA 应用注册**
   - 平台：Single-page application，Redirect URI：`http://localhost:5173`（建议同时加 `http://localhost:5173/`）。
   - API permissions → 添加 Service A 的 delegated scope `access_as_user` → Grant admin consent。
2. **Service A 应用注册**
   - Expose an API：Application ID URI 使用默认 `api://<A-client-id>`，新增 scope `access_as_user`。
   - 添加 Client secret（写入 `service_a/.env`）。
   - API permissions → 添加 Service B 的 delegated scope `access_as_user` → Grant admin consent。
   - Expose an API → Authorized client applications 中加入 **SPA 的 client id**（预授权，减少同意提示）。
3. **Service B 应用注册**
   - Expose an API：Application ID URI `api://<B-client-id>`，新增 scope `access_as_user`。
   - Authorized client applications 中加入 **Service A 的 client id**（OBO 的中间层必须被下游 API 信任）。
4. 三个应用保持同一租户（single-tenant），从 Overview 取 Tenant ID。

> scope 统一使用 `api://<client-id>/access_as_user`，不使用 `.default`，便于在 `scp` 中精确校验。

## 目录结构

```
apps/
├── client/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── .env.example
│   └── src/
│       ├── main.tsx              # msalInstance.initialize() 后挂载，MsalProvider
│       ├── App.tsx               # 布局、登录状态、两个数据面板
│       ├── authConfig.ts         # MSAL 配置、scope、API base URL（含 env 校验）
│       ├── useApiToken.ts        # acquireTokenSilent + popup 回退
│       ├── api.ts                # 带 Bearer 的 fetch 封装
│       ├── vite-env.d.ts         # ImportMetaEnv 类型
│       └── styles.css
├── service_a/
│   ├── pyproject.toml
│   ├── .env.example
│   └── app/
│       ├── __init__.py
│       ├── config.py             # load_dotenv + 必填项校验
│       ├── auth.py               # Bearer 校验依赖，返回 Principal
│       ├── obo.py                # MSAL OBO 换取 Service B token
│       └── main.py               # FastAPI app + CORS + 路由
└── service_b/
    ├── pyproject.toml
    ├── .env.example
    └── app/
        ├── __init__.py
        ├── config.py
        ├── auth.py               # 与 service_a 结构一致（服务独立，不共享包）
        └── main.py
```

根目录新增 `.gitignore`：`node_modules/`、`dist/`、`.venv/`、`__pycache__/`、`*.pyc`、`.env`、`.DS_Store`。

## 关键实现

### 1. Service B（先做，便于 A 联调）

**`pyproject.toml`** 依赖：`fastapi`、`uvicorn`（**不加 `[standard]`**，避免 uvloop 等二进制依赖的 3.14 wheel 风险）、`python-dotenv`、`pyjwt[crypto]`、`httpx`。设置 `requires-python = ">=3.14"`、`[tool.uv] package = false`，并在服务目录放 `.python-version`（内容 `3.14`），保证每个服务使用项目内 `.venv`。

**`config.py`**：启动时 `load_dotenv()`，读取并校验：
- `ENTRA_TENANT_ID`、`ENTRA_CLIENT_ID`、`ENTRA_REQUIRED_SCOPE`（默认 `access_as_user`）
- `ENTRA_AUDIENCE`（可选，额外接受的 audience）
- `CORS_ORIGINS`（可选，默认 `http://localhost:5173`；B 只被 A 服务端调用，实际不需要 CORS）

缺少必填项时直接抛出带变量名的错误，避免运行到一半才 401。

**`auth.py`**：核心校验逻辑（Service A 复制一份结构相同的实现；三个服务保持独立，不建立共享包）：
- `HTTPBearer(auto_error=False)`；无 token → `401`，带 `WWW-Authenticate: Bearer`。
- 用 `PyJWKClient` 从 `https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration` 的 `jwks_uri` 取签名密钥（`lru_cache` 缓存 metadata 与 client）。
- `jwt.decode(..., algorithms=["RS256"], audience=[...], issuer=<metadata.issuer>)`，校验 `exp` 等标准 claim。
- audience 同时接受 `<client-id>`、`api://<client-id>`，以及可选的 `ENTRA_AUDIENCE`，兼容不同 identifier URI 配置。
- 额外校验 `tid` 与租户一致（忽略大小写）。
- 校验 `scp`（空格分隔）包含 `ENTRA_REQUIRED_SCOPE`，缺失 → `403`。
- 返回 `Principal(claims, access_token)`，供路由和 OBO 使用。
- 校验通过后用 `logging` 记录 `aud`、`scp`、`tid`、`oid`（**不记录原始 token**），便于确认 OBO 下游 token 的 audience 与 scope。
- 依赖写成 **同步 `def`**，FastAPI 会在线程池执行，避免阻塞事件循环。

**路由**：
- `GET /api/message`（需鉴权）→ `PlainTextResponse("This message is from Service B.")`
- `GET /health`（无需鉴权）→ `{"status": "ok"}`

### 2. Service A

依赖与 B 相同，额外加 `msal`。

**`config.py`** 额外读取：`ENTRA_CLIENT_SECRET`、`SERVICE_B_BASE_URL`（默认 `http://localhost:8002`）、`SERVICE_B_SCOPE`（必填，`api://<B-client-id>/access_as_user`）。

**`obo.py`**：
- `lru_cache` 创建 `msal.ConfidentialClientApplication(client_id, client_credential=secret, authority=https://login.microsoftonline.com/{tenant})`。
- `acquire_token_on_behalf_of(user_assertion=<收到的 A token>, scopes=[SERVICE_B_SCOPE])`。
- 结果无 `access_token` 时返回 `502`，detail 中包含 MSAL 的 `error` / `error_description`（便于定位 AADSTS 错误），**不记录/返回任何 token**。

**路由**：
- `GET /api/message`（需鉴权）→ `PlainTextResponse("This message is from Service A.")`
- `GET /api/message-from-b`（需鉴权）→
  1. 取 `Principal.access_token` 做 OBO；
  2. `httpx.get(f"{SERVICE_B_BASE_URL}/api/message", headers={"Authorization": f"Bearer {b_token}"}, timeout=15)`；
  3. B 非 2xx → `502`，附带 B 的状态码与响应体（截断）；
  4. 成功 → JSON：
     ```json
     { "message": "This message is from Service B.", "source": "service-b", "via": "service-a-obo", "upstream_status": 200 }
     ```
- `GET /health`（无需鉴权）。
- CORS：`CORSMiddleware` 允许 `http://localhost:5173`、方法 `GET/OPTIONS`、headers `Authorization, Content-Type`；浏览器带 `Authorization` 会先发 OPTIONS 预检。

### 3. Client

**依赖**：`react@19`、`react-dom@19`、`@azure/msal-browser@5`、`@azure/msal-react@5`；dev：`vite@8`、`@vitejs/plugin-react@6`、`typescript@~5.9`、`@types/react`、`@types/react-dom`。
（Node 22.17 满足 Vite 8 的 `>=22.12`；msal-react 5 要求 React `^19.2.1`，选 React 19.3.x。）

**`src/authConfig.ts`**：
```ts
new PublicClientApplication({
  auth: {
    clientId: env.VITE_ENTRA_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${env.VITE_ENTRA_TENANT_ID}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: { cacheLocation: "localStorage", storeAuthStateInCookie: false },
})
```
- 导出 `serviceAScope = VITE_SERVICE_A_SCOPE`、`serviceABaseUrl = VITE_SERVICE_A_BASE_URL`。
- 启动时校验缺失的 `VITE_` 变量并抛错。

**`main.tsx`**：`await msalInstance.initialize()` → 恢复已有账号 `setActiveAccount` → 监听 `EventType.LOGIN_SUCCESS` 设置 active account → `MsalProvider` 包裹 `<App/>`。使用 popup 流程，无需 `handleRedirectPromise`。

**`useApiToken.ts`**：
- `acquireTokenSilent({ scopes: [serviceAScope], account })`；
- 捕获 `InteractionRequiredAuthError` 后回退 `acquireTokenPopup`。

**`App.tsx`**：
- 顶栏：未登录时显示 `Login` 按钮（点击 `loginPopup({ scopes: [serviceAScope] })`）+ 状态文字 `Not logged in`；已登录时显示 `Signed in as <name> (<username>)`，右上角 `Logout` 链接。
- 已登录区域：
  - 按钮 `get data from service A` + 只读 `<textarea>`；点击后请求 `GET {SERVICE_A_BASE_URL}/api/message`，展示原始响应文本。
  - 按钮 `get data from service B` + 只读 `<textarea>`；点击后请求 `GET {SERVICE_A_BASE_URL}/api/message-from-b`，将返回 JSON 格式化后展示（含 `message` 与 `via: service-a-obo`，以体现 OBO 链路）。
  - 请求期间禁用按钮并显示 loading；非 2xx 将状态码与响应体写入 textarea，便于排查。
- **Logout**：`await instance.logoutPopup({ account, postLogoutRedirectUri: window.location.origin })`，随后 `localStorage.clear()`、`sessionStorage.clear()`、`location.replace("/")`；popup 被拦截时回退 `logoutRedirect`。MSAL 缓存默认在 localStorage，`clear()` 会连同应用状态一并清除。
- 不使用 `useEffect` 触发数据请求，避免 StrictMode 双执行导致重复调用。

**`vite.config.ts`**：`@vitejs/plugin-react`，`server.port = 5173`、`strictPort: true`。

**`.env.example`**：
```
VITE_ENTRA_TENANT_ID=<tenant-id>
VITE_ENTRA_CLIENT_ID=<spa-client-id>
VITE_SERVICE_A_SCOPE=api://<service-a-client-id>/access_as_user
VITE_SERVICE_A_BASE_URL=http://localhost:8001
```

### 4. 环境变量文件

- `service_a/.env.example`：tenant id、A client id、A client secret、required scope、`SERVICE_B_SCOPE`、`SERVICE_B_BASE_URL`、`CORS_ORIGINS`。
- `service_b/.env.example`：tenant id、B client id、required scope、可选 audience。
- 每个文件顶部用注释写明对应的 Entra 配置来源；`.env` 已加入 `.gitignore`，不提交真实密钥。

## 验证步骤

1. 安装依赖（在各自目录内，使用项目级环境，不触碰全局 pip）：
   ```bash
   cd apps/service_b && uv sync
   cd ../service_a && uv sync
   cd ../client && npm install
   ```
2. 启动：
   ```bash
   # 三个终端分别执行
   cd apps/service_b && uv run uvicorn app.main:app --reload --port 8002
   cd apps/service_a && uv run uvicorn app.main:app --reload --port 8001
   cd apps/client    && npm run dev
   ```
3. 无 token 校验：`curl -i http://localhost:8001/api/message` → 期望 `401` 且带 `WWW-Authenticate: Bearer`；`/health` → `200`。
4. 浏览器打开 `http://localhost:5173`：
   - 点击 Login → 弹窗完成 Entra 登录 → 状态文字显示当前账号。
   - 点击 `get data from service A` → textarea 显示 `This message is from Service A.`。
   - 点击 `get data from service B` → textarea 显示来自 B 的消息，且 `via` 为 `service-a-obo`；Service A 终端应有 OBO 相关网络调用，Service B 收到的是 B 的 token。
   - 控制台 Network 中 `message-from-b` 请求只带 A 的 token，不会出现 B 的 token。
5. 点击 Logout → 弹窗登出后页面刷新，状态变回 `Not logged in`；DevTools → Application 中 localStorage/sessionStorage 为空。
6. 异常路径抽查：
   - 在 `.env` 中把 `SERVICE_B_SCOPE` 改成错误 scope → OBO 返回 `502` 且 detail 含 AADSTS 错误；
   - 用 Service B 的 token 调 Service A → `401`（audience 不匹配）；
   - 去掉 admin consent → 前端 `acquireTokenPopup` 报 AADSTS65001，textarea 展示错误。

## 风险与注意事项

- **Audience/Issuer 格式**：v2 access token 的 `aud` 可能是 `api://<guid>` 或 `<guid>`；校验时两者都接受。issuer 以 OpenID metadata 中的值为准，不做硬编码拼接。
- **Python 3.14 依赖**：`uvicorn` 不加 `[standard]`；`pyjwt[crypto]`/`cryptography` 使用预编译 wheel。若 `uv sync` 仍遇 wheel 缺失，先回退到兼容版本而非全局 pip 安装。
- **OBO 前置条件**：Service A 必须被 Service B 的 Authorized client applications 信任，且 delegated 权限已完成 admin consent；否则会得到 AADSTS65001 / 50013 类错误。
- **popup 被拦截**：登出与 token 获取均需捕获 popup 异常；登出回退 `logoutRedirect`。
- **CORS 预检**：`Authorization` 头会触发 OPTIONS；必须允许该 header，且 origin 精确匹配（不带结尾 `/`）。
- **统一使用 `localhost`**：Entra 重定向 URI、`VITE_SERVICE_A_BASE_URL`、CORS 均按 `http://localhost:5173` / `http://localhost:8001` 配置；若改用 `127.0.0.1`，需要同步新增重定向 URI 并调整 CORS，否则登录或请求会失败。
- **前端不缓存 B 的 token**：B 的 token 只在 Service A 进程内由 MSAL 持有，符合 OBO 设计。
