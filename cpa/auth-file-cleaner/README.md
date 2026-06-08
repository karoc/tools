# CPA 授权文件处理

该工具用于处理 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 的认证文件，扫描出已被标记为授权失效或在管理中心显示为有问题的认证文件，并将命中文件移出 CPA 的认证目录。

## CPA 认证文件依据

CLIProxyAPI 的配置示例中，认证目录字段为 `auth-dir`，默认值是：

```yaml
auth-dir: "~/.cli-proxy-api"
```

认证文件是该目录下的 `.json` 文件。CPA 会读取 JSON 中的 `type`、`email`、`disabled`、`project_id`、`priority`、`note`、`websockets` 等字段作为认证文件信息。

CPA 管理中心的“问题凭证”标记来自管理接口 `/v0/management/auth-files` 的运行时状态字段，主要是：

- `files[].status_message` / `files[].statusMessage`
- `files[].status`
- `files[].unavailable`
- `files[].path`
- `files[].name`
- `files[].type` / `files[].provider`

管理中心的“仅显示有问题凭证”筛选逻辑是：`status_message` 非空。

如果只扫描认证文件内容，本工具只识别下面这个失效标记，字段路径和字段值必须完全对齐：

```json
{
  "error": {
    "message": "Your authentication token has been invalidated. Please try signing in again.",
    "type": "authentication_error",
    "code": "auth_unavailable"
  }
}
```

## 独立使用

进入工具目录：

```bash
cd cpa/auth-file-cleaner
```

### 扫描管理中心运行时状态

优先使用管理 API 扫描，因为管理中心标记是 CPA 运行时状态，不一定写入认证 JSON 文件。

只扫描授权失效标记：

```bash
CPA_MANAGEMENT_KEY='your-management-key' \
python3 clean_cpa_auths.py \
  --source management \
  --management-url http://127.0.0.1:8317 \
  --auth-dir ~/.cli-proxy-api
```

复现管理中心“仅显示有问题凭证”筛选：

```bash
CPA_MANAGEMENT_KEY='your-management-key' \
python3 clean_cpa_auths.py \
  --source management \
  --management-url http://127.0.0.1:8317 \
  --match problem \
  --auth-dir ~/.cli-proxy-api
```

`--match` 可选：

- `invalidated`：只匹配授权失效信息。
- `problem`：匹配管理中心“有问题凭证”，即 `status_message` 非空。
- `warning`：匹配管理中心警告状态，即 `status_message` 非空且不是 `ok/healthy/ready/success/available`。

### 扫描文件内失效标记

先扫描，不移动文件：

```bash
python3 clean_cpa_auths.py --auth-dir ~/.cli-proxy-api
```

确认输出后执行移动：

```bash
python3 clean_cpa_auths.py --auth-dir ~/.cli-proxy-api --execute
```

默认移动到认证目录旁边的时间戳目录，例如：

```text
~/.cli-proxy-api-invalidated/20260609-113000/
```

指定移动目录：

```bash
python3 clean_cpa_auths.py --auth-dir ~/.cli-proxy-api --move-dir ./invalidated-auths --execute
```

输出 JSON 报告：

```bash
python3 clean_cpa_auths.py --auth-dir ~/.cli-proxy-api --json
```

只扫描认证目录顶层，不递归子目录：

```bash
python3 clean_cpa_auths.py --auth-dir ~/.cli-proxy-api --no-recursive
```

## 统一入口使用

在仓库根目录运行：

```bash
python3 tools.py cpa-auth-file-cleaner --auth-dir ~/.cli-proxy-api
python3 tools.py cpa-auth-file-cleaner --auth-dir ~/.cli-proxy-api --execute
```

管理 API 模式：

```bash
CPA_MANAGEMENT_KEY='your-management-key' \
python3 tools.py cpa-auth-file-cleaner \
  --source management \
  --management-url http://127.0.0.1:8317 \
  --match problem \
  --auth-dir ~/.cli-proxy-api
```

## 安全策略

- 默认 dry-run，只报告命中文件，不移动。
- 只有显式传入 `--execute` 才会移动文件。
- 管理 API 密钥建议通过 `CPA_MANAGEMENT_KEY` 环境变量传入，避免出现在 shell history 中。
- 移动目录不允许位于 `auth-dir` 内部，避免 CPA 继续读取被移走的 `.json` 文件。
- 移动时保留相对路径；目标文件已存在时自动追加序号，避免覆盖。
- 无法解析的 JSON 文件会被计入 skipped，不会被移动。

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
- execute 后 `invalid-auth.json` 被移动到 `$tmp-invalidated/<timestamp>/`。
- `valid-auth.json` 仍留在原认证目录。

## 测试

在仓库根目录执行：

```bash
python3 -m unittest discover -s cpa/auth-file-cleaner/tests
```
