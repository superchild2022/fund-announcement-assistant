from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import load_announcements, load_cases, load_fund_profile  # noqa: E402
from core.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    profile = load_fund_profile()
    announcements = load_announcements()
    cases = load_cases()
    failures: list[str] = []

    def check(name: str, actual, expected) -> None:
        ok = actual == expected
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: actual={actual!r} expected={expected!r}")
        if not ok:
            failures.append(name)

    # 案例2：单日 20,000 触发限制
    res = run_pipeline(
        cases["case2"],
        announcements["B"],
        profile,
        scenario_override={
            "monthly_amount": 20000,
            "single_day_debit": True,
            "plan_date": "2026-05-20",
        },
        use_llm=False,
    )
    check("20,000 单日扣款受影响", res["analysis"]["impact"]["affected"], True)

    # 案例2：正好 10,000 不受限（不含10,000元）
    res = run_pipeline(
        cases["case2"],
        announcements["B"],
        profile,
        scenario_override={
            "monthly_amount": 10000,
            "single_day_debit": True,
            "plan_date": "2026-05-20",
        },
        use_llm=False,
    )
    check("10,000 单日扣款不受影响", res["analysis"]["impact"]["affected"], False)

    # 案例2：10,000.01 触发限制
    res = run_pipeline(
        cases["case2"],
        announcements["B"],
        profile,
        scenario_override={
            "monthly_amount": 10000.01,
            "single_day_debit": True,
            "plan_date": "2026-05-20",
        },
        use_llm=False,
    )
    check("10,000.01 单日扣款受影响", res["analysis"]["impact"]["affected"], True)

    # 案例2：分散到多日，每日 1,000 不受限
    res = run_pipeline(
        cases["case2"],
        announcements["B"],
        profile,
        scenario_override={
            "monthly_amount": 20000,
            "single_day_debit": False,
            "daily_amount": 1000,
            "plan_date": "2026-05-20",
        },
        use_llm=False,
    )
    check("每日1,000分散扣款不受影响", res["analysis"]["impact"]["affected"], False)

    # 案例3：16:00 超过交易时间，本次现金分红
    res = run_pipeline(
        cases["case3"],
        announcements["C"],
        profile,
        scenario_override={
            "shares": 25000,
            "record_date": "2026-06-18",
            "change_request_time": "2026-06-17T16:00:00",
            "current_method": "现金分红",
        },
        use_llm=False,
    )
    check("16:00 本次现金分红", res["analysis"]["impact"]["method_for_this_dividend"], "现金分红")
    check("25,000份分红750元", res["analysis"]["impact"]["dividend_amount"], 750.0)

    # 案例3：用户当前已是红利再投资，16:00 变更失效后仍保持红利再投资
    res = run_pipeline(
        cases["case3"],
        announcements["C"],
        profile,
        scenario_override={
            "shares": 25000,
            "record_date": "2026-06-18",
            "change_request_time": "2026-06-17T16:00:00",
            "current_method": "红利再投资",
        },
        use_llm=False,
    )
    check(
        "当前已是红利再投资，16:00变更失效后仍为红利再投资",
        res["analysis"]["impact"]["method_for_this_dividend"],
        "红利再投资",
    )

    # 案例3：14:00 在交易时间内，可改红利再投资
    res = run_pipeline(
        cases["case3"],
        announcements["C"],
        profile,
        scenario_override={
            "shares": 25000,
            "record_date": "2026-06-18",
            "change_request_time": "2026-06-17T14:00:00",
            "current_method": "现金分红",
        },
        use_llm=False,
    )
    check("14:00 可改红利再投资", res["analysis"]["impact"]["method_for_this_dividend"], "红利再投资")

    # 案例3：权益登记日当天申请，来不及
    res = run_pipeline(
        cases["case3"],
        announcements["C"],
        profile,
        scenario_override={
            "shares": 25000,
            "record_date": "2026-06-18",
            "change_request_time": "2026-06-18T10:00:00",
            "current_method": "现金分红",
        },
        use_llm=False,
    )
    check("6月18日申请本次现金分红", res["analysis"]["impact"]["method_for_this_dividend"], "现金分红")

    # 案例1：张晨继续管理，不是无人管理
    res = run_pipeline(cases["case1"], announcements["A"], profile, use_llm=False)
    check("基金经理变更后不是无人管理", res["analysis"]["impact"]["is_managerless"], False)
    check("事件不是基金终止", res["analysis"]["impact"]["fund_termination_mentioned"], False)

    print("failures:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
