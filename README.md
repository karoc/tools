# Tools

本仓库用于沉淀各类可独立运行、也可通过统一入口调用的小工具。项目约束见 `PROJECT_CONSTRAINTS.md`，Agent 执行规则见 `AGENTS.md`。

## 统一入口

查看已注册工具：

```bash
python3 tools.py list
```

运行 CPA 授权文件处理工具：

```bash
python3 tools.py cpa-auth-file-cleaner --auth-dir ~/.cli-proxy-api
```

默认只扫描和报告，不移动文件。确认结果后执行移动：

```bash
python3 tools.py cpa-auth-file-cleaner --auth-dir ~/.cli-proxy-api --execute
```

## 已有工具

| 分类 | 工具 | 目录 | 说明 |
| --- | --- | --- | --- |
| cpa | auth-file-cleaner | `cpa/auth-file-cleaner/` | 扫描 CPA 认证目录中已失效的授权文件，并将其移出认证目录 |
