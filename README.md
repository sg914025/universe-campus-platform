# 寰校通 UniVerse

面向中外师生的四语校园生活服务一体化平台。中文、英语、日语、俄语共用校园广场、校园跑腿、场地预约和健康导诊；数字伙伴提供问候、语音入口与办事引导。

评审技术文档：[PDF（28 页）](docs/UniVerse_technical_report.pdf) · [可编辑 Word](docs/UniVerse_technical_report.docx)。文档含模型方案、页面截图、测试与部署说明。

## 结构与架构

```text
server/                 Django Web 与接口、迁移、模板、静态资源
  accounts/             学号账户、首次改密、CSV 导入与撤销
  campus/               校园服务、预约、数字伙伴与管理
  triage/               追问、知识检索、Ollama 调用、医生端
  mobile_api/           共享移动客户端接口
mobile/                 uni-app / Vue / Vite 共享客户端
  android/              Android WebView 体验容器源码
docs/                   环境、部署、测试与来源说明
scripts/manage.py       读取本地 .env 后运行 Django 命令
```

Web 浏览器 → Django → SQLite；移动客户端 → mobile_api → 同一业务服务；Django → 本地 Ollama / 经认证的私网网关。三维校园使用 Three.js 映射资源，人体选择图帮助组织部位信息。Qwen3:4B 结合本地 MedlinePlus 摘要检索生成追问与结构化报告，供就医沟通与医生核实。

## 本地运行

需要 Python 3.12、Git。以下命令在仓库根目录的 PowerShell 执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server/requirements.txt
Copy-Item server/.env.example server/.env
.\.venv\Scripts\python.exe scripts/manage.py migrate
.\.venv\Scripts\python.exe scripts/manage.py ensure_campus_superadmin
.\.venv\Scripts\python.exe scripts/manage.py open_study_buildings
.\.venv\Scripts\python.exe scripts/manage.py initialize_map_resources
.\.venv\Scripts\python.exe scripts/manage.py runserver 127.0.0.1:8000
```

打开 http://127.0.0.1:8000/ 。首次创建的管理员凭据写入 `server/private_credentials/`，不会打印或提交到 Git。管理员入口为 `/management/login/superadmin/`。在总管理员界面导入新生 CSV，先预览并核对错误，再确认导入；学生初始密码按既有学号规则生成，首次登录须修改。请仅导入自己的演示名单。

Linux 对应运行：`python3 -m venv .venv`，后续将 Python 路径换成 `.venv/bin/python`；用 `cp server/.env.example server/.env` 复制配置。

## 启动本地 AI

安装 Ollama 后，在单独终端执行 `ollama serve`（如已有服务则无需重复启动），然后执行 `ollama pull qwen3:4b`。模型约 2.50 GB，本仓库不包含模型权重。`.env` 中默认连接 `http://127.0.0.1:11434`。启动 AI 后重启 Django 并进行一次真实追问，以确认推理可用。

```powershell
.\.venv\Scripts\python.exe scripts/manage.py shell -c "from triage.ollama_client import model_status; print(model_status())"
```

默认保留本地摘要库，导入来源见 `docs/AI_AND_RESOURCES.md`。模型状态检查与实际报告生成是不同层次的验证。模型不可用时保留规则流程。

## 移动客户端

使用 Node.js 20 或兼容版本，在 `mobile/` 下运行 `npm ci`，然后 `npm run dev:web` 预览。`config/project.json` 的 `apiBase` 默认指向本地服务器，`backendPath` 为 `../server`。手机需将 API 地址改为电脑可达地址。

`npm run build:web`、`npm run build:weixin`、`npm run build:app` 分别输出 H5、小程序和 App 资源；`npm run update:all` 将 H5 同步到 Django 的 `/m/`。小程序需配置自己的 AppID、合法域名，并在微信开发者工具中导入编译目录。Android 是单独的 WebView 体验容器，说明见 `mobile/android/README.md`，构建资源不是已上架应用。

## 验证与部署

```powershell
.\.venv\Scripts\python.exe scripts/manage.py check
.\.venv\Scripts\python.exe scripts/manage.py test accounts triage campus mobile_api
```

测试使用 Django 测试数据库。部署详见 `docs/DEPLOYMENT.md`，当前交付验证记录见 `docs/VERIFICATION.md`。

## 团队与版本记录

本仓库是匿名评审版本，团队实名信息通过赛事报名系统提交。项目组织、交互整合、四语接入与人工校对由参赛团队完成，开发中使用 Codex / ChatGPT 辅助代码、排错和材料整理。

仓库于 2026-11-17 从现有源码副本首次导入。所提供的副本没有 `.git` 历史，因此本仓库保留此次起真实发生的提交，不伪造此前开发记录。如取得原始 Git 仓库，应另行完整保留与提供原历史。

运行数据库、私信与咨询数据、密码、令牌、上传文件及本机环境不进入仓库；运行时重新迁移并创建自己的账户。第三方资源与许可证保留原出处。详见 `docs/AI_AND_RESOURCES.md`。
