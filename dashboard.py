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
    return df

# 繪製單一 Plotly 圖表 (供左右兩側呼叫)
def draw_half_chart(df, symbol, ratio_col, ratio_name, title, color):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    exchanges = df['exchange'].dropna().unique()
    
    # 畫比值線 (左 Y 軸)
    for ex in exchanges:
        df_ex = df[df['exchange'] == ex]
        if not df_ex[ratio_col].isnull().all():
            fig.add_trace(
                go.Scatter(x=df_ex['time'], y=df_ex[ratio_col], mode='lines', name=f"{ex} {ratio_name}", line=dict(width=2)),
                secondary_y=False,
            )

    # 畫價格線 (右 Y 軸) - 抓第一家有價格的即可
    if len(exchanges) > 0:
        df_price = df[df['exchange'] == exchanges[0]]
        fig.add_trace(
            go.Scatter(x=df_price['time'], y=df_price['price'], mode='lines', name="BTC 價格", line=dict(color='white', width=2, dash='dash'), opacity=0.6),
            secondary_y=True,
        )

    fig.update_layout(
        title=title, height=400, template="plotly_dark", hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=50, b=10)
    )
    fig.update_xaxes(rangeslider_visible=False) # 左右圖表不加下方拉桿以節省空間
    fig.update_yaxes(title_text=ratio_name, secondary_y=False, color=color)
    fig.update_yaxes(title_text="價格 (USD)", secondary_y=True, color="white", showgrid=False)
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

# ==========================================
# 網頁 UI 渲染
# ==========================================
st.title("🐋 巨鯨合約宏觀監控儀表板")
st.markdown("觀測四大交易所籌碼動向，尋找大戶與散戶的背離訊號。")

df_main = load_data()

if df_main.empty:
    st.error("⚠️ 資料庫目前沒有資料！")
else:
    # 只取 BTCUSDT 示範
    df_btc = df_main[df_main['symbol'] == "BTCUSDT"].copy()
    all_exchanges = df_btc['exchange'].dropna().unique().tolist()

    # --- 1. 顯示控制功能 (交易所開關按鈕) ---
    st.markdown("### 👁️ 點擊按鈕開關下方表格與圖表資料")
    
    # 建立橫向排列的 Toggle 按鈕
    cols = st.columns(len(all_exchanges) if len(all_exchanges) > 0 else 1)
    selected_exchanges = []
    
    for i, ex in enumerate(all_exchanges):
        with cols[i]:
            # 使用 st.toggle 作為開關，預設為開啟 (True)
            if st.toggle(f"顯示 {ex}", value=True):
                selected_exchanges.append(ex)

    # 根據按鈕選擇過濾資料
    df_filtered = df_btc[df_btc['exchange'].isin(selected_exchanges)]

    st.divider() # 分隔線

    if df_filtered.empty:
        st.warning("請至少選擇一間交易所。")
    else:
        # --- 2. 圖表配置 (左右雙圖) ---
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # (a) 左邊圖表：BTC 加上帳戶多空比
            draw_half_chart(df_filtered, "BTCUSDT", "ls_acc_ratio", "帳戶比", "🧑‍🤝‍🧑 散戶情緒 (帳戶多空比)", "orange")
            
        with chart_col2:
            # (b) 右邊圖表：BTC 加上資金多空比 (大戶)
            draw_half_chart(df_filtered, "BTCUSDT", "ls_pos_ratio", "資金比", "🐋 大戶動向 (資金多空比)", "cyan")

        st.divider() # 分隔線

        # --- 3. 個別資料表 (依交易所區分 & 展開縮起功能) ---
        st.markdown("### 📊 各交易所最新資料 (顯示前 20 筆)")
        
        # 根據選擇的交易所數量建立相對應的欄位並排顯示表格
        table_cols = st.columns(len(selected_exchanges))
        
        for i, ex in enumerate(selected_exchanges):
            with table_cols[i]:
                st.markdown(f"**{ex} 數據**")
                
                # 撈出該交易所的資料並依時間倒序
                df_ex_table = df_filtered[df_filtered['exchange'] == ex].sort_values('time', ascending=False)
                
                # 整理要顯示的欄位 (包含你要求的做多/做空資金)
                display_cols = ['time', 'price', 'ls_acc_ratio', 'ls_pos_ratio', 'long_vol_usd', 'short_vol_usd']
                df_display = df_ex_table[[c for c in display_cols if c in df_ex_table.columns]]
                
                # 顯示前 20 筆
                st.dataframe(df_display.head(20), use_container_width=True, hide_index=True)
                
                # 利用 expander 製作「展開 20 筆之後數據」的按鈕功能
                if len(df_display) > 20:
                    with st.expander(f"展開 {ex} 完整歷史紀錄"):
                        st.dataframe(df_display.iloc[20:], use_container_width=True, hide_index=True)
