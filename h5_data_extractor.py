import sys
import json
import requests
from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

# 繁體中文翻譯對照表
TRANSLATION_MAP = {
    "schools": {
        1: "天泉",
        2: "梨園",
        3: "狂瀾",
        4: "青溪",
        5: "孤雲",
        6: "三更天",
        8: "文津館",
        10: "無心谷",
        11: "九流門",
        12: "醉花陰",
        13: "墨山道",
        100: "無門無派"
    },
    "kongfus": {
        10101: "積矩九劍",
        10102: "無名劍法",
        10201: "九曲驚神槍",
        10301: "明川藥典",
        10302: "青山執筆",
        10202: "無名槍法",
        20501: "泥犁三垢",
        20401: "嗟夫刀法",
        20103: "八方風雷槍",
        20601: "九重春色",
        20701: "粟子遊塵",
        20602: "千香引魂蠱",
        20603: "醉夢遊春",
        20702: "粟子行雲",
        20801: "斬雪刀法",
        20402: "十方破陣"
    },
    "xinfas": {
        1: "生龍活虎",
        2: "晚雪間",
        3: "鐵身訣",
        4: "山月無影",
        5: "極樂泣血",
        41: "征人歸",
        42: "所恨年年",
        43: "歸燕經",
        44: "怒斬馬",
        45: "長生無相",
        46: "婆娑影",
        81: "易水歌",
        82: "四時無常",
        101: "千山法",
        102: "燎原星火",
        103: "威猛歌",
        104: "無名心法",
        151: "逐狼心經",
        152: "移經易武",
        153: "凝神章",
        154: "劍氣縱横",
        301: "葫蘆飛飛",
        302: "春雷篇",
        303: "縱地摘星",
        304: "花上月令",
        351: "君臣藥",
        352: "杏花不見",
        353: "指玄篇註",
        354: "千絲蠱",
        401: "山河絕韻",
        402: "困獸心經",
        403: "抗造大法",
        404: "磐石訣",
        451: "忘川絕響",
        452: "心彌泥魚",
        453: "斷石之構",
        454: "滄浪劍訣",
        501: "千營一呼",
        502: "繩舟行木",
        503: "燈兒亮",
        504: "大唐歌",
        6: "沙擺尾",
        48: "丹心篆",
        47: "明晦同塵",
        551: "霜天白夜",
        552: "孤忠不辭",
        553: "穿喉訣",
        554: "燎原踏"
    }
}

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
        self.cookie_store = None
        if profile is not None:
            profile.setHttpUserAgent(MOBILE_USER_AGENT)
            # 4. 底層監聽 CookieStore (解決 HttpOnly 無法透過 JS 獲取的問題)
            self.cookie_store = profile.cookieStore()
            if self.cookie_store is not None:
                self.cookie_store.cookieAdded.connect(self.on_cookie_added)
        
        # 2. 建立網頁檢視器
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(LOGIN_URL))
        
        # 3. 憑證與憑據暫存器
        self.intercepted_cookies = {}
        self.intercepted_token = None
        self.intercepted_storage_key = None
        
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
        page = self.browser.page()
        if page is not None:
            page.runJavaScript(js_script, self.on_js_result)

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
    使用 requests 模擬 GET 請求獲取角色數據，並解析輸出指定的欄位
    """
    print("\n🚀 開始向官方私有 API 發送數據擷取請求...")
    
    # 建構 API 請求標頭
    headers = {
        "User-Agent": MOBILE_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.wherewindsmeetgame.com",
        "Referer": "https://www.wherewindsmeetgame.com/m/2025h5sjgj/tw/"
    }
    
    # Token 放入 headers 的 access_token 欄位
    if token:
        headers["access_token"] = token
    elif cookies.get("access_token"):
        headers["access_token"] = cookies.get("access_token")
    elif cookies.get("mpay_token"):
        headers["access_token"] = cookies.get("mpay_token")

    data = None
    try:
        response = requests.get(API_URL, headers=headers, cookies=cookies, timeout=10)
        
        # 處理 401 憑證失效
        if response.status_code == 401:
            print("❌ 錯誤：認證 Token 已失效或過期 (401 Unauthorized)。請重新執行登入驗證。")
            return
            
        response.raise_for_status()
        
        # 強制指定編碼為 utf-8 避免解析中文亂碼
        response.encoding = 'utf-8'
        data = response.json()
        
        # 取得主資料節點
        role_data = data.get("data", {}) if "data" in data else data
        
        # 1. 角色名稱
        role_name = role_data.get('roleName', '未知')
        
        # 2. 武學心法 (包含主流派、副流派及被動心法)
        kongfu_main_id = role_data.get("kongfuMain")
        kongfu_sub_id = role_data.get("kongfuSub")
        passive_slots = role_data.get("passiveSlots", [])
        
        # 翻譯主流派與副流派
        kongfu_main = TRANSLATION_MAP["kongfus"].get(kongfu_main_id, f"未知流派 ({kongfu_main_id})")
        kongfu_sub = TRANSLATION_MAP["kongfus"].get(kongfu_sub_id, f"未知流派 ({kongfu_sub_id})")
        
        # 翻譯被動心法
        parsed_xinfas = []
        for x_id in passive_slots:
            if x_id == 0 or x_id is None:
                continue
            xf_name = TRANSLATION_MAP["xinfas"].get(x_id, f"未知心法 ({x_id})")
            parsed_xinfas.append(xf_name)
        
        xinfas_str = ", ".join(parsed_xinfas) if parsed_xinfas else "無"

        print("=" * 50)
        print("📊 【燕雲十六聲】官方 H5 數據擷取結果")
        print("-" * 50)
        print(f"👤 角色名稱: {role_name}")
        print("🔹 武學心法:")
        print(f"   - 主流派 (主心法): {kongfu_main}")
        print(f"   - 副流派 (副心法): {kongfu_sub}")
        print(f"   - 裝備被動心法   : {xinfas_str}")
        print("=" * 50)
        
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            print("❌ 錯誤：401 認證失敗，請嘗試重新開啟工具登入驗證。")
        else:
            print(f"❌ 官方 API 回傳 HTTP 錯誤：{e}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 網路傳輸異常（可能遭 WAF 阻擋）：{e}")
    except Exception as e:
        print(f"❌ 資料解析失敗或格式不符：{e}")
        try:
            print(f"原始 JSON 數據回傳如下：\n{json.dumps(data, indent=4, ensure_ascii=False)}")
        except Exception:
            pass


def main():
    # 強制控制台輸出使用 UTF-8 編碼，防止 Windows 環境下中文編碼出錯
    if sys.platform.startswith("win"):
        try:
            reconfigure = getattr(sys.stdout, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8")
        except Exception:
            pass
            
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
