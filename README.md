# 基金公告运营助手

面向基金运营/客服的公告处理工作台：上传公告 → 结构化抽取 → 规则计算 → 多角色物料 → 合规复核 → 人工导出。

> 题目材料中的产品、人物、数据均为虚构，仅用于演示；输出为运营草稿，不构成投资建议。

**在线体验：https://fund-announcement-assistant.streamlit.app/**

## 输入方式

- **主流程**：上传 PDF/TXT，或直接粘贴公告全文。
- **三个规定案例**：点击“载入公告 A/B/C”会把公告原文填入可编辑文本框，仍走同一套抽取、规则计算和生成流程，不存在三套写死答案。
- **自定义公告**：上传/粘贴后自动识别类型；识别不准时可手动指定。

## 功能

- 三类公告：基金经理变更、大额申购限制、基金分红
- AI 抽取 + 规则引擎校验，金额/日期/份额不交给大模型算
- 客服短口径 / 完整回复 / App 推送 / FAQ / 运营待办
- 事实卡、原文引用、缺失信息、影响范围、后续跟踪
- 合规检查、安全回退、人工复核、Markdown/JSON 导出
- AI 实时模式 / 离线演示模式
- 模型：DeepSeek V4.1 Flash（`deepseek-flash`），默认关闭思考模式

## 在 Streamlit Community Cloud 部署（稳定公网链接）

1. 打开 https://share.streamlit.io ，用 GitHub 登录。
2. 点击 **New app**。
3. 选择本仓库，Branch 选 `main`，Main file path 填 `app.py`。
4. 点击 **Advanced settings**，在 **Secrets** 中填入：

```toml
DEEPSEEK_API_KEY = "sk-..."
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"
DEEPSEEK_THINKING = "disabled"
```

5. 点击 **Deploy**。部署完成后会得到稳定链接，形如：

```text
https://<your-app-name>.streamlit.app
```

> 不配置 `DEEPSEEK_API_KEY` 也能打开页面，在左侧选择“离线演示模式”即可完整跑通三个案例。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

本地可选配置 `.env`：

```text
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_THINKING=disabled
```

## 三个规定测试案例（可快捷载入）

1. **基金经理变更**：解聘李明，张晨继续管理；用户追问“是不是业绩不好”“后面会不会跌”。
2. **大额申购限制**：用户每月 20,000 元定投，判断是否受影响；询问何时恢复。
3. **基金分红**：持有 25,000 份，计算分红金额；6 月 17 日 16:00 申请改为红利再投资。

这三个案例是快捷示例，不是写死输出；点击后公告原文进入可编辑文本框，处理仍走同一套管线。

## 设计说明

- AI 负责“读懂和表达”：分类、抽取、文案生成、敏感问题识别。
- 规则引擎负责“算和判”：金额边界、生效日、权益登记日、15:00 截止、分红金额。
- 人负责“签字和发送”：所有输出为草稿，需人工复核。
- 公告未披露的信息明确写“公告未说明”，不编造。
- 高风险文案自动回退到安全模板。

## 真实性与限制

- 未接入真实公告源、注册登记机构或销售机构系统。
- 仅支持三类公告；未覆盖清盘、持有人大会、合同修订等类型。
- 扫描件 OCR、复杂表格、跨页公告的解析能力有限。
- AI 生成措辞可能波动，需人工复核。
- 公网部署使用 Streamlit Community Cloud；如链接被平台休眠，重新唤醒即可。
