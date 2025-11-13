# 从合同编码批量拉取飞书协同群聊ID

## 项目概览

- **处理链路**：读取合同编码 → 调用合同搜索获取 `contract_id` → 查询合同详情获取 `cooperation_id` → 查询协同详情获取 `openChatId`，逐步写入结果行。@src/orchestrator.py#51-224
- **核心能力**：支持多接口限流与指数退避重试、结构化 JSON 日志、历史 Excel 结果按合同号 `upsert` 合并、失败记录二次重跑。@src/http/client.py#12-49 @src/orchestrator.py#58-258
- **输出形态**：生成含合同信息与状态的 Excel，保留错误码与错误信息便于排查。@src/io/writer.py#11-35

## 前置条件

- Python 3.9 及以上版本。
- 已为企业飞书应用开通 OpenAPI 权限 **`contract:contract:readonly`**，以便访问合同搜索接口。
- 确保具备对应租户的 `app_id` / `app_secret` 以及 CLM 域名 `session` Cookie（仅用于 contract.feishu.cn 接口）。

## 快速开始

1. 创建虚拟环境并安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 复制 `config.example.yaml` 为 `config.yaml`，填写鉴权、限流、重试等实际参数。配置加载器会补全默认值并校验格式。@src/config.py#78-129
3. 准备 `./input/contracts.txt`（UTF-8，每行一个合同编码，支持空行与 `#` 注释；同一合同会自动去重）。@src/io/reader.py#10-22
4. 执行脚本：
   ```bash
   python main.py --config config.yaml
   ```
   程序会在控制台与 `files.log_file` 指定路径输出 JSON 日志，并将结果写入 `files.output_excel`。@main.py#6-33 @src/logger.py#15-70

## 配置说明

`config.yaml` 采用层级结构，所有字段均在启动时校验：@src/config.py#29-75

- **files**：输入 TXT、输出 Excel、日志文件路径；会自动创建父目录。@src/config.py#19-27
- **auth**：OpenAPI `app_id` / `app_secret`，以及访问 CLM 接口所需的 `cookies.session`。@src/auth.py#9-33 @src/clm/clm_client.py#17-58
- **rate_limit**：全局与各接口 QPM，以及跨合同并发度 `concurrency`。缺省值均为 60，建议根据实际配额调整。@src/orchestrator.py#19-30 @src/http/rate_limiter.py#1-80
- **retry**：HTTP 超时、最大重试次数、退避区间、抖动比例，以及 `skip_result_statuses` 用于控制重跑策略。@src/http/retry.py#1-79 @src/orchestrator.py#58-72
- **log**：最小日志级别，支持 `DEBUG/INFO/WARN/ERROR`。@src/logger.py#15-70

若配置缺失或取值非法，程序会抛出明确的中文错误提示，便于定位问题。@src/config.py#29-75

## 输入与输出

- **输入 TXT**：路径由 `files.input_txt` 指定；程序自动过滤空行、注释与重复合同。@src/io/reader.py#10-22
- **输出 Excel**：包含 `contract_number`、`contract_id`、`cooperation_id`、`openChatId`、`status`、`error_code`、`error_message` 七列。@src/io/writer.py#11-33
- **状态含义**：
  - `SUCCESS`：完整拿到群聊 ID。
  - `NOT_FOUND_CONTRACT` / `NO_COOPERATION` / `NO_CHAT_GROUP`：分别表示链路中断点。@src/orchestrator.py#95-200
  - `AUTH_FAILED` / `PERMISSION_DENIED` / `RETRY_EXCEEDED` / `UNKNOWN_ERROR`：鉴权、权限、重试超限或未分类错误。@src/orchestrator.py#95-224
- 失败场景下会保留可获取的上游字段，并记录错误码与错误信息。@src/orchestrator.py#95-224

## 运行流程与重跑策略

1. 对输入合同逐个执行 SEARCH → CONTRACT_INFO → COOP_INFO 三步查询，单合同内串行，合同间按 `concurrency` 控制并发。@src/orchestrator.py#85-210
2. 每次请求前后输出结构化日志，包含耗时、重试次数、HTTP 状态与业务状态。@src/logger.py#41-70 @src/orchestrator.py#92-209
3. 批量结束后，将新结果与历史 Excel 按 `contract_number` 合并；若历史状态属于 `skip_result_statuses` 列表（默认包括 SUCCESS 等），则本次跳过重跑。@src/orchestrator.py#58-258 @src/config.py#109-120
4. 合并完成后覆盖写回 Excel，可重复执行且不会产生重复记录。@src/orchestrator.py#241-257

## 日志

- 日志格式：单行 JSON，包含时间戳、级别、模块、traceId 以及业务字段，方便检索与追踪。@src/logger.py#15-70
- 输出位置：控制台与 `files.log_file` 指定的文件。
- 建议在调试阶段使用 `DEBUG` 级别，在生产环境将日志级别提升至 `INFO` 或更高。

## 目录与文档

- 目录结构请参阅《项目结构目录图.md》。
- 业务与技术细节详见《需求文档.md》《技术方案.md》，本 README 与代码保持同步更新。

## 注意事项

- 请勿将 `config.yaml`、`logs/`、`output/` 等包含敏感信息或运行产物的目录提交到版本库（已通过 `.gitignore` 忽略）。
- 建议定期检查飞书应用权限与 Cookie 是否有效，以免运行过程中出现鉴权失败。
- 运行发现接口配额不足时，可在配置文件中下调 QPM 或升高重试次数，并评估对全量耗时的影响。
