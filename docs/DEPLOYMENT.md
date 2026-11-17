# 部署与环境配置

后端建议 Python 3.12，依赖见 `server/requirements.txt`。前端依赖与精确锁定见 `mobile/package.json` 和 `package-lock.json`。演示数据使用 SQLite，本地 AI 独立运行。

## Ubuntu 24.04

在自己选择的项目目录克隆仓库，建立 `.venv`，安装依赖，复制 `server/.env.example` 为 `server/.env`。生产配置设置 `DJANGO_DEBUG=0`、随机 `DJANGO_SECRET_KEY`、实际 `DJANGO_ALLOWED_HOSTS`，HTTPS 下使用 `DJANGO_SECURE_COOKIES=1`。不要把示例 localhost 当作公网域名。修改配置后重启应用。

通过 `scripts/manage.py migrate` 初始化数据，再执行 `scripts/manage.py collectstatic --noinput`。先按 README 创建独立管理员、演示资源并验证，随后配置 systemd 启动 Gunicorn。工作目录为仓库内 `server/`，`EnvironmentFile` 指向本地 `server/.env`，启动命令形如：

```text
/path/to/repository/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --threads 2 --timeout 180
```

用非 root 服务用户运行。Nginx 将请求代理到 `127.0.0.1:8000`，保留 Host 和转发协议；`/static/` 指向 `server/staticfiles/`。HTTPS 在反向代理终止时，应按实际可信代理结构配置 Django 的安全请求识别后测试 CSRF 表单。不要为消除错误关闭 CSRF。

## 服务器调用本地模型

两台设备加入同一 Tailscale 网络。本地 Ollama 保持回环监听，由自己的认证网关监听 Tailscale 地址。服务器的 `TRIAGE_OLLAMA_URL` 指向该网关，`TRIAGE_OLLAMA_TOKEN` 与网关令牌一致。防火墙仅允许服务器私网地址访问网关端口。当前客户端限制回环或 Tailscale 范围，远程请求需令牌。

本仓库包含 Django 的模型客户端；私有网关部署及语音引擎运行环境需按自己的设备配置。先检测 TCP、再检查模型列表、最后完成真实追问与报告。电脑关机时模型不可达；重新开机后按需手动启动，不设置自动启动。

SQLite 适用于演示及小规模部署；上线前按实际并发评估数据库与推理服务容量。备份数据库、用户上传文件及配置时分开管理，公开仓库不保存这些运行数据。
