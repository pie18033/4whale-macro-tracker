import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 網頁基本設定
st.set_page_config(page_title="全市場巨鯨監控", page_icon="🐋", layout="wide")

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

@st.cache_data(ttl=60)
def load_data():
    res = supabase.table("crypto_macro_data").select("*").order("time", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['time'] = pd.to_datetime(df['time']) + pd.Timedelta(hours=8)
        df['ls_acc_ratio'] = df.apply(
            lambda row: row['long_acc_ratio'] / row['short_acc_ratio'] if pd.notnull(row['short_acc_ratio']) and row['short_acc_ratio'] != 0 else None, 
            axis=1
        )
    return df

# 繪製專業 Plotly 雙軸圖表
def draw_macro_chart_plotly(df, symbol):
    df_symbol = df[df['symbol'] == symbol].copy()
    if df_symbol.empty:
        st.warning(f"目前沒有 {symbol} 的資料。")
        return

    # 1. 建立雙 Y 軸畫布
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 2. 畫線 - 各交易所的多空帳戶比 (左軸)
    exchanges = df_symbol['exchange'].dropna().unique()
    for exchange in exchanges:
        df_ex = df_symbol[df_symbol['exchange'] == exchange]
        if not df_ex['ls_acc_ratio'].isnull().all():
            fig.add_trace(
                go.Scatter(
                    x=df_ex['time'], y=df_ex['ls_acc_ratio'], 
                    mode='lines', name=f"{exchange} 散戶",
                    line=dict(width=2)
                ),
                secondary_y=False,
            )

    # 3. 畫線 - 價格線 (右軸)
    df_price = df_symbol[df_symbol['exchange'] == exchanges[0]]
    fig.add_trace(
        go.Scatter(
            x=df_price['time'], y=df_price['price'], 
            mode='lines', name="價格", 
            line=dict(color='white', width=2, dash='dash'),
            opacity=0.7
        ),
        secondary_y=True,
    )

    # 4. 佈局與外觀設定
    fig.update_layout(
        title=f"{symbol} 籌碼與價格宏觀監控",
        height=550,
        template="plotly_dark", # 預設暗色主題，質感拉滿
        hovermode="x unified",  # 💡 神器：垂直游標，一次看清所有數據
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20)
    )

    # 5. X 軸獨立縮放設定
    fig.update_xaxes(
        rangeslider_visible=True, # 打開下方時間拉桿，專門用來縮放 X 軸
        title_text="時間"
    )

    # 6. 雙 Y 軸設定
    fig.update_yaxes(title_text="散戶情緒 (帳戶比)", secondary_y=False, color="orange")
    fig.update_yaxes(title_text="價格 (USD)", secondary_y=True, color="white", showgrid=False)

    # 顯示圖表，並開啟滑鼠滾輪縮放支援
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

# ==========================================
# 網頁 UI 渲染
# ==========================================
st.title("🐋 巨鯨合約宏觀監控儀表板")
st.markdown("觀測四大交易所籌碼動向，尋找大戶與散戶的背離訊號。")

df_main = load_data()

if df_main.empty:
    st.error("⚠️ 資料庫目前沒有資料，請確認後端爬蟲是否正在執行！")
else:
    tab1, tab2 = st.tabs(["🔥 BTCUSDT", "💎 ETHUSDT"])
    
    with tab1:
        draw_macro_chart_plotly(df_main, "BTCUSDT")
        st.dataframe(df_main[df_main['symbol'] == "BTCUSDT"].sort_values('time', ascending=False).head(15), use_container_width=True)
        
    with tab2:
        draw_macro_chart_plotly(df_main, "ETHUSDT")
        st.dataframe(df_main[df_main['symbol'] == "ETHUSDT"].sort_values('time', ascending=False).head(15), use_container_width=True)
