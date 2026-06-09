# 專案上下文文件 (Project Context for AI)

## 👤 使用者狀態 (User Profile)
* **程式經驗**：Python 零經驗初學者，將此專案作為 Python 入門練習。
* **開發環境**：Windows 系統，使用 VS Code 編輯器。
* **AI 角色設定**：扮演「程式夥伴」，保持積極、耐心、支持的語氣。使用清晰簡單的文字，專注於程式碼開發，提供詳盡的註解與模組化的架構。

## 🎯 專案目標 (Project Goals)
* **用途**：建立一個 Discord 機器人 (Bot)，代號為「百業戰報名」。
* **核心功能**：
  1. 監聽 Discord 聊天室中的特定「表情符號 (Emoji)」互動。
  2. 當使用者點擊表情符號時，抓取該使用者的 `User ID` 以及其對應的 `身分組標籤 (Roles)`。
  3. 新增過濾機制：可透過設定檔篩選特定的身分組白名單（若未設定則抓取全部）。
  4. 將抓取到的資料，自動導入並寫入到指定的 Google 試算表 (Google Sheets) 欄位中。
* **未來擴充目標**：未來計畫將資料儲存端從 Google 試算表替換為 Web 架構（如關聯式資料庫與網頁後台）。

## 🏗️ 系統架構與實體路徑 (Architecture & Directory)
* **專案實體路徑**：`C:\Users\User\Jack\DC`
* **資料夾結構**：
  ```text
  DC/
  ├── .venv/               # Python 虛擬環境資料夾
  ├── .env                 # 存放 Discord Token 與 Google API 憑證 (絕不寫死在程式碼中)
  ├── requirements.txt     # 記錄相依套件 (discord.py, python-dotenv, gspread)
  ├── main.py              # 程式進入點：負責載入環境變數、初始化模組與啟動機器人
  ├── core_bot.py          # 核心互動邏輯：專責 Discord 互動 (監聽表情符號、白名單過濾身分組)
  ├── storage_sheets.py    # 儲存模組：專責 Google Sheets 串接與寫入邏輯
  └── project_context.md   # 本專案上下文文件 (提供給 AI 助手快速讀取)
  ```

## ⚙️ 環境變數設定 (.env)
* **DISCORD_TOKEN**：機器人登入 Token (已從 Discord Developer Portal 取得並設定)。
* **GOOGLE_SHEETS_KEY**：Google 試算表 Key (待設定)。
* **TARGET_ROLES**：要篩選的特定身分組白名單，以半形逗號分開。例如：`管理員,組長,VIP`。

## ⏳ 目前進度 (Current Status)
1. **已完成**：
   * 在 `C:\Users\User\Jack\DC` 建立完整專案結構與骨架。
   * 成功建置 Python 虛擬環境 (`.venv`) 並安裝 `discord.py`、`python-dotenv` 與 `gspread`。
   * 完成 Discord Developer Portal 的機器人設置，並開啟 `Server Members Intent` 與 `Message Content Intent` 特權意圖。
   * 完成機器人「百業戰報名」的伺服器邀請，順利加入測試伺服器。
   * 完成 `main.py` 與 `core_bot.py` 的基礎程式碼，機器人已能成功連線並回覆 `!ping`。
   * 完成「特定身分組白名單過濾」功能，並與 `.env` 連動。
2. **待進行**：
   * 申請 Google Cloud 專案並開通 Google Sheets API 與 Google Drive API，取得憑證 JSON 檔案。
   * 實作 `storage_sheets.py`，串接實際的寫入邏輯。

## ➡️ 下一步任務 (Next Action)
1. **設定 Google Cloud 憑證**：
   * 指導使用者前往 Google Cloud Console 建立專案。
   * 啟用 Google Sheets API 及 Google Drive API。
   * 建立「服務帳戶 (Service Account)」，並下載其 JSON 憑證金鑰檔，命名為 `creds.json` 放入專案目錄。
2. **共用試算表權限**：
   * 指導使用者建立一個 Google 試算表，並將「服務帳戶的 Email」設為該試算表的共用協作者（權限為編輯者）。
3. **實作 Google Sheets 寫入邏輯**：
   * 撰寫 `storage_sheets.py`，使用 `gspread` 讀取 `creds.json`，完成對 Google 試算表的資料寫入。
