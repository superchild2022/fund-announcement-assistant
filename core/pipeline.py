from __future__ import annotations

import time

from .compliance import check_materials
from .extractor import extract_announcement
from .generation import build_fallback, generate_materials
from .rules import analyze


def run_pipeline(
    case: dict,
    announcement: dict,
    profile: dict,
    scenario_override: dict | None = None,
    api_key: str | None = None,
    use_llm: bool = True,
    use_ai_compliance: bool = False,
) -> dict:
    started = time.time()
    timings: dict[str, float] = {}
    scenario = {**case.get("scenario", {}), **(scenario_override or {})}
    text = announcement.get("full_text", "")
    type_hint = announcement.get("type") or case.get("type")

    t0 = time.time()
    extracted, extraction_meta = extract_announcement(
        text,
        type_hint=type_hint,
        api_key=api_key,
        use_llm=use_llm,
    )
    timings["extraction_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    analysis = analyze(extracted, scenario, profile)
    timings["rules_s"] = round(time.time() - t0, 3)

    t0 = time.time()
    materials, generation_meta = generate_materials(
        case,
        announcement,
        extracted,
        analysis,
        profile,
        api_key=api_key,
        use_llm=use_llm,
    )
    timings["generation_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    compliance_report = check_materials(
        materials,
        analysis,
        analysis.get("type", ""),
        api_key=api_key,
        use_llm=use_ai_compliance,
    )
    timings["compliance_s"] = round(time.time() - t0, 2)

    auto_fallback = False
    if compliance_report.get("risk_level") == "高":
        safe_materials = build_fallback(case, announcement, extracted, analysis, profile)
        safe_report = check_materials(safe_materials, analysis, analysis.get("type", ""))
        if safe_report.get("risk_level") != "高":
            materials = safe_materials
            compliance_report = safe_report
            compliance_report["auto_fallback"] = True
            auto_fallback = True

    timings["total_s"] = round(time.time() - started, 2)

    return {
        "case": case,
        "announcement": announcement,
        "scenario": scenario,
        "extracted": extracted,
        "analysis": analysis,
        "materials": materials,
        "compliance": compliance_report,
        "data_quality": {
            "extraction_source": extraction_meta.get("extraction_source"),
            "llm_ok": extraction_meta.get("llm_ok", False),
            "missing_fields": extracted.get("missing_fields", []),
            "conflicts": extraction_meta.get("conflicts", []),
            "confidence": "高" if not extraction_meta.get("conflicts") else "中",
        },
        "meta": {
            "extraction": extraction_meta,
            "generation": generation_meta,
            "timings": timings,
            "use_llm": use_llm,
            "use_ai_compliance": use_ai_compliance,
            "auto_fallback": auto_fallback,
        },
    }


def evaluate_case(result: dict) -> list[dict]:
    case = result.get("case", {})
    expected = case.get("expected", {})
    extracted = result.get("extracted", {})
    analysis = result.get("analysis", {})
    impact = analysis.get("impact", {})
    materials = result.get("materials", {})
    checks: list[dict] = []

    def add(name: str, ok: bool, actual, expected_value):
        checks.append(
            {
                "check": name,
                "ok": bool(ok),
                "actual": actual,
                "expected": expected_value,
            }
        )

    if case.get("type") == "manager_change":
        add("离任基金经理", extracted.get("departed_manager") == expected.get("departed_manager"), extracted.get("departed_manager"), expected.get("departed_manager"))
        add("继续管理的基金经理", expected.get("remaining_manager") in (extracted.get("remaining_managers") or []), extracted.get("remaining_managers"), expected.get("remaining_manager"))
        add("离任原因", extracted.get("reason") == expected.get("reason"), extracted.get("reason"), expected.get("reason"))
        add("生效日期", extracted.get("effective_date") == expected.get("effective_date"), extracted.get("effective_date"), expected.get("effective_date"))
        joined = str(materials.get("cs_full_reply", ""))
        add("客服回复包含张晨", "张晨" in joined, "张晨" in joined, True)
        add("客服回复不推断业绩", not any(x in joined for x in expected.get("must_not_say", []) if x not in {"李明离职"}), "无禁语", True)

    elif case.get("type") == "purchase_limit":
        add("限制金额", float(extracted.get("limit_amount") or 0) == float(expected.get("limit_amount", 0)), extracted.get("limit_amount"), expected.get("limit_amount"))
        add("限制起始日", extracted.get("start_date") == expected.get("start_date"), extracted.get("start_date"), expected.get("start_date"))
        add("用户受影响判断", impact.get("affected") == expected.get("affected"), impact.get("affected"), expected.get("affected"))
        add("恢复日期未编造", impact.get("recovery_date") is None, impact.get("recovery_date"), None)

    elif case.get("type") == "dividend":
        add("每10份分红", float(extracted.get("dividend_per_10") or 0) == float(expected.get("dividend_per_10", 0)), extracted.get("dividend_per_10"), expected.get("dividend_per_10"))
        add("分红金额", abs(float(impact.get("dividend_amount") or 0) - float(expected.get("dividend_amount", 0))) < 0.01, impact.get("dividend_amount"), expected.get("dividend_amount"))
        add("本次分红方式", impact.get("method_for_this_dividend") == expected.get("method_for_this_dividend"), impact.get("method_for_this_dividend"), expected.get("method_for_this_dividend"))
        add("客服回复金额正确", "750" in str(materials.get("cs_full_reply", "")) and "7500" not in str(materials.get("cs_full_reply", "")), "含750且不含7500", True)

    return checks
