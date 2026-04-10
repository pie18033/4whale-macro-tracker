import pandas as pd
from supabase import create_client, Client
import os
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
from bokeh.plotting import figure
from bokeh.models import LinearAxis, Range1d, WheelZoomTool, HoverTool
from bokeh.palettes import Category10

# 強制每次載入網頁時，都去翻閱密碼本
load_dotenv(override=True)
# 網頁基本設定 (必須放在第一行)
st.set_page_config(page_title="全市場巨鯨監控", page_icon="🐋", layout="wide")

# ==========================================
# ⚙️ 網頁基本設定 & 狀態管理
# ==========================================
st.set_page_config(page_title="全市場巨鯨監控", layout="wide", page_icon="🐋")

if 'symbol' not in st.session_state:
    st.session_state.symbol = 'BTCUSDT'

def change_symbol(new_symbol):
    st.session_state.symbol = new_symbol
# 讀取環境變數
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

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
# 初始化 Supabase
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

st.markdown("##### 🔍 選擇監控標的")
col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 9]) 
supabase = init_supabase()

with col_btn1:
    st.button("🔥 BTCUSDT", use_container_width=True, 
              type="primary" if st.session_state.symbol == "BTCUSDT" else "secondary",
              on_click=change_symbol, args=("BTCUSDT",))
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

with col_btn2:
    st.button("💎 ETHUSDT", use_container_width=True, 
              type="primary" if st.session_state.symbol == "ETHUSDT" else "secondary",
              on_click=change_symbol, args=("ETHUSDT",))
    # 7. 圖例設定 (點擊可隱藏線條)
    p.legend.location = "top_left"
    p.legend.click_policy = "hide"
    p.legend.background_fill_alpha = 0.5

symbol = st.session_state.symbol
st.markdown("---")
    # 顯示圖表
    st.bokeh_chart(p, use_container_width=True)

# ==========================================
# 🔌 連線與讀取資料
# 網頁 UI 渲染
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
st.title("🐋 巨鯨合約宏觀監控儀表板")
st.markdown("觀測四大交易所籌碼動向，尋找大戶與散戶的背離訊號。")

df = load_data()
df_main = load_data()

# ==========================================
# 📊 畫圖與介面顯示
# ==========================================
if df.empty:
    st.warning("⚠️ 資料庫目前沒有資料，請確認「後端爬蟲程式 (whale_macro_tracker.py)」是否正在執行！")
if df_main.empty:
    st.error("⚠️ 資料庫目前沒有資料，請確認後端爬蟲是否正在執行！")
else:
    df_filtered = df[df['symbol'] == symbol]
    # 建立兩個分頁
    tab1, tab2 = st.tabs(["🔥 BTCUSDT", "💎 ETHUSDT"])

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

        with col1:
            st.subheader("帳戶多空比")
            st.caption("左軸：多空比 / 右軸：價格。【左鍵拖曳平移，滾輪縮放，雙擊還原】")
            
            fig_acc = px.line(df_filtered, x='time', y='ls_acc_ratio', color='exchange', color_discrete_map=color_map)
            fig_acc.update_traces(line_shape='spline', hovertemplate=hover_template) 
            
            if not df_price.empty:
                fig_acc.add_trace(
                    go.Scatter(
                        x=df_price['time'], y=df_price['price'], name=f"{symbol[:3]} 價格 (右軸)",
                        line=dict(color=price_color, width=2.5, dash='solid'), 
                        yaxis="y2", line_shape='spline', hovertemplate=hover_template_price
                    )
                )

            # 💡 修復：停用原生的 yaxis_title，改用 annotations 達成「真正的縱書」
            fig_acc.update_layout(
                dragmode='pan',
                xaxis=dict(title="", fixedrange=False),
                yaxis=dict(title="", fixedrange=True),
                yaxis2=dict(title="", overlaying="y", side="right", showgrid=False, fixedrange=True),
                hovermode="x unified",
                margin=dict(l=80, r=80, t=30, b=0), # 加大左右邊界預留給縱書文字
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                annotations=[
                    dict(
                        x=-0.12, y=0.5, xref='paper', yref='paper',
                        text="<b>帳<br>戶<br>比</b>", showarrow=False,
                        font=dict(size=18), align='center'
                    ),
                    dict(
                        x=1.12, y=0.5, xref='paper', yref='paper',
                        text="<b>價<br>格<br><span style='font-size: 13px;'>(USD)</span></b>", showarrow=False,
                        font=dict(size=18), align='center'
                    )
                ]
            )
            fig_acc.add_hline(y=1.0, line_dash="dash", line_color="red", opacity=0.5)
            
            st.plotly_chart(fig_acc, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})

        with col2:
            st.subheader("資金多空比")
            st.caption("僅 Binance 與 Bitget 提供。數值 < 1 代表大戶總資金偏空。")
            df_whale = df_filtered.dropna(subset=['ls_pos_ratio'])
            
            fig_pos = px.line(df_whale, x='time', y='ls_pos_ratio', color='exchange', color_discrete_map=color_map)
            fig_pos.update_traces(line_shape='spline', hovertemplate=hover_template)
            
            if not df_price.empty:
                fig_pos.add_trace(
                    go.Scatter(
                        x=df_price['time'], y=df_price['price'], name=f"{symbol[:3]} 價格 (右軸)",
                        line=dict(color=price_color, width=2.5, dash='solid'), 
                        yaxis="y2", line_shape='spline', hovertemplate=hover_template_price
                    )
                )

            # 💡 修復：停用原生的 yaxis_title，改用 annotations 達成「真正的縱書」
            fig_pos.update_layout(
                dragmode='pan',
                xaxis=dict(title="", fixedrange=False),
                yaxis=dict(title="", fixedrange=True),
                yaxis2=dict(title="", overlaying="y", side="right", showgrid=False, fixedrange=True),
                hovermode="x unified",
                margin=dict(l=80, r=80, t=30, b=0), 
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                annotations=[
                    dict(
                        x=-0.12, y=0.5, xref='paper', yref='paper',
                        text="<b>資<br>金<br>比</b>", showarrow=False,
                        font=dict(size=18), align='center'
                    ),
                    dict(
                        x=1.12, y=0.5, xref='paper', yref='paper',
                        text="<b>價<br>格<br><span style='font-size: 13px;'>(USD)</span></b>", showarrow=False,
                        font=dict(size=18), align='center'
                    )
                ]
            )
            fig_pos.add_hline(y=1.0, line_dash="dash", line_color="red", opacity=0.5)
            
            st.plotly_chart(fig_pos, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})

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
    with tab1:
        draw_macro_chart(df_main, "BTCUSDT")
        st.dataframe(df_main[df_main['symbol'] == "BTCUSDT"].sort_values('time', ascending=False).head(20), use_container_width=True)

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
    with tab2:
        draw_macro_chart(df_main, "ETHUSDT")
        st.dataframe(df_main[df_main['symbol'] == "ETHUSDT"].sort_values('time', ascending=False).head(20), use_container_width=True)
