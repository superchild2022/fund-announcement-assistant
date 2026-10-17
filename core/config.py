from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

load_dotenv(ROOT / ".env")


def load_json(name: str) -> dict:
    with (DATA_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_fund_profile() -> dict:
    return load_json("fund_profile.json")


def load_announcements() -> dict:
    return load_json("announcements.json")


def load_cases() -> dict:
    return load_json("cases.json")


def _get_setting(key: str, default: str = "") -> str:
    """优先读取环境变量；在 Streamlit Cloud 上回退到 st.secrets。"""
    value = os.getenv(key)
    if value:
        return str(value).strip()
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:  # noqa: BLE001 - 非 Streamlit 运行环境
        pass
    return default


def get_api_key() -> str:
    return _get_setting("DEEPSEEK_API_KEY", "")


def get_base_url() -> str:
    return _get_setting("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def get_model() -> str:
    return _get_setting("DEEPSEEK_MODEL", "deepseek-flash")


def get_thinking() -> str:
    return _get_setting("DEEPSEEK_THINKING", "disabled").lower()
