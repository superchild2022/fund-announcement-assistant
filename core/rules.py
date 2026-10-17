from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _d(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except Exception:  # noqa: BLE001
        return None


def money(value: Any) -> str:
    number = _d(value)
    if number is None:
        return "公告未说明"
    return f"{number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def cn_date(value: str | None) -> str:
    if not value:
        return "公告未说明"
    try:
        d = date.fromisoformat(value[:10])
        return f"{d.year}年{d.month}月{d.day}日"
    except Exception:  # noqa: BLE001
        return value


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def analyze_manager_change(extracted: dict, profile: dict) -> dict:
    departed = extracted.get("departed_manager") or "公告未说明"
    remaining = extracted.get("remaining_managers") or []
    reason = extracted.get("reason")
    effective = extracted.get("effective_date")
    other_role = extracted.get("other_role_note")
    amac = extracted.get("amac_procedure_completed")
    is_managerless = not remaining

    fact_card = [
        {"label": "公告类型", "value": "基金经理变更（解聘基金经理）"},
        {"label": "基金名称", "value": extracted.get("fund_name") or profile.get("fund_name")},
        {"label": "基金代码", "value": extracted.get("fund_code") or profile.get("main_code")},
        {"label": "离任基金经理", "value": departed},
        {"label": "离任原因", "value": reason or "公告未说明"},
        {"label": "离任日期/生效日", "value": cn_date(effective)},
        {"label": "继续管理的基金经理", "value": "、".join(remaining) if remaining else "公告未说明"},
        {"label": "协会变更手续", "value": "已按规定办理" if amac else "公告未说明"},
        {"label": "转任本公司其他岗位", "value": other_role or "公告未说明（公告未披露）"},
        {"label": "公告边界", "value": "未提及基金终止、清盘、基金合同变更或投资策略调整"},
    ]

    impact_summary = (
        f"{departed}离任本基金基金经理，自{cn_date(effective)}起生效；"
        f"本基金仍由{'、'.join(remaining)}管理。"
        if remaining
        else f"{departed}离任本基金基金经理，自{cn_date(effective)}起生效；公告未披露其他继续管理的基金经理。"
    )

    sensitive_questions = [
        {
            "question": "基金经理离任是不是因为产品表现不好？",
            "answer": "公告披露的离任原因是“工作安排”，未披露与产品业绩相关的信息，不能据此推断离任与业绩有关。",
            "principle": "只讲公告事实，不推断公告未披露的原因",
        },
        {
            "question": "基金后面是不是一定会跌？",
            "answer": "无法预测基金未来涨跌，也不存在“一定”的结论。基金净值受市场、持仓、策略等多重因素影响，请结合自身风险承受能力判断。",
            "principle": "不预测涨跌、不承诺收益、不给出买卖建议",
        },
    ]

    rule_trace = [
        f"公告类型 = 解聘基金经理；离任原因 = {reason or '公告未说明'}",
        "离任原因只写“工作安排”，公告未披露业绩相关信息 → 不能推断“因为业绩不好”",
        f"共同管理的其他基金经理 = {'、'.join(remaining) if remaining else '公告未说明'} → 本基金不是无人管理",
        "公告未提及基金终止、清盘、基金合同变更或投资策略调整 → 不能延伸解读",
        f"离任日期/生效日 = {cn_date(effective)}；协会变更手续 = {'已办理' if amac else '公告未说明'}",
        "“离任本基金基金经理”不等于“从公司离职”；公告未说明其是否转任公司其他岗位",
    ]

    missing_info = [
        "公告未披露离任与产品业绩之间的关系",
        "公告未说明是否转任本公司其他工作岗位",
        "公告未说明未来投资策略、持仓或基金合同是否调整",
        "公告未说明新任基金经理安排（本次仅为解聘，张晨继续管理）",
    ]

    compliance_notes = [
        "不得使用“因为业绩不好”“业绩差”等公告未披露的原因",
        "不得回答“一定会跌”或“不会跌”，不得给出买入/卖出/赎回建议",
        "不得把“离任本基金基金经理”写成“李明离职”或“离开公司”",
        "所有对外文案需保留风险提示，并注明不构成投资建议",
    ]

    return {
        "type": "manager_change",
        "headline": f"{departed}因工作安排离任，{('、'.join(remaining) or '其他基金经理')}继续管理",
        "fact_card": fact_card,
        "impact": {
            "summary": impact_summary,
            "is_managerless": is_managerless,
            "fund_termination_mentioned": False,
            "strategy_change_announced": False,
        },
        "sensitive_questions": sensitive_questions,
        "impact_level": "中",
        "impact_rationale": (
            "公告仅涉及一名基金经理离任，张晨继续管理，未提及基金终止、清盘、"
            "基金合同或投资策略调整；对投资风格的实际影响需结合后续持仓和定期报告观察。"
        ),
        "stakeholder_impact": {
            "产品/运营": "本基金仍由张晨管理；公告未提及基金终止、清盘、基金合同或投资策略调整。",
            "客户": "可能担心离任原因和未来涨跌；应说明公告未披露业绩原因、无法预测涨跌。",
            "渠道/客服": "统一使用“离任本基金基金经理”，避免“离职”“业绩不好”；准备敏感问题口径。",
            "合规": "不得推断未披露原因，不得预测涨跌或给出买卖建议。",
        },
        "follow_up": [
            "关注是否增聘基金经理或进一步调整共管安排",
            "关注下一期定期报告中的持仓与投资风格变化",
            "关注客服/渠道咨询量与舆情反馈",
            "关注基金管理人后续公告及协会备案信息",
        ],
        "rule_trace": rule_trace,
        "missing_info": missing_info,
        "compliance_notes": compliance_notes,
        "must_not_say": ["因为业绩不好", "业绩差", "一定会跌", "不会跌", "李明离职", "赶紧赎回"],
    }


def analyze_purchase_limit(extracted: dict, scenario: dict, profile: dict) -> dict:
    limit = _d(extracted.get("limit_amount")) or Decimal("10000")
    start = extracted.get("start_date")
    monthly = _d(scenario.get("monthly_amount"))
    single_day = bool(scenario.get("single_day_debit", True))
    daily_amount = monthly if single_day else _d(scenario.get("daily_amount"))
    plan_date = scenario.get("plan_date")
    scope = extracted.get("limit_scope") or ["申购", "定期定额投资", "转换转入"]

    affected: bool | None
    impact_reason: str

    if plan_date and start and plan_date < start:
        affected = False
        impact_reason = f"计划扣款日 {plan_date} 早于限制起始日 {start}，本次限制暂不适用。"
    elif single_day and monthly is not None:
        if monthly > limit:
            affected = True
            impact_reason = (
                f"单日单账户一次性扣款 {money(monthly)} 元，超过限额 {money(limit)} 元；"
                "管理人有权拒绝相关业务申请。"
            )
        else:
            affected = False
            impact_reason = f"单日单账户扣款 {money(monthly)} 元，未超过限额 {money(limit)} 元，不受本次限制影响。"
    elif not single_day and daily_amount is not None:
        if daily_amount > limit:
            affected = True
            impact_reason = (
                f"分散扣款后单日累计 {money(daily_amount)} 元，仍超过限额 {money(limit)} 元；"
                "管理人有权拒绝相关业务申请。"
            )
        else:
            affected = False
            impact_reason = (
                f"分散扣款后单日累计 {money(daily_amount)} 元，未超过限额 {money(limit)} 元，不受本次限制影响。"
            )
    else:
        affected = None
        impact_reason = "缺少每日扣款金额或扣款方式，无法判断；需确认定投计划的单日累计金额。"

    fact_card = [
        {"label": "公告类型", "value": "限制大额申购、定期定额投资和转换转入"},
        {"label": "基金名称", "value": extracted.get("fund_name") or profile.get("fund_name")},
        {"label": "基金代码", "value": extracted.get("fund_code") or profile.get("main_code")},
        {"label": "限制起始日", "value": cn_date(start)},
        {"label": "单日单账户限额", "value": f"{money(limit)} 元"},
        {"label": "限额口径", "value": "申购 + 定期定额投资 + 转换转入合并计算"},
        {"label": "边界说明", "value": "10,000 元本身不受限；超过 10,000 元的部分/申请才触发限制"},
        {"label": "赎回/转换转出", "value": "照常办理" if extracted.get("redemption_unaffected") else "公告未说明"},
        {"label": "恢复时间", "value": "公告未说明，另行公告"},
    ]

    rule_trace = [
        f"限额 = 单日每个基金账户累计 {money(limit)} 元；申购、定投、转换转入合并计算",
        "“不含10,000元” → 单日累计正好 10,000 元不受限；超过 10,000 元才触发限制",
        f"限制起始日 = {start or '公告未说明'}；用户计划扣款日 = {plan_date or '未提供'}",
        impact_reason,
        "恢复办理时间 = 公告未说明（另行公告）→ 不能承诺具体恢复日期",
        "赎回、转换转出等其他业务照常办理",
    ]

    options = [
        "将单日单账户累计金额调整到 10,000 元（含）以内",
        "如销售机构支持，将原定投金额拆分到不同交易日，确保每日累计不超过 10,000 元",
        "向销售机构确认超限申请是整笔拒绝还是部分确认",
        "关注基金管理人后续“恢复大额申购”公告，恢复后再调整回原金额",
    ]

    missing_info = [
        "恢复办理大额申购、定期定额投资和转换转入业务的具体时间（公告称另行公告）",
        "销售机构对超限申请的处理方式（整笔拒绝或部分确认）",
        "用户定投计划的实际扣款日、扣款频率和是否支持拆分",
    ]

    compliance_notes = [
        "不得承诺“5月8日恢复”或任何具体恢复日期",
        "不得承诺超限部分一定确认，也不得承诺系统会自动调整定投金额",
        "不得引导用户通过多开账户等方式规避限制",
        "定投扣款失败是否影响其他业务，以销售机构规则为准，不要自行延伸",
    ]

    if affected is True:
        headline = f"单日定投超过 {money(limit)} 元，可能被拒绝"
    elif affected is False:
        headline = f"单日累计未超过 {money(limit)} 元，不受影响"
    else:
        headline = "需确认单日扣款金额后才能判断影响"

    return {
        "type": "purchase_limit",
        "headline": headline,
        "fact_card": fact_card,
        "impact": {
            "summary": impact_reason,
            "affected": affected,
            "monthly_amount": float(monthly) if monthly is not None else None,
            "single_day_debit": single_day,
            "daily_amount": float(daily_amount) if daily_amount is not None else None,
            "limit_amount": float(limit),
            "recovery_date": extracted.get("recovery_date"),
            "redemption_unaffected": bool(extracted.get("redemption_unaffected")),
        },
        "options": options,
        "impact_level": "中",
        "impact_rationale": (
            "本次限制影响单日单账户超过10,000元的申购、定投和转换转入申请；"
            "赎回和转换转出不受影响，但对依赖大额定投的客户现金流安排有直接影响。"
        ),
        "stakeholder_impact": {
            "产品/运营": "更新定投页和申购页提示，明确单日单账户10,000元限额及合并计算口径。",
            "客户": "20,000元/月定投若单日扣款可能被拒；可调整为10,000元以内或拆分到不同交易日。",
            "渠道": "通知销售机构更新业务规则；确认超限申请是整笔拒绝还是部分确认。",
            "合规": "不得承诺恢复日期，不得引导通过多账户等方式规避限制。",
        },
        "follow_up": [
            "监控基金管理人后续“恢复大额申购”公告",
            "跟踪客服咨询量与定投扣款失败/拒绝情况",
            "恢复后及时更新页面、渠道和客服口径",
        ],
        "rule_trace": rule_trace,
        "missing_info": missing_info,
        "compliance_notes": compliance_notes,
        "must_not_say": ["5月8日恢复", "一定恢复", "超额部分一定确认", "系统会自动调整"],
    }


def analyze_dividend(extracted: dict, scenario: dict, profile: dict) -> dict:
    shares = _d(scenario.get("shares")) or Decimal("0")
    per10 = _d(extracted.get("dividend_per_10")) or Decimal("0")
    per_share = per10 / Decimal("10")
    amount = (shares * per_share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    record_date = extracted.get("record_date") or scenario.get("record_date")
    request_raw = scenario.get("change_request_time")
    request_dt = _parse_dt(request_raw)
    default_method = extracted.get("default_method") or profile.get("default_dividend_method") or "现金分红"
    current_method = scenario.get("current_method") or default_method

    cutoff = datetime.combine(request_dt.date(), time(15, 0)) if request_dt else None
    is_trading_day = request_dt.weekday() < 5 if request_dt else False
    after_cutoff = request_dt.time() > time(15, 0) if request_dt else False
    before_record = False
    if request_dt and record_date:
        try:
            before_record = request_dt.date() < date.fromisoformat(record_date[:10])
        except ValueError:
            before_record = False

    effective: bool | None
    method: str
    confidence: str
    change_reason: str

    if request_dt is None:
        effective = None
        method = current_method
        confidence = "低"
        change_reason = (
            f"未提供分红方式变更申请时间，无法判断；分红方式按当前选择（{current_method}）展示，"
            "最终以登记机构记录为准。"
        )
    elif not before_record:
        effective = False
        method = current_method
        confidence = "高"
        change_reason = (
            "变更申请日期不早于权益登记日，未满足“权益登记日前办理”的要求；"
            f"分红方式仍按当前选择（{current_method}）。"
        )
    elif not is_trading_day:
        effective = False
        method = current_method
        confidence = "中"
        change_reason = (
            "变更申请日期不是工作日，申请可能顺延至下一交易日处理；"
            f"分红方式仍按当前选择（{current_method}）。"
        )
    elif after_cutoff:
        effective = False
        method = current_method
        confidence = "中"
        change_reason = (
            f"申请时间 {request_dt.strftime('%H:%M')} 已超过工作日交易时间（通常为 15:00）；"
            f"申请大概率于下一交易日（{cn_date(record_date)}权益登记日）处理，"
            f"晚于“权益登记日前”的要求，本次变更大概率无法生效，分红方式仍按当前选择（{current_method}）。"
        )
    else:
        effective = True
        method = "红利再投资"
        confidence = "高"
        change_reason = (
            "申请时间早于权益登记日，且在工作日交易时间内，按公告规则可计入本次分红方式；"
            "分红方式调整为红利再投资。"
        )

    cash_amount = amount if method == "现金分红" else Decimal("0.00")
    estimated_reinvest_shares = None
    if method == "红利再投资":
        estimated_reinvest_shares = (
            f"{money(amount)} ÷ {cn_date(extracted.get('ex_date'))}除息后基金份额净值"
        )

    fact_card = [
        {"label": "公告类型", "value": "2026年度第一次分红"},
        {"label": "基金名称", "value": extracted.get("fund_name") or profile.get("fund_name")},
        {"label": "基金代码", "value": extracted.get("fund_code") or profile.get("main_code")},
        {"label": "持有份额（权益登记日）", "value": f"{shares:,.0f} 份"},
        {"label": "分红方案", "value": f"每10份基金份额分配 {per10} 元"},
        {"label": "每份分红", "value": f"{per_share} 元"},
        {"label": "本次分红金额", "value": f"{money(amount)} 元"},
        {"label": "权益登记日 / 除息日", "value": f"{cn_date(record_date)} / {cn_date(extracted.get('ex_date'))}"},
        {"label": "现金红利发放日", "value": cn_date(extracted.get("cash_payment_date"))},
        {"label": "默认分红方式", "value": default_method},
        {"label": "用户当前分红方式", "value": current_method},
        {"label": "用户变更申请时间", "value": request_dt.strftime("%Y-%m-%d %H:%M") if request_dt else "未提供"},
        {"label": "本次判定方式", "value": f"{method}（置信度：{confidence}）"},
    ]

    rule_trace = [
        f"分红金额 = 持有份额 {shares:,.0f} ÷ 10 × 每10份 {per10} 元 = {money(amount)} 元",
        f"默认分红方式 = {default_method}；用户当前分红方式 = {current_method}",
        f"变更申请时间 = {request_dt.strftime('%Y-%m-%d %H:%M') if request_dt else '未提供'}；交易日 = {'是' if is_trading_day else '否'}；15:00 截止 = {'已过' if after_cutoff else '未过'}",
        change_reason,
        f"本次判定方式 = {method}（置信度：{confidence}）；最终以注册登记机构记录为准",
        f"若按红利再投资：再投资份额 = 分红金额 ÷ {cn_date(extracted.get('ex_date'))}除息后净值；{cn_date(extracted.get('reinvest_confirmation_date'))}确认，{cn_date(extracted.get('cash_payment_date'))}起可查询",
    ]

    notes = [
        "分红不是额外收益：除息后基金份额净值会相应下降，持有人的总资产不会因为分红本身而增加。",
        f"现金红利发放日 {cn_date(extracted.get('cash_payment_date'))} 是指现金红利从基金托管账户划出的日期，实际到账时间以销售机构为准。",
        f"若本次按红利再投资，再投资份额以免除申购费的方式计入，具体份额以 {cn_date(extracted.get('ex_date'))} 除息后净值和登记机构确认结果为准。",
        "本次分红免收分红手续费；基金向投资者分配的基金收益暂免征收所得税（以公告为准）。",
        "权益登记日申请申购或转换转入的基金份额不享有本次分红权益；权益登记日申请赎回或转换转出的基金份额享有本次分红权益。",
    ]

    missing_info = [
        f"{cn_date(extracted.get('ex_date'))}除息后的基金份额净值（决定红利再投资份额）",
        "销售机构实际受理变更申请的时间与截止时间（可能影响变更是否生效）",
        "注册登记机构最终记录的分红方式",
    ]

    compliance_notes = [
        f"不得直接断言用户“一定收到基金份额”；本次按规则判断为{method}，但最终以登记机构记录为准",
        "不得把分红描述为“额外收益”“白送钱”；需说明除息后净值下降",
        "不得使用基准日净值 1.1265 元计算红利再投资份额；应使用 6月18日除息后净值",
        "不提供税务建议；税收事项以公告和法规为准",
    ]

    headline = (
        f"本次分红 {money(amount)} 元，按规则判断为{method}"
        if method != "以注册登记机构记录为准"
        else f"本次分红 {money(amount)} 元，分红方式待确认"
    )

    return {
        "type": "dividend",
        "headline": headline,
        "fact_card": fact_card,
        "impact": {
            "summary": (
                f"按公告方案，{shares:,.0f} 份分红 {money(amount)} 元；"
                f"本次按规则判断为{method}。{change_reason}"
            ),
            "shares": float(shares),
            "dividend_per_10": float(per10),
            "dividend_amount": float(amount),
            "method_for_this_dividend": method,
            "method_confidence": confidence,
            "change_effective": effective,
            "change_reason": change_reason,
            "cash_amount": float(cash_amount),
            "estimated_reinvest_shares": estimated_reinvest_shares,
            "record_date": record_date,
            "ex_date": extracted.get("ex_date"),
            "cash_payment_date": extracted.get("cash_payment_date"),
            "reinvest_confirmation_date": extracted.get("reinvest_confirmation_date"),
        },
        "rule_trace": rule_trace,
        "notes": notes,
        "impact_level": "低",
        "impact_rationale": (
            "分红属于常规收益分配事件；本次核心影响是分红金额、分红方式和到账时间，"
            "不改变基金的投资运作。"
        ),
        "stakeholder_impact": {
            "产品/运营": "更新分红公告页、App FAQ和到账提醒。",
            "客户": "25,000份分红750元；默认现金分红；6月17日16:00变更大概率来不及。",
            "渠道": "确认变更申请受理时间和现金红利实际到账时间。",
            "合规": "不得断言一定收到份额；分红不是额外收益；最终以登记机构记录为准。",
        },
        "follow_up": [
            "6月22日关注现金红利到账咨询",
            "核对注册登记机构最终记录的分红方式",
            "提醒客户下次分红前在权益登记日前办理变更",
        ],
        "missing_info": missing_info,
        "compliance_notes": compliance_notes,
        "must_not_say": ["7,500", "7500", "一定是红利再投资", "分红是额外收益", "用1.1265计算再投份额"],
    }


def analyze_generic(extracted: dict, scenario: dict, profile: dict) -> dict:
    fact_card = [
        {"label": "公告类型", "value": "其他公告（通用抽取）"},
        {"label": "基金名称", "value": extracted.get("fund_name") or profile.get("fund_name")},
        {"label": "基金代码", "value": extracted.get("fund_code") or profile.get("main_code")},
        {"label": "公告送出日期", "value": extracted.get("publish_date") or "未识别"},
        {"label": "处理边界", "value": "该类型暂未配置专用抽取模板和规则，仅做通用信息抽取"},
    ]
    return {
        "type": "other",
        "headline": "公告已读取，该类型暂未配置专用规则",
        "fact_card": fact_card,
        "impact": {
            "summary": "该公告类型暂未配置专用抽取模板和规则；系统仅提供通用信息，建议人工阅读全文并复核。",
            "affected": None,
        },
        "impact_level": "待评估",
        "impact_rationale": "缺少该公告类型的专用规则和字段模板，不能自动判断影响。",
        "stakeholder_impact": {
            "产品/运营": "人工阅读公告全文，确认是否需要更新页面、系统或渠道口径。",
            "客户": "暂无自动客服口径，需人工判断。",
            "渠道": "如需通知渠道，先由运营/合规确认公告影响。",
            "合规": "通用抽取结果不作为对外口径，需人工复核。",
        },
        "follow_up": [
            "人工阅读公告全文并确认公告类型",
            "如需长期支持，补充该类型的抽取 Schema、规则和话术模板",
        ],
        "rule_trace": [
            "公告类型不在当前内置的三类高频模板中",
            "仅做通用字段抽取（基金名称、代码、公告日期）",
            "未执行金额/日期/份额等专用规则判断",
            "输出仅为通用信息，需人工复核",
        ],
        "missing_info": [
            "该公告类型暂未配置专用字段模板",
            "该公告类型暂未配置专用规则和客服口径",
            "公告全文中的关键金额、日期、适用范围需人工确认",
        ],
        "compliance_notes": [
            "通用抽取结果不作为对外发布口径",
            "不得基于通用抽取结果预测涨跌或承诺收益",
            "对外材料需人工复核",
        ],
        "must_not_say": ["保证收益", "稳赚", "必涨", "不会跌"],
    }


def analyze(extracted: dict, scenario: dict, profile: dict) -> dict:
    type_ = extracted.get("type")
    if type_ == "manager_change":
        return analyze_manager_change(extracted, profile)
    if type_ == "purchase_limit":
        return analyze_purchase_limit(extracted, scenario, profile)
    if type_ == "dividend":
        return analyze_dividend(extracted, scenario, profile)
    if type_ == "other":
        return analyze_generic(extracted, scenario, profile)
    raise ValueError(f"暂不支持的公告类型：{type_}")
