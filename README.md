# 氣候行動學習互動網站

依照《氣候行動完整功能規格書 v2》建立，目前完成規格書第 10 節「建議推進順序」第 1～2 步：資料庫 schema ＋ LINE webhook 基本收發（含 school 參數判斷），以及每日推送＋答題＋積分/streak/徽章核心邏輯。另外額外做了 Rich Menu（基本資料／目前狀態／環保打卡／排行榜）、暱稱設定、拍照打卡送能量（老師審核制）、Alembic schema migration、GitHub Actions 排程備援、前測/中測/後測成效評估問卷（LIFF 表單）、碳足跡打卡計算器（LIFF 表單，算出「綠色分數」），以及教師後台網頁（總覽／學生列表與個別學生頁／題目分析／成效總覽／碳足跡／打卡審核）。

## 目前進度快照（2026-08-27）

- ✅ 30 題正式題庫已排定實際發送日期（見下方「每日推送」），本機／Render 兩邊資料庫同步
- ✅ 每日推送排程雙保險：服務內建 APScheduler ＋ GitHub Actions 外部 cron，已各自手動觸發驗證成功
- ✅ 成效評估問卷（LIFF 表單）：前測/中測/後測三輪，已部署上線並在真實裝置上完整測試過一輪，可正常送出
- ✅ 教師後台第一版（`/teacher`）：總覽、學生列表／個別學生頁、題目分析、成效總覽、碳足跡、打卡審核，本機已手動測試過所有頁面
- ✅ 碳足跡打卡計算器（LIFF 表單）：交通／居家能源／垃圾回收共 6 題，算出 0~100 的「綠色分數」，首次完成發能量＋解鎖徽章。改成**獨立的 LIFF App／Endpoint URL**（`CARBON_LIFF_ID`，見「碳足跡打卡計算器」一節），不再跟成效問卷共用；Rich Menu「環保打卡」按鈕也改成 URIAction 直接開啟這個 LIFF。**已部署到 Render 正式環境（Endpoint URL、`CARBON_LIFF_ID` 環境變數都已設定好），並在真實 LINE 裝置上對正式環境完整測試過，確認算分、發能量、解鎖徽章都正常**
- ✅ 教師後台審核操作紀錄：登入時填姓名（存進 `teacher_name` cookie），打卡通過／拒絕時記錄是哪位老師審核的（`eco_checkins.reviewed_by`），不是真正的帳號分權限，只是知道「誰做的」；本機已測試過中文姓名登入＋審核紀錄正確寫入
- ⏭️ **下次先做這件事**：教師後台「同一學生前中後測變化」的逐人比較圖表還沒做（見下方「尚未完成」）

## 環境設定

使用 Anaconda 建立的專屬環境 `climate-bot`（Python 3.11，位於 `D:\anaconda3\envs\climate-bot`）：

```powershell
conda activate climate-bot
pip install -r requirements.txt
Copy-Item .env.example .env
```

若尚未建立這個環境：`conda create -y -n climate-bot python=3.11`

（若你的 PowerShell 沒有設定 `conda activate`，可以改用完整路徑呼叫，例如：`D:\anaconda3\envs\climate-bot\python.exe -m uvicorn app.main:app --reload`）

編輯 `.env`，填入你的 LINE Messaging API channel secret / access token（LINE Developers Console → Messaging API 頁籤取得）。

建立/更新資料庫 schema（用 Alembic migration，見下方「資料庫 schema 變更（Alembic）」一節）：

```powershell
alembic upgrade head
```

## 建立第一間學校

```powershell
python -m scripts.seed_school "南投高中" nantou_high
```

會建立 `schools` 資料並印出該校專屬加好友連結。

## 本機啟動

```powershell
uvicorn app.main:app --reload
```

啟動後 webhook 端點為 `http://localhost:8000/webhook`。本機測試需要用 ngrok（或類似工具）把這個網址對外公開，再到 LINE Developers Console 的 Messaging API 設定頁把 Webhook URL 設成 `https://<你的ngrok網址>/webhook` 並啟用 Webhook。

## 目前功能

- `schools / students / questions / answer_logs / assessment_responses / daily_pushes` 六張表（`app/models.py`），對應規格書第 2 節設計；`daily_pushes` 是新增的推送紀錄表，用來決定下一次要推哪一題、避免同一天重複推送
- LINE webhook（`app/routers/webhook.py`）：
  - `follow` 事件：學生加好友時建立 `students` 資料；若加好友連結有帶 `school` 參數則自動歸校，否則以 Quick Reply 按鈕請學生手動選擇學校（規格書第 3 節的保險機制）
  - `postback` 事件：處理學生點選學校按鈕後的歸校，以及點選測驗選項後的答題（`answer|question_id|option_index` 格式）
  - 文字訊息：若尚未歸校則詢問學校，已歸校則回覆目前身分／能量／連續天數／徽章
- 每日推送＋答題＋積分/streak/徽章（規格書第 10 節第 2 步）：
  - `app/scheduler.py`：程式啟動時用 APScheduler 在背景排程，每天 Asia/Taipei 08:00 自動推送當日題目（`push_daily_question`）
  - `app/daily_push.py`：取出「`scheduled_date` 已到（`<=` 今天）、但還沒推送過」的下一題（`app/crud.get_next_unpushed_question`），用 LINE Broadcast API 一次推給所有好友（知識卡 + 測驗，測驗選項做成 Quick Reply 按鈕）；同一天已推送過就不會再推。沒有設定 `scheduled_date` 的題目不會被自動排程選到。用 `<=` 而不是 `==` 是為了在服務曾經漏推（例如 Render 休眠跳過某一天）時能自動補推；排定日期落在週末、或兩個 Round 之間的空檔週，當天就不會有題目符合條件，會自動跳過不推送
  - 學生點選答案後（`app/routers/webhook.py` 的 `_handle_answer_postback`）：寫入 `answer_logs`（同一題只能答一次），更新 `students.total_points / current_streak / longest_streak / badges`
  - `app/game_rules.py`：積分／連續天數／徽章／稱號的規則都集中在這裡（規格書沒有寫死細節，這是我先訂的一版合理規則，可依需求調整數值）：
    - 答對 +10、答錯 +2（給少量參與分數鼓勵持續作答）
    - 連續天數：以 Asia/Taipei 的日期為準，今天已經答過就不重複累計、昨天有答則 +1、中間斷過則歸 1 重新開始
    - 故事線：學生是「氣候行動守護者」，依累積能量從 🌱 幼苗守護者 → 🌿 綠芽行動家 → 🌳 森林守護者 → 🌍 地球衛士 → ⭐ 氣候英雄 逐步升級，每個階段都有對應的故事文案
    - 徽章：首次答題／首次答對／連續 3、7、30 天／累計答對 10、30 題／累積能量達 300，達成條件就解鎖，回覆訊息會附上「解鎖新徽章」提示
  - 手動測試用：`POST /admin/push-daily`（帶 `X-Admin-Key`，可加 `?force=true` 略過「今天已推送過」的檢查）可以不用等到 08:00 就手動觸發一次推送
  - `python -m scripts.seed_question` 可以建立一筆測試題目，方便本機測試整套流程
  - `python -m scripts.seed_questions_from_csv <csv路徑>` 用來批次匯入正式題庫，CSV 欄位為 `knowledge_card_text, question_text, option_a, option_b, option_c, option_d, correct_option, topic_tag, scheduled_date`（`correct_option` 填選項文字本身；`scheduled_date` 就是題目實際會被推送的日期，見上方「每日推送」小節）；已存在相同 `question_text` 的題目會自動跳過，可重複執行
  - **Render 免費方案休眠備援**：`.github/workflows/daily-push.yml` 用 GitHub Actions 排程（`cron: "0 0 * * *"`，即 Asia/Taipei 08:00）每天呼叫一次 `/admin/push-daily`。這個 HTTP 請求本身會把休眠中的 Render 服務叫醒，跟服務內建的 APScheduler 是雙保險：`push_daily_question` 有「今天已經推送過就跳過」的檢查，兩邊前後都觸發到也不會重複推送。需要在 GitHub repo 的 **Settings → Secrets and variables → Actions** 新增一個 secret：`ADMIN_API_KEY`，值要跟 Render 上的 `ADMIN_API_KEY` 一致（之後如果在 Render 換了 key，這裡也要跟著更新，否則 workflow 會收到 401）。GitHub Actions 的排程時間不保證精準觸發，尖峰時段可能延遲，但對「每天推 1 題」這種用途影響不大

## Rich Menu ＋ 暱稱 ＋ 環保打卡 ＋ 排行榜

- `python -m scripts.setup_rich_menu`：產生一張 2500x1686、2x2 四宮格的選單圖片（`Pillow` 畫的，用 Windows 內建的微軟正黑體 `msjh.ttc`），建立 LINE Rich Menu、上傳圖片、設成所有好友的預設選單。重複執行會先刪除同名舊選單再建新的，之後要改文案/版面直接改 `scripts/setup_rich_menu.py` 的 `CELLS` 重跑即可。三個按鈕是 `menu|xxx` 格式的 PostbackAction，由 `app/routers/webhook.py` 的 `_handle_menu_postback` 處理；`環保打卡` 這格改用 URIAction，點下去不經過 webhook，直接開啟碳足跡打卡計算器的 LIFF（`app/carbon_footprint.build_carbon_footprint_url()`，見下方「碳足跡打卡計算器」一節）：
  - `基本資料`：回覆就讀學校
  - `目前狀態`：回覆身分／能量／連續天數／徽章（跟文字訊息查詢共用 `_status_text`）
  - `環保打卡`：直接開啟碳足跡打卡計算器 LIFF（URIAction，非 postback）
  - `排行榜`：回覆該校前 10 名（暱稱＋能量）
- 暱稱設定：學生選完學校後，下一則文字訊息會被當成暱稱存起來（`students.nickname`），設定前選單功能會提示要先設定暱稱。暱稱只存在我們資料庫，跟 LINE 顯示名稱無關，目的是排行榜不曝露 LINE 身份。
- **拍照打卡**（`app/eco_checkin.py` + 學生傳圖片訊息，跟碳足跡計算器是分開的機制，見下方「碳足跡打卡計算器」一節的說明）：學生傳照片給 bot → 用 LINE Blob API 下載原圖 → 用 Pillow 壓縮成長邊 ≤1000px、JPEG quality 70 → 存進新的 `eco_checkins` 表（`status="pending"`）。這個機制目前**不再掛在 Rich Menu 按鈕上**（`環保打卡` 格子已改成開啟碳足跡計算器），純粹靠學生自己傳照片觸發，功能本身不受影響。**設計上刻意先審核再發能量**：
  - `GET /admin/checkins?status=pending`（帶 `X-Admin-Key`）：列出待審核打卡，含 `image_url` 可直接開圖
  - `GET /admin/checkins/{id}/image`：回傳圖片本身，因為要給老師直接在瀏覽器開連結看照片，所以這個端點例外允許用網址參數 `?admin_key=` 代替 Header（其他 admin 端點都只認 Header）——僅限這個用途，網址會留在瀏覽器歷史/伺服器 log，不要外流
  - `POST /admin/checkins/{id}/approve`（可帶 `?points=`，預設 `game_rules.ECO_CHECKIN_POINTS=15`）：發放能量、檢查是否解鎖 `eco_first`／`eco_10` 徽章，並用 LINE Push Message 通知學生
  - `POST /admin/checkins/{id}/reject`：標記未通過，Push 通知學生可以再試一次
  - 打卡目前**不影響**每日答題的連續天數（streak 只跟每日測驗有關）

## 教師後台

網頁介面，路徑 `/teacher`（例如本機 `http://localhost:8000/teacher`，或部署後 `https://climate-action-bot.onrender.com/teacher`），程式在 `app/routers/teacher.py`（路由與畫面）＋ `app/teacher_dashboard.py`（統計彙整邏輯，讓路由檔只處理請求/回應）＋ `app/templates/teacher/`（Jinja2 樣板）。

- **登入方式**：沿用既有的 `ADMIN_API_KEY`（跟 `/admin` 系列 JSON API 共用同一把金鑰），不是另外的帳號系統，所有老師權限相同。`/teacher/login` 頁面輸入金鑰後，正確的話會存進一個 httpOnly cookie（`teacher_key`，效期 30 天），之後每個 `/teacher/*` 頁面都是看這個 cookie 判斷是否已登入，不用像 `/admin` API 那樣每次手動帶 `X-Admin-Key` Header。`/teacher/logout` 清掉 cookie。
- **姓名標記（不是權限控管）**：登入時除了金鑰，還要填一個姓名，存進另一個 httpOnly cookie（`teacher_name`）。這個姓名**不驗證身份**、純粹讓審核打卡時知道「是誰做的」——`eco_checkins` 表新增了 `reviewed_by` 欄位，通過／拒絕打卡時會把目前登入的姓名存進去，之後在「打卡審核」列表跟個別學生頁都看得到是哪位老師審核的。cookie value 只能放 latin-1 字元（HTTP header 限制），中文姓名存之前用 `urllib.parse.quote` 編碼、讀出來時 `unquote` 解碼（`app/routers/teacher.py` 的 `_teacher_name()`），直接塞原始中文字串進 `set_cookie` 會讓伺服器噴 500。
- **總覽**（`/teacher`）：學生總數、待審核打卡數、前測/中測/後測問卷已回收份數，以及各校學生數／已設定暱稱人數／平均能量。
- **學生列表 ＋ 個別學生頁**（`/teacher/students`、`/teacher/students/{id}`）：列表可用學校篩選；個別學生頁彙整這位學生的能量／連續天數／稱號／徽章、完整答題紀錄、環保打卡紀錄（含照片連結）、以及每一輪成效評估問卷的完整回覆（選項代碼會轉回中文顯示文字）。
- **題目分析**（`/teacher/questions`）：每題的作答人數、答對率，以及每個選項各自被選了幾次（可以看出常見的錯誤選項）。
- **成效總覽**（`/teacher/assessment`）：前測/中測/後測三輪各自的回收份數、量表題（1~5 分）平均分數，以及後測開放式回饋（`most_memorable`）的原文列表。目前是各輪獨立呈現平均值，還沒有做「同一學生前中後測變化」的逐人比較圖，之後有需要可以再加。
- **打卡審核**（`/teacher/checkins`）：跟原本 `/admin/checkins` 系列 JSON API 背後邏輯相同（`app/eco_checkin.py`），差別是這裡有網頁介面可以直接看照片縮圖、按按鈕通過／拒絕，不用再自己組 HTTP 請求；審核結果一樣會用 LINE Push Message 通知學生。圖片端點 `/teacher/checkins/{id}/image` 只認 cookie，不像 `/admin/checkins/{id}/image` 那樣額外接受網址參數帶 key（教師後台有登入 session 了，不需要那個為了方便瀏覽器開圖而設計的例外，也比較不會讓金鑰留在瀏覽器歷史）。
- 新增了 `python-multipart` 依賴（`requirements.txt`），FastAPI 的 `Form(...)`（登入表單）需要它才能解析。

## 管理用 API（暫時性，用於雲端環境沒有 Shell 可下指令時建立學校）

`POST /admin/schools`、`GET /admin/schools`，需帶 Header `X-Admin-Key: <ADMIN_API_KEY>`。範例：

```
POST https://climate-action-bot.onrender.com/admin/schools
Header: X-Admin-Key: <你的 ADMIN_API_KEY>
Body: {"school_name": "南投高中", "join_link_code": "nantou_high"}
```

之後有正式教師後台可以管理學校資料時，這個端點可以移除。

## 部署到 Render（測試用）

專案根目錄已附 `render.yaml`，可用 Render 的 Blueprint 功能一鍵建立服務：

1. 到 [Render Dashboard](https://dashboard.render.com) → New → Blueprint，選這個 GitHub repo
2. Render 會讀取 `render.yaml` 自動建立 Web Service，建置指令與啟動指令都已寫好
3. 部署頁面會要求填入標記 `sync: false` 的環境變數：`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`（值同你本機 `.env` 內的內容）
4. 部署完成後會拿到一個固定網址，例如 `https://climate-action-bot.onrender.com`
5. 到 LINE Developers Console → Messaging API 頁籤，把 Webhook URL 設成 `https://climate-action-bot.onrender.com/webhook`，按 Verify 確認成功，並開啟「Use webhook」

**注意**：`render.yaml` 已改用 Render 提供的免費 PostgreSQL（`databases` 區塊，`DATABASE_URL` 會自動指到這個資料庫），資料庫本身跟 Web Service 分開，服務休眠喚醒不會清空資料。但 Render 免費 PostgreSQL 有 90 天期限，到期需要升級或重建。免費方案 Web Service 閒置一段時間會休眠，第一個請求可能要等數十秒喚醒，LINE 平台通常會重試 webhook，不影響功能但體驗上第一次互動可能稍慢。

（本專案一開始用本機 SQLite 起步是延續規格書第 7 節的建議，但實測發現 Render 免費方案的 Web Service 檔案系統在服務休眠喚醒時會重置，SQLite 檔案跟著消失，所以提早換成 PostgreSQL；本機開發若不想裝 PostgreSQL，`DATABASE_URL` 留空或設回 `sqlite:///./climate_action.db` 仍可用 SQLite。）

**踩過的坑：`render.yaml` 新增環境變數不會自動同步到已經建立好的服務。** 加碳足跡計算器的 `CARBON_LIFF_ID` 時，以為改完 `render.yaml`（見上方 `envVars`）push 上去、Render 重新部署就會自動帶上這個新的環境變數，結果部署完 Render 上這個值還是空的——`render.yaml` 的 Blueprint 同步似乎只在**第一次建立服務**時把 `envVars` 套進去，之後 push 新增的變數要自己到 Render Dashboard → 該服務 → **Environment** 分頁手動加一次（存檔後會自動觸發重新部署）。之後如果又要加新的環境變數，記得除了改 `render.yaml`（讓文件跟未來全新部署保持一致）之外，也要手動去 Dashboard 補一次。

## 成效評估問卷（LIFF 表單）

前測（baseline）／中測（midterm）／後測（posttest）三輪問卷，題目改編自使用者提供的「青少年氣候行為調查」（教育部青年發展署 Young 飛計畫），內容是自我覺察／態度／行為／動機題（沒有標準答案），跟每日測驗的客觀對錯（`answer_logs`）是分開的兩種資料。

- `app/assessment_questions.py`：題目定義（`QUESTION_DEFS`）跟每輪要問哪些題（`ROUNDS`）都在這裡集中管理，改題目或調整輪次內容只需要改這個檔案。核心題三輪都問（可以畫出同一個學生的前中後變化曲線）；年級/性別只在前測問一次（存進 `students.grade` / `students.gender`，不會每輪都問）；障礙/激勵題前測中測問「介入前」版本，後測換成「介入後」回顧版本；後測額外加課程整體滿意度、自評成長、開放式回饋
- `app/templates/assessment.html` + `app/routers/liff.py`：`GET /liff/assessment?round=baseline|midterm|posttest` 用 Jinja2 依 `assessment_questions.py` 的定義動態產生表單頁面，內嵌 LIFF SDK；`POST /liff/assessment/submit` 收表單送出的答案
- **身份識別但不顯示**：表單本身不問姓名/帳號（維持匿名體感），但後端會用 `liff.getAccessToken()` 拿到的 access token 呼叫 LINE 的 `GET /v2/profile`（`app/line_client.get_liff_user_id`）換回經過驗證的 `userId`，藉此對應到 `students` 表裡的學生——**刻意不信任前端回傳的任何身份欄位**，因為 `liff.getProfile()` 這類前端呼叫的結果理論上可能被竄改，只有後端自己拿 token 去跟 LINE 換到的 userId 才可信
- 同一個學生同一輪次重複送出，會覆蓋掉舊答案（`crud.upsert_assessment_response`，靠 `assessment_responses` 的 `(student_id, assessment_round)` unique constraint 判斷）
- 推播問卷連結：`POST /admin/push-assessment?round=baseline`（帶 `X-Admin-Key`）廣播問卷連結給所有好友。跟每日測驗不同，前測/中測/後測只知道「哪一週」要發（見下方行程），沒有精確到哪一天，所以做成手動觸發，由管理員自己挑那一週裡的哪一天發送
- **LIFF App 設定**：LIFF App 是掛在獨立的 LINE Login channel 底下（LINE 現在不允許 LIFF 直接掛在 Messaging API channel），LIFF ID 存在 `.env` 的 `LIFF_ID`。LIFF App 的 **Endpoint URL** 要設成 `https://climate-action-bot.onrender.com/liff/assessment`（本機測試則設本機的 ngrok 網址 + `/liff/assessment`）
- **`round` 這個 query 參數是前端處理的，不是後端**：LINE 從 `https://liff.line.me/{LIFF_ID}?round=baseline` 轉址過來時，不保證第一次打到後端的請求就帶著 `?round=baseline`（LINE 會先把它編碼進 `liff.state`，等瀏覽器裡的 `liff.init()` 執行完才會把網址補回正確的 query string）。所以 `GET /liff/assessment` 不吃 `round` 參數、一律回同一個空殼頁面；等 JS 端 `liff.init()` 完成後才從 `location.search` 讀 `round`，再打 `GET /liff/assessment/questions?round=xxx`（回傳題目 JSON）動態把表單畫出來。踩過這個坑：一開始讓後端直接用 `round: str` 當必填 query 參數、伺服器端 Jinja2 直接渲染，結果 LIFF 開出來直接 422 缺參數

## 碳足跡打卡計算器（LIFF 表單）

交通方式／居家能源／垃圾與資源回收三大類共 6 題單選，每題依生活習慣打 0~3 分，加總換算成 0~100 的「綠色分數」，對應一個等級與故事文案（風格比照 `app/game_rules.py` 的稱號設計）。**刻意不做成精確的公斤 CO2e 排放量估算**——那需要具體、有公信力的排放係數，容易被質疑不準確——用意是讓學生反思生活習慣、看到自己的努力方向，不是要精算數字。跟拍照打卡（`app/eco_checkin.py`）是分開的兩個機制：打卡是單次行動記錄、需要老師審核；碳足跡計算器是一次性的生活習慣自評，送出立即算分不用審核。

- `app/carbon_footprint.py`：題目定義（`QUESTIONS`，含每個選項的分數）、算分邏輯（`score_answers` / `green_score` / `current_level`）、首次完成的獎勵邏輯（`award_first_completion`）都集中在這裡
- **獨立的 LIFF App／Endpoint URL**：另外申請了一個獨立的 LINE Login channel／LIFF App，LIFF ID 存在 `.env` 的 `CARBON_LIFF_ID`，對應 `GET /liff/carbon-footprint`（Endpoint URL 要設成 `https://climate-action-bot.onrender.com/liff/carbon-footprint`）。跟成效評估問卷（`/liff/assessment`、`LIFF_ID`）是兩個完全分開的 LIFF App，改任一邊的 Endpoint URL（例如本機測試接 ngrok/cloudflared tunnel）都不會影響另一邊。頁面模板仍共用 `app/templates/assessment.html` 這個殼子，但不再靠網址 query string 分流，而是伺服器端渲染時直接傳入 `mode`（`"assessment"` 或 `"carbon_footprint"`），前端 JS 讀這個值決定要打 `/liff/carbon-footprint/questions` 還是 `/liff/assessment/questions`，畫面也會改成算分結果（分數圓圈＋等級＋首次完成的獎勵提示）而不是單純的「已送出」訊息
- 身份驗證方式跟成效評估問卷完全一樣：後端用 access token 換驗證過的 LINE `userId`，不信任前端回報的任何身份欄位
- **可以重複填寫**：`crud.upsert_carbon_footprint_response` 每位學生只留一筆最新結果，重填會覆蓋分數重新計算；但只有**第一次**送出才會發能量（`game_rules.CARBON_CALC_POINTS`，目前 20）、解鎖「🧮 碳足跡先鋒」徽章，重填不會重複發獎勵
- 推播計算器連結：`POST /admin/push-carbon-footprint`（帶 `X-Admin-Key`）廣播給所有好友，教師後台「碳足跡」頁面（`/teacher/carbon-footprint`）也有對應按鈕，不用開終端機
- 老師可以在教師後台「碳足跡」頁面看整體平均分數／各等級人數分布／全部學生的分數列表，或在個別學生頁看單一學生的逐題作答內容
- **已在真實 LINE 裝置上完整測試過**（第一次送出正確發能量+解鎖徽章、重新填寫正確只更新分數不重複發獎勵），已部署到 Render 正式環境

## 尚未完成（規格書第 10 節後續步驟）

1. 教師後台目前只有第一版：還沒有「同一學生前中後測變化」的逐人比較圖表。帳號系統維持共用 `ADMIN_API_KEY` ＋ 登入時填姓名標記操作紀錄（見上方「教師後台」一節），這是刻意的設計決定（不需要分權限管理），如果之後真的需要老師各自獨立登入、分權限，需要另外設計
2. 目前 30 題正式題庫已依實際行程排定 `scheduled_date`：9/14（一）那週是前測週（推播成效評估問卷，見上方「成效評估問卷」章節，`POST /admin/push-assessment?round=baseline` 手動觸發），不推送每日測驗題目；Round1 為 9/21（一）起連續 3 週的週一到週五（共 15 天，9/21~10/9，中間沒有空檔週）→ question_id 2~16；Round2 為 10/12（一）起同樣連續 3 週的週一到週五（共 15 天，10/12~10/30）→ question_id 17~31，10/12 當天同步發送中測問卷（`round=midterm`）；11/3 那週為後測（`round=posttest`）。Round2 結束後每日測驗題庫即用完，`push_daily_question` 會記 log（info 等級）、不會再推送，之後如果要延伸內容需要追加新題目並設定 `scheduled_date`（用 `scripts/seed_questions_from_csv.py` 匯入即可）

## 資料庫 schema 變更（Alembic）

專案已導入 [Alembic](https://alembic.sqlalchemy.org/) 管理資料庫 schema，取代原本 `Base.metadata.create_all()` 的作法。

> **背景**：先前 `students` 表新增 `nickname` 欄位時，因為 `create_all()` 只會建立「還不存在」的新表、**不會**幫已存在的表補欄位，導致本機 schema 跟 Render 上（已有真實資料的）Postgres 產生落差，上線後查詢 `students` 會直接噴 `UndefinedColumn` 錯誤。改用 Alembic 之後，每次改 `app/models.py` 都會產生一支對應的 migration script，用 `alembic upgrade head` 套用，本機、Render 兩邊的 schema 才會確實同步。

**修改 schema 的流程**：

1. 改 `app/models.py`
2. 產生 migration：`alembic revision --autogenerate -m "說明這次改了什麼"`（會依目前 DB 與 model 的差異，在 `alembic/versions/` 產生一支新檔案，**務必打開檢查**產生的內容是否符合預期，autogenerate 不是 100% 準確）
3. 本機套用：`alembic upgrade head`
4. commit migration 檔案一起 push
5. Render 部署時 `startCommand`（見 `render.yaml`）會自動先跑 `alembic upgrade head` 再啟動服務，正式環境的 schema 會跟著更新，不用手動操作

`alembic/env.py` 已設定成沿用 `app.config.settings.database_url`，本機 sqlite、Render Postgres 都不用另外調整連線設定。

## 關於加好友連結帶入學校參數

LINE 官方並未正式保證一般「加好友連結」（`https://line.me/R/ti/p/@BotID`）能把自訂查詢參數透過 `follow` webhook 事件傳回後端——這點規格書第 3 節也有提到，所以本專案把「加好友後跳出按鈕選單讓學生手動選學校」做成主要、可靠的機制，`school` 參數的自動判斷則是加分項（讀不到也不影響流程）。之後如果要做到「連結一點就自動歸校、完全不用手動選」，建議改用每校專屬的 LIFF 頁面作為入口，這是後續可以再討論的方向。
