import requests
import os
import time
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 錯誤：找不到 Supabase 金鑰，請檢查環境變數。")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}

# ==========================================
# 📡 交易所 API 抓取邏輯
# ==========================================

def get_binance(symbol):
    try:
        t_r = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}", headers=HEADERS, timeout=10).json()
        price = float(t_r['markPrice'])

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
        # 💡 修復 1：OKX 宏觀數據要求使用 ccy 參數 (如 BTC)
        url_acc = f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={coin}&period=5m"
        r_acc = requests.get(url_acc, headers=HEADERS, timeout=10).json()
        
        # 💡 修復 2：OKX 價格 API 要求使用完整的 instId (如 BTC-USDT-SWAP)
        url_price = f"https://www.okx.com/api/v5/market/ticker?instId={coin}-USDT-SWAP"
        r_price = requests.get(url_price, headers=HEADERS, timeout=10).json()
        
        # 防呆機制：如果回傳沒資料，立刻跳出並印出原因，防止 IndexError
        if not r_acc.get('data') or not r_price.get('data'):
            raise ValueError(f"API 回傳為空。多空比回傳: {r_acc.get('msg')} | 價格回傳: {r_price.get('msg')}")

        price = float(r_price['data'][0]['last'])
        
        # OKX 僅提供帳戶多空比，反推百分比
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
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        r = requests.get(url, headers=HEADERS, timeout=10).json()
        price = float(r['result']['list'][0]['lastPrice'])
        return {
            "exchange": "Bybit", "price": price, 
            "long_acc_ratio": None, "short_acc_ratio": None, "ls_acc_ratio": None,
            "long_pos_ratio": None, "short_pos_ratio": None, "ls_pos_ratio": None,
            "open_interest": None, "long_vol_usd": None, "short_vol_usd": None
        }
    except Exception as e: 
        print(f"⚠️ Bybit 抓取失敗: {e}")
        return None

# ==========================================
# 🚀 主程式執行
# ==========================================

def collect_and_save():
    targets = [
        {"symbol": "BTCUSDT", "okx": "BTC"},
        {"symbol": "ETHUSDT", "okx": "ETH"}
    ]
    
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n⏰ 開始執行爬蟲，時間 (UTC): {current_time}")

    for t in targets:
        symbol = t["symbol"]
        print(f"\n🔍 正在獲取 {symbol} 各交易所數據...")
        
        results = [
            get_binance(symbol),
            get_bitget(symbol),
            get_okx(t['okx']),
            get_bybit(symbol)
        ]
        
        for res in results:
            if res:
                res["time"] = current_time
                res["symbol"] = symbol
                
                try:
                    supabase.table("crypto_macro_data").insert(res).execute()
                    print(f"✅ [{res['exchange']}] 寫入資料庫成功！ (價格: {res['price']})")
                except Exception as e:
                    print(f"❌ [{res['exchange']}] 寫入 Supabase 失敗: {e}")

# ==========================================
# 🚀 主程式執行
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動單次雲端爬蟲任務")
    collect_and_save()
    print("✅ 任務結束！")
