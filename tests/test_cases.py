from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import get_api_key, load_announcements, load_cases, load_fund_profile  # noqa: E402
from core.pipeline import evaluate_case, run_pipeline  # noqa: E402


def main(use_llm: bool = False) -> int:
    profile = load_fund_profile()
    announcements = load_announcements()
    cases = load_cases()
    failures = 0

    for case_id, case in cases.items():
        announcement = announcements[case["announcement_id"]]
        result = run_pipeline(
            case,
            announcement,
            profile,
            api_key=get_api_key(),
            use_llm=use_llm,
            use_ai_compliance=False,
        )
        checks = evaluate_case(result)
        print("=" * 80)
        print(case["title"])
        print("headline:", result["materials"]["headline"])
        print("impact:", result["analysis"]["impact"]["summary"])
        print(
            "extraction:",
            result["meta"]["extraction"]["extraction_source"],
            "| generation:",
            result["meta"]["generation"]["generation_source"],
            "| compliance:",
            result["compliance"]["risk_level"],
        )
        print("cs_short:", result["materials"]["cs_short_reply"])
        for check in checks:
            status = "PASS" if check["ok"] else "FAIL"
            if not check["ok"]:
                failures += 1
            print(f"  [{status}] {check['check']}: actual={check['actual']} expected={check['expected']}")
        print("violations:", json.dumps(result["compliance"]["violations"], ensure_ascii=False))

    print("=" * 80)
    print("failures:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    use_llm = "--llm" in sys.argv
    raise SystemExit(main(use_llm=use_llm))
