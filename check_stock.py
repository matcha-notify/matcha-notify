#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Marukyu Koyamaen 補貨監控機器人
================================
定期抓取指定商品頁面，判斷「該商品是否至少有一個規格（variation）有現貨」，
如果狀態從「無貨」變成「有貨」，就透過 LINE Messaging API 推播通知。

判斷邏輯：
  WooCommerce 商品頁面在 HTML 裡會內嵌一段 JSON（藏在 <form class="variations_form">
  的 data-product_variations 屬性中），列出每個規格(variation)的庫存狀態
  (is_in_stock: true/false)。只要任何一個規格 is_in_stock 為 true，就視為「有貨」。

  如果網站改版導致抓不到這段 JSON，程式會退而求其次，改用頁面文字判斷
  （尋找 "currently out of stock and unavailable" 這句話是否存在）。
"""

import json
import os
import re
import sys
import html
from datetime import datetime, timezone, timedelta

import requests

# ---------------------------------------------------------------------------
# 設定：要監控的商品清單（在這裡增減商品即可）
# ---------------------------------------------------------------------------
PRODUCTS = [
    {"name": "若竹",       "url": "https://www.marukyu-koyamaen.co.jp/english/shop/products/11b1100c1"},
    {"name": "青嵐",       "url": "https://www.marukyu-koyamaen.co.jp/english/shop/products/11a1040c1"},
    {"name": "五十鈴",     "url": "https://www.marukyu-koyamaen.co.jp/english/shop/products/1191040c1"},
    {"name": "低咖啡因抹茶", "url": "https://www.marukyu-koyamaen.co.jp/english/shop/products/1f94020c1"},
]

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")  # 也可以是多個 ID 用逗號分隔

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

TAIPEI_TZ = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# 狀態存取
# ---------------------------------------------------------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 庫存判斷
# ---------------------------------------------------------------------------
def check_in_stock(html_text: str) -> bool:
    """
    回傳 True 表示「至少一個規格有貨」。
    優先解析 WooCommerce 的 data-product_variations JSON；
    找不到的話退回用文字判斷。
    """
    # 方法一：解析 variations JSON（最準確）
    match = re.search(r'data-product_variations="([^"]+)"', html_text)
    if match:
        raw_json = html.unescape(match.group(1))
        try:
            variations = json.loads(raw_json)
            if isinstance(variations, list) and len(variations) > 0:
                return any(v.get("is_in_stock") for v in variations)
        except json.JSONDecodeError:
            pass  # 解析失敗，往下用備援方法

    # 方法二（備援）：找不到 JSON 時，用頁面文字判斷
    # 網站在缺貨時會顯示這句話；如果找不到這句話，視為「可能有貨」
    out_of_stock_phrase = "currently out of stock and unavailable"
    if out_of_stock_phrase in html_text:
        # 仍要防呆：如果同時存在 "Add to cart" 按鈕，代表其實有其他規格可買
        if re.search(r'add[_-]?to[_-]?cart', html_text, re.IGNORECASE):
            return True
        return False

    # 完全找不到任何缺貨字樣，保守起見視為有貨（避免漏掉補貨）
    return True


def fetch_product_html(url: str) -> str:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# LINE 推播
# ---------------------------------------------------------------------------
def send_line_message(text: str):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("⚠️  尚未設定 LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID，略過推播。")
        print("---- 原本要發送的內容 ----")
        print(text)
        print("--------------------------")
        return

    user_ids = [uid.strip() for uid in LINE_USER_ID.split(",") if uid.strip()]

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    for uid in user_ids:
        payload = {
            "to": uid,
            "messages": [{"type": "text", "text": text}],
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            print(f"❌ LINE 推播失敗 (user={uid}): {resp.status_code} {resp.text}")
        else:
            print(f"✅ LINE 推播成功 (user={uid})")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    state = load_state()
    restocked = []
    now_str = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")

    for product in PRODUCTS:
        name = product["name"]
        url = product["url"]
        try:
            html_text = fetch_product_html(url)
            in_stock = check_in_stock(html_text)
        except Exception as e:
            print(f"⚠️  抓取失敗：{name} ({url})：{e}")
            continue

        prev_in_stock = state.get(url, {}).get("in_stock", False)

        print(f"[{name}] 目前狀態：{'有貨' if in_stock else '無貨'}（前次：{'有貨' if prev_in_stock else '無貨'}）")

        # 只有「無貨 -> 有貨」才通知，避免每次都通知或一直洗版
        if in_stock and not prev_in_stock:
            restocked.append((name, url))

        state[url] = {
            "name": name,
            "in_stock": in_stock,
            "last_checked": now_str,
        }

    save_state(state)

    if restocked:
        lines = [f"🍵 抹茶補貨通知（{now_str}）", ""]
        for name, url in restocked:
            lines.append(f"- {name}")
            lines.append(url)
        message = "\n".join(lines)
        send_line_message(message)
    else:
        print("本次沒有新的補貨項目。")


if __name__ == "__main__":
    sys.exit(main())
