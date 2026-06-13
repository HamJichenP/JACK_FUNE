/**
 * 「百業戰報名」Google Apps Script 後台接收程式碼 (gas_script.js)
 * 
 * 部署指引：
 * 1. 在您的 Google 試算表選單中，點選「擴充功能」 -> 「Apps Script」。
 * 2. 清除原本預設的內容，將本檔案的全部程式碼貼上。
 * 3. 點選右上角的「部署」 -> 「新增部署」。
 * 4. 點選左上角齒輪旁的「選取類型」，選擇「網頁應用程式 (Web App)」。
 * 5. 設定：
 *    - 說明：(可留空)
 *    - 執行身分：您的帳戶 (擁有試算表權限的帳戶)
 *    - 誰可以存取：任何人 (Anyone)  <-- 非常重要，一定要選「任何人」才能讓機器人通訊
 * 6. 點選「部署」按鈕。若彈出授權視窗，請點選「核准存取/進階授權」完成核准。
 * 7. 複製產生的「網頁應用程式網址 (Web App URL)」，這就是您的 GAS 網址！
 * 8. 在 Discord 頻道輸入 `!setup_gas <您的 GAS 網址>` 完成綁定。
 */

function doPost(e) {
  // 1. 啟用排隊鎖，防止多人同時點擊按鈕時造成寫入衝突或資料遺失
  var lock = LockService.getScriptLock();
  try {
    // 最多等待 30 秒取得寫入許可
    lock.waitLock(30000); 
    
    // 解析 Discord 機器人發過來的 JSON 資料
    var params = JSON.parse(e.postData.contents);
    var name = params.name;
    var roles = params.roles;
    var day = params.day;
    
    // 2. 取得目前活動的試算表
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getActiveSheet();
    
    // 3. 根據報名天數 (day) 進行局部向下推擠並寫入
    if (day === "星期六") {
      // 週六待編制區：局部推擠 A2:B2 以下的資料
      var rangeSat = sheet.getRange("A2:B2");
      rangeSat.insertCells(SpreadsheetApp.Dimension.ROWS); // 局部向下推擠
      
      // 寫入最新報名資料到 A2, B2
      sheet.getRange(2, 1).setValue(name);  // A2 填入遊戲 ID (第 1 欄)
      sheet.getRange(2, 2).setValue(roles); // B2 填入武學 (第 2 欄)
      
    } else {
      // 週日待編制區（"星期日" 或 "反應報名"）：局部推擠 D2:E2 以下的資料
      var rangeSun = sheet.getRange("D2:E2");
      rangeSun.insertCells(SpreadsheetApp.Dimension.ROWS); // 局部向下推擠
      
      // 寫入最新報名資料到 D2, E2
      sheet.getRange(2, 4).setValue(name);  // D2 填入遊戲 ID (第 4 欄)
      sheet.getRange(2, 5).setValue(roles); // E2 填入武學 (第 5 欄)
    }
    
    // 回傳成功狀態 JSON 給機器人
    return ContentService.createTextOutput(JSON.stringify({ "status": "success" }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (err) {
    // 發生異常時回傳錯誤訊息
    return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    // 釋放排隊鎖，讓下一個等待的請求可以進入處理
    lock.releaseLock();
  }
}
