import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# ---------------------------------------------------------
# 頁面設定
# ---------------------------------------------------------
st.set_page_config(page_title="投資組合風險監控 (Pro)", layout="wide")
st.title("🏦 投資組合風險監控面板")
st.markdown("支援 **存檔與讀檔** 功能，請在左側側邊欄進行操作。")
st.markdown("---")

# ---------------------------------------------------------
# 1. 輔助函數：資料結構定義
# ---------------------------------------------------------
def get_empty_df():
    return pd.DataFrame({
        "代號": pd.Series(dtype="str"),
        "股數": pd.Series(dtype="float"),
        "平均成本": pd.Series(dtype="float"),
        "Beta (自訂)": pd.Series(dtype="float")
    })

# ---------------------------------------------------------
# 2. 初始化 Session State
# ---------------------------------------------------------
if 'broker_1' not in st.session_state:
    st.session_state.broker_1 = get_empty_df()

if 'broker_2' not in st.session_state:
    st.session_state.broker_2 = get_empty_df()

if 'broker_3' not in st.session_state:
    st.session_state.broker_3 = get_empty_df()

# ---------------------------------------------------------
# 3. 側邊欄：存檔與讀檔區 (新功能)
# ---------------------------------------------------------
st.sidebar.header("💾 存檔與讀檔")
st.sidebar.caption("由於沒有登入系統，請將設定檔下載至您的電腦以保存資料。")

# --- 讀檔功能 ---
uploaded_file = st.sidebar.file_uploader("📂 讀取舊檔案 (Upload CSV)", type=['csv'])

if uploaded_file is not None:
    try:
        # 讀取 CSV
        df_uploaded = pd.read_csv(uploaded_file)
        
        # 檢查是否有必要的欄位
        required_cols = ["Broker_ID", "代號", "股數", "平均成本", "Beta (自訂)"]
        if all(col in df_uploaded.columns for col in required_cols):
            # 分配回各自的 DataFrame
            st.session_state.broker_1 = df_uploaded[df_uploaded['Broker_ID'] == 'A'][["代號", "股數", "平均成本", "Beta (自訂)"]].reset_index(drop=True)
            st.session_state.broker_2 = df_uploaded[df_uploaded['Broker_ID'] == 'B'][["代號", "股數", "平均成本", "Beta (自訂)"]].reset_index(drop=True)
            st.session_state.broker_3 = df_uploaded[df_uploaded['Broker_ID'] == 'C'][["代號", "股數", "平均成本", "Beta (自訂)"]].reset_index(drop=True)
            st.sidebar.success("✅ 讀檔成功！資料已還原。")
        else:
            st.sidebar.error("❌ 檔案格式錯誤，請使用本系統產出的 CSV。")
    except Exception as e:
        st.sidebar.error(f"讀取失敗: {e}")

# --- 存檔功能 ---
# 將三個券商的資料合併成一個 CSV 供下載
def convert_df_to_csv():
    b1 = st.session_state.broker_1.copy()
    b1['Broker_ID'] = 'A'
    
    b2 = st.session_state.broker_2.copy()
    b2['Broker_ID'] = 'B'
    
    b3 = st.session_state.broker_3.copy()
    b3['Broker_ID'] = 'C'
    
    # 合併並過濾掉空行
    full_df = pd.concat([b1, b2, b3], ignore_index=True)
    full_df = full_df[full_df['代號'].notna() & (full_df['代號'] != "")]
    
    return full_df.to_csv(index=False).encode('utf-8')

csv_data = convert_df_to_csv()

st.sidebar.download_button(
    label="💾 下載目前設定 (Save to CSV)",
    data=csv_data,
    file_name='my_portfolio_config.csv',
    mime='text/csv',
)

st.sidebar.markdown("---")

# ---------------------------------------------------------
# 4. 側邊欄：持倉編輯區
# ---------------------------------------------------------
columns_config = {
    "代號": st.column_config.TextColumn(help="股票代碼"),
    "股數": st.column_config.NumberColumn(min_value=0, format="%.2f", default=0),
    "平均成本": st.column_config.NumberColumn(min_value=0, format="$%.2f", default=0),
    "Beta (自訂)": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help="若不填寫則自動抓取"),
}

st.sidebar.header("📝 持倉編輯")

with st.sidebar.expander("📂 券商 A", expanded=True):
    edited_b1 = st.data_editor(st.session_state.broker_1, num_rows="dynamic", column_config=columns_config, key="ed_b1", hide_index=True)
with st.sidebar.expander("📂 券商 B"):
    edited_b2 = st.data_editor(st.session_state.broker_2, num_rows="dynamic", column_config=columns_config, key="ed_b2", hide_index=True)
with st.sidebar.expander("📂 券商 C"):
    edited_b3 = st.data_editor(st.session_state.broker_3, num_rows="dynamic", column_config=columns_config, key="ed_b3", hide_index=True)

if st.sidebar.button("🔄 更新分析結果"):
    # 這裡不需要特別做什麼，因為 data_editor 會自動更新 session_state
    # 但為了確保重新執行以刷新圖表，保留 rerun
    st.rerun()

# ---------------------------------------------------------
# 5. 數據處理與繪圖
# ---------------------------------------------------------
def fetch_risk_data(df_list):
    results = []
    # 過濾掉空的 DataFrame
    valid_dfs = [df for df in df_list if not df.empty]
    total_rows = sum([len(df) for df in valid_dfs])
    
    if total_rows == 0: return []

    progress_bar = st.progress(0)
    current_progress = 0
    
    for df in valid_dfs:
        for idx, row in df.iterrows():
            ticker = row.get("代號")
            if pd.isna(ticker) or str(ticker).strip() == "": continue
            
            ticker = str(ticker).upper()
            shares = row.get("股數", 0)
            cost = row.get("平均成本", 0)
            user_beta = row.get("Beta (自訂)", 0)
            
            if shares <= 0: continue

            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                
                price = info.get('currentPrice') or info.get('previousClose')
                if price is None:
                    hist = stock.history(period='1d')
                    if not hist.empty: price = hist['Close'].iloc[-1]
                
                if user_beta and user_beta > 0:
                    final_beta = user_beta
                    source_note = "(自訂)"
                else:
                    fetched_beta = info.get('beta', 1.0)
                    final_beta = fetched_beta if fetched_beta is not None else 1.0
                    source_note = "(系統)"

                sector = info.get('sector', '其他')
                
                if price:
                    market_value = price * shares
                    risk_exposure = market_value * final_beta
                    pl_val = (price - cost) * shares
                    
                    results.append({
                        'Ticker': ticker,
                        'Sector': sector,
                        'Price': price,
                        'Beta': final_beta,
                        'BetaSource': source_note,
                        'Shares': shares,
                        'MarketValue': market_value,
                        'RiskExposure': risk_exposure,
                        'PL_Val': pl_val
                    })
            except: pass
            
            current_progress += 1
            progress_bar.progress(min(current_progress / total_rows, 1.0))
            
    progress_bar.empty()
    return results

def create_overall_beta_gauge(weighted_beta):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = weighted_beta,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "<b>總體組合 Beta</b>", 'font': {'size': 18}},
        gauge = {
            'axis': {'range': [None, 3.0], 'tickwidth': 1},
            'bar': {'color': "black", 'thickness': 0.05},
            'bgcolor': "white",
            'borderwidth': 2,
            'steps': [
                {'range': [0, 0.8], 'color': "#a3e635"},
                {'range': [0.8, 1.2], 'color': "#facc15"},
                {'range': [1.2, 3.0], 'color': "#f87171"},
            ],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': weighted_beta}
        }
    ))
    fig.update_layout(height=250, margin=dict(l=30, r=30, t=50, b=10))
    return fig

# ---------------------------------------------------------
# 6. 主畫面顯示
# ---------------------------------------------------------
data_sources = [edited_b1, edited_b2, edited_b3]
stock_data = fetch_risk_data(data_sources)

if stock_data:
    raw_df = pd.DataFrame(stock_data)
    
    # 聚合計算
    grouped_df = raw_df.groupby(['Ticker', 'Sector'], as_index=False).agg({
        'MarketValue': 'sum',
        'RiskExposure': 'sum',
        'PL_Val': 'sum',
        'Shares': 'sum',
        'Price': 'first',
        'BetaSource': 'first'
    })
    
    grouped_df['Beta'] = grouped_df['RiskExposure'] / grouped_df['MarketValue']
    
    total_assets = grouped_df['MarketValue'].sum()
    total_risk_exposure = grouped_df['RiskExposure'].sum()
    total_pl = grouped_df['PL_Val'].sum()
    initial_capital = total_assets - total_pl
    total_pl_pct = (total_pl / initial_capital) * 100 if initial_capital > 0 else 0
    
    if total_assets > 0:
        portfolio_beta = total_risk_exposure / total_assets
    else:
        portfolio_beta = 0

    c1, c2, c3 = st.columns([1, 1.2, 1])
    
    with c1:
        st.plotly_chart(create_overall_beta_gauge(portfolio_beta), use_container_width=True)
        
    with c2:
        fig_pie = px.pie(
            grouped_df, values='MarketValue', names='Ticker', hole=0.4,
            title=f"<b>資產配置 (資金佔比)</b>"
        )
        fig_pie.update_traces(textinfo='label+percent', textposition='inside')
        fig_pie.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=280)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c3:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.metric("💰 總資產", f"${total_assets:,.0f}")
        st.metric("💣 總風險權重", f"${total_risk_exposure:,.0f}")
        st.metric("📈 帳面損益 (估)", f"${total_pl:+,.0f}", f"{total_pl_pct:+.2f}%")

    st.divider()

    st.subheader("🔥 全局風險矩陣 (面積大小 = 風險當量)")
    st.caption("若要保存目前的輸入，請使用左側的「💾 存檔與讀檔」功能。")

    fig_tree = px.treemap(
        grouped_df,
        path=[px.Constant("我的投資組合"), 'Sector', 'Ticker'], 
        values='RiskExposure',
        color='Beta',          
        color_continuous_scale='RdYlGn_r',
        color_continuous_midpoint=1.0,
        range_color=[0.5, 2.5],
        custom_data=['Price', 'Beta', 'RiskExposure', 'BetaSource', 'Shares', 'MarketValue']
    )
    
    fig_tree.update_traces(
        textposition="middle center",
        texttemplate="<b>%{label}</b><br>Beta: %{customdata[1]:.2f}",
        hovertemplate="""
        <b>%{label}</b><br>
        💣 風險當量 (面積): $%{value:,.0f}<br>
        💰 真實市值: $%{customdata[5]:,.0f}<br>
        ⚡ 加權 Beta: %{customdata[1]:.2f}<br>
        <extra></extra>
        """
    )
    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=600)
    st.plotly_chart(fig_tree, use_container_width=True)

else:
    st.info("👋 歡迎使用風險監控面板！")
    st.markdown("""
    **如何保存我的資料？**
    1. 在左側輸入您的股票資料。
    2. 輸入完畢後，點擊左側上方的 **「💾 下載目前設定」** 按鈕，這會下載一個 `.csv` 檔案到您的電腦。
    3. **下次使用時**：將該 `.csv` 檔案拖曳到左側的 **「📂 讀取舊檔案」** 框框中，您的持倉就會自動還原了！
    """)
