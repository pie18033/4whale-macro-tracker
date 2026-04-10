import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from bokeh.plotting import figure
from bokeh.models import LinearAxis, Range1d, WheelZoomTool, HoverTool
from bokeh.palettes import Category10

# 網頁基本設定 (必須放在第一行)
st.set_page_config(page_title="全市場巨鯨監控", page_icon="🐋", layout="wide")

# 讀取環境變數
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 初始化 Supabase
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# 獲取並清理資料
@st.cache_data(ttl=60) # 快取 60 秒，避免狂刷 API
def load_data():
    res = supabase.table("crypto_macro_data").select("*").order("time", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # 轉換為台灣時間 (UTC+8)
        df['time'] = pd.to_datetime(df['time']) + pd.Timedelta(hours=8)
        # 計算多空帳戶比 (散戶情緒)
        df['ls_acc_ratio'] = df.apply(
            lambda row: row['long_acc_ratio'] / row['short_acc_ratio'] if pd.notnull(row['short_acc_ratio']) and row['short_acc_ratio'] != 0 else None, 
            axis=1
        )
    return df

# 繪製專業 Bokeh 雙軸圖表
def draw_macro_chart(df, symbol):
    df_symbol = df[df['symbol'] == symbol].copy()
    if df_symbol.empty:
        st.warning(f"目前沒有 {symbol} 的資料。")
        return

    # 1. 建立圖表 (Y 軸設定為自動 Scale: start=None, end=None)
    p = figure(
        x_axis_type="datetime",
        title=f"{symbol} 全市場籌碼與價格監控",
        height=450,
        y_range=Range1d(start=None, end=None), 
        tools="pan,box_zoom,reset,save", # 預設工具不包含滾輪
        toolbar_location="above"
    )
    
    # 2. 加入 X 軸獨立滾輪縮放 (不會牽扯到 Y 軸)
    wheel_zoom = WheelZoomTool(dimensions="width")
    p.add_tools(wheel_zoom)
    p.toolbar.active_scroll = wheel_zoom # 預設啟用滾輪

    # 3. 設定左側 Y 軸 (多空比)
    p.yaxis.axis_label = "散戶情緒 (多空帳戶比)"
    p.yaxis.axis_label_text_color = "orange"

    # 4. 新增右側 Y 軸 (價格)
    p.extra_y_ranges = {"price_axis": Range1d(start=None, end=None)}
    p.add_layout(LinearAxis(y_range_name="price_axis", axis_label="價格 (USD)", axis_label_text_color="white"), 'right')

    # 5. 畫線 - 各交易所的多空帳戶比 (左軸)
    exchanges = df_symbol['exchange'].dropna().unique()
    colors = Category10[max(3, len(exchanges))]
    
    for i, exchange in enumerate(exchanges):
        df_ex = df_symbol[df_symbol['exchange'] == exchange]
        # 過濾掉沒有帳戶比資料的交易所 (例如舊的 Bybit)
        if not df_ex['ls_acc_ratio'].isnull().all():
            p.line(df_ex['time'], df_ex['ls_acc_ratio'], color=colors[i], legend_label=f"{exchange} 散戶情緒", line_width=2)
    
    # 6. 畫線 - 價格線 (右軸)
    # 取第一家有價格資料的交易所來畫價格線即可 (通常價格差不多)
    df_price = df_symbol[df_symbol['exchange'] == exchanges[0]]
    p.line(df_price['time'], df_price['price'], color="white", line_dash="dashed", legend_label="價格", y_range_name="price_axis", line_width=2, alpha=0.8)

    # 7. 圖例設定 (點擊可隱藏線條)
    p.legend.location = "top_left"
    p.legend.click_policy = "hide"
    p.legend.background_fill_alpha = 0.5

    # 顯示圖表
    st.bokeh_chart(p, use_container_width=True)

# ==========================================
# 網頁 UI 渲染
# ==========================================
st.title("🐋 巨鯨合約宏觀監控儀表板")
st.markdown("觀測四大交易所籌碼動向，尋找大戶與散戶的背離訊號。")

df_main = load_data()

if df_main.empty:
    st.error("⚠️ 資料庫目前沒有資料，請確認後端爬蟲是否正在執行！")
else:
    # 建立兩個分頁
    tab1, tab2 = st.tabs(["🔥 BTCUSDT", "💎 ETHUSDT"])
    
    with tab1:
        draw_macro_chart(df_main, "BTCUSDT")
        st.dataframe(df_main[df_main['symbol'] == "BTCUSDT"].sort_values('time', ascending=False).head(20), use_container_width=True)
        
    with tab2:
        draw_macro_chart(df_main, "ETHUSDT")
        st.dataframe(df_main[df_main['symbol'] == "ETHUSDT"].sort_values('time', ascending=False).head(20), use_container_width=True)
