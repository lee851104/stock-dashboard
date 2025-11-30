import streamlit as st
import yfinance as yf
import pandas as pd  # <--- 就是這行漏掉了，現在補上了
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# 頁面設定
# ---------------------------------------------------------
st.set_page_config(page_title="投資組合風險監控 (公開版)", layout="wide")
st.title("🏦 投資組合風險監控面板")
st.markdown("請在左側側邊欄輸入您的持倉數據 (支援多券商)，系統將自動彙整並分析風險。")
st.markdown("---")


# ---------------------------------------------------------
# 1. 初始化資料 (空白模板)
# ---------------------------------------------------------
# 定義標準的空白資料結構
def get_empty_df():
    return pd.DataFrame({
        "代號": pd.Series(dtype="str"),
        "股數": pd.Series(dtype="float"),
        "平均成本": pd.Series(dtype="float"),
        "Beta (自訂)": pd.Series(dtype="float")
    })


if 'broker_1' not in st.session_state:
    st.session_state.broker_1 = get_empty_df()

if 'broker_2' not in st.session_state:
    st.session_state.broker_2 = get_empty_df()

if 'broker_3' not in st.session_state:
    st.session_state.broker_3 = get_empty_df()

# 欄位設定
columns_config = {
    "代號": st.column_config.TextColumn(help="股票代碼 (例如 AAPL)"),
    "股數": st.column_config.NumberColumn(min_value=0, format="%.2f", default=0),
    "平均成本": st.column_config.NumberColumn(min_value=0, format="$%.2f", default=0),
    "Beta (自訂)": st.column_config.NumberColumn(
        min_value=0.0, max_value=10.0, step=0.01, format="%.2f",
        help="若不填寫，系統將自動抓取 Yahoo Finance 數據"
    ),
}

# ---------------------------------------------------------
# 2. 側邊欄：輸入區
# ---------------------------------------------------------
st.sidebar.header("📝 持倉編輯")
st.sidebar.info("初次使用請點擊表格下方的 `+` 號新增股票。")

with st.sidebar.expander("📂 券商 A (主要)", expanded=True):
    edited_b1 = st.data_editor(st.session_state.broker_1, num_rows="dynamic", column_config=columns_config, key="ed_b1",
                               hide_index=True)
with st.sidebar.expander("📂 券商 B (次要)"):
    edited_b2 = st.data_editor(st.session_state.broker_2, num_rows="dynamic", column_config=columns_config, key="ed_b2",
                               hide_index=True)
with st.sidebar.expander("📂 券商 C (其他)"):
    edited_b3 = st.data_editor(st.session_state.broker_3, num_rows="dynamic", column_config=columns_config, key="ed_b3",
                               hide_index=True)

if st.sidebar.button("🔄 更新分析結果"):
    st.session_state.broker_1 = edited_b1
    st.session_state.broker_2 = edited_b2
    st.session_state.broker_3 = edited_b3
    st.rerun()


# ---------------------------------------------------------
# 3. 數據處理
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
            # 跳過還沒輸入代號的空行
            if pd.isna(ticker) or str(ticker).strip() == "": continue

            ticker = str(ticker).upper()
            shares = row.get("股數", 0)
            cost = row.get("平均成本", 0)
            user_beta = row.get("Beta (自訂)", 0)

            # 如果股數是 0，就不抓取數據以節省資源
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
            except:
                pass

            current_progress += 1
            progress_bar.progress(min(current_progress / total_rows, 1.0))

    progress_bar.empty()
    return results


def create_overall_beta_gauge(weighted_beta):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=weighted_beta,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "<b>總體組合 Beta</b>", 'font': {'size': 18}},
        gauge={
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
# 4. 主畫面佈局
# ---------------------------------------------------------
data_sources = [edited_b1, edited_b2, edited_b3]
stock_data = fetch_risk_data(data_sources)

if stock_data:
    raw_df = pd.DataFrame(stock_data)

    # 數據聚合
    grouped_df = raw_df.groupby(['Ticker', 'Sector'], as_index=False).agg({
        'MarketValue': 'sum',
        'RiskExposure': 'sum',
        'PL_Val': 'sum',
        'Shares': 'sum',
        'Price': 'first',
        'BetaSource': 'first'
    })

    grouped_df['Beta'] = grouped_df['RiskExposure'] / grouped_df['MarketValue']

    # 指標計算
    total_assets = grouped_df['MarketValue'].sum()
    total_risk_exposure = grouped_df['RiskExposure'].sum()
    total_pl = grouped_df['PL_Val'].sum()
    initial_capital = total_assets - total_pl
    total_pl_pct = (total_pl / initial_capital) * 100 if initial_capital > 0 else 0

    if total_assets > 0:
        portfolio_beta = total_risk_exposure / total_assets
    else:
        portfolio_beta = 0

    # === 第一列 ===
    c1, c2, c3 = st.columns([1, 1.2, 1])

    with c1:
        st.plotly_chart(create_overall_beta_gauge(portfolio_beta), use_container_width=True)

    with c2:
        fig_pie = px.pie(
            grouped_df,
            values='MarketValue',
            names='Ticker',
            hole=0.4,
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

    # === 第二列 ===
    st.subheader("🔥 全局風險矩陣 (面積大小 = 風險當量)")
    st.caption("現在方塊的**面積**代表「風險當量 (市值 x Beta)」。")

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
    # 這是給分享對象看到的歡迎畫面
    st.info("👋 歡迎使用風險監控面板！請在左側的「券商資料夾」中點擊 `+` 新增您的股票。")
    st.markdown("""
    **使用說明：**
    1. 展開左側的 **📂 券商資料夾**。
    2. 在表格下方點擊灰色區域或 `+` 號。
    3. 輸入 **代號** (如 NVDA) 與 **股數**。
    4. 點擊 **🔄 更新分析結果**。
    """)