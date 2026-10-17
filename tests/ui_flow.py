from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"


def click_process(page: Page) -> None:
    page.get_by_role("button", name="开始处理").click()
    page.wait_for_timeout(1000)


def shot(page: Page, name: str) -> None:
    page.wait_for_timeout(2500)
    page.screenshot(path=str(SHOTS / name), full_page=True)
    print("saved", name)


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2400})
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        page.on(
            "console",
            lambda msg: errors.append(f"console {msg.type}: {msg.text}") if msg.type == "error" else None,
        )
        page.goto("http://localhost:8501", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("text=基金公告运营助手", timeout=60000)
        page.wait_for_timeout(1500)

        # Case 1
        click_process(page)
        page.get_by_text("公告事实卡", exact=True).first.wait_for(timeout=120000)
        page.get_by_text("影响等级", exact=False).first.wait_for(timeout=60000)
        shot(page, "02_case1_workbench.png")

        page.get_by_role("tab", name="客服物料").click()
        page.wait_for_timeout(600)
        shot(page, "03_case1_cs.png")

        page.get_by_role("tab", name="App 与渠道").click()
        page.wait_for_timeout(1200)
        shot(page, "03b_case1_app.png")

        page.get_by_role("tab", name="合规检查").click()
        page.wait_for_timeout(600)
        shot(page, "04_case1_compliance.png")

        page.get_by_role("tab", name="原始数据与日志").click()
        page.wait_for_timeout(600)
        shot(page, "04b_case1_logs.png")

        # Case 2
        page.get_by_text("案例2：大额申购限制", exact=True).first.click()
        page.get_by_text("单日一次性扣款", exact=True).first.wait_for(timeout=60000)
        page.wait_for_timeout(600)
        click_process(page)
        page.get_by_text("单日限额", exact=True).first.wait_for(timeout=120000)
        page.get_by_text("影响范围", exact=True).first.wait_for(timeout=60000)
        page.get_by_role("tab", name="运营工作台").click()
        shot(page, "05_case2_workbench.png")

        page.get_by_role("tab", name="客服物料").click()
        page.wait_for_timeout(600)
        shot(page, "05b_case2_cs.png")

        # Case 3
        page.get_by_text("案例3：基金分红", exact=True).first.click()
        page.get_by_text("权益登记日持有份额", exact=True).first.wait_for(timeout=60000)
        page.wait_for_timeout(600)
        click_process(page)
        page.get_by_text("分红金额", exact=True).first.wait_for(timeout=120000)
        page.get_by_text("影响范围", exact=True).first.wait_for(timeout=60000)
        page.get_by_role("tab", name="运营工作台").click()
        shot(page, "06_case3_workbench.png")

        page.get_by_role("tab", name="客服物料").click()
        page.wait_for_timeout(600)
        shot(page, "07_case3_cs.png")

        print("errors:", errors[:30])
        browser.close()


if __name__ == "__main__":
    main()
