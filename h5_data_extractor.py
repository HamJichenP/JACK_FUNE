import sys
import json
import requests
from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

# 官方登入與 API 配置
LOGIN_URL = "https://www.wherewindsmeetgame.com/m/2025h5sjgj/tw/"
API_URL = "https://s2.easebar.com/78ae9d90792a3e9b/role/roleInfo"

# 模擬行動裝置 User-Agent 以加載手機版網頁
MOBILE_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("《燕雲十六聲》官方 H5 數據擷取工具")
        
        # 模擬手機版尺寸加載 H5 頁面
        self.resize(450, 800)
        
        # 1. 設置行動裝置專用的 User-Agent
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent(MOBILE_USER_AGENT)
        
        # 2. 建立網頁檢視器
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(LOGIN_URL))
        
        # 3. 憑證與憑據暫存器
        self.intercepted_cookies = {}
        self.intercepted_token = None
        self.intercepted_storage_key = None
        
        # 4. 底層監聽 CookieStore (解決 HttpOnly 無法透過 JS 獲取的問題)
        self.cookie_store = profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self.on_cookie_added)
        
        # 5. 輪詢檢查 localStorage 與 sessionStorage
        self.timer = QTimer(self)
        self.timer.setInterval(1000)  # 每秒檢查一次
        self.timer.timeout.connect(self.check_local_storage)
        self.timer.start()
        
        # 視窗排版
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)
        container.setLayout(layout)
        self.setCentralWidget(container)

    def on_cookie_added(self, cookie):
        """底層 Cookie 新增回呼"""
        name = cookie.name().data().decode("utf-8", errors="ignore")
        value = cookie.value().data().decode("utf-8", errors="ignore")
        
        # 儲存 Cookie 以利後台 requests 調用
        self.intercepted_cookies[name] = value
        
        # 部分系統會直接在 Cookie 中放入授權資訊 (如 access_token, mpay_token)
        if name in ["access_token", "mpay_token", "sdk_token"]:
            print(f"✨ 成功從 Cookie 欄位 [{name}] 擷取到認證憑證！")
            self.intercepted_token = value
            self.close_and_stop()

    def check_local_storage(self):
        """注入 JS 輪詢 local/session storage，搜尋潛在 Token 欄位"""
        js_script = """
        (function() {
            const possibleKeys = [
                'token', 'access_token', 'accessToken', 'sdk_token', 
                'mpay_token', 'authorization', 'login_token', 'mpay_sdk_token'
            ];
            for (let key of possibleKeys) {
                let val = localStorage.getItem(key) || sessionStorage.getItem(key);
                if (val) {
                    return JSON.stringify({key: key, value: val});
                }
            }
            return null;
        })();
        """
        self.browser.page().runJavaScript(js_script, self.on_js_result)

    def on_js_result(self, result):
        """解析 JS 注入的執行結果"""
        if result:
            try:
                data = json.loads(result)
                token = data.get("value")
                key = data.get("key")
                if token:
                    print(f"✨ 成功從 LocalStorage [{key}] 攔截到認證 Token！")
                    self.intercepted_token = token
                    self.intercepted_storage_key = key
                    self.close_and_stop()
            except Exception as e:
                print(f"[警告] 解析 LocalStorage 傳回值時出錯: {e}")

    def close_and_stop(self):
        """停止定時器並關閉 PyQt 視窗"""
        self.timer.stop()
        self.close()


def fetch_role_info(token, cookies, storage_key):
    """
    使用 requests 模擬 GET 請求獲取角色數據（根據 HAR 範例，此 API 採用 GET 方法）
    """
    print("\n🚀 開始向官方私有 API 發送數據擷取請求...")
    
    # 建構 API 請求標頭
    headers = {
        "User-Agent": MOBILE_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.wherewindsmeetgame.com",
        "Referer": "https://www.wherewindsmeetgame.com/m/2025h5sjgj/tw/"
    }
    
    # 根據 HAR 範例，Token 是放入 headers 的 access_token 欄位
    if token:
        headers["access_token"] = token
    elif cookies.get("access_token"):
        headers["access_token"] = cookies.get("access_token")
    elif cookies.get("mpay_token"):
        headers["access_token"] = cookies.get("mpay_token")

    try:
        # 發送 GET 請求 (GET 不需傳入 json body)
        response = requests.get(API_URL, headers=headers, cookies=cookies, timeout=10)
        
        # 處理 401 憑證失效
        if response.status_code == 401:
            print("❌ 錯誤：認證 Token 已失效或過期 (401 Unauthorized)。請重新執行登入驗證。")
            return
            
        response.raise_for_status()
        
        data = response.json()
        print("📥 數據擷取成功！開始解析角色資料：")
        
        # 取得主資料節點
        role_data = data.get("data", {}) if "data" in data else data
        
        # 門派對照表 (依據燕雲十六聲流派，若未知則輸出數字)
        school_names = {
            1: "無門派/散人",
            2: "鐵衣",
            3: "醉花陰",
            4: "梨花槍",
            5: "孤鷹",
            6: "神箭/流派六"  # 根據 HAR 中 school = 6 進行推斷
        }
        school_id = role_data.get("school")
        school_name = school_names.get(school_id, f"流派 {school_id}")

        # 在線時間轉換 (秒 -> 小時)
        online_seconds = role_data.get("onlineTime", 0)
        online_hours = round(online_seconds / 3600, 1) if online_seconds else 0
        
        print("=" * 50)
        print(f"📊 【燕雲十六聲】官方 H5 數據擷取結果")
        print("-" * 50)
        print(f"👤 角色名稱: {role_data.get('roleName', '未知')}")
        print(f"🆔 角色 ID  : {role_data.get('roleId', '未知')}")
        print(f"🔹 角色等級 (level): {role_data.get('level', '未知')}")
        print(f"🔹 流派門派 (school): {school_name}")
        print(f"🔹 風尚值 (fashionScore): {role_data.get('fashionScore', '未知')}")
        print(f"🔹 武學總修為 (xiuWeiKungFu): {role_data.get('xiuWeiKungFu', '未知')}")
        print(f"🔹 最大修為武學 (maxXiuWeiKungFu): {role_data.get('maxXiuWeiKungFu', '無')}")
        print(f"⏰ 累計在線時長: {online_hours} 小時")
        print("-" * 50)
        
        # 裝備字典解析 (wearEquipsDetailed - HAR 格式為 Dict)
        wear_equips = role_data.get("wearEquipsDetailed", {})
        print(f"🔹 穿戴裝備詳情 ({len(wear_equips)} 件)：")
        if not wear_equips:
            print("   （無裝備資訊）")
        else:
            # 裝備部位 ID 對照表
            slot_names = {
                "1": "主武器",
                "2": "副武器",
                "3": "頭部",
                "4": "上衣",
                "5": "下裝",
                "8": "鞋子",
                "9": "項鍊",
                "10": "戒指",
                "11": "護腕",
                "21": "暗器",
                "105": "馬具"
            }
            for idx, (slot_id, equip_info) in enumerate(wear_equips.items(), 1):
                if not isinstance(equip_info, dict):
                    continue
                equip_no = equip_info.get("no", "未知代碼")
                ex_vo = equip_info.get("exVo") or {}
                durability = ex_vo.get("durability", "無") if ex_vo else "無"
                suffix = ex_vo.get("suffix", "無") if ex_vo else "無"
                
                slot_name = slot_names.get(str(slot_id), f"部位 {slot_id}")
                print(f"   [{idx}] 部位: {slot_name:<6} | 裝備代碼 (no): {equip_no:<8} | 耐久度: {durability:<3} | 後綴品質: {suffix}")
        print("=" * 50)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ 錯誤：401 認證失敗，請嘗試重新開啟工具登入驗證。")
        else:
            print(f"❌ 官方 API 回傳 HTTP 錯誤：{e}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 網路傳輸異常（可能遭防火牆阻擋）：{e}")
    except Exception as e:
        print(f"❌ 資料解析失敗或格式不符：{e}")
        print(f"原始 JSON 數據回傳如下：\n{json.dumps(data, indent=4, ensure_ascii=False)}")


def main():
    # 建立 PyQt5 應用程式
    app = QApplication(sys.argv)
    
    print("📢 正在開啟《燕雲十六聲》官方 H5 登入視窗...")
    print("💡 請在彈出的視窗中手動進行登入（並通過圖形驗證碼）。")
    print("💡 登入成功後，視窗會自動關閉並於背景擷取資料。")
    
    window = LoginWindow()
    window.show()
    
    # 執行 GUI 主迴圈
    app.exec_()
    
    # 視窗關閉後，檢查是否成功獲取 Token 憑證
    if window.intercepted_token or window.intercepted_cookies:
        fetch_role_info(
            token=window.intercepted_token,
            cookies=window.intercepted_cookies,
            storage_key=window.intercepted_storage_key
        )
    else:
        print("\n👋 程式已關閉。未偵測到任何登入憑據。")

if __name__ == "__main__":
    main()
