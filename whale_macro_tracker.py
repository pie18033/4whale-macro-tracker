import requests
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# 初始化 Supabase
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# --- 各交易所抓取函數 ---

def get_binance(symbol):
    try:
        # 幣安期貨數據 (GitHub IP 容易報 451)
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200: return None
        acc_ratio = float(r.json()[0]['longShortRatio'])
        price = float(requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}").json()['price'])
        return {"price": price, "ls_acc": acc_ratio, "ls_pos": acc_ratio} # 幣安持倉比需另一個 endpoint，此處簡化
    except: return None

def get_okx(instId):
    try:
        url = f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?instId={instId}"
        r = requests.get(url, headers=HEADERS).json()
        price = float(requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={instId}-SWAP").json()['data'][0]['last'])
        return {"price": price, "ls_acc": float(r['data'][0][1]), "ls_pos": float(r['data'][0][1])}
    except: return None

def get_bitget(symbol):
    try:
        base = "https://api.bitget.com/api/v2/mix/market"
        params = f"symbol={symbol}&productType=USDT-FUTURES"
        r_acc = requests.get(f"{base}/account-long-short?{params}", headers=HEADERS).json()
        r_tick = requests.get(f"{base}/ticker?{params}", headers=HEADERS).json()
        return {"price": float(r_tick['data'][0]['lastPr']), "ls_acc": float(r_acc['data'][0]['longAccountRatio'])/float(r_acc['data'][0]['shortAccountRatio']), "ls_pos": 1.0}
    except: return None

def get_bybit(symbol):
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        r = requests.get(url, headers=HEADERS).json()
        return {"price": float(r['result']['list'][0]['lastPrice']), "ls_acc": 1.0, "ls_pos": 1.0}
    except: return None

# --- 主執行邏輯 ---

def collect_and_save():
    targets = [
        {"symbol": "BTCUSDT", "okx": "BTC", "table": "whale_data", "price_key": "btc_price"},
        {"symbol": "ETHUSDT", "okx": "ETH", "table": "eth_whale_data", "price_key": "eth_price"}
    ]
    
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    for t in targets:
        print(f"🔍 正在同步 {t['symbol']}...")
        # 這裡的邏輯是：嘗試抓取四家，只要有一家成功就寫入
        # 你可以根據需求修改為「平均值」或「加權值」
        data = get_binance(t['symbol']) or get_okx(t['okx']) or get_bitget(t['symbol']) or get_bybit(t['symbol'])
        
        if data:
            db_data = {
                "time": current_time,
                t["price_key"]: data["price"],
                "ls_ratio": data["ls_pos"],
                "long_acc_ratio": data["ls_acc"],
                "short_acc_ratio": 1.0,
                "long_vol_usd": 0, "short_vol_usd": 0
            }
            supabase.table(t["table"]).insert(db_data).execute()
            print(f"✅ {t['symbol']} 寫入成功")
        else:
            print(f"❌ {t['symbol']} 全部交易所抓取失敗")

if __name__ == "__main__":
    collect_and_save()
