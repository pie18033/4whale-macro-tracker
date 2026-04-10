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

# 顏色狀態
if 'color_Binance' not in st.session_state: st.session_state.color_Binance = '#F3BA2F'
if 'color_Bitget' not in st.session_state: st.session_state.color_Bitget = '#00A1E6'
if 'color_Bybit' not in st.session_state: st.session_state.color_Bybit = '#00E676'
if 'color_OKX' not in st.session_state: st.session_state.color_OKX = '#FF4500'

# 💡 新增：資料載入量狀態 (預設 2000 筆)
if 'data_limit' not in st.session_state: st.session_state.data_limit = 2000

# 隱藏預設元件 & 注入🍎 iOS 26 毛玻璃按鈕樣式與選色連動
st.markdown(f"""
    <style>
    #MainMenu {{visibility: hidden;}}
    header {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    
    /* 🍎 iOS 26 毛玻璃基礎按鈕 (未選中) */
    div[data-testid="stButton"] > button {{
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        color: #a0a0a0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        transition: all 0.3s ease !important;
    }}
    
    div[data-testid="stButton"] > button:hover {{
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        color: #ffffff !important;
    }}

    /* 🍎 預設選中狀態發光 */
    div[data-testid="stButton"] > button[kind="primary"] {{
        background: radial-gradient(circle at center, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.02) 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3), inset 0 0 10px rgba(255,255,255,0.05) !important;
        text-shadow: 0 0 5px rgba(255,255,255,0.3) !important;
    }}

    /* 精準指定按鈕發光顏色 */
    div.element-container:has(#btn-btc) + div.element-container div[data-testid="stButton"] > button[kind="primary"],
    div.element-container:has(#btn-layer-price) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px #F3BA2F, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: #F3BA2F !important;
    }}

    div.element-container:has(#btn-eth) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px #A259FF, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: #A259FF !important;
    }}

    div.element-container:has(#btn-layer-vol) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px #FF8C00, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: #FF8C00 !important;
    }}

    div.element-container:has(#btn-layer-pos) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px #00A1E6, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: #00A1E6 !important;
    }}

    div.element-container:has(#btn-layer-acc) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px #00E676, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: #00E676 !important;
    }}

    /* 交易所開關動態顏色連動 */
    div.element-container:has(#btn-exch-Binance) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px {st.session_state.color_Binance}, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: {st.session_state.color_Binance} !important;
    }}
    div.element-container:has(#btn-exch-Bitget) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px {st.session_state.color_Bitget}, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: {st.session_state.color_Bitget} !important;
    }}
    div.element-container:has(#btn-exch-Bybit) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px {st.session_state.color_Bybit}, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: {st.session_state.color_Bybit} !important;
    }}
    div.element-container:has(#btn-exch-OKX) + div.element-container div[data-testid="stButton"] > button[kind="primary"] {{
        box-shadow: 0 0 15px {st.session_state.color_OKX}, inset 0 0 5px rgba(255,255,255,0.3) !important;
        border-color: {st.session_state.color_OKX} !important;
    }}
    </style>
    """, unsafe_allow_html=True)

if 'symbol' not in st.session_state: st.session_state.symbol = 'BTCUSDT'

def change_symbol(new_symbol): st.session_state.symbol = new_symbol

default_exch = {'Binance': True, 'Bitget': True, 'Bybit': False, 'OKX': False}
for exch, default_val in default_exch.items():
    state_key = f"show_{exch}"
    if state_key not in st.session_state: st.session_state[state_key] = default_val

def toggle_exch(exch_name):
    st.session_state[f"show_{exch_name}"] = not st.session_state[f"show_{exch_name}"]

default_layers = {'price': True, 'vol': False, 'pos': True, 'acc': True}
for layer, default_val in default_layers.items():
    state_key = f"show_layer_{layer}"
    if state_key not in st.session_state: st.session_state[state_key] = default_val

def toggle_layer(layer_name):
    st.session_state[f"show_layer_{layer_name}"] = not st.session_state[f"show_layer_{layer_name}"]

# 💡 新增：載入更多資料的邏輯
def load_more_data():
    st.session_state.data_limit += 4000 # 每次增加 4000 筆

# ==========================================
# 🎨 頂部標題與按鈕選單
# ==========================================
st.title("🐋 全市場巨鯨合約監控儀表板")

st.markdown("##### 🔍 選擇監控標的")
col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 9]) 

with col_btn1:
    st.markdown('<div id="btn-btc"></div>', unsafe_allow_html=True)
    st.button("🔥 BTCUSDT", use_container_width=True, 
              type="primary" if st.session_state.symbol == "BTCUSDT" else "secondary",
              on_click=change_symbol, args=("BTCUSDT",))

with col_btn2:
    st.markdown('<div id="btn-eth"></div>', unsafe_allow_html=True)
    st.button("💎 ETHUSDT", use_container_width=True, 
              type="primary" if st.session_state.symbol == "ETHUSDT" else "secondary",
              on_click=change_symbol, args=("ETHUSDT",))

symbol = st.session_state.symbol

# 自訂顏色面板 
with st.expander("🎨 自訂圖表顏色 (點擊展開)"):
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.session_state.color_Binance = st.color_picker("Binance", st.session_state.color_Binance)
    with c2: st.session_state.color_Bitget = st.color_picker("Bitget", st.session_state.color_Bitget)
    with c3: st.session_state.color_Bybit = st.color_picker("Bybit", st.session_state.color_Bybit)
    with c4: st.session_state.color_OKX = st.color_picker("OKX", st.session_state.color_OKX)

color_map = {
    'Binance': st.session_state.color_Binance, 
    'Bitget': st.session_state.color_Bitget,  
    'Bybit': st.session_state.color_Bybit,   
    'OKX': st.session_state.color_OKX      
}

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

# 💡 修改：將 data_limit 傳入快取函數，讓它根據狀態動態抓取
@st.cache_data(ttl=10) 
def load_data(limit):
    if supabase is None: return pd.DataFrame()
    try:
        # 使用傳入的 limit 變數動態決定抓取數量
        response = supabase.table("crypto_macro_data").select("*").order("time", desc=True).limit(limit).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['time'] = pd.to_datetime(df['time']) + pd.Timedelta(hours=8)
            df = df.sort_values('time') 
        return df
    except Exception as e:
        st.error(f"❌ 讀取 Supabase 資料失敗: {e}")
        return pd.DataFrame()

# 使用 session_state 中的 limit 來載入資料
df = load_data(st.session_state.data_limit)

# ==========================================
# 📊 畫圖與介面顯示 (動態圖表)
# ==========================================
if df.empty:
    st.warning("⚠️ 資料庫目前沒有資料，請確認「後端爬蟲程式」是否正在執行！")
else:
    df_filtered = df[df['symbol'] == symbol]
    
    if df_filtered.empty:
        st.info(f"目前資料庫中尚未收集到 {symbol} 的數據。")
    else:
        # 💡 新增：載入更多資料的控制區塊
        st.markdown("##### ⏳ 資料載入範圍控制")
        col_info, col_btn, _ = st.columns([3, 2, 7])
        with col_info:
            # 顯示目前抓了幾筆，大約涵蓋多久的時間
            time_span_hours = (df_filtered['time'].max() - df_filtered['time'].min()).total_seconds() / 3600
            st.caption(f"✅ 目前已載入最新 **{len(df)}** 筆資料 (約涵蓋過去 **{time_span_hours:.1f}** 小時的走勢)。")
        
        with col_btn:
            # 防呆上限：超過 20000 筆就不給按了，保護網頁不卡死
            if st.session_state.data_limit < 20000:
                st.button("📥 載入更久以前的資料 (+4000筆)", on_click=load_more_data, use_container_width=True)
            else:
                st.caption("⚠️ 已達單次載入安全上限，以確保圖表流暢度。")

        st.markdown("---")

        df_binance = df_filtered[df_filtered['exchange'] == 'Binance']
        if not df_binance.empty:
            latest_price = df_binance.iloc[-1]['price']
            st.markdown(f"### 目前 {symbol} 價格: **${latest_price:,.2f} USD**")

        st.markdown("##### 👁️ 點擊按鈕顯示/隱藏圖層")
        l_col1, l_col2, l_col3, l_col4 = st.columns(4)
        
        layer_configs = [
            (l_col1, 'price', '價格 (Price)'),
            (l_col2, 'vol', '多空絕對資金 (Volume)'),
            (l_col3, 'pos', '資金多空比 (大戶)'),
            (l_col4, 'acc', '帳戶多空比 (散戶)')
        ]
        
        active_layers = []
        for col, layer_key, layer_name in layer_configs:
            is_active = st.session_state[f"show_layer_{layer_key}"]
            if is_active: active_layers.append(layer_key)
            with col:
                st.markdown(f'<div id="btn-layer-{layer_key}"></div>', unsafe_allow_html=True)
                st.button(
                    f"{layer_name}", 
                    use_container_width=True, 
                    type="primary" if is_active else "secondary",
                    on_click=toggle_layer, args=(layer_key,)
                )

        if not active_layers:
            st.info("請至少開啟一個圖層來顯示圖表。")
        else:
            st.caption("【操作提示】圖表右上角有『Autoscale (自動縮放)』按鈕。框選可局部放大，雙擊圖表自動還原最佳化。")

            fig = make_subplots(
                rows=len(active_layers), cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03 
            )

            exchanges = df_filtered['exchange'].unique()

            for exch in exchanges:
                df_ex = df_filtered[df_filtered['exchange'] == exch]
                exch_color = color_map.get(exch, 'white')

                for idx, layer in enumerate(active_layers, start=1):
                    if layer == 'price' and not df_ex['price'].isnull().all():
                        fig.add_trace(
                            go.Scatter(x=df_ex['time'], y=df_ex['price'], name=f"{exch} 價格",
                                       line=dict(color=exch_color, width=2), mode='lines',
                                       line_shape='spline', 
                                       hovertemplate='$%{y:,.2f}<extra></extra>'),
                            row=idx, col=1
                        )
                    
                    elif layer == 'vol' and not df_ex['long_vol_usd'].isnull().all():
                        vol_long_b = df_ex['long_vol_usd'] / 1e9
                        vol_short_b = df_ex['short_vol_usd'] / 1e9
                        
                        fig.add_trace(
                            go.Scatter(x=df_ex['time'], y=vol_long_b, name=f"{exch} 多單",
                                       line=dict(color=exch_color, width=2, dash='solid'), mode='lines',
                                       line_shape='spline', 
                                       hovertemplate='$%{y:,.2f}B<extra></extra>'),
                            row=idx, col=1
                        )
                        fig.add_trace(
                            go.Scatter(x=df_ex['time'], y=vol_short_b, name=f"{exch} 空單",
                                       line=dict(color=exch_color, width=2, dash='dot'), mode='lines',
                                       line_shape='spline', 
                                       hovertemplate='$%{y:,.2f}B<extra></extra>'),
                            row=idx, col=1
                        )

                    elif layer == 'pos' and not df_ex['ls_pos_ratio'].isnull().all():
                        fig.add_trace(
                            go.Scatter(x=df_ex['time'], y=df_ex['ls_pos_ratio'], name=f"{exch} 資金比",
                                       line=dict(color=exch_color, width=2), mode='lines',
                                       line_shape='spline', 
                                       hovertemplate='%{y:.4f}<extra></extra>'),
                            row=idx, col=1
                        )

                    elif layer == 'acc' and not df_ex['ls_acc_ratio'].isnull().all():
                        fig.add_trace(
                            go.Scatter(x=df_ex['time'], y=df_ex['ls_acc_ratio'], name=f"{exch} 帳戶比",
                                       line=dict(color=exch_color, width=2), mode='lines',
                                       line_shape='spline', 
                                       hovertemplate='%{y:.4f}<extra></extra>'),
                            row=idx, col=1
                        )

            for idx, layer in enumerate(active_layers, start=1):
                if layer == 'price':
                    fig.update_yaxes(title_text="價格", tickformat="$.2s", autorange=True, row=idx, col=1)
                elif layer == 'vol':
                    fig.update_yaxes(title_text="資金 (B)", tickformat="$.2f", autorange=True, row=idx, col=1)
                elif layer == 'pos':
                    fig.update_yaxes(title_text="資金比", autorange=True, row=idx, col=1)
                elif layer == 'acc':
                    fig.update_yaxes(title_text="帳戶比", autorange=True, row=idx, col=1)

            fig.update_xaxes(
                tickformat="%m-%d %H:%M",
                hoverformat="%m-%d %H:%M:%S", 
                showgrid=True, gridwidth=1, gridcolor='rgba(128, 128, 128, 0.1)',
                showline=True, linewidth=1.5, linecolor='rgba(200, 200, 200, 0.6)', 
                mirror=True,
                showspikes=True, spikecolor="rgba(255, 255, 255, 0.3)", spikethickness=1, spikedash="solid", spikemode="across" 
            )
            fig.update_yaxes(
                showgrid=True, gridwidth=1, gridcolor='rgba(128, 128, 128, 0.1)',
                showline=True, linewidth=1.5, linecolor='rgba(200, 200, 200, 0.6)', 
                mirror=True
            )

            chart_height = max(350, len(active_layers) * 260)

            fig.update_layout(
                height=chart_height, 
                dragmode='pan', 
                hovermode="x unified",
                margin=dict(l=40, r=40, t=10, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)",
                hoverlabel=dict(
                    bgcolor="rgba(20, 20, 20, 0.85)", 
                    font_size=13, 
                    bordercolor="rgba(255, 255, 255, 0.2)"
                )
            )

            st.plotly_chart(fig, use_container_width=True, config={
                'scrollZoom': True, 
                'displayModeBar': True, 
                'displaylogo': False,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d']
            })

        # ==========================================
        # 下方表格區塊
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
                st.markdown(f'<div id="btn-exch-{exch}"></div>', unsafe_allow_html=True)
                st.button(
                    f"{exch}", 
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
                        
                        top_20_df_display = top_20_df[['time', 'price', '多單資金 (B)', '空單資金 (B)', '帳戶比', '多空持倉比']].copy()
                        top_20_df_display['time'] = top_20_df_display['time'].dt.strftime('%m-%d %H:%M:%S')
                        st.dataframe(top_20_df_display, use_container_width=True, hide_index=True)
                        
                        if not rest_df.empty:
                            with st.expander(f"📂 展開 {exch} 更早的歷史紀錄"):
                                rest_df_display = rest_df[['time', 'price', '多單資金 (B)', '空單資金 (B)', '帳戶比', '多空持倉比']].copy()
                                rest_df_display['time'] = rest_df_display['time'].dt.strftime('%m-%d %H:%M:%S')
                                st.dataframe(rest_df_display, use_container_width=True, hide_index=True)
        elif not selected_exchanges:
            st.info("請點擊上方按鈕，選擇至少一間交易所來顯示數據表格。")
