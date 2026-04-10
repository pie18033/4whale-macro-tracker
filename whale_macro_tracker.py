import requests
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 錯誤：找不到 Supabase 金鑰。")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# ==========================================
# 📡 交易所 API 抓取邏輯
# ==========================================

def get_binance(symbol):
    try:
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200: return None
        acc_ratio = float(r.json()[0]['longShortRatio'])
        price = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}").json()['price'])
        return {"exchange": "Binance", "price": price, "ls_acc": acc_ratio, "ls_pos": acc_ratio} 
    except: return None

def get_okx(instId):
    try:
        url = f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?instId={instId}"
        r = requests.get(url, headers=HEADERS, timeout=10).json()
        price = float(requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={instId}-SWAP").json()['data'][0]['last'])
        return {"exchange": "OKX", "price": price, "ls_acc": float(r['data'][0][1]), "ls_pos": float(r['data'][0][1])}
    except: return None

def get_bitget(symbol):
    try:
        base = "https://api.bitget.com/api/v2/mix/market"
        params = f"symbol={symbol}&productType=USDT-FUTURES"
        r_acc = requests.get(f"{base}/account-long-short?{params}", headers=HEADERS, timeout=10).json()
        r_tick = requests.get(f"{base}/ticker?{params}", headers=HEADERS, timeout=10).json()
        r_pos = requests.get(f"{base}/position-long-short?{params}", headers=HEADERS, timeout=10).json()
        return {
            "exchange": "Bitget", 
            "price": float(r_tick['data'][0]['lastPr']), 
            "ls_acc": float(r_acc['data'][0]['longAccountRatio']) / float(r_acc['data'][0]['shortAccountRatio']), 
            "ls_pos": float(r_pos['data'][0]['longPositionRatio']) / float(r_pos['data'][0]['shortPositionRatio'])
        }
    except: return None

def get_bybit(symbol):
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        r = requests.get(url, headers=HEADERS, timeout=10).json()
        return {"exchange": "Bybit", "price": float(r['result']['list'][0]['lastPrice']), "ls_acc": 1.0, "ls_pos": 1.0}
    except: return None

# ==========================================
# 🚀 主程式執行
# ==========================================

def collect_and_save():
    targets = [
        {"symbol": "BTCUSDT", "okx": "BTC"},
        {"symbol": "ETHUSDT", "okx": "ETH"}
    ]
    
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"⏰ 執行時間 (UTC): {current_time}")

    for t in targets:
        symbol = t["symbol"]
        print(f"🔍 正在獲取 {symbol} 各交易所數據...")
        
        # 把四家交易所的資料都抓一輪
        results = [
            get_binance(symbol),
            get_okx(t['okx']),
            get_bitget(symbol),
            get_bybit(symbol)
        ]
        
        # 只要有抓到，就各自寫入 crypto_macro_data，並標記交易所名稱
        for res in results:
            if res:
                db_data = {
                    "time": current_time,
                    "symbol": symbol,
                    "exchange": res["exchange"],
                    "price": res["price"],
                    "ls_ratio": res["ls_pos"],
                    "long_acc_ratio": res["ls_acc"],
                    "short_acc_ratio": 1.0,
                    "long_vol_usd": 0,
                    "short_vol_usd": 0
                }
                try:
                    # 這次絕對乖乖只寫入 crypto_macro_data！
                    supabase.table("crypto_macro_data").insert(db_data).execute()
                    print(f"✅ {symbol} ({res['exchange']}) 寫入成功")
                except Exception as e:
                    print(f"❌ {symbol} ({res['exchange']}) 寫入失敗: {e}")

if __name__ == "__main__":
    collect_and_save()
