# 从合同编码批量拉取飞书协同群聊ID

统一术语：`contract_number`、`openChatId`。配置来源：`config.yaml`。输入为 TXT（每行一个合同编码），输出为 Excel。

## 快速开始

- 环境：Python 3.9+
- 准备：
  - 创建 `config.yaml`（示例字段：files.input_txt、files.output_excel、auth.app_id、auth.app_secret、auth.cookies.session、rate_limit、retry）
  - 准备 `./input/contracts.txt`（UTF-8，一行一个合同编码，支持空行和以 `#` 开头注释）
- 运行：

```bash
python main.py --config config.yaml
```

当前阶段：已完成项目骨架与运行入口，后续补齐查询与导出逻辑。

## 目录结构

详见《项目结构目录图.md》。

## 注意

- 请勿将 `config.yaml`、`logs/`、`output/` 提交到版本库（已在 `.gitignore` 中忽略）。
- 示例与说明以《需求文档.md》《技术方案.md》为准。
