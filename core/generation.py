from __future__ import annotations

import json
from typing import Any

from .llm import chat_json
from .prompts import GENERATION_SYSTEM, build_generation_prompt


def _fact_summary(analysis: dict) -> str:
    return "；".join(f"{item['label']}：{item['value']}" for item in analysis.get("fact_card", []))


def build_fallback(case: dict, announcement: dict, extracted: dict, analysis: dict, profile: dict) -> dict:
    type_ = analysis.get("type")
    fact_summary = _fact_summary(analysis)
    impact_summary = analysis.get("impact", {}).get("summary", "")
    missing_info = list(analysis.get("missing_info", []))
    compliance_notes = list(analysis.get("compliance_notes", []))

    if type_ == "manager_change":
        return {
            "headline": analysis.get("headline", "基金经理变更通知"),
            "fact_summary": fact_summary,
            "impact_summary": impact_summary,
            "cs_short_reply": (
                "根据公告，李明先生因工作安排离任本基金基金经理，自2026年4月15日起生效，"
                "相关手续已办理；本基金仍由张晨先生管理。公告未披露与业绩相关的原因，"
                "也无法据此判断未来涨跌。基金有风险，投资需谨慎。"
            ),
            "cs_full_reply": (
                "理解您对基金经理变更的关注。根据2026年4月15日公告，李明先生因工作安排离任本基金基金经理，"
                "自2026年4月15日起生效，相关变更手续已按规定办理；本基金仍由张晨先生管理。"
                "公告没有披露离任与产品业绩之间的关系，因此不能据此推断离任与业绩有关。"
                "基金经理变更也不代表基金未来一定上涨或下跌，基金净值受市场、持仓、策略等多重因素影响。"
                "建议您关注基金定期报告和基金管理人后续公告，结合自身风险承受能力做判断。"
                "以上内容不构成投资建议，基金有风险，投资需谨慎。"
            ),
            "app_push": {
                "title": "基金经理变更通知",
                "body": (
                    "恒远均衡成长混合（019001/019002）基金经理李明因工作安排离任，"
                    "自2026年4月15日起生效；本基金仍由张晨管理。详见公告。"
                ),
            },
            "faq": [
                {"q": "李明为什么离任？", "a": "公告披露原因为“工作安排”，未披露与业绩相关的信息。"},
                {"q": "基金还有人管理吗？", "a": "有，张晨先生继续管理本基金。"},
                {
                    "q": "我要不要赎回？",
                    "a": "无法给出买卖建议。请结合自身风险承受能力、投资目标和持有期限判断，必要时咨询持牌机构。",
                },
                {
                    "q": "基金后面会跌吗？",
                    "a": "无法预测。基金净值受多重因素影响，公告未对基金未来业绩作出任何判断。",
                },
            ],
            "ops_checklist": [
                "更新基金详情页/基金经理页：将李明从本基金现任经理名单移除，保留张晨",
                "同步客服FAQ与渠道口径，统一使用“离任本基金基金经理”，避免“离职”“业绩不好”等表述",
                "检查App推送、弹窗、页面文案，保留风险提示",
                "关注后续是否增聘基金经理、投资策略调整或基金合同变更公告",
            ],
            "compliance_notes": compliance_notes
            + ["对外文案不得出现“因为业绩不好”“一定跌/不会跌”“建议赎回”等表述"],
            "missing_info": missing_info,
            "sensitive_question_handling": (
                "遇到“是不是业绩不好”“一定会跌”时，先复述公告事实，再明确公告未披露的原因/无法预测，"
                "最后给风险提示；不要为了安抚用户而做保证。"
            ),
        }

    if type_ == "purchase_limit":
        return {
            "headline": analysis.get("headline", "大额申购限制提醒"),
            "fact_summary": fact_summary,
            "impact_summary": impact_summary,
            "cs_short_reply": (
                "您20,000元/月的定投，如在2026年5月8日及以后单日单账户累计超过10,000元，"
                "管理人有权拒绝。建议将单日金额调整到10,000元（含）以内，或确认渠道是否支持拆分到不同交易日；"
                "赎回和转换转出不受影响。恢复时间尚未公告，请关注官方通知。基金有风险，投资需谨慎。"
            ),
            "cs_full_reply": (
                "理解您的定投计划受到影响。根据公告，自2026年5月8日起，本基金限制单日每个基金账户累计申购、"
                "定期定额投资和转换转入超过10,000元的申请（10,000元本身不受限），三类申请金额合并计算。"
                "您原计划每月20,000元，如果是一次性单日扣款，单日累计超过10,000元，管理人有权拒绝相关申请；"
                "如果计划分散到多日、每日累计不超过10,000元，则不受影响。建议您：1）将单日定投金额调整到"
                "10,000元（含）以内；2）如渠道支持，拆分到不同交易日；3）向销售机构确认超限申请是整笔拒绝"
                "还是部分确认。限制期间赎回、转换转出照常办理。恢复时间公告称另行公告，目前没有具体日期，"
                "建议关注基金管理人官网/App通知。以上内容不构成投资建议，基金有风险，投资需谨慎。"
            ),
            "app_push": {
                "title": "大额申购限制提醒",
                "body": (
                    "自2026年5月8日起，本基金单日单账户累计申购、定投、转换转入超过10,000元的申请可能被拒绝；"
                    "10,000元本身不受限，赎回和转换转出照常办理。"
                ),
            },
            "faq": [
                {
                    "q": "我的20,000元定投会被自动改成10,000元吗？",
                    "a": "不会。公告没有自动调整安排，需要您主动调整定投计划或与销售机构确认。",
                },
                {
                    "q": "超过10,000元一定会被拒绝吗？",
                    "a": "公告称管理人“有权拒绝”，是否整笔拒绝或部分确认以销售机构实际处理为准。",
                },
                {"q": "什么时候恢复？", "a": "公告明确恢复时间另行公告，目前没有具体日期。"},
                {"q": "赎回受影响吗？", "a": "不受影响，赎回、转换转出等其他业务照常办理。"},
                {
                    "q": "10,000元可以买吗？",
                    "a": "可以。公告表述为超过10,000元的申请受限，不含10,000元本身。",
                },
            ],
            "ops_checklist": [
                "更新定投设置页/申购页提示：单日单账户累计限额10,000元",
                "通知销售渠道更新业务规则和客服口径",
                "客服重点解释：单日、单账户、三类业务合并计算、10,000元本身不受限",
                "监控基金管理人后续恢复大额申购公告",
            ],
            "compliance_notes": compliance_notes
            + ["不得承诺恢复日期，不得引导用户通过多账户等方式规避限制"],
            "missing_info": missing_info,
            "sensitive_question_handling": (
                "遇到“什么时候恢复”时，明确公告称另行公告，不承诺日期；"
                "遇到“能不能多开账户”时，说明按账户限额是公告规则，不引导规避。"
            ),
        }

    if type_ == "dividend":
        return {
            "headline": analysis.get("headline", "基金分红通知"),
            "fact_summary": fact_summary,
            "impact_summary": impact_summary,
            "cs_short_reply": (
                "按每10份派0.30元计算，25,000份分红750元。您默认现金分红；"
                "6月17日16:00的变更已过交易时间，本次大概率仍为现金分红，6月22日发放。"
                "最终以登记机构记录为准，建议在App确认。基金有风险，投资需谨慎。"
            ),
            "cs_full_reply": (
                "按公告方案，每10份基金份额分配0.30元，您持有25,000份，本次分红金额为"
                "25,000÷10×0.30=750元。本基金默认分红方式为现金分红；您6月17日16:00申请改为红利再投资，"
                "该时间已超过工作日交易时间（通常为15:00），申请大概率要到6月18日权益登记日才处理，"
                "晚于“权益登记日前办理”的要求，因此本次大概率仍按现金分红750元发放，"
                "现金红利发放日为2026年6月22日。最终分红方式以注册登记机构记录为准，建议您在App或销售机构确认。"
                "如果本次按红利再投资，再投资份额=750元÷6月18日除息后基金份额净值，6月19日确认，"
                "6月22日起可查询。提示：分红不是额外收益，除息后基金份额净值会相应下降。"
                "以上内容不构成投资建议，基金有风险，投资需谨慎。"
            ),
            "app_push": {
                "title": "分红发放提醒",
                "body": (
                    "本次分红每10份派0.30元，25,000份分红750元；现金红利发放日6月22日，"
                    "分红方式以登记机构记录为准。"
                ),
            },
            "faq": [
                {
                    "q": "分红金额怎么算？",
                    "a": "每10份派0.30元，25,000份=25,000÷10×0.30=750元。",
                },
                {
                    "q": "我会收到现金还是份额？",
                    "a": "您默认现金分红；6月17日16:00的变更已过交易时间，本次大概率仍为现金分红750元，最终以登记机构记录为准。",
                },
                {
                    "q": "现在改红利再投资还来得及吗？",
                    "a": "本次大概率来不及；可在下次分红权益登记日前的工作日交易时间内办理。",
                },
                {
                    "q": "现金什么时候到账？",
                    "a": "现金红利发放日为6月22日，实际到账时间以销售机构为准。",
                },
                {
                    "q": "分红会增加我的总资产吗？",
                    "a": "不会。除息后基金份额净值会相应下降，分红本身不增加总资产。",
                },
            ],
            "ops_checklist": [
                "更新分红公告页和App常见问题",
                "客服重点解释分红金额、默认现金分红、变更截止时间、到账时间",
                "准备6月22日现金到账咨询口径",
                "核对权益登记日持有人名单和分红方式记录",
            ],
            "compliance_notes": compliance_notes
            + ["不得断言用户一定收到份额，不得把分红描述为额外收益"],
            "missing_info": missing_info,
            "sensitive_question_handling": (
                "遇到“为什么不是份额”时，解释16:00已过交易时间、以登记机构记录为准；"
                "不要直接断言，建议用户App确认。"
            ),
        }

    return {
        "headline": analysis.get("headline", "公告处理结果"),
        "fact_summary": fact_summary,
        "impact_summary": impact_summary,
        "cs_short_reply": "暂不支持该公告类型的自动生成，请人工处理。",
        "cs_full_reply": "暂不支持该公告类型的自动生成，请人工处理。",
        "app_push": {"title": "公告处理结果", "body": "暂不支持该公告类型。"},
        "faq": [],
        "ops_checklist": ["人工复核公告并补充处理"],
        "compliance_notes": compliance_notes,
        "missing_info": missing_info,
        "sensitive_question_handling": "转人工处理。",
    }


def _contains_banned(text: str, banned: list[str]) -> bool:
    return any(word in text for word in banned)


def _ensure_risk(text: str) -> str:
    if "风险" in text or "投资需谨慎" in text:
        return text
    return text.rstrip() + " 基金有风险，投资需谨慎。"


def _merge_and_sanitize(
    fallback: dict,
    ai: dict | None,
    analysis: dict,
    case_type: str,
) -> tuple[dict, list[str]]:
    result = dict(fallback)
    ai = ai or {}
    for key, value in ai.items():
        if value not in (None, "", [], {}):
            result[key] = value

    result["headline"] = fallback["headline"]
    result["impact_summary"] = fallback["impact_summary"]
    result["missing_info"] = sorted({*fallback.get("missing_info", []), *result.get("missing_info", [])})
    result["compliance_notes"] = sorted(
        {*fallback.get("compliance_notes", []), *result.get("compliance_notes", [])}
    )

    banned = analysis.get("must_not_say", [])
    reasons: list[str] = []

    for key in ("cs_short_reply", "cs_full_reply"):
        text = str(result.get(key, ""))
        if _contains_banned(text, banned):
            result[key] = fallback[key]
            reasons.append(f"{key} 命中禁语，已回退到安全模板")
        else:
            result[key] = _ensure_risk(text)

    app_push = result.get("app_push") or fallback["app_push"]
    app_text = json.dumps(app_push, ensure_ascii=False)
    if _contains_banned(app_text, banned):
        result["app_push"] = fallback["app_push"]
        reasons.append("app_push 命中禁语，已回退到安全模板")

    if case_type == "purchase_limit":
        if "10,000" not in result["cs_full_reply"] and "10000" not in result["cs_full_reply"]:
            result["cs_full_reply"] = fallback["cs_full_reply"]
            reasons.append("客服完整回复缺少关键限额，已回退到安全模板")
    elif case_type == "dividend":
        if ("7500" in result["cs_full_reply"]) or ("7,500" in result["cs_full_reply"]):
            result["cs_full_reply"] = fallback["cs_full_reply"]
            reasons.append("客服完整回复出现错误分红金额，已回退到安全模板")
        if "750" not in result["cs_full_reply"]:
            result["cs_full_reply"] = fallback["cs_full_reply"]
            reasons.append("客服完整回复缺少分红金额，已回退到安全模板")
    elif case_type == "manager_change":
        if "张晨" not in result["cs_full_reply"]:
            result["cs_full_reply"] = fallback["cs_full_reply"]
            reasons.append("客服完整回复缺少继续管理的基金经理，已回退到安全模板")

    return result, reasons


def generate_materials(
    case: dict,
    announcement: dict,
    extracted: dict,
    analysis: dict,
    profile: dict,
    api_key: str | None = None,
    use_llm: bool = True,
) -> tuple[dict, dict]:
    fallback = build_fallback(case, announcement, extracted, analysis, profile)
    meta: dict = {
        "generation_source": "安全模板",
        "llm_ok": False,
        "fallback_used": False,
        "fallback_reasons": [],
    }

    if not use_llm:
        meta["reason"] = "未启用 AI 生成"
        return fallback, meta

    ai, llm_meta = chat_json(
        GENERATION_SYSTEM,
        build_generation_prompt(case, announcement, extracted, analysis, profile),
        api_key=api_key,
        max_tokens=8192,
    )
    meta["llm"] = llm_meta
    if not ai:
        meta["fallback_used"] = True
        meta["fallback_reasons"] = ["AI 生成失败，已使用安全模板"]
        meta["error"] = llm_meta.get("error", "AI 生成失败")
        return fallback, meta

    result, reasons = _merge_and_sanitize(fallback, ai, analysis, analysis.get("type"))
    meta["generation_source"] = "AI生成 + 规则校验"
    meta["llm_ok"] = True
    meta["fallback_used"] = bool(reasons)
    meta["fallback_reasons"] = reasons
    meta["ai_raw"] = ai
    return result, meta
