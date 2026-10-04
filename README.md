# 智能实验室预约系统（AI Lab）

一个前后端分离的实验室预约管理系统，在常规的「实验室 / 设备 / 预约 / 审核」业务之上，集成了 **RAG 知识库问答**与 **LangGraph 智能预约 Agent**，用户可以直接用自然语言完成「查实验室 → 问设备 → 确认信息 → 提交预约」的完整流程。

---

## 一、系统简介

### 1.1 业务能力

| 角色 | 能做什么 |
| --- | --- |
| 学生（student） | 浏览实验室列表与设备、提交预约、查看/取消自己的预约、修改个人资料与密码、与 AI 助手对话 |
| 管理员（admin） | 实验室管理、设备管理、用户管理、预约审核（通过/拒绝）、AI 助手对话 |

预约的完整生命周期：**提交（待审核） → 管理员审核（通过 / 拒绝） → 使用**，另有两条自动/手动出口：学生主动取消、系统定时扫描把过期的待审核单自动取消。

### 1.2 技术栈

| 层次 | 选型 |
| --- | --- |
| 后端框架 | FastAPI 0.115 + Uvicorn |
| ORM / 数据库 | SQLAlchemy 2.0（`Mapped` 声明式）+ MySQL（PyMySQL） |
| 参数校验 / 配置 | Pydantic v2 + pydantic-settings |
| 认证鉴权 | PyJWT（HS256）+ bcrypt 密码哈希 + OAuth2PasswordBearer |
| 大模型 | LangGraph + langchain-openai（走 OpenAI 兼容协议，可对接 DeepSeek / 通义 / OpenAI 等） |
| 向量检索（RAG） | ChromaDB（本地持久化）+ `BAAI/bge-small-zh-v1.5` 中文向量模型（sentence-transformers） |
| 流式输出 | SSE（`text/event-stream`）+ LangGraph `astream_events(v2)` |
| 前端 | Vue 3（`<script setup>`）+ Vite + Vue Router + Element Plus（中文语言包）+ Axios |
| 前端渲染 | marked（Markdown）+ DOMPurify（XSS 过滤） |

---

## 二、目录结构与文件介绍

```
ai-lab/
├── .vscode/                     # 编辑器调试配置
│   ├── launch.json              #   F5 一键调试 FastAPI（uvicorn app.main:app）
│   ├── tasks.json               #   调试前置任务 kill-port-8000
│   └── kill-port-8000.ps1       #   释放 8000 端口，避免上次进程没退干净
├── backend/                     # 后端服务
│   ├── .env                     # 环境变量（数据库 / JWT / 大模型），已被 .gitignore 忽略
│   ├── requirements.txt         # Python 依赖清单
│   ├── data/
│   │   ├── kb/                  # 知识库源文件（Markdown），见下方说明
│   │   └── chroma/              # ChromaDB 向量库持久化目录（自动生成）
│   └── app/
│       ├── main.py              # 应用入口：建表、生命周期、CORS、异常注册、路由挂载、静态目录
│       ├── config.py            # Settings 配置类 + 上传目录/大小/后缀白名单
│       ├── database.py          # engine / SessionLocal / get_db + Base（统一 id、create_time、update_time）
│       ├── api/                 # 路由层（只做参数接收与响应包装，业务在 services）
│       ├── schemas/             # Pydantic 请求/响应模型
│       ├── models/              # SQLAlchemy ORM 模型
│       ├── services/            # 业务逻辑层
│       ├── dependencies/        # 依赖注入（登录态、管理员校验）
│       ├── utils/               # 工具函数（JWT、密码）
│       └── common/              # 统一响应体与全局异常处理
└── frontend/                    # 前端工程
    ├── vite.config.js           # 端口 5173、/api 与 /upload 代理、SSE 缓冲关闭、@ 别名
    ├── .env.development         # VITE_API_BASE_URL
    ├── index.html               # 应用外壳（标题：智能实验室预约系统）
    └── src/
        ├── main.js              # 挂载 Vue、Element Plus（zh-cn）、全局注册全部图标
        ├── App.vue              # 根组件
        ├── router/index.js      # 路由表 + 全局前置守卫（无 token 一律打回登录页）
        ├── layouts/Layout.vue   # 主框架：顶部栏 + 用户下拉 + 左侧按角色渲染的菜单
        ├── views/               # 页面
        ├── components/          # 可复用组件
        ├── api/                 # 接口封装（按模块拆分）
        ├── utils/               # request 拦截器、本地登录态、用户状态
        └── assets/              # 全局样式与图片
```

### 2.1 后端文件详解

#### 入口与基础设施

| 文件 | 说明 |
| --- | --- |
| `app/main.py` | 应用装配中心。启动时用 `Base.metadata.create_all` 自动建表；`lifespan` 中预热向量库并启动「过期预约扫描」异步任务，退出时 `task.cancel()` 并 `gather(return_exceptions=True)` 优雅收尾。注册了 CORS（只放开 5173）、四个异常处理器、`/api` 路由、`/uploads` 静态目录。 |
| `app/config.py` | `Settings` 从 `.env` 读取数据库、JWT、大模型配置；同时定义上传目录 `uploads/`、单文件 100MB 上限、允许的后缀白名单。 |
| `app/database.py` | 创建 engine 与 `SessionLocal`，提供 `get_db()` 依赖；`Base` 抽出公共字段 `id / create_time / update_time`，业务表无需重复声明。 |
| `app/common/response.py` | 统一响应体 `Response(code, message, data)` + `success()/error()` 工厂，以及分页体 `PageResponse(list, total)`。 |
| `app/common/exceptions.py` | `BusinessException` 自定义业务异常 + 四个处理器：业务异常（HTTP 200 但 code 非 200）、Starlette HTTP 异常、参数校验异常（422）、全局兜底（500，不泄露堆栈细节）。 |
| `app/dependencies/auth.py` | `get_current_user`：解析 JWT → 查用户 → 校验状态（禁用则 401）；`get_current_admin`：在登录基础上校验 `role == "admin"`。 |
| `app/utils/jwt.py` | `create_access_token` / `decode_access_token`，payload 只放 `user_id` 与 `exp`。 |
| `app/utils/password.py` | bcrypt 哈希与校验封装。 |

#### 数据模型（`app/models/`）

| 文件 | 表 | 关键字段 |
| --- | --- | --- |
| `user.py` | `users` | username、password（bcrypt）、name、role（student/admin）、email、phone、avatar、status |
| `lab.py` | `labs` | name、description、img、location、capacity、open_time、close_time、status（0 关闭 / 1 开放） |
| `equipment.py` | `equipments` | lab_id（外键）、name、description、img、spec、quantity、status（0 维修 / 1 正常），`lab` 关系对象 |
| `reservation.py` | `reservations` | user_id、lab_id、equipment_id（为空表示预约整个实验室）、date、start_time、end_time、remark、status（0 待审核 / 1 已通过 / 2 已拒绝 / 3 已取消），并挂载 user / lab / equipment 关系便于回显名称 |

#### 业务逻辑（`app/services/`）

| 文件 | 说明 |
| --- | --- |
| `auth_service.py` | 登录（校验账号密码、账号状态、签发 JWT）与注册（重名校验，注册一律为 student）。 |
| `user_service.py` | 个人信息查询/修改（`exclude=("role","status")` 防止越权改角色）、改密码（校验原密码且新旧不能相同）、用户分页模糊查询与增删改（禁止删除当前登录用户）。 |
| `lab_service.py` | 实验室分页（支持 name/location 模糊 + 状态筛选）、详情、新增（重名校验）、修改、删除。 |
| `equipment_service.py` | 设备分页（按 lab_id / name 筛选并回填 `lab_name`）、增删改；修改时校验「同一实验室内设备不能重名」。 |
| `reservation_service.py` | 预约核心：分页（非管理员只能看自己的）、创建、取消、审核、过期扫描。 |
| `kb_service.py` | RAG 检索：ChromaDB 集合懒加载 + 启动预热；首次访问时把 `data/kb/*.md` 整篇入库存为一个文档；`search()` 查询后按 `1/(1+距离)` 折算相关度排序，取 Top-2 拼成带文件名标注的上下文。 |
| `agent_service.py` | **当前使用的 AI 实现**（见亮点二）。 |
| `agent_tools.py` | Agent 可调用的 5 个工具，通过闭包把 `db` 与 `current_user` 注入，保证工具执行也受登录态约束。 |
| `ai_service.py` | 早期版本的手写「OpenAI Function Calling + RAG」实现，当前**未被任何路由引用**，保留作为对照与演进记录。 |

#### 接口层（`app/api/`）

| 文件 | 前缀 | 说明 |
| --- | --- | --- |
| `auth.py` | `/api/auth` | 登录、注册 |
| `user.py` | `/api/user` | 个人信息、改密码、用户管理（管理端接口均挂 `get_current_admin`） |
| `files.py` | `/api/files` | 文件上传：后缀白名单 → 大小校验 → `时间戳_随机串` 重命名 → 流式写盘 → 返回可访问 URL |
| `lab.py` | `/api/lab` | 实验室列表/详情/增删改 |
| `equipment.py` | `/api/equipment` | 设备列表/增删改 |
| `reservation.py` | `/api/reservation` | 预约列表/创建/取消/审核 |
| `ai.py` | `/api/ai` | `POST /chat` 一次性返回、`POST /chat/stream` SSE 流式返回 |

### 2.2 前端文件详解

#### 核心

| 文件 | 说明 |
| --- | --- |
| `main.js` | 创建应用，挂载路由与 Element Plus（中文语言包），并遍历注册全部 Element Plus 图标为全局组件。 |
| `App.vue` | 根组件，仅承载 `<router-view>`。 |
| `router/index.js` | 路由表：`/manager` 为带布局的父路由，子路由含首页、实验室列表、我的预约、实验室管理、设备管理、用户管理、预约审核、AI 助手；另有 `/login`、`/register`。全局前置守卫：非登录/注册页且无 token 时重定向到登录页。 |
| `layouts/Layout.vue` | 主布局：顶部标题与用户下拉（个人信息 / 修改密码 / 退出登录）、左侧菜单（按 `userInfo.role` 用 `v-if` 控制显示）、右侧 `<router-view>`。 |
| `utils/request.js` | Axios 实例：请求拦截自动带 `Authorization: Bearer <token>`；响应拦截统一判断 `code`，401 时清登录态并跳登录页，网络异常给出友好提示。 |
| `utils/auth.js` | token 与用户信息的 localStorage 读写、`logout()`。 |
| `utils/user.js` | 基于 `ref` 的轻量全局用户状态（`useUser`），登录/更新后立即响应式刷新。 |
| `assets/css/global.css` | 全局重置样式：盒模型、铺满视口、微软雅黑字体、去掉标题与列表默认边距等。 |

#### 页面（`src/views/`）

| 文件 | 页面 | 说明 |
| --- | --- | --- |
| `Login.vue` | 登录 | 表单校验 → 调登录接口 → 存登录态 → 跳首页；含注册入口 |
| `Register.vue` | 注册 | 账号 + 密码 + 确认密码（自定义校验两次一致），成功后回到登录页 |
| `Home.vue` | 系统首页 | 问候语与角色标识、统计卡片（开放实验室数 / 我的预约 / AI 助手）、功能说明与快捷入口，管理员额外显示管理入口 |
| `Profile.vue` | 个人信息 | 查看/编辑名称、邮箱、手机号，头像上传（限图片、≤2MB），保存后同步本地用户信息 |
| `Password.vue` | 修改密码 | 原密码 + 新密码 + 确认校验，修改成功后强制登出并跳登录页 |
| `User.vue` | 用户管理（管理员） | 关键词分页表格，新增/编辑/删除弹窗 |
| `Lab.vue` | 实验室管理（管理员） | 分页表格 + 查询 + 增删改，弹窗支持封面上传与开放时段设置 |
| `LabList.vue` | 实验室列表（学生） | 卡片网格展示封面/位置/容量/开放时间，「查看设备」与「预约」按钮，内嵌预约弹窗 |
| `Equipment.vue` | 设备管理（管理员） | 按关键词 + 实验室筛选的分页表格，支持图片上传与增删改 |
| `LabEquipment.vue` | 实验室设备列表 | 依据路由 `lab_id` 加载实验室详情与设备列表，可预约整个实验室或指定设备 |
| `MyReservation.vue` | 我的预约（学生） | 按状态筛选，展示类型/设备/时段/备注/状态，待审核记录可取消 |
| `AuditReservation.vue` | 预约审核（管理员） | 默认筛选待审核，对记录执行「通过 / 拒绝」 |
| `AIChat.vue` | AI 智能助手 | 气泡式对话界面，消费 SSE 流实现打字机输出与工具调用过程可视化 |

#### 组件与接口封装

| 文件 | 说明 |
| --- | --- |
| `components/ReserveDialog.vue` | 通用预约弹窗（`visible / labId / labName / equipmentId / equipmentName` 作为 props），选择日期、起止时间、备注后提交，通过 `update:visible` 双向控制显隐 |
| `api/auth.js` | 登录、注册 |
| `api/user.js` | 个人信息、改密码、用户管理 CRUD |
| `api/lab.js` / `api/equipment.js` | 实验室 / 设备的分页与增删改查 |
| `api/reservation.js` | 创建预约、预约分页、取消、审核 |
| `api/file.js` | 基于 `FormData` 的文件上传 |
| `api/ai.js` | `chatApi`（一次性）与 `chatStreamApi`（`fetch` 读取 SSE：手动附带 JWT、按 `\n\n` 分帧、逐行解析 `data:` JSON、401 或非流式响应时抛错） |

### 2.3 知识库（`backend/data/kb/`）

内置 4 篇 Markdown 作为 RAG 语料，每篇整篇入库为一个向量文档：

- `预约规则.md` — 预约流程与状态说明
- `开放时间.md` — 各类实验室的开放时段
- `安全规范.md` — 实验室安全要求
- `设备使用.md` — 设备预约与使用规范

> **修改知识库后需重建索引**：`kb_service` 仅在集合为空时写入。改动 `data/kb/*.md` 后请删除 `backend/data/chroma/` 目录再重启后端。

---

## 三、启动命令

### 3.1 环境要求

| 组件 | 版本建议 |
| --- | --- |
| Python | 3.11+（当前开发环境为 3.13） |
| Node.js | ^22.18.0 或 ≥24.12.0（见 `frontend/package.json` 的 `engines`） |
| MySQL | 8.x，字符集 `utf8mb4` |

### 3.2 准备数据库

```sql
CREATE DATABASE `ai-lab` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

建库即可，**数据表由后端启动时自动创建**（`Base.metadata.create_all`）。

### 3.3 配置环境变量

复制模板生成配置文件（`.env` 已被 `.gitignore` 忽略，不会入库）：

```bash
cd backend
cp .env.example .env
```

`.env.example` 内容如下，按实际情况填写：

```ini
# 数据库连接
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/ai-lab

# JWT 配置
JWT_SECRET_KEY=请替换为一串足够随机的字符串
JWT_EXPIRE_HOURS=24
JWT_ALGORITHM=HS256

# 大模型配置（OpenAI 兼容协议，示例为 DeepSeek）
LLM_API_KEY=sk-你的APIKey
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
```

### 3.4 启动后端

```bash
cd backend

# 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows (cmd / PowerShell)
# source .venv/Scripts/activate # Windows (Git Bash)
# source .venv/bin/activate     # macOS / Linux

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --reload --port 8000
```

启动后访问：

- 服务根路径：http://127.0.0.1:8000/
- 交互式 API 文档（Swagger）：http://127.0.0.1:8000/docs

> **首次启动较慢属正常**：`lifespan` 会预热向量库，`sentence-transformers` 需要下载 `BAAI/bge-small-zh-v1.5` 模型（约 100MB 级），并完成一次编码。
>
> **VSCode 一键调试**：按 `F5` 选择 `Python Debugger: FastAPI`，会先执行 `kill-port-8000` 释放端口，再以 `backend` 为工作目录启动 uvicorn。

### 3.5 启动前端

```bash
cd frontend

npm install
npm run dev        # 开发模式，http://localhost:5173
```

其他脚本：

```bash
npm run build      # 生产构建，输出 dist/
npm run preview    # 预览构建产物
npm run format     # Prettier 格式化 src/（semi:false、singleQuote、printWidth:100）
```

前端通过 `vite.config.js` 的代理把 `/api`、`/upload` 转发到 `http://127.0.0.1:8000`，并针对 `text/event-stream` 关闭响应缓冲，保证 SSE 实时性。

### 3.6 初始化第一个账号

1. 打开 http://localhost:5173/register 注册一个账号（默认角色为 `student`）。
2. 需要管理员权限时，直接在数据库提升：

```sql
UPDATE users SET role = 'admin' WHERE username = '你的账号';
```

3. 重新登录即可看到「实验室管理 / 设备列表管理 / 用户管理 / 预约审核」等菜单。

---

## 四、接口一览

所有接口统一前缀 `/api`，除登录/注册外均需请求头 `Authorization: Bearer <token>`。

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公开 | 登录，返回 token 与用户信息 |
| POST | `/api/auth/register` | 公开 | 注册（student） |
| GET | `/api/user/me` | 登录 | 当前用户信息 |
| PUT | `/api/user/me` | 登录 | 修改个人信息 |
| PUT | `/api/user/password` | 登录 | 修改密码 |
| GET | `/api/user/list` | 管理员 | 用户分页（keywords 模糊） |
| POST | `/api/user` | 管理员 | 新增用户 |
| PUT | `/api/user/{user_id}` | 管理员 | 更新用户 |
| DELETE | `/api/user/{user_id}` | 管理员 | 删除用户 |
| POST | `/api/files/upload` | 公开 | 文件上传 |
| GET | `/api/lab/list` | 登录 | 实验室分页（keywords / status） |
| GET | `/api/lab/{lab_id}` | 登录 | 实验室详情 |
| POST | `/api/lab` | 管理员 | 新增实验室 |
| PUT | `/api/lab/{lab_id}` | 管理员 | 更新实验室 |
| DELETE | `/api/lab/{lab_id}` | 管理员 | 删除实验室 |
| GET | `/api/equipment/list` | 登录 | 设备分页（keywords / lab_id） |
| POST | `/api/equipment` | 管理员 | 新增设备 |
| PUT | `/api/equipment/{equipment_id}` | 管理员 | 更新设备 |
| DELETE | `/api/equipment/{equipment_id}` | 管理员 | 删除设备 |
| GET | `/api/reservation/list` | 登录 | 预约分页（学生仅见自己的，status 筛选） |
| POST | `/api/reservation` | 登录 | 创建预约 |
| PUT | `/api/reservation/{id}/cancel` | 登录 | 取消预约（仅本人、仅待审核） |
| PUT | `/api/reservation/{id}/audit` | 管理员 | 审核（body：`{"status": 1\|2}`） |
| POST | `/api/ai/chat` | 登录 | AI 对话，一次性返回完整文本 |
| POST | `/api/ai/chat/stream` | 登录 | AI 对话，SSE 流式返回 |

统一响应格式：

```json
{ "code": 200, "message": "请求成功", "data": {} }
```

---

## 五、亮点功能介绍

### 亮点一：RAG 知识库问答，回答有据可依

- 使用 **ChromaDB** 本地向量库 + **`BAAI/bge-small-zh-v1.5`** 中文向量模型，对 `data/kb/` 下的实验室规则文档建立索引。
- `kb_service.search()` 检索后按 `1 / (1 + 距离)` 折算相似度并排序，取 **Top-2** 片段拼成带 `[文件名]` 标注的上下文，避免把无关文档塞进 prompt。
- 应用启动时通过 `lifespan` 完成**向量库预热**（模型加载 + 一次空查询），把首次对话的冷启动延迟提前到启动阶段。
- 检索结果不是直接拼 prompt，而是包装成 Agent 的 `search_lab_docs` 工具，由模型自行决定何时检索——问开放时间就查文档，问实验室列表就走数据库。

### 亮点二：LangGraph 智能预约 Agent，对话即预约

`agent_service.py` 用 LangGraph 的 `StateGraph` 构建了一个「模型 ⇄ 工具」循环：

```
START → agent（LLM） ──tools_condition──→ tools（ToolNode）
           ↑                                   │
           └───────────────────────────────────┘
```

- **5 个工具**（`agent_tools.py`）：`search_lab_docs` 检索知识库、`list_open_labs` 查开放实验室、`list_lab_equipments` 查实验室设备、`create_lab_reservation` 真实落库预约、`get_today` 换算日期。
- **服务端注入上下文**：工具通过闭包捕获 `db` 与 `current_user`，模型只能拿到「当前登录用户」的数据与权限，无法越权；预约落库直接复用 `reservation_service.create_reservation`，业务校验完全一致。
- **强约束的系统提示词**：明确要求「用户说了今天/明天/后天时必须先调 `get_today`，不要回答『我需要确定明天的具体日期』」；「提交前必须复述实验室 ID 与名称、日期、起止时间并获得用户确认」；「缺少 `lab_id` / `equipment_id` 必须先查再建，不要瞎写」；「不要编造数据库里不存在的实验室或设备」。
- **人机确认闭环**：只有用户回复「确认」类确定性话语后才允许调用 `create_lab_reservation`，落地后状态为「待审核」，仍需管理员审核。
- **防死循环**：`recursion_limit=10` 限制 agent ⇄ tools 的往返次数；`temperature=0` 保证行为稳定。

### 亮点三：SSE 流式输出，工具调用过程全程可见

普通对话机器人只有「等待 → 一大段文字」两帧，本系统把 Agent 的内部执行过程实时透出：

- 后端基于 `astream_events(version="v2")`，把 LangGraph 的内部事件翻译成 6 种业务事件：

| 事件 | 触发时机 | 前端表现 |
| --- | --- | --- |
| `status` | 开始处理 | 显示「正在思考…」 |
| `tool_start` | 工具开始调用 | 展示中文步骤，如「检索实验室知识库」「提交预约」 |
| `tool_end` | 工具返回 | 追加结果预览（截断至 200 字符，不刷屏） |
| `token` | 模型逐字输出 | 打字机效果追加正文 |
| `done` | 正常结束 | 清除状态行 |
| `error` | 业务/系统异常 | 展示错误文案（异常以 `yield` 形式下发，不再走普通 JSON 响应） |

- 工具名通过 `TOOL_LABELS` 映射为中文文案，用户看到的是可读的过程而非 `list_open_labs(...)`。
- 只采集 `langgraph_node == "agent"` 的 token，过滤掉其它内部节点的噪声输出。
- 前端 `chatStreamApi` 用原生 `fetch` 读取流（而非 axios），手动携带 JWT，按 `\n\n` 分帧、逐行解析 `data:`，既能拿到 401 状态码做兜底，也不受 axios 响应拦截器影响。
- 链路两端都做了缓冲治理：后端响应头带 `X-Accel-Buffering: no`，Vite 代理对 `text/event-stream` 关闭缓冲。

### 亮点四：预约冲突检测与自动过期清理

- **时段重叠检测**：创建预约时按「同实验室 + 同日期 + 状态属于 待审核/已通过 + 区间相交（`start < 目标 end` 且 `end > 目标 start`）」判断冲突，直接拒绝重复预约。
- **多重时间校验**：不能预约过去的日期；结束时间不能早于开始时间；当天预约的开始时间不能早于当前时刻；必须落在实验室开放时段内。
- **资源状态校验**：实验室必须处于开放状态、设备必须非「维修中」；预约设备时同样占用实验室时段。
- **定时任务**：应用启动时创建异步任务，**每 60 秒**扫描一次（`asyncio.to_thread` 把同步数据库操作挪出事件循环），把日期已过或当天已结束的「待审核」预约批量置为「已取消」，避免脏数据长期堆积。

### 亮点五：统一的工程规范

- **统一响应体**：所有接口返回 `{code, message, data}`，前端拦截器只需判断一个字段。
- **四层异常处理**：业务异常（HTTP 200 + 业务 code，前端统一弹提示）、Starlette HTTP 异常、参数校验异常（422 且不暴露内部细节）、全局兜底（500「服务器内部错误」，真实堆栈只落日志）。
- **模型层复用**：`Base` 抽公共字段，业务表只写自己的列。
- **前后端一致的拦截逻辑**：请求自动带 token、401 自动登出并跳转登录页、后端未启动时提示「网络异常，请检查后端服务」。

### 亮点六：体验细节

- 前端路由守卫 + 后端 `get_current_admin` 的**双重权限控制**，菜单按角色渲染，避免学生看到管理入口。
- 对话内容用 **marked 渲染 + DOMPurify 过滤**，在支持 Markdown 表格/列表的同时防住 XSS。
- 文件上传做了**后缀白名单 + 100MB 上限 + 时间戳/uuid 重命名**，避免同名覆盖与路径穿越。
- Element Plus 全量图标全局注册 + 中文语言包，页面直接使用 `<el-icon><House /></el-icon>`。

---

## 六、已知问题与后续计划

- `backend/app/services/ai_service.py`：早期手写 Function Calling 实现，当前无路由引用，可考虑清理或改造为工具执行层。

后续可扩展方向：预约审批的消息通知、实验室/设备的可用时段可视化日历、知识库文件的后台管理上传、多轮对话的会话持久化。

---

## 七、常见问题

**Q：启动后端报数据库连接失败？**
检查 MySQL 是否已启动、`ai-lab` 库是否已创建、`.env` 中 `DATABASE_URL` 的用户名密码是否正确。密码含特殊字符时需做 URL 编码。

**Q：首次调用 AI 助手很慢甚至超时？**
首次启动会下载并加载中文向量模型，请耐心等待预热完成（控制台会打印 `检索出来的 score_parts` 之类的日志）；同时确认 `LLM_API_KEY` / `LLM_BASE_URL` 可用。前端对话请求超时为 60s，流式接口建议用 `chatStreamApi`。

**Q：改了 `data/kb/` 里的文档，AI 回答还是旧的？**
知识库只在向量集合为空时写入。删除 `backend/data/chroma/` 目录后重启后端即可重建索引。

**Q：前端请求 404 / 跨域？**
确认后端跑在 `8000` 端口、前端跑在 `5173`。跨域由 `vite.config.js` 的代理与后端 CORS 共同处理，改动端口需要同步修改 `main.py` 的 `origins`。

**Q：端口 8000 被占用？**
Windows 下可直接执行 `.vscode/kill-port-8000.ps1`，或用 `netstat -ano | findstr :8000` 找到 PID 后 `taskkill /PID <pid> /F`。
