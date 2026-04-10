import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots # 💡 僅新增這個用來繪製穩定的雙 Y 軸
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
        st.error("❌ 缺少 SUPABASE_URL 或 SUPABASE_KEY 環境變數。請檢查 .env 檔案。")
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
# 📊 畫圖與介面顯示
# ==========================================
if df.empty:
    st.warning("⚠️ 資料庫目前沒有資料，請確認「後端爬蟲程式 (whale_macro_tracker.py)」是否正在執行！")
else:
    df_filtered = df[df['symbol'] == symbol]
    
    if df_filtered.empty:
        st.info(f"目前資料庫中尚未收集到 {symbol} 的數據，請稍後再試。")
    else:
        df_price = df_filtered[df_filtered['exchange'] == 'Binance']
        
        if not df_price.empty:
            latest_price = df_price.iloc[-1]['price']
            st.markdown(f"### 當前 {symbol} 價格 (Binance): **${latest_price:,.2f}**")
        else:
            latest_price = df_filtered.iloc[-1]['price']
            st.markdown(f"### 當前 {symbol} 價格: **${latest_price:,.2f}**")

        col1, col2 = st.columns(2)

        color_map = {
            'Binance': '#F3BA2F', 
            'Bitget': '#00A1E6',  
            'Bybit': '#00E676',   
            'OKX': '#00BFFF'      
        }
        price_color = '#F7931A' if symbol == 'BTCUSDT' else '#A259FF'
        
        hover_template = '<b>時間:</b> %{x|%Y-%m-%d %H:%M:%S}<br><b>數值:</b> %{y:.4f}<extra></extra>'
        hover_template_price = '<b>時間:</b> %{x|%Y-%m-%d %H:%M:%S}<br><b>價格:</b> $%{y:,.2f}<extra></extra>'

        # ------------------------------------------
        # 💡 圖表區間：重構為 make_subplots，保留你的縱書設計與乾淨外觀
        # ------------------------------------------
        with col1:
            st.subheader("帳戶多空比")
            st.caption("左軸：多空比 / 右軸：價格。【游標置於圖表內滾動可縮放時間，雙擊圖表可還原/自動最佳化】")
            
            fig_acc = make_subplots(specs=[[{"secondary_y": True}]])
            
            for exch in df_filtered['exchange'].unique():
                df_ex = df_filtered[df_filtered['exchange'] == exch].dropna(subset=['ls_acc_ratio'])
                if not df_ex.empty:
                    fig_acc.add_trace(
                        go.Scatter(x=df_ex['time'], y=df_ex['ls_acc_ratio'], name=exch,
                                   line=dict(color=color_map.get(exch, 'gray'), width=2),
                                   line_shape='spline', hovertemplate=hover_template),
                        secondary_y=False
                    )
                    
            if not df_price.empty:
                fig_acc.add_trace(
                    go.Scatter(x=df_price['time'], y=df_price['price'], name=f"{symbol[:3]} 價格",
                               line=dict(color=price_color, width=2.5, dash='solid'), 
                               line_shape='spline', hovertemplate=hover_template_price),
                    secondary_y=True
                )

            fig_acc.update_layout(
                dragmode='pan',
                hovermode="x unified",
                margin=dict(l=80, r=80, t=30, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                annotations=[
                    dict(x=-0.12, y=0.5, xref='paper', yref='paper', text="<b>帳<br>戶<br>比</b>", showarrow=False, font=dict(size=18), align='center'),
                    dict(x=1.12, y=0.5, xref='paper', yref='paper', text="<b>價<br>格<br><span style='font-size: 13px;'>(USD)</span></b>", showarrow=False, font=dict(size=18), align='center')
                ]
            )
            fig_acc.update_xaxes(title="", fixedrange=False)
            fig_acc.update_yaxes(title="", fixedrange=False, autorange=True, secondary_y=False)
            fig_acc.update_yaxes(title="", fixedrange=False, autorange=True, showgrid=False, secondary_y=True)
            fig_acc.add_hline(y=1.0, line_dash="dash", line_color="red", opacity=0.5)
            
            st.plotly_chart(fig_acc, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})

        with col2:
            st.subheader("資金多空比")
            st.caption("僅 Binance 與 Bitget 提供。數值 < 1 代表大戶總資金偏空。")
            df_whale = df_filtered.dropna(subset=['ls_pos_ratio'])
            
            fig_pos = make_subplots(specs=[[{"secondary_y": True}]])
            
            for exch in df_whale['exchange'].unique():
                df_ex = df_whale[df_whale['exchange'] == exch]
                if not df_ex.empty:
                    fig_pos.add_trace(
                        go.Scatter(x=df_ex['time'], y=df_ex['ls_pos_ratio'], name=exch,
                                   line=dict(color=color_map.get(exch, 'gray'), width=2),
                                   line_shape='spline', hovertemplate=hover_template),
                        secondary_y=False
                    )
                    
            if not df_price.empty:
                fig_pos.add_trace(
                    go.Scatter(x=df_price['time'], y=df_price['price'], name=f"{symbol[:3]} 價格",
                               line=dict(color=price_color, width=2.5, dash='solid'), 
                               line_shape='spline', hovertemplate=hover_template_price),
                    secondary_y=True
                )

            fig_pos.update_layout(
                dragmode='pan',
                hovermode="x unified",
                margin=dict(l=80, r=80, t=30, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                annotations=[
                    dict(x=-0.12, y=0.5, xref='paper', yref='paper', text="<b>資<br>金<br>比</b>", showarrow=False, font=dict(size=18), align='center'),
                    dict(x=1.12, y=0.5, xref='paper', yref='paper', text="<b>價<br>格<br><span style='font-size: 13px;'>(USD)</span></b>", showarrow=False, font=dict(size=18), align='center')
                ]
            )
            fig_pos.update_xaxes(title="", fixedrange=False)
            fig_pos.update_yaxes(title="", fixedrange=False, autorange=True, secondary_y=False)
            fig_pos.update_yaxes(title="", fixedrange=False, autorange=True, showgrid=False, secondary_y=True)
            fig_pos.add_hline(y=1.0, line_dash="dash", line_color="red", opacity=0.5)
            
            st.plotly_chart(fig_pos, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})

        # ------------------------------------------
        # 💡 以下完全是你的原始程式碼，一字未改！
        # ------------------------------------------
        st.markdown("---")
        st.subheader("不同交易所多空比紀錄")
        
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
        
        df_vol = df_filtered.dropna(subset=['ls_acc_ratio']).copy()
        
        if not df_vol.empty and selected_exchanges:
            df_vol['多單資金 (B)'] = (df_vol['long_vol_usd'] / 1_000_000_000).round(2)
            df_vol['空單資金 (B)'] = (df_vol['short_vol_usd'] / 1_000_000_000).round(2)
            df_vol = df_vol[['exchange', 'time', 'price', '多單資金 (B)', '空單資金 (B)', 'ls_acc_ratio', 'ls_pos_ratio']]
            df_vol = df_vol.rename(columns={'ls_acc_ratio': '帳戶比', 'ls_pos_ratio': '多空持倉比'})
            
            df_vol['多單資金 (B)'] = df_vol['多單資金 (B)'].astype(str).replace('nan', 'N/A')
            df_vol['空單資金 (B)'] = df_vol['空單資金 (B)'].astype(str).replace('nan', 'N/A')
            df_vol['多空持倉比'] = df_vol['多空持倉比'].astype(str).replace('nan', 'N/A')
            
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
                        st.markdown(f"<h4 style='color: {exch_color};'>{exch} 最新資料 (顯示前 20 筆)</h4>", unsafe_allow_html=True)
                        
                        st.dataframe(
                            top_20_df[['time', 'price', '多單資金 (B)', '空單資金 (B)', '帳戶比', '多空持倉比']], 
                            use_container_width=True, 
                            hide_index=True 
                        )
                        
                        if not rest_df.empty:
                            with st.expander(f"📂 展開 {exch} 更早的歷史紀錄 (共 {len(rest_df)} 筆)"):
                                st.dataframe(
                                    rest_df[['time', 'price', '多單資金 (B)', '空單資金 (B)', '帳戶比', '多空持倉比']], 
                                    use_container_width=True, 
                                    hide_index=True
                                )
        elif not selected_exchanges:
            st.info("請點擊上方按鈕，選擇至少一間交易所來顯示數據表格。")
        else:
            st.info("目前選定幣種沒有足夠的資料。")
