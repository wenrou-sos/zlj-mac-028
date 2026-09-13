# 银卫 · 银行押运管理系统

面向银行现金营运中心的**押运调度与款箱交接核对系统**：安排押运路线与车组人员，
登记款箱**出库 → 在途 → 交接 → 送达/回库**的完整链路，支持任务全程追踪、
验证码 + 封签双人核对、异常上报与处置。

技术栈：**Vue 3 + Vite + Element Plus + Pinia** ／ **Django 5 + DRF + SimpleJWT** ／ **PostgreSQL 15**

---

## 一、快速开始

```bash
cd cash-transit
chmod +x start.sh
./start.sh
```

脚本会自动：建 Python 虚拟环境并装依赖 → 下载解包**免 root 的本地 PostgreSQL**（Debian 官方包，端口 55432）
→ 初始化数据库、执行迁移 → 写入内置样例数据 → 启动前后端。

启动后访问：

| 入口 | 地址 |
| --- | --- |
| 前端页面 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000/api/ |
| Django 管理后台 | http://127.0.0.1:8000/admin/ |

### 演示账号（密码统一 `cash123456`）

| 账号 | 角色 | 用途 |
| --- | --- | --- |
| `1001` | 调度员 张建国 | 派车排班、安排任务、总览 |
| `4001` | 金库管理员 周金库 | 金库出库 / 回库核对 |
| `2001` | 车长 王海涛 | 到离站、网点交接 |
| `3001` | 驾驶员 吴铁军 | — |
| `admin` | 系统管理员 | Django 后台（同密码） |

### 手动启动（分步）

```bash
# 1. PostgreSQL（首次）
export PGBIN=$PWD/pgsql/local/usr/lib/postgresql/15/bin
export LD_LIBRARY_PATH=$PWD/pgsql/local/usr/lib/aarch64-linux-gnu
$PGBIN/pg_ctl -D pgdata -l pgsql/pg.log start        # 停止见 stop-pg.sh

# 2. 后端
venv/bin/pip install -r backend/requirements.txt
cd backend
venv/bin/python manage.py migrate
venv/bin/python manage.py init_demo        # 内置样例数据（--reset 可重建）
venv/bin/python manage.py runserver 127.0.0.1:8000

# 3. 前端
cd frontend && npm install && npm run dev
```

> 连接已有的 PostgreSQL：设置环境变量 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
> 覆盖默认的 `127.0.0.1:55432/cash_transit`。

---

## 二、功能模块

### 调度总览（Dashboard）
今日任务数、在外车辆、待处置异常等指标卡；任务状态分布进度条；最近任务动态。

### 押运任务
- **安排任务**：选择方向（下解金库→网点 / 上收网点→金库）、线路、日期、车辆；
  按"车长 1 + 押运员 ≥1 + 驾驶员 1"编组（同一人不能身兼两职、车辆当天不能重复派车、
  维修车辆不可派车，均有后端校验）；款箱按停靠点逐站分配，实时汇总箱数与金额。
- **任务追踪**：线路停靠时间线（计划/实际到离站时间）、各站款箱状态与交接操作、
  全程操作日志（时间轴）。
- **四阶段交接核对**：

  | 方向 | 环节 |
  | --- | --- |
  | 下解 | 金库出库 → 网点接收（送达） |
  | 上收 | 网点移交装车 → 金库回库 |

  - **网点交接验证码**：任务创建时每站生成 4 位验证码，到站后显示；
  - **封签号核对**：出库封签沿链路传递，逐环节录入比对，封签外观可登记破损；
  - **双人核对**：每次交接必须登记交出人、接收人，缺任一人员不允许提交；
  - 验证码不符 / 封签不符 → 自动生成**异常事件**并将任务**挂起**
    （出车前上报也挂起，处置后恢复「已派车」可重新出发；已出发的恢复「押运中」）；
  - **已办结 / 已取消任务不允许再上报异常**；
  - 全部异常处置完成后任务自动恢复押运；款箱与站点全部完成后任务自动办结、车辆归队。
- **交接核对表（Reconcile）**：逐箱展示应完成/已完成环节、封签链一致性、
  验证码核验结果、异常标记，一眼判定"全部一致"。
- **异常情况**：交通延误、封签异常、款箱短少/破损、车辆故障、安全事件等
  8 类 × 3 级，可关联停靠点与款箱；处置后填写处置说明、记录处置人。
- 支持手动跳过站点、办结任务、取消任务（释放车辆与款箱）。

### 基础档案
- **网点金库**：内置 10 个样例（1 中心金库 + 1 分金库 + 7 支行 + 1 自助银行），
  含地址、联系人、营业时间、经纬度，并提供坐标分布示意图；
- **押运线路**：4 条线路模板（城西线、海淀线、朝阳环线、亚运村线），
  停靠顺序、计划到达时间、停留时长、里程；可一键按线路安排任务；
- **车辆**：5 辆运钞车（待命/执行/维修状态、容量、GPS 设备号）；
- **款箱**：柜员尾箱、现金箱、凭证箱、ATM 加钞箱，含面额合计；
- **人员**：调度员、车长、武装押运员、驾驶员、金库管理员、网点柜员。

### 内置演示场景（`init_demo` 自动生成）
1. `YY-当日-001` 昨日**已完成**下解任务（5 箱 3 站，交接链完整）；
2. `YY-当日-002` **押运中**下解任务：已到中关村站，1 箱已交接、1 箱待核对；
3. `YY-当日-003` **异常挂起**下解任务：国贸站交接验证码录入不符（可在任务页处置后继续）；
4. `YY-当日-004` **已派车**的上收任务（城西线尾箱回收）：回收任务 1 昨日下解、
   现停留在各网点的 5 个款箱；执行完毕后款箱回库恢复空闲、可再次安排下解，
   形成"下解送达 → 上收回库 → 再排班"的日循环。

### 款箱排班规则
- **下解任务**只能选择「在库空闲」款箱，**上收任务**只能选择「已送达网点、
  待回收」款箱，且款箱归属网点必须与所选停靠网点一致；
- 已被未完成任务占用的款箱（含已派车未出库、在途）禁止重复排班；
- 任务取消时按方向释放款箱：下解箱退回在库、上收箱退回网点已送达。

---

## 三、主要 API

`POST /api/auth/login/` 登录获取 JWT（`access` / `refresh`）。

| 模块 | 端点 |
| --- | --- |
| 总览 | `GET /api/tasks/dashboard/` |
| 任务 | `GET/POST /api/tasks/`、`GET /api/tasks/{id}/` |
| 流转 | `POST /api/tasks/{id}/depart/`（出发） |
|  | `POST /api/tasks/{id}/arrive/`（到达停靠站，body: `stop_id`） |
|  | `POST /api/tasks/{id}/handover/`（交接核对） |
|  | `POST /api/tasks/{id}/finish-stop/`、`complete/`、`cancel/` |
| 异常 | `GET/POST /api/tasks/{id}/incidents/`、`POST .../incidents/{iid}/resolve/` |
| 核对 | `GET /api/tasks/{id}/reconcile/`（交接核对表） |
| 日志 | `GET /api/tasks/{id}/timeline/` |
| 档案 | `/api/branches/` `/api/routes/` `/api/vehicles/` `/api/boxes/` `/api/staff/` |
| 全局 | `GET /api/incidents/`、`GET /api/handovers/`（支持筛选/分页） |

交接请求示例（网点接收）：

```json
POST /api/tasks/12/handover/
{
  "task_box_id": 301,
  "phase": "branch_recv",
  "stop_id": 55,
  "code": "3721",
  "seal_no_in": "FJ0001",
  "seal_intact": true,
  "from_user_id": 4,
  "to_user_id": 16
}
```

返回 `result`：`confirmed`（一致）/ `seal_mismatch`（封签异常）/
`code_mismatch`（验证码不符）/ `box_missing`（款箱短少）。

---

## 四、项目结构

```
cash-transit/
├── start.sh / stop-pg.sh        # 一键启动 / 停止内置 PostgreSQL
├── pgsql/                       # 免 root 的 PostgreSQL（deb 解包，首次自动下载）
├── pgdata/                      # 数据库集群目录
├── venv/                        # Python 虚拟环境
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/                  # Django 配置 / URL / WSGI
│   ├── accounts/                # 自定义用户（工号、角色、岗位）+ JWT 登录
│   └── core/
│       ├── models_base.py       # 网点/车辆/款箱/线路
│       ├── models_task.py       # 任务/停靠点/任务款箱/交接/异常/日志
│       ├── services.py          # ★ 任务状态机与交接核对核心逻辑
│       ├── serializers.py / views.py / urls.py / admin.py
│       └── management/commands/init_demo.py   # 内置样例数据
├── frontend/
│   └── src/
│       ├── api/http.js          # axios + JWT 拦截器
│       ├── store/auth.js        # Pinia 登录态
│       ├── layouts/MainLayout.vue
│       ├── components/          # HandoverDialog / IncidentDialog
│       └── views/               # 总览/任务/追踪/异常/交接/网点/线路/资源
└── scripts/e2e_test.py          # 24 项端到端业务流测试（HTTP API）
```

## 五、测试

```bash
# 需后端运行中
venv/bin/python scripts/e2e_test.py
```

覆盖：登录、异常挂起/处置/按出发状态恢复、终态任务禁止上报异常、
错误封签拦截、交接人员必填、验证码核对、
上收"移交→回库"全链路自动办结与款箱日循环、占用款箱/车辆冲突派车拦截等 39 个用例。
