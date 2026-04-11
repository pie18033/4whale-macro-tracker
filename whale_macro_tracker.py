import requests
import os
import time
import threading
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import Flask

# 初始化 Flask
app = Flask(__name__)
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 錯誤：找不到 Supabase 金鑰。")

# 建立 Supabase 連線
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}

# ==========================================
# 📡 交易所 API 抓取邏輯
# ==========================================
def get_binance(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 451: return None
        price = float(res.json()['markPrice'])
        oi_r = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}", headers=HEADERS, timeout=10).json()
        open_interest = float(oi_r['openInterest']) * price 
        acc_r = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1", headers=HEADERS, timeout=10).json()
        ls_acc_ratio = float(acc_r[0]['longShortRatio'])
        pos_r = requests.get(f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1", headers=HEADERS, timeout=10).json()
        ls_pos_ratio = float(pos_r[0]['longShortRatio'])
        return {
            "exchange": "Binance", "price": price, "open_interest": open_interest,
            "long_acc_ratio": ls_acc_ratio / (1 + ls_acc_ratio), "short_acc_ratio": 1 / (1 + ls_acc_ratio), "ls_acc_ratio": ls_acc_ratio,
            "long_pos_ratio": ls_pos_ratio / (1 + ls_pos_ratio), "short_pos_ratio": 1 / (1 + ls_pos_ratio), "ls_pos_ratio": ls_pos_ratio,
            "long_vol_usd": open_interest * (ls_pos_ratio / (1 + ls_pos_ratio)), "short_vol_usd": open_interest * (1 / (1 + ls_pos_ratio))
        }
    except: return None

def get_bitget(symbol):
    try:
        base = "https://api.bitget.com/api/v2/mix/market"
        params = f"symbol={symbol}&productType=USDT-FUTURES"
        r_tick = requests.get(f"{base}/ticker?{params}", headers=HEADERS, timeout=10).json()['data'][0]
        r_acc = requests.get(f"{base}/account-long-short?{params}", headers=HEADERS, timeout=10).json()['data'][0]
        r_pos = requests.get(f"{base}/position-long-short?{params}", headers=HEADERS, timeout=10).json()['data'][0]
        r_oi = requests.get(f"{base}/open-interest?{params}", headers=HEADERS, timeout=10).json()['data']['openInterestList'][0]
        price = float(r_tick['lastPr'])
        oi_usd = float(r_oi['size']) * price
        l_acc, s_acc = float(r_acc['longAccountRatio']), float(r_acc['shortAccountRatio'])
        l_pos, s_pos = float(r_pos['longPositionRatio']), float(r_pos['shortPositionRatio'])
        return {
            "exchange": "Bitget", "price": price, "open_interest": oi_usd,
            "long_acc_ratio": l_acc, "short_acc_ratio": s_acc, "ls_acc_ratio": l_acc / s_acc if s_acc else None,
            "long_pos_ratio": l_pos, "short_pos_ratio": s_pos, "ls_pos_ratio": l_pos / s_pos if s_pos else None,
            "long_vol_usd": oi_usd * l_pos, "short_vol_usd": oi_usd * s_pos
        }
    except: return None

def get_okx(coin):
    try:
        r_acc = requests.get(f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={coin}&period=5m", headers=HEADERS, timeout=10).json()
        r_price = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={coin}-USDT-SWAP", headers=HEADERS, timeout=10).json()
        price = float(r_price['data'][0]['last'])
        ls_acc_ratio = float(r_acc['data'][0][1])
        return {
            "exchange": "OKX", "price": price, 
            "long_acc_ratio": ls_acc_ratio / (1 + ls_acc_ratio), "short_acc_ratio": 1 / (1 + ls_acc_ratio), "ls_acc_ratio": ls_acc_ratio,
            "long_pos_ratio": None, "short_pos_ratio": None, "ls_pos_ratio": None,
            "open_interest": None, "long_vol_usd": None, "short_vol_usd": None
        }
    except: return None

def get_bybit(symbol):
    try:
        r_tick = requests.get(f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}", headers=HEADERS, timeout=10).json()['result']['list'][0]
        price = float(r_tick['lastPrice'])
        oi_usd = float(r_tick['openInterest']) * price if 'openInterest' in r_tick and r_tick['openInterest'] else None
        r_acc = requests.get(f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={symbol}&period=5min&limit=1", headers=HEADERS, timeout=10).json()
        b_ratio = float(r_acc['result']['list'][0]['buyRatio']) if r_acc.get('result') and r_acc['result'].get('list') else None
        s_ratio = float(r_acc['result']['list'][0]['sellRatio']) if r_acc.get('result') and r_acc['result'].get('list') else None
        return {
            "exchange": "Bybit", "price": price, "open_interest": oi_usd,
            "long_acc_ratio": b_ratio, "short_acc_ratio": s_ratio, "ls_acc_ratio": b_ratio / s_ratio if s_ratio else None,
            "long_pos_ratio": None, "short_pos_ratio": None, "ls_pos_ratio": None,
            "long_vol_usd": None, "short_vol_usd": None
        }
    except: return None

# ==========================================
# 🚀 爬蟲與無限迴圈邏輯
# ==========================================
def collect_and_save():
    targets = [{"symbol": "BTCUSDT", "okx": "BTC"}, {"symbol": "ETHUSDT", "okx": "ETH"}]
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n⏰ [{current_time}] 開始執行爬蟲任務...")

    for t in targets:
        symbol = t["symbol"]
        results = [get_binance(symbol), get_bitget(symbol), get_okx(t['okx']), get_bybit(symbol)]
        for res in results:
            if res:
                res["time"] = current_time
                res["symbol"] = symbol
                try:
                    supabase.table("crypto_macro_data").insert(res).execute()
                    print(f"✅ [{res['exchange']}] 寫入成功！")
                except Exception as e:
                    print(f"❌ 寫入失敗: {e}")

# 💡 新增：背景無限迴圈 (每 30 分鐘執行一次)
def run_scraper_loop():
    # 開機先等待 10 秒，讓伺服器完全啟動再開始抓
    time.sleep(10)
    while True:
        try:
            collect_and_save()
        except Exception as e:
            print(f"⚠️ 迴圈執行異常: {e}")
        
        print("⏳ 爬蟲結束，進入 30 分鐘休眠等待下一次...")
        time.sleep(1800)  # 暫停 1800 秒 = 30 分鐘

# ==========================================
# 🌐 Flask 伺服器 (僅負責回應 cron-job 保持喚醒)
# ==========================================
@app.route('/')
def home():
    # 💡 cron-job 只要來敲門，就回覆它機器醒著
    return "✅ Whale Tracker is Awake and Running!", 200

# 保留手動觸發功能，以防你隨時想補資料
# ... (上面的 get_binance, collect_and_save 等邏輯完全不動) ...

@app.route('/')
def home():
    return "✅ Whale Tracker is Awake and Running!", 200

@app.route('/scrape')
def manual_scrape():
    thread = threading.Thread(target=collect_and_save)
    thread.start()
    return "✅ 手動爬蟲已觸發", 200

# 💡 關鍵修復：把啟動背景迴圈的指令移到最外層！
# 這樣 Render (Gunicorn) 在載入這支檔案時，就會立刻執行這兩行，生出爬蟲小精靈
scraper_thread = threading.Thread(target=run_scraper_loop, daemon=True)
scraper_thread.start()

# 底下這段留給本地端測試用，Render 會自動忽略它
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
