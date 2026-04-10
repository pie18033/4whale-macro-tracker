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

# 隱藏預設元件
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

if 'symbol' not in st.session_state: st.session_state.symbol = 'BTCUSDT'

def change_symbol(new_symbol): st.session_state.symbol = new_symbol

# 交易所與圖層狀態
for exch in ['Binance', 'Bitget', 'Bybit', 'OKX']:
    if f"show_{exch}" not in st.session_state: st.session_state[f"show_{exch}"] = True

def toggle_exch(exch_name): st.session_state[f"show_{exch_name}"] = not st.session_state[f"show_{exch_name}"]

default_layers = {'price': True, 'vol': False, 'pos': True, 'acc': True}
for layer, default_val in default_layers.items():
    if f"show_layer_{layer}" not in st.session_state: st.session_state[f"show_layer_{layer}"] = default_val

def toggle_layer(layer_name): st.session_state[f"show_layer_{layer_name}"] = not st.session_state[f"show_layer_{layer_name}"]

# 顏色設定
if 'color_Binance' not in st.session_state: st.session_state.color_Binance = '#F3BA2F'
if 'color_Bitget' not in st.session_state: st.session_state.color_Bitget = '#00A1E6'
if 'color_Bybit' not in st.session_state: st.session_state.color_Bybit = '#00E676'
if 'color_OKX' not in st.session_state: st.session_state.color_OKX = '#FF4500'

# ==========================================
# 🎨 UI 控制面板
# ==========================================
st.title("🐋 全市場巨鯨合約監控儀表板")

st.markdown("##### 🔍 選擇監控標的")
col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 9]) 
with col_btn1: st.button("🔥 BTCUSDT", use_container_width=True, type="primary" if st.session_state.symbol == "BTCUSDT" else "secondary", on_click=change_symbol, args=("BTCUSDT",))
with col_btn2: st.button("💎 ETHUSDT", use_container_width=True, type="primary" if st.session_state.symbol == "ETHUSDT" else "secondary", on_click=change_symbol, args=("ETHUSDT",))

with st.expander("🎨 自訂圖表顏色"):
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.session_state.color_Binance = st.color_picker("Binance", st.session_state.color_Binance)
    with c2: st.session_state.color_Bitget = st.color_picker("Bitget", st.session_state.color_Bitget)
    with c3: st.session_state.color_Bybit = st.color_picker("Bybit", st.session_state.color_Bybit)
    with c4: st.session_state.color_OKX = st.color_picker("OKX", st.session_state.color_OKX)

color_map = {'Binance': st.session_state.color_Binance, 'Bitget': st.session_state.color_Bitget, 'Bybit': st.session_state.color_Bybit, 'OKX': st.session_state.color_OKX}

# ==========================================
# 🔌 資料獲取 (台灣時間 UTC+8)
# ==========================================
@st.cache_resource
def init_connection():
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

supabase = init_connection()

@st.cache_data(ttl=10) 
def load_data():
    response = supabase.table("crypto_macro_data").select("*").execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['time'] = pd.to_datetime(df['time']) + pd.Timedelta(hours=8)
        df = df.sort_values('time')
    return df

df = load_data()

# ==========================================
# 📊 核心圖表區
# ==========================================
if df.empty:
    st.warning("⚠️ 資料庫目前沒有資料。")
else:
    df_filtered = df[df['symbol'] == st.session_state.symbol]
    
    st.markdown("##### 👁️ 點擊按鈕顯示/隱藏圖層")
    l_cols = st.columns(4)
    layer_configs = [('price', '價格'), ('vol', '資金'), ('pos', '資金比'), ('acc', '帳戶比')]
    active_layers = []
    for i, (key, name) in enumerate(layer_configs):
        is_active = st.session_state[f"show_layer_{key}"]
        if is_active: active_layers.append(key)
        with l_cols[i]: st.button(f"{'🟢' if is_active else '⚫'} {name}", use_container_width=True, on_click=toggle_layer, args=(key,))

    if active_layers:
        # 💡 修復 1: 圖層分界重疊，vertical_spacing 設為 0
        fig = make_subplots(rows=len(active_layers), cols=1, shared_xaxes=True, vertical_spacing=0)

        # 💡 修復 2: 統一數字月份格式
        hover_fmt = "%m-%d %H:%M:%S"

        for exch in df_filtered['exchange'].unique():
            df_ex = df_filtered[df_filtered['exchange'] == exch]
            clr = color_map.get(exch, 'white')

            for idx, layer in enumerate(active_layers, start=1):
                if layer == 'price':
                    fig.add_trace(go.Scatter(x=df_ex['time'], y=df_ex['price'], name=f"{exch} 價格", line=dict(color=clr, width=2), hovertemplate=f'%{{y:,.2f}}<extra></extra>'), row=idx, col=1)
                elif layer == 'vol' and not df_ex['long_vol_usd'].isnull().all():
                    fig.add_trace(go.Scatter(x=df_ex['time'], y=df_ex['long_vol_usd']/1e9, name=f"{exch} 多單(B)", line=dict(color=clr, width=2), hovertemplate=f'$%{{y:,.2f}}B<extra></extra>'), row=idx, col=1)
                    fig.add_trace(go.Scatter(x=df_ex['time'], y=df_ex['short_vol_usd']/1e9, name=f"{exch} 空單(B)", line=dict(color=clr, width=2, dash='dot'), hovertemplate=f'$%{{y:,.2f}}B<extra></extra>'), row=idx, col=1)
                elif layer == 'pos' and not df_ex['ls_pos_ratio'].isnull().all():
                    fig.add_trace(go.Scatter(x=df_ex['time'], y=df_ex['ls_pos_ratio'], name=f"{exch} 資金比", line=dict(color=clr, width=2), hovertemplate=f'%{{y:.4f}}<extra></extra>'), row=idx, col=1)
                elif layer == 'acc' and not df_ex['ls_acc_ratio'].isnull().all():
                    fig.add_trace(go.Scatter(x=df_ex['time'], y=df_ex['ls_acc_ratio'], name=f"{exch} 帳戶比", line=dict(color=clr, width=2), hovertemplate=f'%{{y:.4f}}<extra></extra>'), row=idx, col=1)

        # 💡 修復 1: 亮邊框與網格
        fig.update_xaxes(
            tickformat="%m-%d %H:%M",
            showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)',
            showline=True, linewidth=2, linecolor='rgba(255, 255, 255, 0.4)', # 亮邊框
            mirror=True,
            showspikes=True, spikecolor="rgba(255, 255, 255, 0.3)", spikethickness=1, spikedash="solid", spikemode="across"
        )
        fig.update_yaxes(
            showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)',
            showline=True, linewidth=2, linecolor='rgba(255, 255, 255, 0.4)', # 亮邊框
            mirror=True, autorange=True
        )

        fig.update_layout(
            height=max(350, len(active_layers) * 250),
            dragmode='pan', hovermode="x unified",
            margin=dict(l=40, r=40, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hoverlabel=dict(bgcolor="rgba(30, 30, 30, 0.9)", font_size=13)
        )

        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True, 'displaylogo': False})

    # ==========================================
    # 下方表格 (略，保留原本邏輯)
    # ==========================================
