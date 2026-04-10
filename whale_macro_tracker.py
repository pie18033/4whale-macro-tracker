import requests
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import Flask
import threading

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
# 📡 交易所 API 抓取邏輯 (全套完整版)
# ==========================================

def get_binance(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        
        if res.status_code == 451:
            print(f"⚠️ Binance 抓取失敗: HTTP 451 (伺服器 IP 遭幣安封鎖)")
            return None
            
        price = float(res.json()['markPrice'])

        oi_r = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}", headers=HEADERS, timeout=10).json()
        open_interest = float(oi_r['openInterest']) * price 

        acc_r = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1", headers=HEADERS, timeout=10).json()
        ls_acc_ratio = float(acc_r[0]['longShortRatio'])
        long_acc = ls_acc_ratio / (1 + ls_acc_ratio)
        short_acc = 1 / (1 + ls_acc_ratio)

        pos_r = requests.get(f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1", headers=HEADERS, timeout=10).json()
        ls_pos_ratio = float(pos_r[0]['longShortRatio'])
        long_pos = ls_pos_ratio / (1 + ls_pos_ratio)
        short_pos = 1 / (1 + ls_pos_ratio)

        return {
            "exchange": "Binance", "price": price, "open_interest": open_interest,
            "long_acc_ratio": long_acc, "short_acc_ratio": short_acc, "ls_acc_ratio": ls_acc_ratio,
            "long_pos_ratio": long_pos, "short_pos_ratio": short_pos, "ls_pos_ratio": ls_pos_ratio,
            "long_vol_usd": open_interest * long_pos, "short_vol_usd": open_interest * short_pos
        }
    except Exception as e: 
        print(f"⚠️ Binance 抓取失敗: {e}")
        return None

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
        
        l_acc = float(r_acc['longAccountRatio'])
        s_acc = float(r_acc['shortAccountRatio'])
        l_pos = float(r_pos['longPositionRatio'])
        s_pos = float(r_pos['shortPositionRatio'])

        return {
            "exchange": "Bitget", "price": price, "open_interest": oi_usd,
            "long_acc_ratio": l_acc, "short_acc_ratio": s_acc, "ls_acc_ratio": l_acc / s_acc if s_acc else None,
            "long_pos_ratio": l_pos, "short_pos_ratio": s_pos, "ls_pos_ratio": l_pos / s_pos if s_pos else None,
            "long_vol_usd": oi_usd * l_pos, "short_vol_usd": oi_usd * s_pos
        }
    except Exception as e:
        print(f"⚠️ Bitget 抓取失敗: {e}")
        return None

def get_okx(coin):
    try:
        url_acc = f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={coin}&period=5m"
        r_acc = requests.get(url_acc, headers=HEADERS, timeout=10).json()
        
        url_price = f"https://www.okx.com/api/v5/market/ticker?instId={coin}-USDT-SWAP"
        r_price = requests.get(url_price, headers=HEADERS, timeout=10).json()
        
        if not r_acc.get('data') or not r_price.get('data'):
            raise ValueError(f"API 回傳為空。")

        price = float(r_price['data'][0]['last'])
        ls_acc_ratio = float(r_acc['data'][0][1])
        long_acc = ls_acc_ratio / (1 + ls_acc_ratio)
        short_acc = 1 / (1 + ls_acc_ratio)

        return {
            "exchange": "OKX", "price": price, 
            "long_acc_ratio": long_acc, "short_acc_ratio": short_acc, "ls_acc_ratio": ls_acc_ratio,
            "long_pos_ratio": None, "short_pos_ratio": None, "ls_pos_ratio": None,
            "open_interest": None, "long_vol_usd": None, "short_vol_usd": None
        }
    except Exception as e: 
        print(f"⚠️ OKX 抓取失敗: {e}")
        return None

def get_bybit(symbol):
    try:
        url_tick = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        r_tick = requests.get(url_tick, headers=HEADERS, timeout=10).json()['result']['list'][0]
        price = float(r_tick['lastPrice'])
        
        oi_usd = None
        if 'openInterest' in r_tick and r_tick['openInterest']:
            oi_usd = float(r_tick['openInterest']) * price
            
        url_acc = f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={symbol}&period=5min&limit=1"
        r_acc = requests.get(url_acc, headers=HEADERS, timeout=10).json()
        
        b_ratio, s_ratio = None, None
        if r_acc.get('result') and r_acc['result'].get('list'):
            b_ratio = float(r_acc['result']['list'][0]['buyRatio'])
            s_ratio = float(r_acc['result']['list'][0]['sellRatio'])
            
        return {
            "exchange": "Bybit", "price": price, "open_interest": oi_usd,
            "long_acc_ratio": b_ratio, "short_acc_ratio": s_ratio, 
            "ls_acc_ratio": b_ratio / s_ratio if s_ratio else None,
            "long_pos_ratio": None, "short_pos_ratio": None, "ls_pos_ratio": None,
            "long_vol_usd": None, "short_vol_usd": None
        }
    except Exception as e: 
        print(f"⚠️ Bybit 抓取失敗: {e}")
        return None

# ==========================================
# 🚀 Flask 與 爬蟲排程邏輯
# ==========================================

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
                try:
                    supabase.table("crypto_macro_data").insert(res).execute()
                    print(f"✅ [{res['exchange']}] 寫入資料庫成功！")
                except Exception as db_err:
                    print(f"❌ 寫入 Supabase 失敗: {db_err}")
    return f"Done at {current_time}"

@app.route('/')
def home():
    return "Whale Tracker is Running!"

# (節錄核心部分)
@app.route('/scrape')
def trigger_scrape():
    try:
        # 💡 秒回大法：把苦力活交給背景小精靈
        thread = threading.Thread(target=collect_and_save)
        thread.start()
        
        # 💡 讓伺服器在 0.1 秒內就回覆 200 OK，讓 cron-job 覺得你很準時
        return "✅ 任務已在背景啟動", 200
    except Exception as e:
        return f"❌ 啟動失敗: {e}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
