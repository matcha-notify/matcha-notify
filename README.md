# 🍵 Marukyu Koyamaen 抹茶補貨監控機器人

自動每 15 分鐘檢查指定商品是否補貨，一補貨就用 LINE 通知你。
完全免費，跑在 GitHub Actions 上，不需要自己顧電腦或伺服器。

---

## 這是怎麼運作的

1. GitHub Actions 每 15 分鐘自動啟動一次 `check_stock.py`
2. 程式抓取每個商品頁面的 HTML，解析裡面的庫存資料（WooCommerce 內嵌的
   `data-product_variations` JSON），判斷該商品是否「至少一個規格有貨」
3. 跟上一次記錄的狀態（存在 `state.json`）比對：
   - 如果從「無貨」變成「有貨」→ 發送 LINE 通知
   - 如果狀態沒變 → 不通知（避免洗版）
4. 最新狀態寫回 `state.json` 並提交回 GitHub repo，供下次比對使用

---

## 目前監控的商品

| 商品 | 網址 |
|---|---|
| 若竹 | https://www.marukyu-koyamaen.co.jp/english/shop/products/11b1100c1 |
| 青嵐 | https://www.marukyu-koyamaen.co.jp/english/shop/products/11a1040c1 |
| 五十鈴 | https://www.marukyu-koyamaen.co.jp/english/shop/products/1191040c1 |
| 低咖啡因抹茶 | https://www.marukyu-koyamaen.co.jp/english/shop/products/1f94020c1 |

想增減商品，直接編輯 `check_stock.py` 最上面的 `PRODUCTS` 清單即可，格式：

```python
{"name": "商品中文名", "url": "商品網址"},
```

---

## 設定步驟

### 第一步：建立 LINE Messaging API 官方帳號（免費）

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)，用你的 LINE 帳號登入
2. 建立一個新的 **Provider**（名稱隨意，例如「我的抹茶通知」）
3. 在該 Provider 底下建立一個新的 **Channel**，類型選擇 **Messaging API**
   - Channel 名稱：例如「抹茶補貨通知」
   - Channel 圖示、說明可隨意填寫
   - 類別選擇任一個接近的即可（例如 Individual / Others）
4. 建立完成後，進入該 Channel 的設定頁：
   - 在 **Messaging API** 分頁裡，找到 **Channel access token**，點選「Issue」產生一組長期權杖（long-lived token），**複製起來**——這是 `LINE_CHANNEL_ACCESS_TOKEN`
   - 同一頁面上方會有一個 **QR Code**，用你的手機 LINE 掃描，把這個官方帳號加為好友（一定要加好友，機器人才推得到訊息給你）
   - 建議把「Auto-reply messages」「Greeting messages」都關閉（在 [LINE Official Account Manager](https://manager.line.biz/) 的「Response settings」裡），避免干擾

### 第二步：取得你的 User ID

有兩個簡單方法：

**方法 A（推薦）：用 LINE Official Account Manager 查看**
1. 前往 [LINE Official Account Manager](https://manager.line.biz/)，選擇你剛建立的帳號
2. 到「一對一聊天」或「聊天」功能，找到你自己加好友後傳的訊息（或系統顯示的好友資訊）
3. 部分方案可以直接在好友清單看到 User ID；如果看不到，改用方法 B

**方法 B：暫時串一個 Webhook 印出 User ID**
1. 用任何線上工具（例如 [webhook.site](https://webhook.site)）取得一個臨時網址
2. 在 LINE Developers Console 的 Channel 設定裡，把 Webhook URL 設定成這個臨時網址並啟用 Webhook
3. 用手機對著這個官方帳號傳一句話（例如「hi」）
4. 到 webhook.site 看收到的 JSON 內容，裡面 `events[0].source.userId` 就是你的 User ID（格式類似 `U4af4980629...`，開頭是大寫 U）
5. 查到之後記得把 Webhook 關掉或改回空白，這個機器人不需要接收訊息

拿到後，這就是 `LINE_USER_ID`。如果想同時通知多人，可以用逗號分隔多個 User ID，例如：`Uxxxxx,Uyyyyy`

### 第三步：把程式碼放到 GitHub

1. 在 GitHub 建立一個新的 **Private repository**（建議設為 Private，因為程式邏輯不需要公開）
2. 把這個資料夾裡的所有檔案（`check_stock.py`、`requirements.txt`、`state.json`、
   `.github/workflows/check_stock.yml`、`README.md`）上傳到這個 repo
   - 最簡單的方式：在 repo 頁面用「Add file → Upload files」直接拖曳上傳
   - 或用 git 指令：
     ```bash
     git init
     git add .
     git commit -m "init"
     git branch -M main
     git remote add origin <你的repo網址>
     git push -u origin main
     ```

### 第四步：設定 GitHub Secrets（把 LINE 金鑰安全地存起來）

1. 進入你的 GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. 點選 **New repository secret**，新增兩組：
   - Name: `LINE_CHANNEL_ACCESS_TOKEN`　Value: 貼上第一步拿到的 token
   - Name: `LINE_USER_ID`　Value: 貼上第二步拿到的 User ID

### 第五步：手動測試一次

1. 進入 repo 的 **Actions** 分頁
2. 左側選擇 **抹茶補貨監控** 這個 workflow
3. 右邊點選 **Run workflow** 按鈕，手動觸發一次
4. 跑完後點進去看 log：
   - 會顯示每個商品目前是「有貨」還是「無貨」
   - 如果 LINE 有設定成功，補貨的商品會立即收到 LINE 訊息（但因為是第一次執行，
     `state.json` 是空的，所以「有貨」的商品這次就會被當成新補貨而通知一次；
     之後就會正常運作，只在狀態改變時才通知）

之後就完全自動了，每 15 分鐘會自動檢查一次，補貨時手機就會收到 LINE 通知。

---

## 想調整檢查頻率？

編輯 `.github/workflows/check_stock.yml` 裡的這一行：

```yaml
- cron: "*/15 * * * *"
```

例如改成每 5 分鐘一次：`*/5 * * * *`
（注意：GitHub Actions 的免費排程有時會有幾分鐘延遲，這是平台限制，屬正常現象；
太頻繁的排程也可能被 GitHub 自動降頻，建議 5-15 分鐘之間即可）

---

## 常見問題

**Q: 完全沒收到 LINE 通知？**
先檢查：
1. 有沒有把 LINE 官方帳號加為好友（掃 QR Code）
2. GitHub Secrets 的 Token 和 User ID 有沒有貼對（注意不要多空白）
3. 到 Actions 分頁看該次執行的 log，裡面會清楚顯示是「沒有補貨」還是「LINE 推播失敗」

**Q: 想在自己電腦先測試，不想馬上上傳 GitHub？**
在本機安裝好 Python 之後：
```bash
pip install -r requirements.txt
export LINE_CHANNEL_ACCESS_TOKEN="你的token"
export LINE_USER_ID="你的userid"
python check_stock.py
```
（Windows 用 `set` 取代 `export`）

**Q: 網站改版導致抓不到庫存狀態怎麼辦？**
程式已內建一個備援判斷方式（用頁面文字判斷），但如果網站大改版，
可能需要重新調整 `check_stock.py` 裡 `check_in_stock()` 的解析邏輯。跟我說一聲，我可以幫你更新。
