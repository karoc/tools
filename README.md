# Tools

本仓库用于沉淀各类可独立运行、也可通过统一入口调用的小工具。项目约束见 `PROJECT_CONSTRAINTS.md`，Agent 执行规则见 `AGENTS.md`。

## 新人从这里开始

先确认当前仓库有哪些工具：

```bash
python3 tools.py list
```

再进入目标工具文档，按该工具的“最短使用流程”执行。每个工具都应同时支持：

- 统一入口：在仓库根目录通过 `python3 tools.py <tool-name>` 调用。
- 独立入口：进入 `工具分类/工具名/` 后直接运行该工具自己的入口。
- dry-run 或等价预览：危险操作必须先能预览，再显式执行。

## 统一入口

查看已注册工具：

```bash
python3 tools.py list
```

运行 CPA 授权文件处理工具：

```bash
python3 tools.py cpa-auth-file-cleaner --auth-dir ~/.cli-proxy-api
```

扫描 CPA 管理中心运行时状态。授权失效状态由 CPA 运行时维护时，优先使用这个模式：

```bash
export CPA_SECRET_KEY='your-management-key'
python3 tools.py cpa-auth-file-cleaner \
  --source management \
  --management-url http://127.0.0.1:8317 \
  --match invalidated \
  --auth-dir ~/.cli-proxy-api
```

默认只扫描和报告，不移动文件。确认结果后执行移动：

```bash
python3 tools.py cpa-auth-file-cleaner \
  --source management \
  --management-url http://127.0.0.1:8317 \
  --match invalidated \
  --auth-dir ~/.cli-proxy-api \
  --execute
```

CPA 工具的完整说明见 `cpa/auth-file-cleaner/README.md`，包括 Docker 端口映射、管理密钥、systemd 定时服务和输出解释。

## 已有工具

| 分类 | 工具 | 目录 | 说明 |
| --- | --- | --- | --- |
| cpa | auth-file-cleaner | `cpa/auth-file-cleaner/` | 扫描 CPA 认证目录中已失效的授权文件，并将其移出认证目录 |
