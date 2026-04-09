import requests
import os
from datetime import datetime
from supabase import create_client, Client
import time
from dotenv import load_dotenv

# 讀取環境變數 (本地讀 .env, 雲端讀 Secrets)
load_dotenv()

# ==========================================
# ⚙️ 環境變數設定
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# 初始化 Supabase
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 錯誤：找不到 Supabase 金鑰，請檢查環境變數設定。")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 📡 交易所 API 抓取邏輯
# ==========================================

def get_binance_data(symbol):
    try:
        # 1. 抓取帳戶多空比
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        r = requests.get(url, timeout=10).json()
        acc_ratio = float(r[0]['longShortRatio'])
        
        # 2. 抓取最新價格
        ticker_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        price = float(requests.get(ticker_url).json()['price'])
        
        # 3. 抓取大戶持倉多空比
        pos_url = f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1"
        pos_r = requests.get(pos_url).json()
        pos_ratio = float(pos_r[0]['longShortRatio'])
        
        return {
            "exchange": "Binance",
            "symbol": symbol,
            "price": price,
            "ls_acc_ratio": acc_ratio,
            "ls_pos_ratio": pos_ratio
        }
    except Exception as e:
        print(f"❌ Binance {symbol} 抓取失敗: {e}")
        return None

def get_bitget_data(symbol):
    try:
        symbol_fixed = symbol.replace("USDT", "")
        # Bitget API 邏輯
        url = f"https://api.bitget.com/api/v2/mix/market/long-short-ratio?symbol={symbol_fixed}USDT&productType=USDT-FUTURES&period=5m"
        r = requests.get(url, timeout=10).json()['data'][0]
        return {
            "exchange": "Bitget",
            "symbol": symbol,
            "price": float(r['price']),
            "ls_acc_ratio": float(r['buySellRatio']),
            "ls_pos_ratio": float(r['posRatio'])
        }
    except Exception as e:
        print(f"❌ Bitget {symbol} 抓取失敗: {e}")
        return None

# ==========================================
# 🚀 核心執行邏輯
# ==========================================

def collect_and_save():
    # 定義要抓取的目標與對應的資料表
    targets = [
        {"symbol": "BTCUSDT", "table": "whale_data", "price_key": "btc_price"},
        {"symbol": "ETHUSDT", "table": "eth_whale_data", "price_key": "eth_price"}
    ]

    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"⏰ 開始執行抓取任務 (UTC): {current_time}")

    for target in targets:
        symbol = target["symbol"]
        table_name = target["table"]
        price_key = target["price_key"]

        print(f"🔍 正在處理 {symbol}...")

        # 這裡示範整合 Binance 和 Bitget 的數據 (也可以只取一家，看你需求)
        # 為了簡單起見，我們以 Binance 為主，若失敗則改用 Bitget
        data_source = get_binance_data(symbol)
        if not data_source:
            data_source = get_bitget_data(symbol)

        if data_source:
            # 組合寫入資料庫的欄位
            # 這裡必須對應你 Supabase 資料表的欄位名稱！
            db_data = {
                "time": current_time,
                price_key: data_source["price"],
                "ls_ratio": data_source["ls_pos_ratio"],
                "long_acc_ratio": data_source["ls_acc_ratio"], # 這裡可以根據你表結構調整
                "short_acc_ratio": 1.0, # 暫時給 1.0 讓 dashboard 計算
                "long_vol_usd": 0,      # 若 API 沒提供則給 0
                "short_vol_usd": 0
            }

            try:
                supabase.table(table_name).insert(db_data).execute()
                print(f"✅ {symbol} 成功寫入資料表 {table_name}")
            except Exception as e:
                print(f"❌ {symbol} 寫入 Supabase 失敗: {e}")
        else:
            print(f"⚠️ 無法取得 {symbol} 的任何數據。")

    print("🏁 所有任務已完成！")

if __name__ == "__main__":
    collect_and_save()
