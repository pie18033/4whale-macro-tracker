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
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}

def get_binance(symbol):
    try:
        # 1. 價格 & 資金費率
        t_r = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}", headers=HEADERS).json()
        price = float(t_r['markPrice'])
        funding_rate = float(t_r['lastFundingRate'])

        # 2. 未平倉量 (OI)
        oi_r = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}", headers=HEADERS).json()
        open_interest = float(oi_r['openInterest']) * price # 換算成 USD

        # 3. 散戶帳戶比
        acc_r = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1", headers=HEADERS).json()
        ls_acc_ratio = float(acc_r[0]['longShortRatio'])
        long_acc = ls_acc_ratio / (1 + ls_acc_ratio)
        short_acc = 1 / (1 + ls_acc_ratio)

        # 4. 大戶持倉比
        pos_r = requests.get(f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1", headers=HEADERS).json()
        ls_pos_ratio = float(pos_r[0]['longShortRatio'])
        long_pos = ls_pos_ratio / (1 + ls_pos_ratio)
        short_pos = 1 / (1 + ls_pos_ratio)

        return {
            "exchange": "Binance", "price": price, "funding_rate": funding_rate, "open_interest": open_interest,
            "long_acc_ratio": long_acc, "short_acc_ratio": short_acc, "ls_acc_ratio": ls_acc_ratio,
            "long_pos_ratio": long_pos, "short_pos_ratio": short_pos, "ls_pos_ratio": ls_pos_ratio,
            "long_vol_usd": open_interest * long_pos, "short_vol_usd": open_interest * short_pos
        }
    except Exception as e: 
        print(f"Binance 錯誤: {e}")
        return None

def get_bitget(symbol):
    try:
        base = "https://api.bitget.com/api/v2/mix/market"
        params = f"symbol={symbol}&productType=USDT-FUTURES"
        
        # 抓取綜合數據
        r_tick = requests.get(f"{base}/ticker?{params}", headers=HEADERS).json()['data'][0]
        r_acc = requests.get(f"{base}/account-long-short?{params}", headers=HEADERS).json()['data'][0]
        r_pos = requests.get(f"{base}/position-long-short?{params}", headers=HEADERS).json()['data'][0]
        r_fund = requests.get(f"{base}/current-fund-rate?{params}", headers=HEADERS).json()['data'][0]
        r_oi = requests.get(f"{base}/open-interest?{params}", headers=HEADERS).json()['data']['openInterestList'][0]

        price = float(r_tick['lastPr'])
        oi_usd = float(r_oi['size']) * price
        
        l_acc = float(r_acc['longAccountRatio'])
        s_acc = float(r_acc['shortAccountRatio'])
        l_pos = float(r_pos['longPositionRatio'])
        s_pos = float(r_pos['shortPositionRatio'])

        return {
            "exchange": "Bitget", "price": price, "funding_rate": float(r_fund['fundingRate']), "open_interest": oi_usd,
            "long_acc_ratio": l_acc, "short_acc_ratio": s_acc, "ls_acc_ratio": l_acc / s_acc if s_acc else None,
            "long_pos_ratio": l_pos, "short_pos_ratio": s_pos, "ls_pos_ratio": l_pos / s_pos if s_pos else None,
            "long_vol_usd": oi_usd * l_pos, "short_vol_usd": oi_usd * s_pos
        }
    except Exception as e:
        print(f"Bitget 錯誤: {e}")
        return None

def collect_and_save():
    targets = ["BTCUSDT", "ETHUSDT"]
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"⏰ 執行時間 (UTC): {current_time}")

    for symbol in targets:
        print(f"🔍 正在獲取 {symbol} 數據...")
        results = [get_binance(symbol), get_bitget(symbol)]
        
        for res in results:
            if res:
                # 將字典加上 time 和 symbol，準備寫入
                res["time"] = current_time
                res["symbol"] = symbol
                
                try:
                    supabase.table("crypto_macro_data").insert(res).execute()
                    print(f"✅ {symbol} ({res['exchange']}) 寫入成功")
                except Exception as e:
                    print(f"❌ {symbol} ({res['exchange']}) 寫入失敗: {e}")

if __name__ == "__main__":
    collect_and_save()
