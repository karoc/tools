# CPA 授权文件处理

该工具用于清理 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 中已经授权失效的认证文件。它优先读取 CPA 管理接口维护的运行时状态，扫出失效认证文件，并把这些文件从活动认证目录移动到隔离目录。

默认行为是 dry-run：只扫描、只展示计划，不移动文件。只有显式传入 `--execute` 才会移动文件。

## 先看这三件事

使用管理中心状态扫描前，先确认三个值：

| 配置 | 默认值 | 什么时候要改 |
|---|---|---|
| `--management-url` | `http://127.0.0.1:8317` | CPA 通过 Docker 端口映射、反向代理或非默认端口访问时必须显式传入 |
| `--auth-dir` | `~/.cli-proxy-api` | CPA 容器挂载到宿主机目录时，必须填宿主机上的认证目录 |
| `CPA_SECRET_KEY` | 无 | 必须提供，来自 CPA 配置 `remote-management.secret-key` |

如果你是直接在宿主机上运行 CPA，默认 URL 通常可用：

```bash
--management-url http://127.0.0.1:8317
```

如果 CPA 通过 Docker 暴露端口，例如：

```yaml
ports:
  - "41363:8317"
```

工具必须使用宿主机端口：

```bash
--management-url http://127.0.0.1:41363
```

当前示例服务器就是这种情况，所以需要显式传 `--management-url http://127.0.0.1:41363`。

## 最短使用流程

在仓库根目录执行：

```bash
cd /home/admin/tools
```

先让 Python 子进程能读到管理密钥。如果当前 shell 已经有 `CPA_SECRET_KEY`，但没有导出，执行：

```bash
export CPA_SECRET_KEY
python3 -c 'import os; print("python sees key:", bool(os.environ.get("CPA_SECRET_KEY")))'
```

期望输出：

```text
python sees key: True
```

先 dry-run，只扫描不移动：

```bash
python3 tools.py cpa-auth-file-cleaner \
  --source management \
  --management-url http://127.0.0.1:41363 \
  --auth-dir /srv/CLIProxyAPI/auths
```

确认输出后，再执行移动：

```bash
python3 tools.py cpa-auth-file-cleaner \
  --source management \
  --management-url http://127.0.0.1:41363 \
  --auth-dir /srv/CLIProxyAPI/auths \
  --execute
```

执行后工具会自动输出：

- 执行前扫描结果；
- 移动文件数量；
- 隔离目录路径；
- 隔离目录实际文件数；
- 移动后复扫结果；
- `verification.status` 校验状态。

## 管理密钥

管理模式需要 CPA 管理密钥。工具查找顺序是：

1. `--management-key` 参数；
2. 已导出的 `CPA_SECRET_KEY` 环境变量；
3. 已导出的旧变量 `CPA_MANAGEMENT_KEY`；
4. env 文件，默认 `/etc/cpa-auth-file-cleaner.env`。

不推荐把密钥写在命令行里。手动执行时推荐：

```bash
export CPA_SECRET_KEY='your-management-key'
```

给 systemd 或长期使用时，推荐写 env 文件：

```bash
sudo install -m 600 /dev/null /etc/cpa-auth-file-cleaner.env
sudo sh -c 'printf "%s\n" "CPA_SECRET_KEY=your-management-key" > /etc/cpa-auth-file-cleaner.env'
```

文件内容不需要 `export`：

```env
CPA_SECRET_KEY=your-management-key
```

如果密钥包含特殊字符，可以加引号：

```env
CPA_SECRET_KEY='your-management-key'
```

如果看到下面错误：

```text
error: management key is required
```

先确认 Python 是否能看到环境变量：

```bash
python3 -c 'import os; print(bool(os.environ.get("CPA_SECRET_KEY")))'
```

如果输出 `False`，但 `echo "$CPA_SECRET_KEY"` 有值，说明变量没有导出，执行：

```bash
export CPA_SECRET_KEY
```

## 输出怎么理解

dry-run 输出里常见字段：

```text
Mode: dry-run
Invalidated auth files: 10
Move plan:
Dry-run only. Add --execute to move matched files.
```

这表示只生成移动计划，没有移动文件。

execute 输出里常见字段：

```text
Mode: execute
Moved files: 10
Post-move verification:
  Post-scan invalidated auth files: 0
  Quarantine dir: /srv/CLIProxyAPI/auths-invalidated/20260609/113000
  Quarantine files: 10
  Quarantine JSON files: 10
  Confirmed moved destinations: 10
  Verification: ok
```

默认隔离目录结构是：

```text
<auth-dir>-invalidated/<YYYYMMDD>/<HHMMSS>/
```

例如：

```text
/srv/CLIProxyAPI/auths-invalidated/20260609/113000/
```

`Verification` 有几种状态：

| 状态 | 含义 | 是否表示移动失败 |
|---|---|---|
| `ok` | 移动成功，复扫没有失效项 | 否 |
| `stale_management_state` | 文件已移走，但 CPA 管理接口仍返回旧状态 | 否，通常是运行时状态残留或刷新延迟 |
| `failed` | 复扫仍有失效项，且对应文件还在活动认证目录 | 是，需要检查权限、路径或文件状态 |
| `post_scan_failed` | 文件移动后，复扫管理接口失败 | 不一定，需要看接口错误 |

如果看到：

```text
Verification: stale_management_state
Post-scan active files still present: 0
Post-scan management-only stale entries: 17
```

这表示文件层面已经清理完成，只是 CPA 管理中心还保留了运行时状态。

## 注册为 systemd 定时服务

定时服务使用 systemd `service + timer`。默认每 1 分钟执行一次，可以用 `--service-interval` 修改。

先准备 env 文件：

```bash
sudo install -m 600 /dev/null /etc/cpa-auth-file-cleaner.env
sudo sh -c 'printf "%s\n" "CPA_SECRET_KEY=your-management-key" > /etc/cpa-auth-file-cleaner.env'
```

先预览 unit，不写系统：

```bash
python3 tools.py cpa-auth-file-cleaner \
  --source management \
  --management-url http://127.0.0.1:41363 \
  --match invalidated \
  --auth-dir /srv/CLIProxyAPI/auths \
  --execute \
  --service-user admin \
  --service-interval 5min \
  --print-service-units
```

确认 `ExecStart` 里的 `--management-url`、`--auth-dir`、`--execute` 都正确后，再安装：

```bash
sudo python3 tools.py cpa-auth-file-cleaner \
  --source management \
  --management-url http://127.0.0.1:41363 \
  --match invalidated \
  --auth-dir /srv/CLIProxyAPI/auths \
  --execute \
  --install-service \
  --service-user admin \
  --service-interval 5min
```

安装成功会看到：

```text
Commands:
  - systemctl daemon-reload -> 0
  - systemctl enable --now cpa-auth-file-cleaner.timer -> 0
```

`-> 0` 表示 systemd 命令成功。

检查 timer：

```bash
systemctl status cpa-auth-file-cleaner.timer
systemctl list-timers cpa-auth-file-cleaner.timer
```

查看最近一次执行：

```bash
systemctl status cpa-auth-file-cleaner.service
journalctl -u cpa-auth-file-cleaner.service -n 100 --no-pager
```

立即手动触发一次：

```bash
sudo systemctl start cpa-auth-file-cleaner.service
journalctl -u cpa-auth-file-cleaner.service -n 100 --no-pager
```

查看实际写入的 unit：

```bash
systemctl cat cpa-auth-file-cleaner.service
systemctl cat cpa-auth-file-cleaner.timer
```

卸载定时服务：

```bash
sudo python3 tools.py cpa-auth-file-cleaner --uninstall-service
```

## 独立入口

也可以进入工具目录独立使用：

```bash
cd cpa/auth-file-cleaner
```

管理接口 dry-run：

```bash
export CPA_SECRET_KEY='your-management-key'
python3 clean_cpa_auths.py \
  --source management \
  --management-url http://127.0.0.1:41363 \
  --auth-dir /srv/CLIProxyAPI/auths
```

管理接口执行移动：

```bash
python3 clean_cpa_auths.py \
  --source management \
  --management-url http://127.0.0.1:41363 \
  --auth-dir /srv/CLIProxyAPI/auths \
  --execute
```

## 文件内容扫描模式

管理中心的状态是 CPA 运行时维护的，不一定写入认证 JSON 文件。因此清理授权失效文件时，优先使用 `--source management`。

如果只想扫描文件内容，可以不传 `--source management`：

```bash
python3 tools.py cpa-auth-file-cleaner --auth-dir ~/.cli-proxy-api
python3 tools.py cpa-auth-file-cleaner --auth-dir ~/.cli-proxy-api --execute
```

文件内容模式只识别下面这个字段结构和值完全匹配的标记：

```json
{
  "error": {
    "message": "Your authentication token has been invalidated. Please try signing in again.",
    "type": "authentication_error",
    "code": "auth_unavailable"
  }
}
```

## 参数速查

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--source` | `file-marker` | `management` 读取 CPA 运行时状态；`file-marker` 扫描 JSON 文件内容 |
| `--management-url` | `http://127.0.0.1:8317` | CPA 管理接口地址；Docker 映射端口时必须显式传宿主机端口 |
| `--auth-dir` | `~/.cli-proxy-api` | 宿主机上的认证文件目录 |
| `--match` | `invalidated` | `invalidated` 只扫授权失效；`problem` 复现管理中心问题凭证筛选；`warning` 扫非健康状态 |
| `--execute` | 不启用 | 不传时只 dry-run；传入后才移动文件 |
| `--move-dir` | `<auth-dir>-invalidated/<YYYYMMDD>/<HHMMSS>` | 隔离目录 |
| `--json` | 不启用 | 输出机器可读 JSON |
| `--service-interval` | `1min` | systemd timer 间隔 |

## 安全策略

- 默认 dry-run，只报告命中文件，不移动。
- 只有显式传入 `--execute` 才会移动文件。
- 管理 API 密钥建议通过 `CPA_SECRET_KEY` 或 env 文件传入，避免出现在 shell history 中。
- 移动目录不允许位于 `auth-dir` 内部，避免 CPA 继续读取被移走的 `.json` 文件。
- 移动时保留相对路径；目标文件已存在时自动追加序号，避免覆盖。
- 无法解析的 JSON 文件会被计入 skipped，不会被移动。
- 执行后会自动复扫，并区分真正失败和 CPA 管理中心状态残留。

## 运行时验收

在仓库根目录执行：

```bash
tmp="$(mktemp -d)"
cp cpa/auth-file-cleaner/examples/*.json "$tmp/"
python3 tools.py cpa-auth-file-cleaner --auth-dir "$tmp"
python3 tools.py cpa-auth-file-cleaner --auth-dir "$tmp" --execute
find "$tmp" -type f -name '*.json' -print
find "$tmp-invalidated" -type f -name '*.json' -print
```

期望结果：

- dry-run 输出命中 `invalid-auth.json`，且文件仍留在原目录。
- execute 后 `invalid-auth.json` 被移动到 `$tmp-invalidated/<YYYYMMDD>/<HHMMSS>/`。
- `valid-auth.json` 仍留在原认证目录。

## 测试

在仓库根目录执行：

```bash
python3 -m unittest discover -s cpa/auth-file-cleaner/tests
```
