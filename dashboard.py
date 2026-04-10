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

# 資料載入量狀態 (預設 2000 筆)
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

def load_more_data():
    st.session_state.data_limit += 4000 

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

st.markdown("---
