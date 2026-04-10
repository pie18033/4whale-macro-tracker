import requests
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import Flask # 💡 新增 Flask 讓 Render 運行

# 初始化 Flask
app = Flask(__name__)
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}

# ... (中間的 get_binance, get_bitget, get_okx, get_bybit 函數保持不變) ...

def collect_and_save():
    targets = [{"symbol": "BTCUSDT", "okx": "BTC"}, {"symbol": "ETHUSDT", "okx": "ETH"}]
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"⏰ 開始爬蟲任務: {current_time}")

    for t in targets:
        symbol = t["symbol"]
        results = [get_binance(symbol), get_bitget(symbol), get_okx(t['okx']), get_bybit(symbol)]
        for res in results:
            if res:
                res["time"] = current_time
                res["symbol"] = symbol
                supabase.table("crypto_macro_data").insert(res).execute()
    return f"Done at {current_time}"

# 💡 新增：建立一個網頁路徑，cron-job.org 只要訪問這個路徑就會觸發爬蟲
@app.route('/')
def home():
    return "Whale Tracker is Running!"

@app.route('/scrape')
def trigger_scrape():
    result = collect_and_save()
    return f"✅ 爬蟲執行成功: {result}", 200

if __name__ == "__main__":
    # Render 會自動分配 PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
