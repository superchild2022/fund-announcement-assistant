from __future__ import annotations

import re
from typing import Any

from .llm import chat_json
from .prompts import EXTRACTION_SYSTEM, build_extraction_prompt


TYPE_KEYWORDS = {
    "manager_change": ["基金经理变更", "解聘基金经理", "离任基金经理"],
    "purchase_limit": ["限制大额申购", "限制申购金额", "限制大额定期定额投资"],
    "dividend": ["分红公告", "收益分配基准日", "权益登记日", "本次分红方案"],
}


def detect_type(text: str) -> str:
    scores = {k: sum(text.count(w) for w in words) for k, words in TYPE_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().strip("：:").strip()
    if value in {"", "—", "-", "－", "null", "None", "无"}:
        return None
    return value


def _value_after(text: str, key: str) -> str | None:
    pattern = rf"{re.escape(key)}\s*[：:]?\s*([^\n]+)"
    match = re.search(pattern, text)
    if not match:
        return None
    return _clean_value(match.group(1))


def _line_with(text: str, keyword: str) -> str | None:
    for line in text.splitlines():
        if keyword in line:
            return line.strip()
    return None


def _sentence_with(text: str, keyword: str) -> str | None:
    for sentence in re.split(r"(?<=[。；])", text):
        if keyword in sentence:
            return sentence.strip()
    return _line_with(text, keyword)


def _date_iso(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
    if match:
        y, m, d = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", value)
    if match:
        y, m, d = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return None


def _amount(value: str | None) -> float | int | None:
    if value is None:
        return None
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
    if not match:
        return None
    number = float(match.group(0).replace(",", ""))
    return int(number) if number.is_integer() else number


def _bool_cn(value: str | None) -> bool | None:
    if value is None:
        return None
    if value.startswith("是"):
        return True
    if value.startswith("否"):
        return False
    return None


def _split_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in re.split(r"[、,，;；/\s]+", value) if x.strip()]


def _missing(fields: list[tuple[str, Any]]) -> list[str]:
    return [name for name, value in fields if value in (None, "", [], {})]


def rule_based_extract(text: str, type_hint: str) -> dict:
    publish_date = _date_iso(_value_after(text, "公告送出日期"))
    fund_name = _value_after(text, "基金名称")
    fund_code = _value_after(text, "基金主代码")

    if type_hint == "manager_change":
        departed = _value_after(text, "离任基金经理姓名")
        remaining = _split_names(_value_after(text, "共同管理本基金的其他基金经理姓名"))
        reason = _value_after(text, "离任原因")
        effective_raw = _value_after(text, "离任日期")
        effective = _date_iso(effective_raw)
        if not effective:
            match = re.search(r"调整自(.+?)起生效", text)
            if match:
                effective = _date_iso(match.group(1))
        change_type = _value_after(text, "基金经理变更类型")
        amac = _bool_cn(_value_after(text, "办理变更手续"))
        other_role = _value_after(text, "转任本公司其他工作岗位的说明")
        data = {
            "type": "manager_change",
            "fund_name": fund_name,
            "fund_code": fund_code,
            "publish_date": publish_date,
            "change_type": change_type,
            "departed_manager": departed,
            "remaining_managers": remaining,
            "reason": reason,
            "effective_date": effective,
            "amac_procedure_completed": amac,
            "other_role_note": other_role,
            "source_quotes": {
                "departed_manager": _line_with(text, "离任基金经理姓名"),
                "remaining_managers": _line_with(text, "共同管理本基金的其他基金经理姓名"),
                "reason": _line_with(text, "离任原因"),
                "effective_date": _line_with(text, "离任日期")
                or _sentence_with(text, "起生效"),
                "amac": _line_with(text, "办理变更手续"),
            },
        }
        data["missing_fields"] = _missing(
            [
                ("离任原因", reason),
                ("共同管理本基金的其他基金经理", remaining),
                ("离任日期", effective),
                ("转任本公司其他工作岗位的说明", other_role),
            ]
        )
        return data

    if type_hint == "purchase_limit":
        start = _date_iso(_value_after(text, "限制大额申购起始日"))
        limit = _amount(_value_after(text, "限制申购金额"))
        scope = []
        for name in ["申购", "定期定额投资", "转换转入"]:
            if name in text:
                scope.append(name)
        reason = _value_after(text, "限制相关业务的原因说明")
        recovery = None
        if "另行公告" in text:
            recovery = None
        data = {
            "type": "purchase_limit",
            "fund_name": fund_name,
            "fund_code": fund_code,
            "publish_date": publish_date,
            "start_date": start,
            "limit_amount": limit,
            "limit_scope": scope,
            "per_account_per_day": "每个基金账户" in text and "单日" in text,
            "combined_calculation": "合并计算" in text,
            "threshold_inclusive": "不含10,000元" in text or "不含10000元" in text,
            "reason": reason,
            "redemption_unaffected": "赎回、转换转出等其他业务照常办理" in text,
            "recovery_date": recovery,
            "source_quotes": {
                "start_date": _line_with(text, "限制大额申购起始日"),
                "limit_amount": _line_with(text, "限制申购金额"),
                "scope": _line_with(text, "限制接受单日每个基金账户累计"),
                "recovery": _line_with(text, "恢复办理大额申购")
                or _sentence_with(text, "另行公告"),
                "redemption": _line_with(text, "赎回、转换转出等其他业务照常办理"),
            },
        }
        data["missing_fields"] = _missing(
            [
                ("限制金额", limit),
                ("限制起始日", start),
                ("恢复大额申购的具体时间（公告称另行公告）", recovery),
            ]
        )
        if recovery is None:
            data["missing_fields"].append("恢复办理大额申购、定期定额投资和转换转入业务的具体时间")
        return data

    if type_hint == "dividend":
        record = _date_iso(_value_after(text, "权益登记日"))
        ex_date = _date_iso(_value_after(text, "除息日"))
        cash = _date_iso(_value_after(text, "现金红利发放日"))
        per10 = None
        match = re.search(r"每10份基金份额分配\s*([\d,]+(?:\.\d+)?)\s*元", text)
        if match:
            per10 = _amount(match.group(1))
        base_nav = _amount(_value_after(text, "基准日基金份额净值"))
        profit = _amount(_value_after(text, "基准日基金可供分配利润"))
        default_method = "现金分红" if "默认采用现金分红" in text else None
        reinvest_confirm = None
        match = re.search(r"将于(\d{4}年\d{1,2}月\d{1,2}日)对红利再投资份额进行确认", text)
        if match:
            reinvest_confirm = _date_iso(match.group(1))
        data = {
            "type": "dividend",
            "fund_name": fund_name,
            "fund_code": fund_code,
            "publish_date": publish_date,
            "record_date": record,
            "ex_date": ex_date,
            "cash_payment_date": cash,
            "dividend_per_10": per10,
            "base_nav": base_nav,
            "distributable_profit": profit,
            "default_method": default_method,
            "tax_note": _value_after(text, "税收相关事项"),
            "fee_note": _value_after(text, "费用相关事项"),
            "reinvest_nav_rule": _sentence_with(text, "除息后的基金份额净值为计算基准"),
            "reinvest_confirmation_date": reinvest_confirm,
            "change_cutoff_rule": _sentence_with(text, "权益登记日前记录的最后一次有效选择")
            or _sentence_with(text, "应在权益登记日前办理相关手续"),
            "source_quotes": {
                "record_date": _line_with(text, "权益登记日"),
                "ex_date": _line_with(text, "除息日"),
                "cash_payment_date": _line_with(text, "现金红利发放日"),
                "dividend_per_10": _line_with(text, "每10份基金份额分配"),
                "default_method": _line_with(text, "默认采用现金分红"),
                "change_cutoff_rule": _line_with(text, "工作日交易时间内")
                or _line_with(text, "权益登记日前"),
                "reinvest": _line_with(text, "除息后的基金份额净值"),
            },
        }
        data["missing_fields"] = _missing(
            [
                ("权益登记日", record),
                ("每10份分红金额", per10),
                ("现金红利发放日", cash),
                ("默认分红方式", default_method),
                ("红利再投资确认日", reinvest_confirm),
            ]
        )
        return data

    return {
        "type": type_hint,
        "fund_name": fund_name,
        "fund_code": fund_code,
        "publish_date": publish_date,
        "missing_fields": ["暂不支持的公告类型"],
    }


def _norm(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    if isinstance(value, list):
        return tuple(sorted(str(x) for x in value))
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        try:
            return round(float(text), 6)
        except ValueError:
            return text
    return value


def merge_extraction(base: dict, ai: dict | None) -> tuple[dict, list[dict]]:
    merged = dict(base)
    conflicts: list[dict] = []
    ai = ai or {}

    for key, ai_value in ai.items():
        if key in {"source_quotes", "missing_fields"}:
            if isinstance(ai_value, dict):
                merged[key] = {**base.get(key, {}), **{k: v for k, v in ai_value.items() if v}}
            elif isinstance(ai_value, list):
                merged[key] = sorted({*base.get(key, []), *{str(x) for x in ai_value}})
            continue

        base_value = merged.get(key)
        if base_value in (None, "", [], {}) and ai_value not in (None, "", [], {}):
            merged[key] = ai_value
        elif base_value not in (None, "", [], {}) and ai_value not in (None, "", [], {}):
            if _norm(base_value) != _norm(ai_value):
                conflicts.append(
                    {
                        "field": key,
                        "rule_value": base_value,
                        "ai_value": ai_value,
                        "resolution": "采用规则值",
                    }
                )
        # 规则值存在时始终保留规则值；AI 只补充规则未覆盖的字段

    for key, value in ai.items():
        if key not in merged:
            merged[key] = value
    merged["conflicts"] = conflicts
    return merged, conflicts


def extract_announcement(
    text: str,
    type_hint: str | None = None,
    api_key: str | None = None,
    use_llm: bool = True,
) -> tuple[dict, dict]:
    detected = type_hint or detect_type(text)
    base = rule_based_extract(text, detected)
    meta: dict = {
        "type": detected,
        "extraction_source": "规则抽取",
        "llm_ok": False,
        "conflicts": [],
    }

    if use_llm and detected in {"manager_change", "purchase_limit", "dividend"}:
        ai_data, llm_meta = chat_json(
            EXTRACTION_SYSTEM,
            build_extraction_prompt(text, detected),
            api_key=api_key,
            max_tokens=8192,
        )
        meta["llm"] = llm_meta
        if ai_data:
            merged, conflicts = merge_extraction(base, ai_data)
            meta["extraction_source"] = "AI抽取 + 规则校验"
            meta["llm_ok"] = True
            meta["conflicts"] = conflicts
            meta["ai_raw"] = ai_data
            return merged, meta
        meta["llm_error"] = llm_meta.get("error", "AI 抽取失败")
    else:
        meta["llm_skipped"] = "未启用 AI 抽取或暂不支持该公告类型"

    return base, meta
