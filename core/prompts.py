from __future__ import annotations

import json

EXTRACTION_SYSTEM = """你是基金公告信息抽取器。你只依据公告原文抽取信息，不得补充、推测或改写。
要求：
1. 只输出一个 JSON 对象，不要输出 Markdown 代码块。
2. 日期统一为 YYYY-MM-DD；金额为数字（单位：元），不要带千分位。
3. 公告没有写的字段填 null，并在 missing_fields 中列出。
4. 每个关键字段尽量在 source_quotes 中给出对应的原文句子。
5. 不确定的字段不要猜。"""


SCHEMAS = {
    "manager_change": {
        "type": "manager_change",
        "fund_name": "基金全称",
        "fund_code": "基金主代码",
        "publish_date": "YYYY-MM-DD",
        "change_type": "如：解聘基金经理",
        "departed_manager": "离任基金经理姓名",
        "remaining_managers": ["共同管理本基金的其他基金经理姓名"],
        "reason": "离任原因，原文没有则 null",
        "effective_date": "YYYY-MM-DD",
        "amac_procedure_completed": True,
        "other_role_note": "转任本公司其他工作岗位的说明，原文没有则 null",
        "source_quotes": {
            "reason": "原文句子",
            "effective_date": "原文句子",
            "remaining_managers": "原文句子",
        },
        "missing_fields": ["公告未说明的字段"],
    },
    "purchase_limit": {
        "type": "purchase_limit",
        "fund_name": "基金全称",
        "fund_code": "基金主代码",
        "publish_date": "YYYY-MM-DD",
        "start_date": "YYYY-MM-DD",
        "limit_amount": 10000,
        "limit_scope": ["申购", "定期定额投资", "转换转入"],
        "per_account_per_day": True,
        "combined_calculation": True,
        "threshold_inclusive": True,
        "reason": "限制原因",
        "redemption_unaffected": True,
        "recovery_date": None,
        "source_quotes": {
            "limit_amount": "原文句子",
            "start_date": "原文句子",
            "recovery": "原文句子",
        },
        "missing_fields": ["公告未说明的字段"],
    },
    "dividend": {
        "type": "dividend",
        "fund_name": "基金全称",
        "fund_code": "基金主代码",
        "publish_date": "YYYY-MM-DD",
        "record_date": "YYYY-MM-DD",
        "ex_date": "YYYY-MM-DD",
        "cash_payment_date": "YYYY-MM-DD",
        "dividend_per_10": 0.3,
        "base_nav": 1.1265,
        "distributable_profit": 38520416.75,
        "default_method": "现金分红或红利再投资",
        "tax_note": "税收相关事项",
        "fee_note": "费用相关事项",
        "reinvest_nav_rule": "红利再投资净值计算规则",
        "reinvest_confirmation_date": "YYYY-MM-DD",
        "change_cutoff_rule": "分红方式变更的时间规则",
        "source_quotes": {
            "record_date": "原文句子",
            "dividend_per_10": "原文句子",
            "default_method": "原文句子",
            "change_cutoff_rule": "原文句子",
        },
        "missing_fields": ["公告未说明的字段"],
    },
}


def build_extraction_prompt(text: str, type_hint: str | None) -> str:
    schema = SCHEMAS.get(type_hint, {})
    return f"""公告类型提示：{type_hint or "未知，请根据公告内容判断"}
请按下面的 JSON 结构抽取公告信息。字段名必须保持一致。

JSON 结构：
{json.dumps(schema, ensure_ascii=False, indent=2)}

公告原文：
\"\"\"
{text}
\"\"\"

请输出抽取结果 JSON。"""


GENERATION_SYSTEM = """你是基金公司的公告运营助手，服务对象是客服、App 运营、渠道运营和合规人员。
你必须遵守：
1. 只使用下面给出的事实和规则计算结果，不得改变数字、日期、人名、份额类别。
2. 严格区分三类内容：公告事实、规则计算、运营建议。
3. 不得预测基金涨跌，不得承诺收益，不得使用“一定”“必涨”“稳赚”“不会跌”“无风险”等表述。
4. 不得推断公告未披露的原因，例如不得说“因为业绩不好”“因为业绩差”。
5. 公告没有说明的，写“公告未说明”，不要编造。
6. 客服回复要先共情、再讲事实、再给下一步；明确说明不构成投资建议。
7. 只输出一个 JSON 对象，不要输出 Markdown 代码块。"""


GENERATION_SCHEMA = {
    "headline": "一句话结论，20字以内",
    "fact_summary": "公告事实摘要，3-5条，使用分号分隔",
    "impact_summary": "对当前用户场景的影响判断，必须包含规则计算结论",
    "cs_short_reply": "客服电话/在线客服的短口径，80-150字",
    "cs_full_reply": "客服完整回复，200-400字，先共情、再事实、再下一步",
    "app_push": {"title": "App推送标题，20字以内", "body": "App推送正文，60-120字"},
    "faq": [{"q": "用户可能问的问题", "a": "回复"}],
    "ops_checklist": ["运营待办1", "运营待办2"],
    "compliance_notes": ["合规提示1", "合规提示2"],
    "missing_info": ["公告未说明的信息1", "公告未说明的信息2"],
    "sensitive_question_handling": "遇到敏感问题时的处理原则和示例口径",
}


def build_generation_prompt(
    case: dict,
    announcement: dict,
    extracted: dict,
    analysis: dict,
    profile: dict,
) -> str:
    payload = {
        "测试案例": {
            "标题": case.get("title"),
            "用户请求": case.get("user_request"),
            "用户场景": case.get("scenario"),
        },
        "公告基本信息": {
            "标题": announcement.get("title"),
            "公告类型": announcement.get("type_label"),
            "公告送出日期": announcement.get("publish_date"),
        },
        "AI抽取与规则校验后的结构化事实": extracted,
        "规则引擎计算结果": analysis,
        "产品基本资料": profile,
    }
    return f"""请根据下面的材料生成运营物料。

材料：
{json.dumps(payload, ensure_ascii=False, indent=2)}

输出 JSON 结构必须如下：
{json.dumps(GENERATION_SCHEMA, ensure_ascii=False, indent=2)}

额外要求：
- fact_summary 只能写公告事实，不能写推测。
- impact_summary 必须引用规则引擎的结论和关键数字。
- cs_short_reply 与 cs_full_reply 必须包含“基金有风险，投资需谨慎”或同义风险提示。
- app_push 不得使用夸张、承诺收益或预测涨跌的标题。
- 如果规则引擎给出“公告未说明/未公告”，必须在 missing_info 中保留。
- 不要输出任何 JSON 以外的内容。"""


LLM_COMPLIANCE_SYSTEM = """你是基金公告合规审核员。请检查给定文案是否存在以下问题：
1. 预测基金涨跌或承诺收益；
2. 使用“一定”“必涨”“稳赚”“不会跌”“无风险”等绝对化/保证性表述；
3. 推断公告未披露的原因（如“因为业绩不好”）；
4. 给出买入、卖出、赎回等投资建议；
5. 篡改公告中的数字、日期、人名；
6. 缺少风险提示。
只输出 JSON：{"risk_level":"低/中/高","violations":[{"type":"...","quote":"...","suggestion":"..."}],"summary":"..."}"""
