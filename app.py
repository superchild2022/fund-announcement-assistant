from __future__ import annotations

import html
import json
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import get_api_key, get_model, get_thinking, load_announcements, load_cases, load_fund_profile  # noqa: E402
from core.extractor import detect_type  # noqa: E402
from core.pipeline import evaluate_case, run_pipeline  # noqa: E402

TYPE_LABELS = {
    "manager_change": "基金经理变更",
    "purchase_limit": "大额申购限制",
    "dividend": "基金分红",
    "unknown": "未识别",
}

TYPE_OPTIONS = {
    "自动识别": None,
    "基金经理变更": "manager_change",
    "大额申购限制": "purchase_limit",
    "基金分红": "dividend",
}

SAMPLE_CASE_MAP = {"A": "case1", "B": "case2", "C": "case3"}


def inject_css() -> None:
    st.markdown(
        """
<style>
:root { --ink:#152033; --muted:#64748b; --line:#e2e8f0; --brand:#0f766e; }
.block-container { max-width: 1280px; padding-top: 3.8rem; padding-bottom: 3rem; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
h1,h2,h3 { letter-spacing:-0.02em; }
.app-title { font-size: 2.0rem; font-weight: 800; color: var(--ink); margin-bottom: .1rem; }
.app-subtitle { color: var(--muted); margin-bottom: .7rem; font-size: .98rem; }
.card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:1rem 1.1rem; box-shadow:0 6px 18px rgba(15,23,42,.04); }
.card-title { font-size:1.05rem; font-weight:700; color:var(--ink); margin:.45rem 0 .3rem 0; line-height:1.45; }
.muted { color:var(--muted); font-size:.84rem; line-height:1.6; }
.badge { display:inline-block; padding:.18rem .55rem; border-radius:999px; font-size:.75rem; font-weight:650; letter-spacing:.01em; }
.badge-blue { background:#e0f2fe; color:#075985; }
.badge-green { background:#dcfce7; color:#166534; }
.badge-amber { background:#fef3c7; color:#92400e; }
.badge-red { background:#fee2e2; color:#991b1b; }
.badge-gray { background:#f1f5f9; color:#475569; }
.callout { background:linear-gradient(135deg,#0f766e,#115e59); color:#fff; border-radius:16px; padding:1rem 1.2rem; margin: .4rem 0 1rem 0; }
.callout-label { font-size:.72rem; opacity:.8; letter-spacing:.08em; text-transform:uppercase; }
.callout-text { font-size:1.12rem; font-weight:700; margin-top:.25rem; line-height:1.5; }
.metric-strip { display:grid; gap:.65rem; margin:.2rem 0 .8rem 0; }
.metric-box { background:#fff; border:1px solid var(--line); border-radius:12px; padding:.65rem .75rem; }
.metric-label { color:var(--muted); font-size:.70rem; margin-bottom:.2rem; }
.metric-value { color:var(--ink); font-size:1.0rem; font-weight:750; line-height:1.35; }
.section-title { font-size:1.0rem; font-weight:750; color:var(--ink); margin:.35rem 0 .45rem 0; }
.fact-table { width:100%; border-collapse:collapse; font-size:.85rem; background:#fff; border:1px solid var(--line); border-radius:10px; overflow:hidden; }
.fact-table td { padding:.5rem .6rem; border-bottom:1px solid #eef2f7; vertical-align:top; line-height:1.55; }
.fact-table tr:last-child td { border-bottom:none; }
.fact-table .fact-label { width:34%; color:#64748b; font-weight:650; }
.fact-table .fact-value { color:var(--ink); word-break:break-word; }
.small-note { background:#f8fafc; border:1px dashed #cbd5e1; border-radius:10px; padding:.6rem .8rem; color:#475569; font-size:.85rem; line-height:1.55; }
[data-testid="stSidebar"] { background:#ffffff; border-right:1px solid #e2e8f0; }
.stButton>button { border-radius:10px; font-weight:650; }
.stTabs [data-baseweb="tab-list"] { gap: .25rem; }
.stTabs [data-baseweb="tab"] { border-radius:8px 8px 0 0; padding: .45rem .8rem; }
</style>
""",
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "blue") -> str:
    return f'<span class="badge badge-{kind}">{html.escape(str(text))}</span>'


def metric_strip(items: list[tuple[str, str]], cols: int = 4) -> None:
    boxes = "".join(
        f'<div class="metric-box"><div class="metric-label">{html.escape(str(label))}</div>'
        f'<div class="metric-value">{html.escape(str(value))}</div></div>'
        for label, value in items
    )
    st.markdown(
        f'<div class="metric-strip" style="grid-template-columns: repeat({cols}, minmax(0,1fr));">{boxes}</div>',
        unsafe_allow_html=True,
    )


def fmt_number(value: Any, digits: int = 0) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:  # noqa: BLE001
        return str(value)


def render_fact_table(items: list[dict]) -> None:
    rows = "".join(
        f'<tr><td class="fact-label">{html.escape(str(item.get("label", "")))}</td>'
        f'<td class="fact-value">{html.escape(str(item.get("value", "")))}</td></tr>'
        for item in items
    )
    st.markdown(f'<table class="fact-table">{rows}</table>', unsafe_allow_html=True)


def read_uploaded_file(uploaded) -> str:
    data = uploaded.getvalue()
    if uploaded.name.lower().endswith(".pdf"):
        try:
            import pymupdf

            doc = pymupdf.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as exc:  # noqa: BLE001
            st.error(f"PDF 解析失败：{exc}")
            return ""
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def render_header() -> None:
    st.markdown('<div class="app-title">基金公告运营助手</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">把一份基金公告，3 分钟变成可审核、可追溯、可分发的运营物料</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        " ".join(
            [
                badge("AI 抽取", "blue"),
                badge("规则计算", "green"),
                badge("合规复核", "amber"),
                badge("3 类公告", "gray"),
            ]
        ),
        unsafe_allow_html=True,
    )


def render_sidebar(profile: dict, cases: dict, announcements: dict) -> dict:
    st.sidebar.markdown("### 运行设置")
    env_key = get_api_key()
    if env_key:
        st.sidebar.markdown(badge("API Key 已配置", "green"), unsafe_allow_html=True)
    else:
        st.sidebar.markdown(badge("未配置 API Key", "amber"), unsafe_allow_html=True)

    key_input = st.sidebar.text_input(
        "DeepSeek API Key（留空使用 .env）",
        type="password",
        placeholder="sk-...",
        help="Demo 默认从本地 .env 读取，不会写入导出文件。",
    )
    mode = st.sidebar.radio(
        "运行模式",
        ["AI 实时模式", "离线演示模式"],
        index=0,
        help="离线模式使用规则抽取 + 安全模板，可复现但不代表 AI 实时生成。",
    )
    use_ai_compliance = st.sidebar.checkbox(
        "启用 AI 合规复核",
        value=False,
        help="规则引擎已做基础合规检查；开启后额外调用一次模型进行复核。",
    )
    st.sidebar.caption(
        f"模型：{get_model()}　思考模式：{'开启' if get_thinking() == 'enabled' else '关闭'}"
    )

    st.sidebar.divider()
    st.sidebar.markdown("### 产品资料")
    st.sidebar.caption(
        f"{profile['fund_name']}（{profile['main_code']} / {profile['c_code']}）\n\n"
        f"风险等级：{profile['risk_level']}　默认分红：{profile['default_dividend_method']}"
    )

    st.sidebar.divider()
    st.sidebar.markdown("### 质量自检")
    if st.sidebar.button("运行三案例自检（离线规则）", use_container_width=True):
        rows: list[dict] = []
        for case in cases.values():
            announcement = announcements[case["announcement_id"]]
            result = run_pipeline(
                case,
                announcement,
                profile,
                use_llm=False,
                use_ai_compliance=False,
            )
            for item in evaluate_case(result):
                rows.append(
                    {
                        "案例": case["title"],
                        "检查项": item["check"],
                        "结果": "通过" if item["ok"] else "失败",
                        "实际值": str(item["actual"]),
                        "期望值": str(item["expected"]),
                    }
                )
        st.session_state["self_check_rows"] = rows

    rows = st.session_state.get("self_check_rows")
    if rows:
        passed = sum(1 for row in rows if row["结果"] == "通过")
        total = len(rows)
        if passed == total:
            st.sidebar.success(f"自检通过 {passed}/{total}")
        else:
            st.sidebar.error(f"自检通过 {passed}/{total}，请检查失败项")
        st.sidebar.dataframe(
            pd.DataFrame([{"案例": r["案例"], "检查项": r["检查项"], "结果": r["结果"]} for r in rows]),
            hide_index=True,
            use_container_width=True,
        )

    st.sidebar.divider()
    with st.sidebar.expander("关于本 Demo / 如实说明"):
        st.markdown(
            "- 本题三类公告为虚构材料，仅用于演示。\n"
            "- AI 负责分类、抽取、文案生成；金额、日期、份额等由规则引擎计算。\n"
            "- 三个案例的规则判断可离线复现；离线模式不调用大模型。\n"
            "- 未接入真实注册登记机构、销售机构或公告源系统，最终数据以官方记录为准。\n"
            "- 恢复公告监控、批量处理、真实渠道对接尚未实现。\n"
            "- 输出为运营草稿，必须人工复核，不构成投资建议。"
        )

    return {
        "api_key": key_input.strip() or env_key,
        "mode": mode,
        "use_ai_compliance": use_ai_compliance,
    }


def render_inputs(announcements: dict, cases: dict, profile: dict) -> tuple[dict, dict, dict, str]:
    st.markdown("### 1. 上传或粘贴公告")
    st.caption(
        "试题要求运营人员上传公告；上传/粘贴是主流程。三个规定案例只是快捷示例，"
        "载入后公告原文会进入可编辑文本框，仍走同一套抽取、规则计算和生成流程。"
    )

    left, right = st.columns([1.15, 1])

    with left:
        uploaded = st.file_uploader(
            "上传公告 PDF / TXT",
            type=["pdf", "txt", "md"],
            key="announcement_upload",
        )
        file_text = read_uploaded_file(uploaded) if uploaded else ""
        if uploaded:
            st.success(f"已读取文件：{uploaded.name}（{len(file_text)} 字）")
            st.caption("上传文件优先；如果要使用示例文本，请先移除上传文件。")

        st.session_state.setdefault("announcement_text", "")
        announcement_text = st.text_area(
            "公告原文",
            height=240,
            key="announcement_text",
            label_visibility="collapsed",
            placeholder="把公告全文粘贴到这里……",
        )

        st.markdown("**没有文件？载入规定测试案例：**")

        def load_sample(sample_id: str) -> None:
            st.session_state["announcement_text"] = announcements[sample_id]["full_text"]
            st.session_state["sample_id"] = sample_id
            st.session_state["announcement_type_choice"] = "自动识别"

        sample_cols = st.columns(3)
        for col, sample_id in zip(sample_cols, ("A", "B", "C")):
            with col:
                st.button(
                    f"载入公告 {sample_id}",
                    key=f"load_sample_{sample_id}",
                    on_click=load_sample,
                    args=(sample_id,),
                    use_container_width=True,
                )
        st.caption("载入后仍可在文本框中编辑；修改后按自定义公告处理。")

        text = file_text or announcement_text.strip()
        detected = detect_type(text) if text else "unknown"
        if text:
            type_choice = st.selectbox(
                "公告类型（自动识别不准时可手动指定）",
                list(TYPE_OPTIONS),
                index=0,
                key="announcement_type_choice",
            )
            type_hint = TYPE_OPTIONS[type_choice] or detected
            if type_hint == "unknown":
                st.warning("暂未识别公告类型，请手动选择；当前支持三类公告。")
            else:
                st.caption(f"识别类型：{TYPE_LABELS.get(type_hint, type_hint)}")
        else:
            type_hint = "unknown"

        sample_id = st.session_state.get("sample_id")
        sample = announcements.get(sample_id) if sample_id else None
        is_sample = bool(sample and text == sample["full_text"] and not file_text)

        if file_text:
            source_label = "上传文件"
        elif is_sample:
            source_label = f"示例公告 {sample_id}"
        elif text:
            source_label = "粘贴文本"
        else:
            source_label = "未输入"

        if is_sample:
            title = sample["title"]
            publish = sample.get("publish_date", "")
        else:
            title = (
                next((line.strip() for line in text.splitlines() if line.strip()), "等待输入公告")
                if text
                else "等待输入公告"
            )
            publish = ""

        announcement = {
            "id": sample_id if is_sample else "custom",
            "type": type_hint,
            "type_label": TYPE_LABELS.get(type_hint, "未识别"),
            "title": title[:100],
            "publish_date": publish,
            "full_text": text,
        }

        if text:
            publish_text = publish or "未识别"
            st.markdown(
                f"""
<div class="card">
  {badge(announcement.get("type_label", "公告"), "blue")}
  <div class="card-title">{html.escape(str(announcement.get("title", "")))}</div>
  <div class="muted">公告送出日期：{html.escape(str(publish_text))}　·　基金代码：{profile['main_code']} / {profile['c_code']}　·　输入来源：{html.escape(source_label)}</div>
</div>
""",
                unsafe_allow_html=True,
            )
            with st.expander("查看公告原文", expanded=False):
                st.text(text)
        else:
            st.info("请上传 PDF/TXT、粘贴公告原文，或点击上方示例按钮载入公告 A/B/C。")

    with right:
        st.markdown("### 2. 用户场景")
        case_type = type_hint if text else "unknown"

        if case_type == "unknown":
            st.markdown(
                '<div class="small-note">先上传/粘贴公告，或载入示例公告；系统会根据公告类型显示对应的用户场景输入。</div>',
                unsafe_allow_html=True,
            )
            scenario_override: dict = {}
            user_request = "用户上传/粘贴公告，请生成运营物料。"
        else:
            sample_case = cases.get(SAMPLE_CASE_MAP.get(sample_id, "")) if is_sample else None
            user_request = (
                sample_case.get("user_request")
                if sample_case
                else "用户上传/粘贴公告，请生成运营物料，并按下方场景判断影响。"
            )
            with st.expander("查看用户请求", expanded=False):
                st.write(user_request)

            scenario_override = {}
            if case_type == "manager_change":
                questions = (
                    (sample_case or {}).get("scenario", {}).get("user_questions")
                    or ["基金经理为什么离任？", "基金后面会不会跌？"]
                )
                st.markdown("**用户可能追问：**")
                for question in questions:
                    st.markdown(f"- {question}")
                st.markdown(
                    '<div class="small-note">系统需要同时处理“原因推断”和“涨跌预测”两类敏感问题，不能只做摘要。</div>',
                    unsafe_allow_html=True,
                )
            elif case_type == "purchase_limit":
                default_monthly = 20000 if (is_sample and sample_id == "B") else 10000
                monthly = st.number_input(
                    "原定投计划金额（元/月）",
                    min_value=0,
                    value=default_monthly,
                    step=1000,
                    key="scenario_monthly",
                )
                single_day = st.checkbox(
                    "单日一次性扣款",
                    value=True,
                    key="scenario_single_day",
                    help="取消勾选表示分散到多日扣款",
                )
                plan_date = st.date_input(
                    "计划扣款日",
                    value=date(2026, 5, 20),
                    key="scenario_plan_date",
                )
                daily = None
                if not single_day:
                    daily = st.number_input(
                        "每日计划扣款金额（元）",
                        min_value=0,
                        value=1000,
                        step=500,
                        key="scenario_daily",
                    )
                scenario_override = {
                    "monthly_amount": monthly,
                    "single_day_debit": single_day,
                    "plan_date": plan_date.isoformat(),
                    "daily_amount": daily,
                }
                st.caption("试试取消“单日一次性扣款”，看看影响判断如何变化。")
            elif case_type == "dividend":
                default_shares = 25000 if (is_sample and sample_id == "C") else 10000
                shares = st.number_input(
                    "权益登记日持有份额",
                    min_value=0,
                    value=default_shares,
                    step=1000,
                    key="scenario_shares",
                )
                change_date = st.date_input(
                    "分红方式变更申请日期",
                    value=date(2026, 6, 17),
                    key="scenario_change_date",
                )
                change_time = st.time_input(
                    "申请时间",
                    value=time(16, 0),
                    key="scenario_change_time",
                )
                current_method = st.selectbox(
                    "当前分红方式",
                    ["现金分红", "红利再投资"],
                    index=0,
                    key="scenario_current_method",
                )
                scenario_override = {
                    "shares": shares,
                    "record_date": "2026-06-18",
                    "change_request_time": datetime.combine(change_date, change_time).isoformat(),
                    "current_method": current_method,
                }
                st.caption("把申请时间改到 15:00 前，系统会给出不同的分红方式判断。")

    if is_sample:
        case_key = SAMPLE_CASE_MAP.get(sample_id, "case1")
        case = dict(cases[case_key])
        case["id"] = case_key
    else:
        case = {
            "id": "custom",
            "title": "自定义公告",
            "type": type_hint,
            "user_request": user_request,
            "scenario": scenario_override,
            "expected": {},
        }

    return announcement, scenario_override, case, source_label


def render_empty_state() -> None:
    st.markdown("---")
    st.markdown("### 处理流程")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div class="card"><div class="card-title">1. 读懂公告</div>'
            '<div class="muted">自动识别公告类型，抽取人物、日期、金额、份额、适用范围，并保留原文引用。</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="card"><div class="card-title">2. 算清影响</div>'
            '<div class="muted">规则引擎处理金额边界、生效日、时间截止、分红金额，避免大模型算错数字。</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="card"><div class="card-title">3. 产出物料</div>'
            '<div class="muted">生成客服口径、App 推送、FAQ、运营待办和合规提示，人工复核后导出。</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="small-note" style="margin-top:1rem;">上传/粘贴公告，或点击“载入公告 A/B/C”示例，然后点击“开始处理”。示例公告载入后仍可编辑，处理走同一套流程。</div>',
        unsafe_allow_html=True,
    )


def build_export_markdown(
    result: dict,
    cs_short: str,
    cs_full: str,
    app_title: str,
    app_body: str,
    reviewed: bool,
) -> str:
    case = result["case"]
    announcement = result["announcement"]
    analysis = result["analysis"]
    materials = result["materials"]
    compliance = result["compliance"]
    meta = result["meta"]

    lines: list[str] = []
    lines.append(f"# 基金公告运营物料：{case['title']}")
    lines.append("")
    lines.append(f"- 公告：{announcement.get('title', '')}")
    lines.append(f"- 公告类型：{announcement.get('type_label', '')}")
    lines.append(f"- 生成方式：{meta.get('generation', {}).get('generation_source', '')}")
    lines.append(f"- 抽取方式：{meta.get('extraction', {}).get('extraction_source', '')}")
    lines.append(f"- 合规风险：{compliance.get('risk_level', '')}")
    lines.append(f"- 人工复核：{'已完成' if reviewed else '未完成'}")
    lines.append("")
    lines.append("## 一句话结论")
    lines.append("")
    lines.append(str(materials.get("headline", "")))
    lines.append("")
    lines.append("## 公告事实卡")
    lines.append("")
    lines.append("| 字段 | 内容 |")
    lines.append("|---|---|")
    for item in analysis.get("fact_card", []):
        lines.append(f"| {item.get('label', '')} | {item.get('value', '')} |")
    lines.append("")
    lines.append("## 影响判断")
    lines.append("")
    lines.append(str(materials.get("impact_summary", "")))
    lines.append("")
    lines.append("### 规则判断过程")
    lines.append("")
    for item in analysis.get("rule_trace", []):
        lines.append(f"- {item}")
    lines.append("")
    if analysis.get("impact_level"):
        lines.append(f"### 影响等级：{analysis['impact_level']}")
        lines.append("")
        if analysis.get("impact_rationale"):
            lines.append(analysis["impact_rationale"])
            lines.append("")
    if analysis.get("stakeholder_impact"):
        lines.append("## 影响范围")
        lines.append("")
        for role, text in analysis["stakeholder_impact"].items():
            lines.append(f"- **{role}**：{text}")
        lines.append("")
    if analysis.get("follow_up"):
        lines.append("## 后续跟踪")
        lines.append("")
        for item in analysis["follow_up"]:
            lines.append(f"- [ ] {item}")
        lines.append("")
    lines.append("## 客服物料")
    lines.append("")
    lines.append("### 短口径")
    lines.append("")
    lines.append(cs_short or str(materials.get("cs_short_reply", "")))
    lines.append("")
    lines.append("### 完整回复")
    lines.append("")
    lines.append(cs_full or str(materials.get("cs_full_reply", "")))
    lines.append("")
    lines.append("## App 推送")
    lines.append("")
    lines.append(f"**{app_title or (materials.get('app_push') or {}).get('title', '')}**")
    lines.append("")
    lines.append(app_body or (materials.get("app_push") or {}).get("body", ""))
    lines.append("")
    lines.append("## 用户 FAQ")
    lines.append("")
    for item in materials.get("faq", []) or []:
        if isinstance(item, dict):
            lines.append(f"**Q：{item.get('q', '')}**")
            lines.append("")
            lines.append(str(item.get("a", "")))
            lines.append("")
    lines.append("## 运营待办")
    lines.append("")
    for item in materials.get("ops_checklist", []) or []:
        lines.append(f"- [ ] {item}")
    lines.append("")
    lines.append("## 缺失信息 / 待确认")
    lines.append("")
    for item in analysis.get("missing_info", []) or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 合规检查")
    lines.append("")
    lines.append(f"- 风险等级：{compliance.get('risk_level', '')}")
    lines.append(f"- 检查摘要：{compliance.get('summary', '')}")
    for item in compliance.get("violations", []) or []:
        lines.append(f"- 待处理：{item.get('type', '')}；建议：{item.get('suggestion', '')}")
    lines.append("")
    if analysis.get("notes"):
        lines.append("## 投资者教育要点")
        lines.append("")
        for item in analysis["notes"]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("## 处理日志")
    lines.append("")
    lines.append(f"- 总耗时：{meta.get('timings', {}).get('total_s', '')} 秒")
    lines.append(f"- 抽取耗时：{meta.get('timings', {}).get('extraction_s', '')} 秒")
    lines.append(f"- 生成耗时：{meta.get('timings', {}).get('generation_s', '')} 秒")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("本 Demo 使用题目提供的虚构数据；输出为运营草稿，需人工复核，不构成投资建议。")
    return "\n".join(lines)


def render_result(result: dict, case_id: str) -> None:
    announcement = result["announcement"]
    analysis = result["analysis"]
    materials = result["materials"]
    compliance = result["compliance"]
    meta = result["meta"]
    timings = meta.get("timings", {})
    run_id = result.get("run_id", 0)

    metric_strip(
        [
            ("公告类型", announcement.get("type_label", "未识别")),
            ("处理耗时", f"{timings.get('total_s', 0)} 秒"),
            ("合规风险", compliance.get("risk_level", "未检查")),
            (
                "抽取方式",
                "AI + 规则" if meta.get("extraction", {}).get("llm_ok") else "规则抽取",
            ),
        ],
        cols=4,
    )

    st.markdown(
        f'<div class="callout"><div class="callout-label">一句话结论</div>'
        f'<div class="callout-text">{html.escape(str(materials.get("headline", "")))}</div></div>',
        unsafe_allow_html=True,
    )

    if not meta.get("use_llm"):
        st.info("当前为离线演示模式：规则抽取 + 安全模板，结果可复现，但不代表 AI 实时生成。")
    if meta.get("auto_fallback"):
        st.caption("合规保护：本次 AI 文案未通过检查，系统已自动切换为安全模板；详情见“合规检查/处理日志”。")
    if meta.get("generation", {}).get("fallback_used"):
        reasons = "；".join(meta["generation"].get("fallback_reasons", []))
        st.caption(f"生成保护：{reasons}")
    if meta.get("use_llm") and not meta.get("extraction", {}).get("llm_ok"):
        st.caption("抽取提示：AI 抽取未成功，已使用规则抽取结果。")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["运营工作台", "客服物料", "App 与渠道", "合规检查", "原始数据与日志"]
    )

    with tab1:
        left, right = st.columns([1.15, 1])
        with left:
            st.markdown('<div class="section-title">公告事实卡</div>', unsafe_allow_html=True)
            render_fact_table(analysis.get("fact_card", []))
            with st.expander("字段级原文引用（可追溯）", expanded=False):
                quotes = result["extracted"].get("source_quotes", {})
                if quotes:
                    for key, quote in quotes.items():
                        if quote:
                            st.markdown(f"**{key}**：{quote}")
                else:
                    st.caption("暂无引用")
            with st.expander("公告原文", expanded=False):
                st.text(announcement.get("full_text", ""))

        with right:
            st.markdown('<div class="section-title">规则判断</div>', unsafe_allow_html=True)
            for line in analysis.get("rule_trace", []):
                st.markdown(f"- {line}")

            if analysis.get("impact_level"):
                st.markdown(f"**影响等级：{analysis['impact_level']}**")
                if analysis.get("impact_rationale"):
                    st.caption(analysis["impact_rationale"])

            impact = analysis.get("impact", {})
            if analysis.get("type") == "purchase_limit":
                metric_strip(
                    [
                        ("用户月定投", f"{fmt_number(impact.get('monthly_amount', 0))} 元"),
                        ("单日限额", f"{fmt_number(impact.get('limit_amount', 0))} 元"),
                        (
                            "是否受影响",
                            "是"
                            if impact.get("affected") is True
                            else "否"
                            if impact.get("affected") is False
                            else "待确认",
                        ),
                    ],
                    cols=3,
                )
            elif analysis.get("type") == "dividend":
                metric_strip(
                    [
                        ("持有份额", f"{fmt_number(impact.get('shares', 0))} 份"),
                        ("分红金额", f"{fmt_number(impact.get('dividend_amount', 0), 2)} 元"),
                        ("本次方式", str(impact.get("method_for_this_dividend", ""))),
                    ],
                    cols=3,
                )

            stakeholder = analysis.get("stakeholder_impact") or {}
            if stakeholder:
                st.markdown('<div class="section-title">影响范围</div>', unsafe_allow_html=True)
                for role, text in stakeholder.items():
                    st.markdown(f"**{role}**：{text}")

            if analysis.get("follow_up"):
                st.markdown('<div class="section-title">后续跟踪</div>', unsafe_allow_html=True)
                for item in analysis["follow_up"]:
                    st.markdown(f"- {item}")

            st.markdown('<div class="section-title">缺失信息 / 待确认</div>', unsafe_allow_html=True)
            if analysis.get("missing_info"):
                for item in analysis["missing_info"]:
                    st.markdown(f"- {item}")
            else:
                st.caption("无")

            st.markdown('<div class="section-title">敏感问题处理</div>', unsafe_allow_html=True)
            if analysis.get("sensitive_questions"):
                for item in analysis["sensitive_questions"]:
                    st.markdown(f"**Q：{item.get('question', '')}**")
                    st.info(item.get("answer", ""))
                    st.caption(f"处理原则：{item.get('principle', '')}")
            else:
                st.info(
                    materials.get("sensitive_question_handling")
                    or analysis.get("sensitive_question_handling")
                    or "无"
                )

            if analysis.get("options"):
                st.markdown('<div class="section-title">可选处理方案</div>', unsafe_allow_html=True)
                for index, option in enumerate(analysis["options"], 1):
                    st.markdown(f"{index}. {option}")

            if analysis.get("notes"):
                st.markdown('<div class="section-title">投资者教育要点</div>', unsafe_allow_html=True)
                for note in analysis["notes"]:
                    st.markdown(f"- {note}")

    with tab2:
        st.markdown("##### 客服物料")
        st.caption("短口径用于电话/在线客服；完整回复用于工单或详细解答。修改后会保留在导出文件中。")
        c1, c2 = st.columns([1, 1.35])
        with c1:
            cs_short_val = st.text_area(
                "客服短口径",
                value=str(materials.get("cs_short_reply", "")),
                height=190,
                key=f"cs_short_{case_id}_{run_id}",
            )
        with c2:
            cs_full_val = st.text_area(
                "客服完整回复",
                value=str(materials.get("cs_full_reply", "")),
                height=320,
                key=f"cs_full_{case_id}_{run_id}",
            )
        st.caption("对外发布前请由客服主管/合规复核；本 Demo 不构成投资建议。")

    with tab3:
        st.markdown("##### App 推送")
        app_push = materials.get("app_push") or {}
        if not isinstance(app_push, dict):
            app_push = {"title": str(app_push), "body": ""}
        app_title_val = st.text_input(
            "推送标题",
            value=str(app_push.get("title", "")),
            key=f"app_title_{case_id}_{run_id}",
        )
        app_body_val = st.text_area(
            "推送正文",
            value=str(app_push.get("body", "")),
            height=120,
            key=f"app_body_{case_id}_{run_id}",
        )

        st.markdown("##### 用户 FAQ")
        for index, item in enumerate(materials.get("faq", []) or []):
            if isinstance(item, dict):
                question, answer = item.get("q", ""), item.get("a", "")
            else:
                question, answer = str(item), ""
            with st.expander(f"Q{index + 1}：{question}", expanded=index == 0):
                st.write(answer)

        st.markdown("##### 运营待办")
        for index, item in enumerate(materials.get("ops_checklist", []) or []):
            st.checkbox(str(item), key=f"ops_{case_id}_{run_id}_{index}")

        st.markdown("##### 合规提示")
        for item in materials.get("compliance_notes", []) or []:
            st.markdown(f"- {item}")

    with tab4:
        risk = compliance.get("risk_level", "未检查")
        kind = {"低": "green", "中": "amber", "高": "red"}.get(risk, "gray")
        st.markdown(badge(f"合规风险：{risk}", kind), unsafe_allow_html=True)
        st.caption(compliance.get("summary", ""))

        if compliance.get("auto_fallback"):
            st.info("AI 文案未通过合规检查，已自动回退到安全模板。")
        violations = compliance.get("violations", []) or []
        if violations:
            for item in violations:
                st.error(f"**{item.get('type', '问题')}**：{item.get('suggestion', '')}")
                if item.get("quote"):
                    st.code(item["quote"], language=None)
        else:
            st.success("规则层面未发现合规问题。")

        if compliance.get("passed"):
            with st.expander("查看通过项", expanded=False):
                for item in compliance["passed"]:
                    st.markdown(f"- {item}")
        if compliance.get("llm_review"):
            with st.expander("AI 合规复核详情", expanded=False):
                st.json(compliance["llm_review"])
        with st.expander("合规检查说明", expanded=False):
            st.markdown(
                "规则引擎检查：禁语/保证性表述、关键事实、关键数字、关键日期、风险提示。"
                "AI 复核为可选项，最终仍需人工签批。"
            )

    with tab5:
        st.markdown("##### 结构化抽取结果")
        st.json(result["extracted"])
        st.markdown("##### 规则分析结果")
        st.json(analysis)
        st.markdown("##### 处理日志与模型用量")
        st.json(meta)
        st.markdown("##### 合规报告")
        st.json(compliance)
        conflicts = result["extracted"].get("conflicts") or meta.get("extraction", {}).get("conflicts")
        if conflicts:
            st.warning("AI 抽取与规则抽取存在冲突，系统已采用规则值。")
            st.json(conflicts)

    st.divider()
    reviewed = st.checkbox(
        "我已人工复核以上内容，确认对外发布前由运营/合规负责人签批",
        key=f"reviewed_{case_id}_{run_id}",
    )
    export_md = build_export_markdown(
        result,
        cs_short_val,
        cs_full_val,
        app_title_val,
        app_body_val,
        reviewed,
    )
    export_json = {
        **result,
        "materials": {
            **result["materials"],
            "cs_short_reply": cs_short_val,
            "cs_full_reply": cs_full_val,
            "app_push": {"title": app_title_val, "body": app_body_val},
        },
        "human_reviewed": reviewed,
    }
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "导出全部物料（Markdown）",
            data=export_md,
            file_name=f"基金公告运营物料_{case_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "导出结构化 JSON",
            data=json.dumps(export_json, ensure_ascii=False, indent=2, default=str),
            file_name=f"基金公告运营结果_{case_id}.json",
            mime="application/json",
            use_container_width=True,
        )
    st.caption("导出内容包含：公告事实卡、影响判断、客服物料、App 物料、运营待办、合规检查、抽取与规则日志。")


def main() -> None:
    st.set_page_config(page_title="基金公告运营助手", layout="wide")
    inject_css()
    render_header()

    profile = load_fund_profile()
    announcements = load_announcements()
    cases = load_cases()

    settings = render_sidebar(profile, cases, announcements)
    api_key = settings["api_key"]
    mode = settings["mode"]
    use_ai_compliance = settings["use_ai_compliance"]

    announcement, scenario_override, case, source_label = render_inputs(announcements, cases, profile)

    st.markdown("")
    can_process = bool(announcement.get("full_text")) and announcement.get("type") != "unknown"
    process = st.button(
        "开始处理",
        type="primary",
        use_container_width=True,
        disabled=not can_process,
    )
    if can_process:
        st.caption(
            f"当前输入：{source_label} · {announcement.get('type_label')} · "
            "AI 负责理解与表达，规则引擎负责金额/日期判断，输出需人工复核。"
        )
    else:
        st.caption("请先上传/粘贴公告，或载入示例公告 A/B/C，并确认公告类型。")

    signature = json.dumps(
        {
            "case": case["id"],
            "announcement": announcement.get("id"),
            "type": announcement.get("type"),
            "text_head": announcement.get("full_text", "")[:200],
            "scenario": scenario_override,
            "mode": mode,
            "ai_compliance": use_ai_compliance,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )

    if process:
        use_llm = mode == "AI 实时模式" and bool(api_key)
        if mode == "AI 实时模式" and not api_key:
            st.warning("未配置 API Key，本次自动使用离线演示模式。")
        if announcement.get("type") == "unknown":
            st.error("公告类型未识别，请先在上方手动选择公告类型。")
        else:
            with st.spinner("正在解析公告、计算影响并生成物料..."):
                try:
                    result = run_pipeline(
                        case,
                        announcement,
                        profile,
                        scenario_override=scenario_override,
                        api_key=api_key,
                        use_llm=use_llm,
                        use_ai_compliance=use_ai_compliance and use_llm,
                    )
                    run_id = st.session_state.get("run_count", 0) + 1
                    st.session_state["run_count"] = run_id
                    result["run_id"] = run_id
                    st.session_state["result"] = result
                    st.session_state["result_signature"] = signature
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"处理失败：{exc}")
                    st.exception(exc)

    result = st.session_state.get("result")
    if result:
        if st.session_state.get("result_signature") != signature:
            st.warning("输入已变更。下方展示的是上一次结果，请重新点击“开始处理”以更新。")
        render_result(result, case["id"])
    else:
        render_empty_state()

    st.markdown("---")
    st.caption("本 Demo 使用题目提供的虚构数据；输出为运营草稿，需人工复核，不构成投资建议。")


if __name__ == "__main__":
    main()
