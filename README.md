英文選擇題測驗系統（English Quiz System）

本系統為 OOAD（物件導向分析與設計）課程開發的 Django 網頁應用，支援學生測驗、答題紀錄與 GPT 詳解。

功能特色

學生與管理員帳號登入、註冊、登出

支援詞彙、文法、克漏字與閱讀理解題型

自動批改、統計答題正確率

每題可查閱 GPT 解釋

題目收藏與備註功能

僅限管理員使用者權限管理介面

⚙️ 安裝教學

1. 下載專案

git clone https://github.com/weiber82/english-quiz-system.git
cd english-quiz-system

2. 建立虛擬環境

python -m venv .venv
.venv\Scripts\activate    # Windows

3. 安裝所需套件

pip install -r requirements.txt

4. 設定 OpenAI API 金鑰

建立 .env 檔案：

OPENAI_API_KEY=your_openai_key_here

5. 建立資料庫

python manage.py migrate

6. 建立管理員帳號

python manage.py createsuperuser

7. 執行系統

python manage.py runserver

本機網址：http://127.0.0.1:8000/

預設角色說明

帳號名稱
admin 密碼:admin 權限:管理員
student 密碼:student 權限:學生

測驗流程

選擇題型與題數，開始測驗

每題作答，送出後顯示對錯與詳解

最後呈現成績統計與錯題清單，可前往 GPT 詳解頁
