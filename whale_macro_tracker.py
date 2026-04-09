import requests
import os
from datetime import datetime
from supabase import create_client, Client
import time
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 錯誤：找不到 Supabase 金鑰。")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 💡 關鍵：模擬真實瀏覽器的 Header，避免被伺服器判定為機器人而封鎖
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json'
}

def get_binance_data(symbol):
    try:
        # 抓取帳戶多空比
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        r = requests.get(url, headers=HEADERS, timeout=15)
        
        # 如果狀態碼不是 200，印出錯誤
        if r.status_code != 200:
            print(f"⚠️ Binance API 拒絕存取，狀態碼: {r.status_code}")
            return None
            
        data_list = r.json()
        if not data_list: return None
        acc_ratio = float(data_list[0]['longShortRatio'])
        
        # 抓取價格
        t_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        price = float(requests.get(t_url, headers=HEADERS).json()['price'])
        
        # 抓取大戶持倉比
        p_url = f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1"
        pos_r = requests.get(p_url, headers=HEADERS).json()
        pos_ratio = float(pos_r[0]['longShortRatio'])
        
        return {"price": price, "ls_acc_ratio": acc_ratio, "ls_pos_ratio": pos_ratio}
    except Exception as e:
        print(f"❌ Binance {symbol} 處理失敗: {e}")
        return None

def get_bitget_data(symbol):
    try:
        symbol_fixed = symbol.replace("USDT", "")
        url = f"https://api.bitget.com/api/v2/mix/market/long-short-ratio?symbol={symbol_fixed}USDT&productType=USDT-FUTURES&period=5m"
        r = requests.get(url, headers=HEADERS, timeout=15).json()
        
        # 檢查回傳資料結構
        if 'data' not in r or not r['data']:
            print(f"⚠️ Bitget 回傳無效資料: {r.get('msg', '未知錯誤')}")
            return None
            
        d = r['data'][0]
        return {
            "price": float(d['price']),
            "ls_acc_ratio": float(d['buySellRatio']),
            "ls_pos_ratio": float(d['posRatio'])
        }
    except Exception as e:
        print(f"❌ Bitget {symbol} 處理失敗: {e}")
        return None

def collect_and_save():
    targets = [
        {"symbol": "BTCUSDT", "table": "whale_data", "price_key": "btc_price"},
        {"symbol": "ETHUSDT", "table": "eth_whale_data", "price_key": "eth_price"}
    ]

    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"⏰ 開始執行抓取任務 (UTC): {current_time}")

    for target in targets:
        symbol = target["symbol"]
        print(f"🔍 正在處理 {symbol}...")

        # 嘗試從 Binance 抓取，如果失敗改用 Bitget
        data = get_binance_data(symbol)
        if not data:
            print(f"🔄 Binance 失敗，嘗試從 Bitget 獲取 {symbol}...")
            data = get_bitget_data(symbol)

        if data:
            db_data = {
                "time": current_time,
                target["price_key"]: data["price"],
                "ls_ratio": data["ls_pos_ratio"],
                "long_acc_ratio": data["ls_acc_ratio"],
                "short_acc_ratio": 1.0,
                "long_vol_usd": 0,
                "short_vol_usd": 0
            }
            try:
                supabase.table(target["table"]).insert(db_data).execute()
                print(f"✅ {symbol} 成功寫入資料庫！")
            except Exception as e:
                print(f"❌ {symbol} 寫入 Supabase 失敗: {e}")
        else:
            print(f"💀 無法從任何來源取得 {symbol} 資料。")

if __name__ == "__main__":
    collect_and_save()
