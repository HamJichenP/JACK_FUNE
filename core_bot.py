"""
核心互動模組 (core_bot.py)
專責 Discord 機器人的互動邏輯，包含多伺服器獨立設定（金鑰與篩選身分組）與寫入流程。
"""

import os
import json
import asyncio
import aiohttp
import aiohttp.web
import discord
from storage_sheets import StorageSheets
import urllib.parse

CONFIG_FILE = "server_config.json"
TEMPLATE_COPY_URL = "https://docs.google.com/spreadsheets/d/1hRvW70XsD4d3WBlaaHQ8JytAHNDWRKL8r54tdHca4Bk/copy"

# 繁體中文翻譯對照表 (用於 H5 數據解析)
TRANSLATION_MAP = {
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

def rewrite_request_text(text: str, local_host: str) -> str:
    """將請求內容中的本地網址重寫回官方網域以通過安全驗證"""
    # 定義需要被替換的本地 host 清單
    hosts_to_replace = list(set([local_host, "127.0.0.1:8826", "localhost:8826"]))
    
    # 官方的目標網域
    target_www = "https://www.wherewindsmeetgame.com"
    target_sdk = "https://sdk-os.mpsdk.easebar.com"
    target_who = "https://who.nie.easebar.com"
    
    for h in hosts_to_replace:
        if not h:
            continue
        
        # === 1. 替換未編碼的完整網址 (先長後短) ===
        # http
        text = text.replace(f"http://{h}/proxy_sdk", target_sdk)
        text = text.replace(f"http://{h}/proxy_who", target_who)
        text = text.replace(f"http://{h}", target_www)
        
        # https
        text = text.replace(f"https://{h}/proxy_sdk", target_sdk)
        text = text.replace(f"https://{h}/proxy_who", target_who)
        text = text.replace(f"https://{h}", target_www)
        
        # === 2. 替換已編碼的完整網址 (先長後短，指定 safe="") ===
        # 取得各種組合的編碼值
        enc_local_http = urllib.parse.quote(f"http://{h}", safe="")
        enc_local_https = urllib.parse.quote(f"https://{h}", safe="")
        
        enc_local_http_sdk = urllib.parse.quote(f"http://{h}/proxy_sdk", safe="")
        enc_local_https_sdk = urllib.parse.quote(f"https://{h}/proxy_sdk", safe="")
        enc_local_http_who = urllib.parse.quote(f"http://{h}/proxy_who", safe="")
        enc_local_https_who = urllib.parse.quote(f"https://{h}/proxy_who", safe="")
        
        enc_target_www = urllib.parse.quote(target_www, safe="")
        enc_target_sdk = urllib.parse.quote(target_sdk, safe="")
        enc_target_who = urllib.parse.quote(target_who, safe="")
        
        # 大寫替換
        text = text.replace(enc_local_http_sdk, enc_target_sdk)
        text = text.replace(enc_local_https_sdk, enc_target_sdk)
        text = text.replace(enc_local_http_who, enc_target_who)
        text = text.replace(enc_local_https_who, enc_target_who)
        text = text.replace(enc_local_http, enc_target_www)
        text = text.replace(enc_local_https, enc_target_www)
        
        # 小寫替換
        text = text.replace(enc_local_http_sdk.lower(), enc_target_sdk.lower())
        text = text.replace(enc_local_https_sdk.lower(), enc_target_sdk.lower())
        text = text.replace(enc_local_http_who.lower(), enc_target_who.lower())
        text = text.replace(enc_local_https_who.lower(), enc_target_who.lower())
        text = text.replace(enc_local_http.lower(), enc_target_www.lower())
        text = text.replace(enc_local_https.lower(), enc_target_www.lower())
    
    # === 3. 替換獨立的代理相對路徑 ===
    text = text.replace("/proxy_sdk", "")
    text = text.replace("/proxy_who", "")
    
    encoded_proxy_sdk_upper = urllib.parse.quote("/proxy_sdk", safe="")
    encoded_proxy_who_upper = urllib.parse.quote("/proxy_who", safe="")
    text = text.replace(encoded_proxy_sdk_upper, "")
    text = text.replace(encoded_proxy_who_upper, "")
    
    text = text.replace(encoded_proxy_sdk_upper.lower(), "")
    text = text.replace(encoded_proxy_who_upper.lower(), "")
    
    return text


def rewrite_response_location(location_str: str, local_host: str) -> str:
    """將官方重定向網址改寫為我們本地的代理網址，使用戶留在代理環境中"""
    # 將官方主網域替換為本地伺服器位址
    if "https://www.wherewindsmeetgame.com" in location_str:
        location_str = location_str.replace("https://www.wherewindsmeetgame.com", f"http://{local_host}")
    elif "http://www.wherewindsmeetgame.com" in location_str:
        location_str = location_str.replace("http://www.wherewindsmeetgame.com", f"http://{local_host}")
        
    # 將官方 API 域名替換為代理路徑
    location_str = location_str.replace("https://sdk-os.mpsdk.easebar.com", f"http://{local_host}/proxy_sdk")
    location_str = location_str.replace("https://who.nie.easebar.com", f"http://{local_host}/proxy_who")
    
    return location_str

def rewrite_response_bytes(body_bytes: bytes, local_host: str) -> bytes:
    """將官方響應內容中的絕對網域替換為本地代理路徑"""
    body_bytes = body_bytes.replace(b"https://www.wherewindsmeetgame.com", b"")
    body_bytes = body_bytes.replace(b"http://www.wherewindsmeetgame.com", b"")
    body_bytes = body_bytes.replace(b"https://sdk-os.mpsdk.easebar.com", f"http://{local_host}/proxy_sdk".encode('utf-8'))
    body_bytes = body_bytes.replace(b"https://who.nie.easebar.com", f"http://{local_host}/proxy_who".encode('utf-8'))
    
    hosts_to_replace = list(set([local_host, "127.0.0.1:8826", "localhost:8826"]))
    for h in hosts_to_replace:
        if not h:
            continue
        # 處理 URL 編碼的網址替換 (safe="")
        # 大寫
        encoded_sdk_target_upper = urllib.parse.quote(f"http://{h}/proxy_sdk", safe="")
        encoded_who_target_upper = urllib.parse.quote(f"http://{h}/proxy_who", safe="")
        
        body_bytes = body_bytes.replace(b"https%3A%2F%2Fsdk-os.mpsdk.easebar.com", encoded_sdk_target_upper.encode('utf-8'))
        body_bytes = body_bytes.replace(b"https%3A%2F%2Fwho.nie.easebar.com", encoded_who_target_upper.encode('utf-8'))
        
        # 小寫
        body_bytes = body_bytes.replace(b"https%3a%2f%2fsdk-os.mpsdk.easebar.com", encoded_sdk_target_upper.lower().encode('utf-8'))
        body_bytes = body_bytes.replace(b"https%3a%2f%2fwho.nie.easebar.com", encoded_who_target_upper.lower().encode('utf-8'))
    
    # 處理 HTML/JS 內部的靜態資源相對路徑 (避免資源 404)
    body_bytes = body_bytes.replace(b'"/static/', b'"/proxy_sdk/static/')
    body_bytes = body_bytes.replace(b"'/static/", b"'/proxy_sdk/static/")
    body_bytes = body_bytes.replace(b'="/static/', b'="/proxy_sdk/static/')
    
    return body_bytes

class H5ExtractorModal(discord.ui.Modal, title="燕雲十六聲數據查詢"):
    token_input = discord.ui.TextInput(
        label="請輸入您的 H5 登入 Token (access_token)",
        placeholder="請貼上 access_token 憑證...",
        required=True,
        max_length=200,
        style=discord.TextStyle.short
    )

    def __init__(self, bot: 'DiscordBot'):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # 延遲回應，並設定為公開訊息 (ephemeral=False)，且之後不會自動刪除
        await interaction.response.defer(ephemeral=False)
        token = self.token_input.value.strip()

        if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
            await self.bot.query_and_send_h5(token, interaction.channel, str(interaction.user.id))
        else:
            await interaction.followup.send("❌ 此查詢僅限於伺服器的文字頻道中執行。")


class H5ExtractorLinkView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Button(label="🔗 點我登入官方數據工具", url=url, style=discord.ButtonStyle.link))


class H5ExtractorView(discord.ui.View):
    def __init__(self, bot: 'DiscordBot'):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🔍 查詢角色心法", style=discord.ButtonStyle.primary, custom_id="btn_h5_extractor", emoji="📊")
    async def extract_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id) if interaction.guild else "global"
        config = self.bot.load_config()
        server_cfg = config.get(guild_id, {})
        
        # 讀取設定的 API URL，若未設定則嘗試使用本地預設 IP 的 port
        api_url = server_cfg.get("bot_api_url", "")
        if not api_url:
            port = config.get("global", {}).get("web_port", 8826)
            api_url = f"http://127.0.0.1:{port}"

        # 組合專屬的登入跳轉連結
        login_url = f"{api_url}/m/2025h5sjgj/tw/?user_id={interaction.user.id}&channel_id={interaction.channel_id}"

        embed = discord.Embed(
            title="📊 一鍵自動查詢角色心法",
            description="本功能已完美實現**一鍵自動擷取**！\n"
                        "請點擊下方按鈕開啟官方登入網頁，完成登入後您的武學配置卡片即會自動同步至本頻道中！\n\n"
                        "💡 **使用說明**：\n"
                        "1. 點擊下方連結按鈕。\n"
                        "2. 在彈出的網頁中正常進行登入（可使用手機號碼驗證碼）。\n"
                        "3. 登入成功後網頁會顯示「查詢成功」，您的配置卡片將立即發送至 Discord 頻道！",
            color=discord.Color.blue()
        )
        view = H5ExtractorLinkView(login_url)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RoleSelect(discord.ui.Select):
    def __init__(self, bot: 'DiscordBot', day: str, gas_url: str, roles: list[str]):
        """
        自訂下拉選單元件，用於讓有多重武學身分組的成員選擇其一報名。
        """
        self.bot = bot
        self.day = day
        self.gas_url = gas_url

        # 建立選單選項 (最多 25 個，Discord API 限制)
        options = [
            discord.SelectOption(label=role_name, value=role_name, emoji="⚔️")
            for role_name in roles[:25]
        ]
        
        super().__init__(
            placeholder="請選擇您此戰要使用的武學身分...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # 取得使用者所選取的單一身分組
        selected_role = self.values[0]
        member = interaction.user
        
        # 點選後立即將原下拉選單訊息更新為處理中狀態並清除選單元件，防止重複點擊並維持畫面清爽
        await interaction.response.edit_message(content="⏳ 正在處理報名資料，請稍候...", view=None)
        
        # 呼叫非同步寫入方法，將選定的單一身分組寫入試算表
        success = await self.bot.storage.write_user_data_via_gas(
            gas_url=self.gas_url,
            display_name=member.display_name if isinstance(member, discord.Member) else member.name,
            roles=[selected_role],
            registered_day=self.day
        )
        
        msg = None
        if success:
            # 發送公開的成功報名訊息，以利 2 秒後機器人能將其完全刪除以維持版面乾淨
            msg = await interaction.followup.send(
                f"✅ **報名成功！**\n"
                f"📅 報名日期：`{self.day}`\n"
                f"👤 登記名稱：`{member.display_name if isinstance(member, discord.Member) else member.name}`\n"
                f"🏷️ 選擇武學：`{selected_role}`",
                ephemeral=False,
                wait=True
            )
        else:
            msg = await interaction.followup.send(
                "❌ **報名失敗！**\n"
                "無法連線或寫入 Google 試算表，請聯絡伺服器管理員確認 GAS 網址設定與權限是否正確。",
                ephemeral=False,
                wait=True
            )
        
        # 嘗試清除最初的「處理中」隱密提示訊息
        try:
            await interaction.delete_original_response()
        except Exception:
            try:
                await interaction.edit_original_response(content="✅ 登記程序已完成。")
            except Exception:
                pass

        # 延遲 2 秒後刪除公開的通知訊息
        await asyncio.sleep(2.0)
        if msg:
            try:
                await msg.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除公開的報名結果訊息: {e}")



class RoleSelectionView(discord.ui.View):
    def __init__(self, bot: 'DiscordBot', day: str, gas_url: str, roles: list[str]):
        """
        自訂的下拉選單視圖，這裡的 timeout 設為 60 秒以自動回收，不需使用持久化 (Persistent)。
        """
        super().__init__(timeout=60)
        self.add_item(RoleSelect(bot, day, gas_url, roles))


class RegistrationView(discord.ui.View):
    def __init__(self, bot: 'DiscordBot'):
        """
        初始化持久化報名按鈕視圖。
        設定 timeout=None 是持久化視圖的關鍵，這表示視圖不會因逾時而失效。
        """
        super().__init__(timeout=None)
        self.bot = bot

    async def handle_registration(self, interaction: discord.Interaction, day: str):
        """共通的報名處理邏輯"""
        guild = interaction.guild
        member = interaction.user

        # 防禦性檢查：確保是在伺服器中，且發起人為 Member 類型
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ 此功能僅限於伺服器頻道中使用。", ephemeral=True)
            return

        guild_id = str(guild.id)
        config = self.bot.load_config()
        server_cfg = config.get(guild_id, {})

        gas_url = server_cfg.get("gas_web_app_url")
        if not gas_url:
            await interaction.response.send_message(
                "❌ 此伺服器尚未設定 Google GAS Web App 網址，無法進行報名。請聯絡管理員使用 `!setup_gas` 進行設定。",
                ephemeral=False
            )
            await asyncio.sleep(2.0)
            try:
                await interaction.delete_original_response()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除設定錯誤提示: {e}")
            return

        target_roles = server_cfg.get("target_roles", [])

        # 過濾身分組
        if target_roles:
            roles = [role.name for role in member.roles if role.name in target_roles]
        else:
            roles = [role.name for role in member.roles if role.name != "@everyone"]

        # 智慧過濾與選單分流邏輯
        if not roles:
            # 情況 3：沒有任何符合白名單的身分組 -> 直接回覆失敗 (使用公開訊息)
            await interaction.response.send_message(
                "❌ **報名失敗**\n"
                "您目前在伺服器中沒有擁有任何符合登記要求的武學身分組。\n"
                "*提示：請先向幹部申請對應的武學身分組。*",
                ephemeral=False
            )
            # 2 秒後自動刪除此回覆
            await asyncio.sleep(2.0)
            try:
                await interaction.delete_original_response()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除失敗提示訊息: {e}")
            return

        if len(roles) == 1:
            # 情況 1：只擁有一個符合身分組 -> 直接一鍵快速報名
            # 先延遲回應 (Defer) 為公開訊息，避免網路傳輸超時，以利 2 秒後刪除
            await interaction.response.defer(ephemeral=False)
            
            success = await self.bot.storage.write_user_data_via_gas(
                gas_url=gas_url,
                display_name=member.display_name,
                roles=roles,
                registered_day=day
            )
            
            if success:
                await interaction.edit_original_response(
                    content=f"✅ **報名成功！**\n"
                            f"📅 報名日期：`{day}`\n"
                            f"👤 登記名稱：`{member.display_name}`\n"
                            f"🏷️ 登記武學：`{roles[0]}`"
                )
            else:
                await interaction.edit_original_response(
                    content="❌ **報名失敗！**\n"
                            "無法連線或寫入 Google 試算表，請聯絡伺服器管理員確認：\n"
                            "1. Google GAS 網址設定是否正確\n"
                            "2. 該 GAS 網頁應用程式是否已部署，且存取權限設定為「任何人 (Anyone)」\n"
                            "3. 本機網路是否能正常連線至外部 API"
                )
            # 2 秒後自動刪除報名結果訊息
            await asyncio.sleep(2.0)
            try:
                await interaction.delete_original_response()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除報名結果訊息: {e}")
        else:
            # 情況 2：擁有多個符合身分組 -> 彈出下拉選單讓使用者自行挑選一個
            view = RoleSelectionView(self.bot, day, gas_url, roles)
            await interaction.response.send_message(
                "⚔️ **偵測到您擁有多個武學身分組**\n"
                "請於下方選單選擇您此戰要使用的武學進行登記：",
                view=view,
                ephemeral=True
            )

    # 星期六報名按鈕，設定唯一的 custom_id 是持久化視圖重啟後能繼續運作的關鍵
    @discord.ui.button(label="星期六 報名", style=discord.ButtonStyle.primary, custom_id="btn_register_saturday", emoji="💙")
    async def register_saturday(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_registration(interaction, "星期六")

    # 星期日報名按鈕
    @discord.ui.button(label="星期日 報名", style=discord.ButtonStyle.success, custom_id="btn_register_sunday", emoji="💚")
    async def register_sunday(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_registration(interaction, "星期日")


class DiscordBot(discord.Client):
    def __init__(self, storage_client: StorageSheets):
        """
        初始化 Discord 機器人。
        
        :param storage_client: 儲存模組 (StorageSheets 實例)
        """
        # 設定 Discord 機器人所需的權限 (Intents)
        intents = discord.Intents.default()
        intents.message_content = True  # 用於讀取設定與測試指令
        intents.members = True          # 用於讀取成員身分組資訊
        
        super().__init__(intents=intents)
        self.storage = storage_client

        # 初始化 Web API 服務
        self.web_app = aiohttp.web.Application()
        self.web_app.router.add_route('*', '/api/h5_token', self.handle_web_token)
        self.web_app.router.add_get('/m/2025h5sjgj/tw/', self.handle_auth_login)
        self.web_app.router.add_route('*', '/proxy_who/{path:.*}', self.handle_proxy_who)
        self.web_app.router.add_route('*', '/proxy_sdk/{path:.*}', self.handle_proxy_sdk)
        self.web_app.router.add_route('*', '/{path:.*}', self.handle_proxy)
        self.web_runner = None
        self.web_site = None

    # --- 設定檔讀寫輔助方法 ---
    def load_config(self) -> dict:
        """載入伺服器設定檔"""
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Bot][設定錯誤] 無法讀取設定檔 {CONFIG_FILE}: {e}")
            return {}

    def save_config(self, config: dict):
        """儲存伺服器設定檔"""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Bot][設定錯誤] 無法寫入設定檔 {CONFIG_FILE}: {e}")

    # --- Discord 事件監聽 ---
    async def on_ready(self):
        """當機器人成功登入並準備就緒時觸發"""
        print(f"[Bot] 機器人已成功上線！")
        if self.user:
            print(f"[Bot] 登入帳號：{self.user.name} (ID: {self.user.id})")
        
        # 註冊 Persistent View 讓舊按鈕在機器人重啟後依然有效
        self.add_view(RegistrationView(self))
        self.add_view(H5ExtractorView(self))
        print("[Bot] 已成功註冊持久化按鈕視圖 (Persistent View)")

        # 啟動 Web 服務
        try:
            self.web_runner = aiohttp.web.AppRunner(self.web_app)
            await self.web_runner.setup()
            
            config = self.load_config()
            port = config.get("global", {}).get("web_port", 8826)
            
            self.web_site = aiohttp.web.TCPSite(self.web_runner, '0.0.0.0', port)
            await self.web_site.start()
            print(f"[Bot] Web API 伺服器已啟動，監聽 port: {port}")
        except Exception as e:
            print(f"[Bot][錯誤] 無法啟動 Web API 伺服器: {e}")
            
        print("--------------------------------------------------")

    async def close(self):
        """關閉機器人並清理非同步資源"""
        if self.web_site:
            try:
                await self.web_site.stop()
                print("[Bot] Web API 伺服器已停止")
            except Exception:
                pass
        if self.web_runner:
            try:
                await self.web_runner.cleanup()
            except Exception:
                pass
        await super().close()

    async def handle_web_token(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """處理 Web API `/api/h5_token` 的跨網域 POST 請求"""
        # 處理 CORS 預檢請求 (Preflight)
        if request.method == "OPTIONS":
            response = aiohttp.web.Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return response

        try:
            data = await request.json()
            token = data.get("token")
            channel_id_str = data.get("channel_id")
            user_id_str = data.get("user_id")

            if not token or not channel_id_str:
                return aiohttp.web.json_response(
                    {"error": "Missing parameters"}, 
                    status=400, 
                    headers={"Access-Control-Allow-Origin": "*"}
                )

            channel_id = int(channel_id_str)
            channel = self.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.fetch_channel(channel_id)
                except Exception:
                    channel = None

            if not channel or not isinstance(channel, discord.TextChannel):
                return aiohttp.web.json_response(
                    {"error": "Channel not found or invalid type"}, 
                    status=404, 
                    headers={"Access-Control-Allow-Origin": "*"}
                )

            # 使用 asyncio.create_task 在背景執行 API 擷取並發送訊息，避免阻塞 Web 回應
            asyncio.create_task(self.query_and_send_h5(token, channel, user_id_str))

            return aiohttp.web.json_response(
                {"status": "success"}, 
                headers={"Access-Control-Allow-Origin": "*"}
            )

        except Exception as e:
            print(f"[Bot][WebAPI] 處理 Token 請求時出錯: {e}")
            return aiohttp.web.json_response(
                {"error": str(e)}, 
                status=500, 
                headers={"Access-Control-Allow-Origin": "*"}
            )

    async def handle_auth_login(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """使用者點擊 Discord 連結後的進入點，代理官方 HTML 並注入監聽腳本"""
        user_id = request.query.get('user_id', '')
        channel_id = request.query.get('channel_id', '')
        
        target_url = "https://www.wherewindsmeetgame.com/m/2025h5sjgj/tw/"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.wherewindsmeetgame.com/"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(target_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    body = await resp.read()
                    
                    html_content = body.decode('utf-8', errors='ignore')
                    html_content = html_content.replace('https://www.wherewindsmeetgame.com', '')
                    html_content = html_content.replace('https://who.nie.easebar.com', '/proxy_who')
                    html_content = html_content.replace('https://sdk-os.mpsdk.easebar.com', '/proxy_sdk')
                    
                    # 智慧注入提示橫幅，提醒使用者不要使用第三方 OAuth 登入
                    banner_html = """
                    <div style="background:#e74c3c;color:#fff;text-align:center;padding:12px;font-family:sans-serif;font-size:14px;position:relative;z-index:999999;font-weight:bold;box-shadow:0 2px 5px rgba(0,0,0,0.2);line-height:1.5;">
                      ⚠️ 注意事項：請使用「手機驗證碼」或「網易帳號密碼」進行登入。<br>
                      <span style="font-size:12px;font-weight:normal;opacity:0.9;">（本工具為本機代理環境，不支援 Google/Apple/Steam 等第三方授權跳轉登入）</span>
                    </div>
                    """
                    if '<body>' in html_content:
                        html_content = html_content.replace('<body>', f'<body>{banner_html}')
                    elif '<body' in html_content:
                        parts = html_content.split('<body', 1)
                        if len(parts) == 2:
                            body_rest = parts[1].split('>', 1)
                            if len(body_rest) == 2:
                                html_content = f"{parts[0]}<body{body_rest[0]}>{banner_html}{body_rest[1]}"
                    
                    inject_js = f"""
                    <script>
                      (function() {{
                        console.log("✦ 燕雲十六聲數據擷取監聽已啟動 ✦");
                        const checkInterval = setInterval(function() {{
                          const keys = ['token', 'access_token', 'accessToken', 'sdk_token', 'mpay_token', 'authorization', 'login_token', 'mpay_sdk_token'];
                          let token = null;
                          for (let k of keys) {{
                            let v = localStorage.getItem(k) || sessionStorage.getItem(k);
                            if (v) {{ token = v; break; }}
                          }}
                          if (token) {{
                            clearInterval(checkInterval);
                            console.log("✨ 成功擷取到 Token！正在回傳給機器人...");
                            fetch('/api/h5_token', {{
                              method: 'POST',
                              headers: {{ 'Content-Type': 'application/json' }},
                              body: JSON.stringify({{
                                token: token,
                                channel_id: '{channel_id}',
                                user_id: '{user_id}'
                              }})
                            }})
                            .then(function(res) {{
                              if (res.ok) {{
                                document.body.innerHTML = '<div style="text-align:center;margin-top:200px;font-family:sans-serif;"><div style="font-size:50px;">✅</div><div style="font-size:24px;color:#2ecc71;margin-top:20px;font-weight:bold;">查詢成功！</div><div style="font-size:16px;color:#7f8c8d;margin-top:10px;">您的武學配置卡片已發送至 Discord 頻道。<br>此視窗現在可以關閉了。</div></div>';
                              }} else {{
                                alert("❌ 資料傳送失敗，請聯絡管理員確認機器人服務狀態。");
                              }}
                            }})
                            .catch(function(err) {{
                              alert("❌ 連線錯誤: " + err.message);
                            }});
                          }}
                        }}, 1000);
                      }})();
                    </script>
                    """
                    if '</body>' in html_content:
                        html_content = html_content.replace('</body>', f'{inject_js}</body>')
                    else:
                        html_content += inject_js
                        
                    return aiohttp.web.Response(text=html_content, content_type='text/html', charset='utf-8')
        except Exception as e:
            print(f"[Bot][錯誤] 獲取官方 HTML 失敗: {e}")
            return aiohttp.web.Response(text=f"❌ 無法連線至官方伺服器，請稍後再試。原因: {e}", status=500)

    async def handle_proxy_who(self, request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
        """代理 who.nie.easebar.com 請求，繞過 CORS 跨域政策限制"""
        if request.method == "OPTIONS":
            response = aiohttp.web.Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "*"
            return response

        path = request.match_info.get('path', '')
        local_host = request.host
        
        # 雙向 URL 參數重寫
        query_str = request.query_string
        if query_str:
            query_str = rewrite_request_text(query_str, local_host)
            target_url = f"https://who.nie.easebar.com/{path}?{query_str}"
        else:
            target_url = f"https://who.nie.easebar.com/{path}"

        print(f"[DEBUG][ProxyWho] 轉發前 URL: {target_url}")
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length', 'origin', 'referer']}
        headers['Origin'] = 'https://www.wherewindsmeetgame.com'
        headers['Referer'] = 'https://www.wherewindsmeetgame.com/'

        req_data = None
        if request.has_body:
            raw_body = await request.read()
            content_type = request.headers.get('Content-Type', '').lower()
            if 'json' in content_type or 'x-www-form-urlencoded' in content_type or 'text' in content_type:
                try:
                    body_text = raw_body.decode('utf-8', errors='ignore')
                    body_text = rewrite_request_text(body_text, local_host)
                    req_data = body_text.encode('utf-8')
                except Exception:
                    req_data = raw_body
            else:
                req_data = raw_body

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=req_data,
                    allow_redirects=False
                ) as resp:
                    body = await resp.read()
                    
                    res_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']}
                    res_headers['Access-Control-Allow-Origin'] = '*'
                    
                    if resp.status in [301, 302]:
                        location = resp.headers.get('Location', '')
                        if location:
                            res_headers['Location'] = rewrite_response_location(location, local_host)

                    content_type = resp.headers.get('Content-Type', '').lower()
                    if 'javascript' in content_type or 'html' in content_type or 'json' in content_type or 'css' in content_type:
                        body = rewrite_response_bytes(body, local_host)

                    print(f"[Bot][ProxyWho] {request.method} /{path} -> Status {resp.status}")
                    return aiohttp.web.Response(body=body, status=resp.status, headers=res_headers)
        except Exception as e:
            print(f"[Bot][ProxyWhoError] 代理 who 資源 {path} 時出錯: {e}")
            return aiohttp.web.Response(status=502)

    async def handle_proxy_sdk(self, request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
        """代理 sdk-os.mpsdk.easebar.com 請求，繞過 CORS 跨域政策限制"""
        if request.method == "OPTIONS":
            response = aiohttp.web.Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "*"
            return response

        path = request.match_info.get('path', '')
        local_host = request.host
        
        # 雙向 URL 參數重寫
        query_str = request.query_string
        if query_str:
            query_str = rewrite_request_text(query_str, local_host)
            target_url = f"https://sdk-os.mpsdk.easebar.com/{path}?{query_str}"
        else:
            target_url = f"https://sdk-os.mpsdk.easebar.com/{path}"

        print(f"[DEBUG][ProxySDK] 轉發前 URL: {target_url}")
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length', 'origin', 'referer']}
        headers['Origin'] = 'https://www.wherewindsmeetgame.com'
        headers['Referer'] = 'https://www.wherewindsmeetgame.com/'

        req_data = None
        if request.has_body:
            raw_body = await request.read()
            content_type = request.headers.get('Content-Type', '').lower()
            if 'json' in content_type or 'x-www-form-urlencoded' in content_type or 'text' in content_type:
                try:
                    body_text = raw_body.decode('utf-8', errors='ignore')
                    body_text = rewrite_request_text(body_text, local_host)
                    req_data = body_text.encode('utf-8')
                except Exception:
                    req_data = raw_body
            else:
                req_data = raw_body

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=req_data,
                    allow_redirects=False
                ) as resp:
                    body = await resp.read()
                    
                    res_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']}
                    res_headers['Access-Control-Allow-Origin'] = '*'
                    
                    if resp.status in [301, 302]:
                        location = resp.headers.get('Location', '')
                        if location:
                            res_headers['Location'] = rewrite_response_location(location, local_host)

                    content_type = resp.headers.get('Content-Type', '').lower()
                    if 'javascript' in content_type or 'html' in content_type or 'json' in content_type or 'css' in content_type:
                        body = rewrite_response_bytes(body, local_host)

                    print(f"[Bot][ProxySDK] {request.method} /{path} -> Status {resp.status}")
                    return aiohttp.web.Response(body=body, status=resp.status, headers=res_headers)
        except Exception as e:
            print(f"[Bot][ProxySDKError] 代理 sdk 資源 {path} 時出錯: {e}")
            return aiohttp.web.Response(status=502)

    async def handle_proxy(self, request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
        """萬用代理，將所有靜態資源與 API 轉發給官方網站"""
        path = request.match_info.get('path', '')
        local_host = request.host
        
        query_str = request.query_string
        if query_str:
            query_str = rewrite_request_text(query_str, local_host)
            target_url = f"https://www.wherewindsmeetgame.com/{path}?{query_str}"
        else:
            target_url = f"https://www.wherewindsmeetgame.com/{path}"

        headers = {k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length']}
        headers['Referer'] = 'https://www.wherewindsmeetgame.com/m/2025h5sjgj/tw/'
        
        try:
            async with aiohttp.ClientSession() as session:
                req_data = await request.read() if request.has_body else None
                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=req_data,
                    allow_redirects=False
                ) as resp:
                    body = await resp.read()
                    
                    res_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']}
                    res_headers['Access-Control-Allow-Origin'] = '*'
                    
                    if resp.status in [301, 302]:
                        location = resp.headers.get('Location', '')
                        if location:
                            res_headers['Location'] = rewrite_response_location(location, local_host)

                    content_type = resp.headers.get('Content-Type', '').lower()
                    if 'javascript' in content_type or 'html' in content_type or 'json' in content_type or 'css' in content_type:
                        body = rewrite_response_bytes(body, local_host)
                    
                    print(f"[Bot][Proxy] {request.method} /{path} -> Status {resp.status}")
                    return aiohttp.web.Response(body=body, status=resp.status, headers=res_headers)
        except Exception as e:
            print(f"[Bot][ProxyError] 代理資源 {path} 時出錯: {e}")
            return aiohttp.web.Response(status=502)

    async def query_and_send_h5(self, token: str, channel: discord.TextChannel, user_id_str: str | None = None):
        """核心 H5 API 查詢與資料發送"""
        api_url = "https://s2.easebar.com/78ae9d90792a3e9b/role/roleInfo"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.wherewindsmeetgame.com",
            "Referer": "https://www.wherewindsmeetgame.com/m/2025h5sjgj/tw/",
            "access_token": token
        }

        user_mention = f"<@{user_id_str}> " if user_id_str else ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 401:
                        await channel.send(f"{user_mention}❌ **查詢失敗**：認證 Token 已失效或過期，請重新取得。")
                        return
                    resp.raise_for_status()
                    data = await resp.json()

            # 取得主要資料節點
            role_data = data.get("data", {}) if "data" in data else data
            if not role_data:
                await channel.send(f"{user_mention}❌ **查詢失敗**：未獲取到有效的角色數據。")
                return

            role_name = role_data.get('roleName', '未知')
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

            embed = discord.Embed(
                title="📊 【燕雲十六聲】官方數據擷取結果",
                color=discord.Color.dark_teal()
            )
            embed.add_field(name="👤 角色名稱", value=f"`{role_name}`", inline=False)
            embed.add_field(name="⚔️ 主流派 (主心法)", value=f"`{kongfu_main}`", inline=True)
            embed.add_field(name="🛡️ 副流派 (副心法)", value=f"`{kongfu_sub}`", inline=True)
            embed.add_field(name="🏷️ 裝備被動心法", value=f"`{xinfas_str}`", inline=False)
            embed.set_footer(text="數據來源：燕雲十六聲官方 H5 數據工具")

            await channel.send(content=f"{user_mention}的武學數據查詢成功！", embed=embed)

        except Exception as e:
            print(f"[Bot][錯誤] 擷取 H5 資料時出錯: {e}")
            await channel.send(f"{user_mention}❌ **查詢失敗**：連接官方 API 時發生異常，請確認 Token 是否正確。")

    async def on_message(self, message: discord.Message):
        """當伺服器中有新訊息發送時觸發 (處理設定指令與連線測試)"""
        # 排除機器人自己發送的訊息
        if message.author == self.user:
            return

        # 防禦性檢查：排除私訊 (DM) 且確保作者為伺服器成員 (Member)
        if message.guild is None or not isinstance(message.author, discord.Member):
            return

        # 1. 連線測試指令
        if message.content.lower() == "!ping":
            msg = await message.channel.send("🏓 pong! 機器人運作正常！")
            await msg.delete(delay=2.0)
            try:
                await message.delete()
            except Exception:
                pass
            return

        # 2. 設定試算表金鑰指令 (!setup_sheet <Key>)
        if message.content.startswith("!setup_sheet"):
            # 權限檢查：限制只有管理員能執行
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            parts = message.content.split(maxsplit=1)
            if len(parts) < 2:
                msg = await message.channel.send("❌ 用法錯誤！請使用：`!setup_sheet <您的Google試算表Key>`")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            sheet_key = parts[1].strip()
            guild_id = str(message.guild.id)
            
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}
            config[guild_id]["google_sheets_key"] = sheet_key
            self.save_config(config)

            msg = await message.channel.send(f"✅ 已成功設定此伺服器的 Google 試算表金鑰！\n金鑰：`{sheet_key}`")
            # 2 秒後自動刪除機器人的提示訊息
            await msg.delete(delay=2.0)
            
            # 自動刪除管理員打的指令訊息
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除指令訊息: {e}")
            print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已更新試算表金鑰。")
            return

        # 3. 設定篩選身分組指令 (!setup_roles <身分組1,身分組2,...>)
        if message.content.startswith("!setup_roles"):
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            parts = message.content.split(maxsplit=1)
            guild_id = str(message.guild.id)
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}

            if len(parts) < 2 or parts[1].strip().lower() == "none":
                # 清除篩選身分組，代表擷取全部
                config[guild_id]["target_roles"] = []
                self.save_config(config)
                msg = await message.channel.send("✅ 已清除身分組篩選限制，未來將記錄成員所擁有的所有身分組（排除 @everyone）。")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已清除身分組篩選條件。")
            else:
                roles = [r.strip() for r in parts[1].split(",") if r.strip()]
                config[guild_id]["target_roles"] = roles
                self.save_config(config)
                msg = await message.channel.send(f"✅ 已成功設定此伺服器的篩選身分組白名單：`{', '.join(roles)}`")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 設定篩選身分組：{roles}")
            
            # 自動刪除管理員的設定指令
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除指令訊息: {e}")
            return

        # 4. 顯示目前伺服器設定指令 (!setup_show)
        if message.content.lower() == "!setup_show":
            guild_id = str(message.guild.id)
            config = self.load_config()
            server_cfg = config.get(guild_id, {})
            
            sheet_key = server_cfg.get("google_sheets_key", "尚未設定")
            gas_url = server_cfg.get("gas_web_app_url", "尚未設定")
            api_url = server_cfg.get("bot_api_url", "尚未設定")
            target_roles = server_cfg.get("target_roles", [])
            roles_display = ", ".join(target_roles) if target_roles else "記錄所有身分組 (排除 @everyone)"
            
            embed = discord.Embed(
                title=f"📊 {message.guild.name} 機器人設定狀態",
                color=discord.Color.blue()
            )
            embed.add_field(name="Google GAS Web App 網址", value=f"`{gas_url}`", inline=False)
            embed.add_field(name="Google 試算表金鑰 (舊/備用)", value=f"`{sheet_key}`", inline=False)
            embed.add_field(name="機器人 Web API 網址", value=f"`{api_url}`", inline=False)
            embed.add_field(name="篩選身分組白名單", value=roles_display, inline=False)
            embed.set_footer(text="提示：使用 !setup_gas, !setup_api_url 與 !setup_roles 進行修改")
            
            await message.channel.send(embed=embed)
            try:
                await message.delete()
            except Exception:
                pass
            return

        # 5. 部署報名按鈕指令 (!setup_buttons)
        if message.content.lower() == "!setup_buttons":
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            embed = discord.Embed(
                title="📅 週末活動快速報名",
                description="請點擊下方按鈕選擇您想報名的日期。\n"
                            "系統會自動擷取您的**顯示名稱**與**身分組**寫入至 Google 試算表。\n\n"
                            "🔹 點選 **星期六 報名** 登記週六活動\n"
                            "🔸 點選 **星期日 報名** 登記週日活動\n\n"
                            "*備註：報名結果將以即時訊息回覆，並於 2 秒後由機器人完全刪除以維持頻道整潔。*",
                color=discord.Color.dark_teal()
            )
            view = RegistrationView(self)
            await message.channel.send(embed=embed, view=view)
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除管理員設定指令訊息: {e}")
            return

        # 8. 設定 GAS Web App 網址指令 (!setup_gas <GAS網址>)
        if message.content.startswith("!setup_gas"):
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            parts = message.content.split(maxsplit=1)
            guild_id = str(message.guild.id)
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}

            if len(parts) < 2 or parts[1].strip().lower() == "none":
                config[guild_id]["gas_web_app_url"] = ""
                self.save_config(config)
                msg = await message.channel.send("✅ 已清除此伺服器的 Google GAS 網址設定。")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已清除 GAS 網址。")
            else:
                gas_url = parts[1].strip()
                if not (gas_url.startswith("http://") or gas_url.startswith("https://")):
                    msg = await message.channel.send("❌ 用法錯誤！請提供以 `http://` 或 `https://` 開頭的有效 GAS 網址。")
                    await msg.delete(delay=2.0)
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return
                
                config[guild_id]["gas_web_app_url"] = gas_url
                self.save_config(config)
                msg = await message.channel.send(f"✅ 已成功設定此伺服器的 Google GAS Web App 網址！\n網址：`{gas_url}`")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已設定 GAS 網址：{gas_url}")
            
            # 自動刪除管理員指令
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除指令訊息: {e}")
            return

        # 9. 顯示架設與設定說明指令 (!setup_help)
        if message.content.lower() == "!setup_help":
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            embed = discord.Embed(
                title="🛡️ 醉翁百業戰分隊表 - 架設與設定指南",
                description="請按照以下 4 個步驟，為您的伺服器架設專屬的百業戰報名系統：",
                color=discord.Color.brand_green()
            )
            embed.add_field(
                name="1️⃣ 一鍵複製試算表模板 (Google 官方範本)",
                value=f"請點擊下方連結，在您的雲端硬碟建立分隊表複本：\n"
                      f"👉 **[點此一鍵複製百業戰分隊表模板]({TEMPLATE_COPY_URL})**",
                inline=False
            )
            embed.add_field(
                name="2️⃣ 貼入並部署 Apps Script 腳本",
                value="1. 在複製好的試算表上方選單，點選 **「擴充功能」** -> **「Apps Script」**。\n"
                      "2. 複製專案中的 `gas_script.js` 全部程式碼，覆蓋貼上並儲存。\n"
                      "3. 點選右上角 **「部署」** -> **「新增部署」**。\n"
                      "4. 類型選擇 **「網頁應用程式 (Web App)」**：\n"
                      "   - *執行身分*：選擇您的帳戶。\n"
                      "   - *誰可以存取*：選擇 **「任何人 (Everyone)」** *(非常重要！)*。\n"
                      "5. 點選部署並授權，複製產生的 **「網頁應用程式網址」**。",
                inline=False
            )
            embed.add_field(
                name="3️⃣ 與 Discord 機器人進行綁定",
                value="在您伺服器的任何頻道中，輸入管理員指令綁定剛剛複製的網址：\n"
                      "```text\n!setup_gas <您複製的網頁應用程式網址>\n```\n"
                      "*(提示：您也可以使用 `!setup_roles 丐幫,霸刀` 設定要篩選的武學身分組。)*",
                inline=False
            )
            embed.add_field(
                name="4️⃣ 部署報名按鈕",
                value="在要提供成員報名的頻道中，輸入以下指令：\n"
                      "```text\n!setup_buttons\n```\n"
                      "機器人會發送「星期六/日」報名按鈕，成員即可開始登記！",
                inline=False
            )
            embed.set_footer(text="💡 您可以隨時輸入 !setup_show 檢視當前的設定狀態。")

            await message.channel.send(embed=embed)
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除管理員說明指令訊息: {e}")
            return

        # 10. 部署 H5 數據擷取按鈕指令 (!setup_extractor)
        if message.content.lower() == "!setup_extractor":
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            embed = discord.Embed(
                title="🔍 燕雲十六聲 - 角色與心法配置查詢",
                description="點擊下方按鈕，系統會為您生成專屬的 **書籤小工具** 與詳細教學。\n"
                            "在瀏覽器中登入官方 H5 數據工具後，只需**點選該書籤**即可自動查詢並將您的武學配置卡片發送至本頻道中！\n\n"
                            "💡 **特點**：\n"
                            "* **完全免下載/免安裝任何軟體**。\n"
                            "* 一分鐘快速設定，手機或電腦均可使用。\n"
                            "* 查詢結果公開展示，且**不會**自動刪除，方便大家互相交流配置。",
                color=discord.Color.blue()
            )
            view = H5ExtractorView(self)
            await message.channel.send(embed=embed, view=view)
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除管理員 H5 設定指令訊息: {e}")
            return

        # 11. 設定機器人 API 外部網址指令 (!setup_api_url <URL>)
        if message.content.startswith("!setup_api_url"):
            if not message.author.guild_permissions.administrator:
                msg = await message.channel.send("❌ 只有具備「管理員 (Administrator)」權限的成員才能使用此指令。")
                await msg.delete(delay=2.0)
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            parts = message.content.split(maxsplit=1)
            guild_id = str(message.guild.id)
            config = self.load_config()
            if guild_id not in config:
                config[guild_id] = {}

            if len(parts) < 2 or parts[1].strip().lower() == "none":
                config[guild_id]["bot_api_url"] = ""
                self.save_config(config)
                msg = await message.channel.send("✅ 已清除此伺服器的機器人 API 網址設定。")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已清除 API 網址。")
            else:
                api_url = parts[1].strip().rstrip('/')
                if not (api_url.startswith("http://") or api_url.startswith("https://")):
                    msg = await message.channel.send("❌ 用法錯誤！請提供以 `http://` 或 `https://` 開頭的有效網址。")
                    await msg.delete(delay=2.0)
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return

                config[guild_id]["bot_api_url"] = api_url
                self.save_config(config)
                msg = await message.channel.send(f"✅ 已成功設定此伺服器的機器人 API 網址！\n網址：`{api_url}`")
                await msg.delete(delay=2.0)
                print(f"[Bot][設定] 伺服器 {message.guild.name} (ID: {guild_id}) 已設定 API 網址：{api_url}")

            # 自動刪除管理員指令
            try:
                await message.delete()
            except Exception as e:
                print(f"[Bot][警告] 無法刪除指令訊息: {e}")
            return

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """當使用者對任何訊息點擊表情符號時觸發"""
        if self.user is None or payload.user_id == self.user.id:
            return

        # 防禦性檢查：排除沒有伺服器 ID 的私訊 (DM) 反應
        if not payload.guild_id:
            return

        # 1. 取得對應伺服器設定
        guild_id = str(payload.guild_id)
        config = self.load_config()
        server_cfg = config.get(guild_id, {})

        gas_url = server_cfg.get("gas_web_app_url")
        sheet_key = server_cfg.get("google_sheets_key")
        
        if not gas_url and not sheet_key:
            # 兩者皆未設定，無法寫入
            print(f"[Bot][忽略] 偵測到表情符號互動，但伺服器 (ID: {guild_id}) 尚未設定 GAS 網址或試算表金鑰！")
            return

        target_roles = server_cfg.get("target_roles", [])

        # 2. 獲取點擊成員的詳細資料與身分組
        guild = self.get_guild(payload.guild_id)
        if not guild:
            try:
                guild = await self.fetch_guild(payload.guild_id)
            except Exception as e:
                print(f"[Bot][錯誤] 無法取得伺服器資訊: {e}")
                return

        member = payload.member
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception as e:
                print(f"[Bot][錯誤] 無法取得成員 (ID: {payload.user_id}) 資訊: {e}")
                return

        # 3. 過濾身分組
        if target_roles:
            roles = [role.name for role in member.roles if role.name in target_roles]
        else:
            roles = [role.name for role in member.roles if role.name != "@everyone"]

        print(f"[Bot] 伺服器 {guild.name} 偵測到表情符號互動：")
        print(f" - 名字: {member.display_name}")
        print(f" - 身分組: {roles}")

        # 4. 優先使用 GAS 非同步寫入，若未設定則回退至原生試算表寫入
        if gas_url:
            await self.storage.write_user_data_via_gas(
                gas_url=gas_url,
                display_name=member.display_name,
                roles=roles,
                registered_day="反應報名"
            )
        elif sheet_key:
            self.storage.write_user_data(
                spreadsheet_key=sheet_key,
                display_name=member.display_name,
                roles=roles,
                registered_day="反應報名"
            )
