"""
專案進入點 (main.py)
負責載入設定、初始化各個模組，並啟動 Discord 機器人。
"""

import os
import sys
import discord
from dotenv import load_dotenv
from core_bot import DiscordBot
from storage_sheets import StorageSheets

def main():
    print("==================================================")
    print("           MyDiscordBot 啟動程序開始              ")
    print("==================================================")

    # 1. 載入 .env 檔案中的環境變數
    # load_dotenv() 會自動尋找當前目錄底下的 .env 檔案，並將其變數載入到系統環境變數中
    load_dotenv()

    # 2. 讀取並驗證必要環境變數 (防禦性設計)
    discord_token = os.getenv("DISCORD_TOKEN")

    # 檢查 Token 是否存在或是否仍為預設的 placeholder
    if not discord_token or discord_token == "your_discord_token_here":
        print("[系統錯誤] 找不到有效的 Discord Token！")
        print("請確認專案目錄下的 `.env` 檔案中是否已正確填入 `DISCORD_TOKEN`。")
        print("程式即將關閉。")
        sys.exit(1)

    # 3. 初始化儲存模組與機器人
    try:
        # 初始化儲存模組，會自動尋找同目錄下的 creds.json
        storage = StorageSheets(creds_path="creds.json")
        
        # 初始化機器人，將儲存模組傳遞進去 (試算表金鑰與身分組已改為在各伺服器獨立設定)
        bot = DiscordBot(storage_client=storage)
        
    except Exception as e:
        print(f"[系統錯誤] 模組初始化失敗: {e}")
        sys.exit(1)

    # 4. 啟動 Discord 機器人
    try:
        print("[系統] 正在嘗試連線至 Discord...")
        bot.run(discord_token)
    except discord.errors.LoginFailure:
        print("[系統錯誤] 登入失敗！請確認你的 `DISCORD_TOKEN` 是否正確。")
    except Exception as e:
        print(f"[系統錯誤] 機器人執行時發生異常: {e}")

if __name__ == "__main__":
    main()
