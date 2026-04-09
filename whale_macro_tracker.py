import requests
import os
from datetime import datetime
from supabase import create_client, Client
import time
from dotenv import load_dotenv

# 讀取本地環境變數 (GitHub 上線時會自動失效，改由 Secrets 讀取)
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
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        r = requests.get(url, timeout=10).json()
        acc_ratio = float(r[0]['longShortRatio'])
        
        # 獲取價格與持倉量
        ticker_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        price = float(requests.get(ticker_url).json()['price'])
        
        # 獲取大戶持倉比
        pos_url = f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1"
        pos_r = requests.get(pos_url).json()
        pos_ratio = float(pos_r[0]['longShortRatio'])
        
        return {
            "exchange": "Binance",
            "symbol": symbol,
            "price": price,
            "ls_acc_ratio": acc_ratio,
            "ls_pos_ratio": pos_ratio,
            "long_vol_usd": None,  # 這些在宏觀圖表可選填
            "short_vol_usd": None
        }
    except: return None

def get_bitget_data(symbol):
    try:
        # 簡化版邏輯，確保能抓到核心帳戶比與大戶持倉比
        symbol_fixed = symbol.replace("USDT", "")
        url = f"https://api.bitget.com/api/v2/mix/market/long-short-ratio?symbol={symbol_fixed}USDT&productType=USDT-FUTURES&period=5m"
        r = requests.get(url).json()['data'][0]
        return {
            "exchange": "Bitget",
            "symbol": symbol,
            "price": float(r['price']),
            "ls_acc_ratio": float(r['buySellRatio']),
            "ls_pos_ratio": float(r['posRatio']),
            "long_vol_usd": None,
            "short_vol_usd": None
        }
    except: return None

# ... (以此類推 Bybit 與 OKX 的抓取函數，此處簡化示意)

def send_tg_notify(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"})
    except: pass

# ==========================================
# 🚀 主程式執行
# ==========================================
def collect_and_save():
    targets = ["BTCUSDT", "ETHUSDT"]
    for symbol in targets:
        print(f"正在處理 {symbol}...")
        results = [
            get_binance_data(symbol),
            get_bitget_data(symbol),
            # 此處可補上 Bybit/OKX 函數
        ]
        
        valid_data = [d for d in results if d is not None]
        if valid_data:
            # 寫入 Supabase
            try:
                for data in valid_data:
                    data['time'] = datetime.utcnow().isoformat()
                    supabase.table("crypto_macro_data").insert(data).execute()
                print(f"✅ {symbol} 資料成功寫入 Supabase")
            except Exception as e:
                print(f"❌ 寫入失敗: {e}")
        
    print("🏁 所有任務已完成！")

if __name__ == "__main__":
    # GitHub Actions 不需要 while True，執行一次即結束
    collect_and_save()