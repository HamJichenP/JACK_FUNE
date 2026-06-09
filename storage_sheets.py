"""
儲存模組 (storage_sheets.py)
專責 Google Sheets API 的連線與寫入邏輯。
支援防禦性模擬模式：若 creds.json 不存在，會以模擬模式運行，避免程式崩潰。
"""

import os
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

class StorageSheets:
    def __init__(self, creds_path: str = "creds.json"):
        """
        初始化儲存模組，載入 Google 憑證。
        
        :param creds_path: 服務帳戶憑證 JSON 檔案的路徑
        """
        self.creds_path = creds_path
        self.gc = None
        self.mock_mode = False

        # 檢查憑證檔案是否存在
        if not os.path.exists(creds_path):
            print(f"[Storage][警告] 找不到憑證檔案 '{creds_path}'！")
            print("[Storage][提示] 將自動啟用【模擬模式】，所有寫入操作只會輸出至終端機。")
            self.mock_mode = True
            return

        try:
            # 設定 API 權限範圍 (Scope)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            # 載入憑證並授權與 Google API 連線
            credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
            self.gc = gspread.authorize(credentials)
            print("[Storage] 儲存模組初始化完成，已成功連接 Google Sheets 用戶端。")
        except Exception as e:
            print(f"[Storage][錯誤] 憑證授權失敗: {e}")
            print("[Storage][提示] 連線失敗，切換為【模擬模式】。")
            self.mock_mode = True
    def write_user_data(self, spreadsheet_key: str, display_name: str, roles: list[str], registered_day: str = "未指定") -> bool:
        """
        將使用者的顯示名稱 (暱稱) 與身分組資訊及報名日期寫入指定的 Google 試算表。
        
        :param spreadsheet_key: 該伺服器所設定的 Google 試算表 Key
        :param display_name: 使用者的顯示名稱 / 暱稱 (字串)
        :param roles: 使用者目前擁有的身分組名稱清單
        :param registered_day: 報名的日期 (例如 "星期六" 或 "星期日"，預設為 "未指定")
        :return: 寫入成功返回 True，失敗則返回 False
        """
        # 防禦性檢查：防範輸入為 None 或格式不正確
        if not display_name:
            print("[Storage][錯誤] 寫入失敗，使用者名字不可為空。")
            return False

        roles_str = ", ".join(roles) if roles else "無身分組"

        # 模擬模式或試算表金鑰無效時，使用模擬寫入
        if self.mock_mode or not spreadsheet_key or spreadsheet_key == "MOCK_KEY":
            print(f"[Storage][模擬寫入] 成功寫入資料 (試算表 Key: {spreadsheet_key}) -> "
                  f"名字: {display_name}, 身分組: {roles_str}, 報名日期: {registered_day}")
            return True

        # 正式連線寫入
        try:
            if not self.gc:
                print("[Storage][錯誤] 未成功與 Google Sheets 建立連線，無法寫入。")
                return False
            # 1. 開啟試算表
            spreadsheet = self.gc.open_by_key(spreadsheet_key)
            
            # 2. 取得第一個分頁 (Worksheet)
            worksheet = spreadsheet.get_worksheet(0)
            
            # 3. 準備寫入的一列資料 (名字, 身分組, 報名日期)
            row_data = [display_name, roles_str, registered_day]
            
            # 4. 新增一列到最後面
            worksheet.append_row(row_data)
            
            print(f"[Storage] 已成功將資料寫入試算表 (Key: {spreadsheet_key}) - 名字: {display_name}, 身分組: {roles_str}, 日期: {registered_day}")
            return True
        except gspread.exceptions.APIError as e:
            print(f"[Storage][錯誤] Google API 呼叫錯誤: {e}")
            return False
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"[Storage][錯誤] 找不到指定的試算表，請檢查 Key: {spreadsheet_key}")
            return False
        except Exception as e:
            print(f"[Storage][錯誤] 寫入 Google Sheets 時發生未知異常: {e}")
            return False

    def create_and_share_sheet(self, spreadsheet_title: str, user_email: str, template_key: str | None = None) -> str:
        """
        建立或複製一份試算表，並自動共享給指定的 Google Email (編輯者權限)。
        
        :param spreadsheet_title: 新試算表的標題名稱
        :param user_email: 要共享的 Google 信箱
        :param template_key: 模板試算表 Key (選填，若提供則會複製該模板)
        :return: 建立好的新試算表金鑰 ID，若失敗則回傳空字串
        """
        # 防禦性檢查：信箱與標題不能為空
        if not spreadsheet_title or not user_email:
            print("[Storage][錯誤] 建立試算表失敗，標題與使用者信箱不可為空。")
            return ""

        if self.mock_mode:
            print(f"[Storage][模擬模式] 成功模擬建立新表: 標題={spreadsheet_title}, 共享給={user_email}, 模板={template_key}")
            return "MOCK_NEW_SHEET_KEY"

        try:
            if not self.gc:
                print("[Storage][錯誤] 未成功與 Google Sheets 建立連線，無法建立。")
                return ""

            new_spreadsheet = None

            # 1. 建立或複製試算表
            if template_key:
                try:
                    print(f"[Storage] 正在自模板複製試算表 (範本 Key: {template_key})...")
                    new_spreadsheet = self.gc.copy(template_key, title=spreadsheet_title)
                    print(f"[Storage] 成功自模板複製，新金鑰 ID: {new_spreadsheet.id}")
                except Exception as e:
                    print(f"[Storage][警告] 無法自模板複製試算表 ({e})。改為建立空白試算表。")
                    new_spreadsheet = None

            # 若沒有 template_key 或複製失敗，則建立空白試算表並初始化標題
            if not new_spreadsheet:
                print(f"[Storage] 正在建立空白試算表: '{spreadsheet_title}'...")
                new_spreadsheet = self.gc.create(spreadsheet_title)
                
                # 初始化空白試算表的標題欄
                worksheet = new_spreadsheet.get_worksheet(0)
                worksheet.append_row(["名字", "身分組", "報名日期"])
                print(f"[Storage] 成功建立空白試算表並寫入標題，新金鑰 ID: {new_spreadsheet.id}")

            # 2. 自動將新試算表共享給使用者的 Google Email (給予編輯者權限)
            print(f"[Storage] 正在將試算表權限共享給 {user_email} (編輯者權限)...")
            new_spreadsheet.share(user_email, perm_type='user', role='writer', notify=True)
            print(f"[Storage] 權限共享成功！")

            return new_spreadsheet.id

        except Exception as e:
            print(f"[Storage][錯誤] 建立或共享試算表時發生異常: {e}")
            return ""
