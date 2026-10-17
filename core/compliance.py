from __future__ import annotations

import json
import re
from typing import Any

from .llm import chat_json
from .prompts import LLM_COMPLIANCE_SYSTEM


GENERIC_BANNED = [
    "保证收益",
    "稳赚",
    "必涨",
    "包赚",
    "无风险",
    "翻倍",
    "业绩不好",
    "业绩差",
    "赶紧赎回",
    "建议买入",
    "建议卖出",
    "一定会涨",
    "一定会跌",
    "肯定涨",
    "肯定跌",
]


def _customer_text(materials: dict) -> str:
    """只扫描对外文案，避免把内部合规提示中的“禁语示例”误判为违规。"""
    parts: list[str] = []
    for key in ("headline", "fact_summary", "impact_summary", "cs_short_reply", "cs_full_reply"):
        parts.append(str(materials.get(key, "")))
    app_push = materials.get("app_push") or {}
    if isinstance(app_push, dict):
        parts.extend(str(app_push.get(k, "")) for k in ("title", "body"))
    else:
        parts.append(str(app_push))
    for item in materials.get("faq", []) or []:
        if isinstance(item, dict):
            # 用户问题可以引用敏感表述；合规扫描只检查客服答案。
            parts.append(str(item.get("a", "")))
    return "\n".join(parts)


def _all_text(materials: dict) -> str:
    """给 AI 复核使用的完整文本。"""
    parts = [_customer_text(materials)]
    for key in ("ops_checklist", "compliance_notes", "missing_info"):
        parts.extend(str(x) for x in (materials.get(key) or []))
    parts.append(str(materials.get("sensitive_question_handling", "")))
    return "\n".join(parts)


def _find_quote(text: str, word: str) -> str:
    for line in text.splitlines():
        if word in line:
            return line.strip()[:160]
    return word


def rule_compliance(materials: dict, analysis: dict, case_type: str) -> dict:
    text = _customer_text(materials)
    banned = list(dict.fromkeys(GENERIC_BANNED + list(analysis.get("must_not_say", []))))
    violations: list[dict] = []
    passed: list[str] = []

    for word in banned:
        if word in text:
            violations.append(
                {
                    "type": "禁语/保证性表述",
                    "quote": _find_quote(text, word),
                    "suggestion": f"删除“{word}”，改为基于公告事实的中性表述。",
                }
            )

    if "风险" not in text and "投资需谨慎" not in text and "不构成投资建议" not in text:
        violations.append(
            {
                "type": "缺少风险提示",
                "quote": "",
                "suggestion": "至少保留“基金有风险，投资需谨慎”或“以上内容不构成投资建议”。",
            }
        )
    else:
        passed.append("包含风险提示/不构成投资建议")

    if case_type == "manager_change":
        if "张晨" in text:
            passed.append("明确说明张晨继续管理")
        else:
            violations.append(
                {
                    "type": "关键事实缺失",
                    "quote": "",
                    "suggestion": "必须说明本基金仍由张晨管理，避免用户误以为基金无人管理。",
                }
            )
        if "公告未披露" in text or "未披露" in text:
            passed.append("明确说明公告未披露业绩原因")
        else:
            violations.append(
                {
                    "type": "关键边界缺失",
                    "quote": "",
                    "suggestion": "必须说明公告未披露离任与业绩的关系，不能推断原因。",
                }
            )
        if "李明离职" in text or "离开公司" in text:
            violations.append(
                {
                    "type": "事实表述错误",
                    "quote": _find_quote(text, "李明离职") or _find_quote(text, "离开公司"),
                    "suggestion": "改为“离任本基金基金经理”，公告未说明其从公司离职。",
                }
            )
        else:
            passed.append("未把“离任本基金”误写为“离职”")

    elif case_type == "purchase_limit":
        if "10,000" in text or "10000" in text:
            passed.append("包含10,000元限额")
        else:
            violations.append(
                {
                    "type": "关键数字缺失",
                    "quote": "",
                    "suggestion": "必须写明单日单账户累计限额10,000元。",
                }
            )
        if "另行公告" in text or "尚未公告" in text or "没有具体日期" in text:
            passed.append("明确恢复时间另行公告")
        else:
            violations.append(
                {
                    "type": "关键边界缺失",
                    "quote": "",
                    "suggestion": "恢复时间公告称另行公告，不能承诺具体日期。",
                }
            )
        if "赎回" in text and "转换转出" in text:
            passed.append("说明赎回/转换转出不受影响")
        else:
            violations.append(
                {
                    "type": "关键事实缺失",
                    "quote": "",
                    "suggestion": "需说明限制期间赎回、转换转出等其他业务照常办理。",
                }
            )

    elif case_type == "dividend":
        if "750" in text:
            passed.append("分红金额750元正确出现")
        else:
            violations.append(
                {
                    "type": "关键数字缺失",
                    "quote": "",
                    "suggestion": "25,000份按每10份0.30元计算，分红金额为750元。",
                }
            )
        if "7500" in text or "7,500" in text:
            violations.append(
                {
                    "type": "分红金额计算错误",
                    "quote": _find_quote(text, "7500") or _find_quote(text, "7,500"),
                    "suggestion": "正确计算为25,000÷10×0.30=750元，不是7,500元。",
                }
            )
        if "现金分红" in text:
            passed.append("说明本次按现金分红判断")
        else:
            violations.append(
                {
                    "type": "关键结论缺失",
                    "quote": "",
                    "suggestion": "按公告规则，本次大概率仍为现金分红，需明确说明。",
                }
            )
        if "6月22日" in text or "2026年6月22日" in text:
            passed.append("包含现金红利发放日6月22日")
        else:
            violations.append(
                {
                    "type": "关键日期缺失",
                    "quote": "",
                    "suggestion": "写明现金红利发放日为2026年6月22日。",
                }
            )
        if "登记机构" in text:
            passed.append("提示最终以登记机构记录为准")
        else:
            violations.append(
                {
                    "type": "关键边界缺失",
                    "quote": "",
                    "suggestion": "必须提示最终分红方式以注册登记机构记录为准。",
                }
            )
        if "额外收益" in text and "不是额外收益" not in text and "并非额外收益" not in text:
            violations.append(
                {
                    "type": "投资者教育缺失",
                    "quote": _find_quote(text, "额外收益"),
                    "suggestion": "分红不是额外收益，除息后净值会相应下降。",
                }
            )
        else:
            passed.append("未把分红描述为额外收益")

    serious_types = {
        "禁语/保证性表述",
        "关键数字缺失",
        "分红金额计算错误",
        "事实表述错误",
        "关键事实缺失",
        "关键边界缺失",
        "关键结论缺失",
        "关键日期缺失",
        "缺少风险提示",
    }
    serious = [v for v in violations if v["type"] in serious_types]
    if serious:
        risk_level = "高"
    elif violations:
        risk_level = "中"
    else:
        risk_level = "低"

    return {
        "risk_level": risk_level,
        "violations": violations,
        "passed": passed,
        "summary": (
            f"规则检查：{len(passed)} 项通过，{len(violations)} 项待处理；风险等级：{risk_level}。"
        ),
        "source": "规则引擎",
    }


def check_materials(
    materials: dict,
    analysis: dict,
    case_type: str,
    api_key: str | None = None,
    use_llm: bool = False,
) -> dict:
    report = rule_compliance(materials, analysis, case_type)
    if not use_llm:
        return report

    text = _all_text(materials)
    ai, meta = chat_json(
        LLM_COMPLIANCE_SYSTEM,
        f"请审核以下基金公告运营文案：\n\n{text}",
        api_key=api_key,
        max_tokens=4096,
    )
    report["llm"] = meta
    if ai:
        report["llm_review"] = ai
        if ai.get("risk_level") == "高":
            report["risk_level"] = "高"
        elif ai.get("risk_level") == "中" and report["risk_level"] == "低":
            report["risk_level"] = "中"
        report["summary"] += f" AI复核：{ai.get('summary', '')}"
        report["source"] = "规则引擎 + AI复核"
    return report


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")
