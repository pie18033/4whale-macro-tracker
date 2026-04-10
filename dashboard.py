import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

# 強制每次載入網頁時，都去翻閱密碼本
load_dotenv(override=True)

# ==========================================
# ⚙️ 網頁基本設定 & 狀態管理
# ==========================================
st.set_page_config(page_title="全市場巨鯨監控", layout="wide", page_icon="🐋")

if 'symbol' not in st.session_state:
    st.session_state.symbol = 'BTCUSDT'

def change_symbol(new_symbol):
    st.session_state.symbol = new_symbol

for exch in ['Binance', 'Bitget', 'Bybit', 'OKX']:
    state_key = f"show_{exch}"
    if state_key not in st.session_state:
        st.session_state[state_key] = True

def toggle_exch(exch_name):
    state_key = f"show_{exch_name}"
    st.session_state[state_key] = not st.session_state[state_key]

# ==========================================
# 🎨 頂部標題與按鈕選單
# ==========================================
st.title("🐋 全市場巨鯨合約監控儀表板")

st.markdown("##### 🔍 選擇監控標的")
col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 9]) 

with col_btn1:
    st.button("🔥 BTCUSDT", use_container_width=True, 
              type="primary" if st.session_state.symbol == "BTCUSDT" else "secondary",
              on_click=change_symbol, args=("BTCUSDT",))

with col_btn2:
    st.button("💎 ETHUSDT", use_container_width=True, 
              type="primary" if st.session_state.symbol == "ETHUSDT" else "secondary",
              on_click=change_symbol, args=("ETHUSDT",))

symbol = st.session_state.symbol
st.markdown("---")

# ==========================================
# 🔌 連線與讀取資料
# ==========================================
@st.cache_resource
def init_connection():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        st.error("❌ 缺少 SUPABASE_URL 或 SUPABASE_KEY 環境變數。")
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Supabase 連線失敗: {e}")
        return None

supabase = init_connection()

@st.cache_data(ttl=10) 
def load_data():
    if supabase is None:
        return pd.DataFrame()
    try:
        response = supabase.table("crypto_macro_data").select("*").execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            df = df.sort_values('time')
        return df
    except Exception as e:
        st.error(f"❌ 讀取 Supabase 資料失敗: {e}")
        return pd.DataFrame()

df = load_data()

# ==========================================
# 📊 畫圖與介面顯示 (四層堆疊圖表)
# ==========================================
if df.empty:
    st.warning("⚠️ 資料庫目前沒有資料，請確認「後端爬蟲程式」是否正在執行！")
else:
    df_filtered = df[df['symbol'] == symbol]
    
    if df_filtered.empty:
        st.info(f"目前資料庫中尚未收集到 {symbol} 的數據。")
    else:
        df_binance = df_filtered[df_filtered['exchange'] == 'Binance']
        if not df_binance.empty:
            latest_price = df_binance.iloc[-1]['price']
            st.markdown(f"### 當前 {symbol} 價格 (Binance): **${latest_price:,.2f}**")
            
        st.caption("【操作提示】在圖表內滾動可同步縮放四個圖層的時間軸，框選特定區域可局部放大，雙擊圖表自動還原最佳化。")

        color_map = {
            'Binance': '#F3BA2F', 
            'Bitget': '#00A1E6',  
            'Bybit': '#00E676',   
            'OKX': '#FF4500'      
        }

        # 建立 4 列 1 行的子圖表，共用 X 軸
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, # 圖層之間的間距
            subplot_titles=("1. 價格 (Price)", "2. 多空絕對資金 (Volume USD)", "3. 資金多空比 (大戶)", "4. 帳戶多空比 (散戶)")
        )

        exchanges = df_filtered['exchange'].unique()

        for exch in exchanges:
            df_ex = df_filtered[df_filtered['exchange'] == exch]
            exch_color = color_map.get(exch, 'white')

            # --- 第一層：價格 (所有交易所) ---
            if not df_ex['price'].isnull().all():
                fig.add_trace(
                    go.Scatter(x=df_ex['time'], y=df_ex['price'], name=f"{exch} 價格",
                               line=dict(color=exch_color, width=2), mode='lines',
                               hovertemplate='<b>%{x|%H:%M:%S}</b><br>價格: $%{y:,.2f}<extra></extra>'),
                    row=1, col=1
                )

            # --- 第二層：多空絕對資金 (僅 Binance, Bitget) ---
            if not df_ex['long_vol_usd'].isnull().all():
                fig.add_trace(
                    go.Scatter(x=df_ex['time'], y=df_ex['long_vol_usd'], name=f"{exch} 多單資金",
                               line=dict(color=exch_color, width=2, dash='solid'), mode='lines',
                               hovertemplate='<b>多單資金:</b> $%{y:,.0f}<extra></extra>'),
                    row=2, col=1
                )
                fig.add_trace(
                    go.Scatter(x=df_ex['time'], y=df_ex['short_vol_usd'], name=f"{exch} 空單資金",
                               line=dict(color=exch_color, width=2, dash='dot'), mode='lines',
                               hovertemplate='<b>空單資金:</b> $%{y:,.0f}<extra></extra>'),
                    row=2, col=1
                )

            # --- 第三層：資金多空比 (大戶) ---
            if not df_ex['ls_pos_ratio'].isnull().all():
                fig.add_trace(
                    go.Scatter(x=df_ex['time'], y=df_ex['ls_pos_ratio'], name=f"{exch} 資金比",
                               line=dict(color=exch_color, width=2), mode='lines',
                               hovertemplate='<b>資金比:</b> %{y:.4f}<extra></extra>'),
                    row=3, col=1
                )

            # --- 第四層：帳戶多空比 (散戶) ---
            if not df_ex['ls_acc_ratio'].isnull().all():
                fig.add_trace(
                    go.Scatter(x=df_ex['time'], y=df_ex['ls_acc_ratio'], name=f"{exch} 帳戶比",
                               line=dict(color=exch_color, width=2), mode='lines',
                               hovertemplate='<b>帳戶比:</b> %{y:.4f}<extra></extra>'),
                    row=4, col=1
                )

        # 加入 1.0 的基準紅虛線 (第三、第四層)
        fig.add_hline(y=1.0, row=3, col=1, line_dash="dash", line_color="red", opacity=0.5)
        fig.add_hline(y=1.0, row=4, col=1, line_dash="dash", line_color="red", opacity=0.5)

        # 💡 完美修復：dragmode 已改為合法參數 'pan'
        fig.update_layout(
            height=1000, 
            dragmode='pan', 
            hovermode="x unified",
            margin=dict(l=40, r=40, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        # 設定 Y 軸格式
        fig.update_yaxes(title_text="USD", tickformat="$.2s", autorange=True, row=1, col=1)
        fig.update_yaxes(title_text="資金量 (USD)", tickformat="$.2s", autorange=True, row=2, col=1)
        fig.update_yaxes(title_text="比例", autorange=True, row=3, col=1)
        fig.update_yaxes(title_text="比例", autorange=True, row=4, col=1)
        fig.update_xaxes(fixedrange=False)

        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})

        # ==========================================
        # 💡 下方表格區塊
        # ==========================================
        st.markdown("---")
        st.subheader("不同交易所數據紀錄")
        
        st.markdown("##### 👁️ 點擊按鈕開關下方表格")
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        exchanges_list = ['Binance', 'Bitget', 'Bybit', 'OKX']
        cols_list = [col_t1, col_t2, col_t3, col_t4]
        
        for col, exch in zip(cols_list, exchanges_list):
            is_active = st.session_state[f"show_{exch}"]
            with col:
                st.button(
                    f"{'🟢' if is_active else '⚫'} {exch}", 
                    use_container_width=True, 
                    type="primary" if is_active else "secondary",
                    on_click=toggle_exch, 
                    args=(exch,)
                )

        selected_exchanges = [exch for exch in exchanges_list if st.session_state[f"show_{exch}"]]
        
        df_vol = df_filtered.copy()
        
        if not df_vol.empty and selected_exchanges:
            df_vol['多單資金 (B)'] = (df_vol['long_vol_usd'] / 1_000_000_000).round(3)
            df_vol['空單資金 (B)'] = (df_vol['short_vol_usd'] / 1_000_000_000).round(3)
            df_vol = df_vol[['exchange', 'time', 'price', '多單資金 (B)', '空單資金 (B)', 'ls_acc_ratio', 'ls_pos_ratio']]
            df_vol = df_vol.rename(columns={'ls_acc_ratio': '帳戶比', 'ls_pos_ratio': '多空持倉比'})
            
            for col in ['多單資金 (B)', '空單資金 (B)', '帳戶比', '多空持倉比']:
                df_vol[col] = df_vol[col].astype(str).replace('nan', 'N/A')
            
            col_v1, col_v2 = st.columns(2)
            
            for i, exch in enumerate(selected_exchanges):
                exch_df = df_vol[df_vol['exchange'] == exch]
                if not exch_df.empty:
                    exch_df_sorted = exch_df.sort_values(by='time', ascending=False)
                    top_20_df = exch_df_sorted.head(20)
                    rest_df = exch_df_sorted.iloc[20:]
                    
                    target_col = col_v1 if i % 2 == 0 else col_v2
                    with target_col:
                        exch_color = color_map.get(exch, '#FFFFFF')
                        st.markdown(f"<h4 style='color: {exch_color};'>{exch} 最新資料</h4>", unsafe_allow_html=True)
                        
                        st.dataframe(
                            top_20_df[['time', 'price', '多單資金 (B)', '空單資金 (B)', '帳戶比', '多空持倉比']], 
                            use_container_width=True, 
                            hide_index=True 
                        )
                        
                        if not rest_df.empty:
                            with st.expander(f"📂 展開 {exch} 更早的歷史紀錄"):
                                st.dataframe(
                                    rest_df[['time', 'price', '多單資金 (B)', '空單資金 (B)', '帳戶比', '多空持倉比']], 
                                    use_container_width=True, 
                                    hide_index=True
                                )
        elif not selected_exchanges:
            st.info("請點擊上方按鈕，選擇至少一間交易所來顯示數據表格。")
