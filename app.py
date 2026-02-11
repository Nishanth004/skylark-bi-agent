import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from openai import OpenAI

# --- PAGE CONFIG ---
st.set_page_config(page_title="Skylark BI Agent", layout="wide", page_icon="🚁")

# --- CSS FOR PROFESSIONAL LOOK ---
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; color: #1E1E1E;}
    .sub-header {font-size: 1.5rem; color: #4A4A4A;}
    .metric-card {background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🚁 Skylark Drones Executive Agent</div>', unsafe_allow_html=True)

# --- SIDEBAR: CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")
    MONDAY_API_KEY = st.text_input("Monday API Key", type="password")
    OPENAI_API_KEY = st.text_input("OpenAI API Key", type="password")
    WO_BOARD_ID = st.text_input("Work Orders Board ID")
    DEALS_BOARD_ID = st.text_input("Deals Board ID")
    
    st.markdown("---")
    load_btn = st.button("🔄 Sync with Monday.com", type="primary")
    
    st.info("💡 **Tip:** Use the 'Leadership Briefing' button for a one-click executive update.")

# --- MODULE: MONDAY.COM INTEGRATION ---
def fetch_board_data(board_id, api_key):
    url = "https://api.monday.com/v2"
    headers = {"Authorization": api_key, "API-Version": "2023-10"}
    
    query = f"""
    query {{
      boards (ids: {board_id}) {{
        items_page (limit: 500) {{
          items {{
            name
            column_values {{
              column {{ title }}
              text
            }}
          }}
        }}
      }}
    }}
    """
    try:
        response = requests.post(url, json={'query': query}, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'errors' in data:
                return pd.DataFrame(), f"GraphQL Error: {data['errors'][0]['message']}"
            
            items = data['data']['boards'][0]['items_page']['items']
            rows = []
            for item in items:
                row = {'Item Name': item['name']}
                for col in item['column_values']:
                    if col['column']['title']:
                        row[col['column']['title']] = col['text']
                rows.append(row)
            return pd.DataFrame(rows), None
        else:
            return pd.DataFrame(), f"HTTP Error: {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- MODULE: DATA RESILIENCE & CLEANING ---
def process_data(df):
    if df.empty: return df
    
    # 1. Normalize Text (Handle messy casing)
    cols_to_normalize = ['Sector', 'Status', 'Deal Stage', 'Execution Status']
    for col in df.columns:
        for target in cols_to_normalize:
            if target in col:
                df[col] = df[col].astype(str).str.strip().str.title()

    # 2. Handle Numeric & Currency
    for col in df.columns:
        if any(x in col.lower() for x in ['amount', 'price', 'value', 'billed', 'collected']):
            # Remove symbols, handle "Masked" values by coercing to NaN
            df[col] = df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 3. Handle Dates
    for col in df.columns:
        if 'date' in col.lower():
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
    return df

# --- MODULE: INTELLIGENCE ENGINE ---
def ask_analyst(query, df_wo, df_deals, api_key, is_briefing=False):
    client = OpenAI(api_key=api_key)
    
    # Create lightweight context
    # We limit to first 100 rows to avoid token limits if data is huge
    wo_context = df_wo.head(100).to_csv(index=False)
    deal_context = df_deals.head(100).to_csv(index=False)
    
    # specialized prompt for leadership updates vs normal queries
    if is_briefing:
        role_instruction = """
        You are the Chief of Staff preparing a **Leadership Update Memo**.
        Format your response as follows:
        1. **Executive Summary**: 3 bullet points on overall health.
        2. **Revenue Pulse**: Billed vs. Collected (Cash Flow).
        3. **Pipeline Radar**: High probability deals closing soon.
        4. **Risk Watch**: Projects marked "Stuck", "On Hold", or with massive outstanding balances.
        """
    else:
        role_instruction = """
        You are a Senior BI Analyst. Answer the user's specific question.
        - If data is "Masked" or 0, explicitly mention this as a data quality caveat.
        - Normalize sectors (e.g., treat "Mining" and "mining" as the same).
        - If the user asks for a chart, provide the data in a table format so I can plot it.
        """

    system_prompt = f"""
    {role_instruction}
    
    DATA CONTEXT:
    --- WORK ORDERS (Project Execution) ---
    {wo_context}
    
    --- DEALS (Sales Pipeline) ---
    {deal_context}
    
    Refuse to answer non-business questions.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # CHANGED FROM gpt-4 to gpt-4o-mini
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {e}"

# --- MAIN LOGIC ---

# Session State Initialization
if 'wo_data' not in st.session_state: st.session_state.wo_data = None
if 'deal_data' not in st.session_state: st.session_state.deal_data = None

# Data Loading Logic
if load_btn:
    if not (MONDAY_API_KEY and WO_BOARD_ID and DEALS_BOARD_ID):
        st.error("❌ Please provide all Credentials.")
    else:
        with st.spinner("📡 Connecting to Monday.com..."):
            wo_raw, err1 = fetch_board_data(WO_BOARD_ID, MONDAY_API_KEY)
            deal_raw, err2 = fetch_board_data(DEALS_BOARD_ID, MONDAY_API_KEY)
            
            if err1 or err2:
                st.error(f"Connection Failed: {err1 or err2}")
            else:
                st.session_state.wo_data = process_data(wo_raw)
                st.session_state.deal_data = process_data(deal_raw)
                st.success(f"✅ Synced {len(st.session_state.wo_data)} Work Orders & {len(st.session_state.deal_data)} Deals")

# UI Layout
if st.session_state.wo_data is not None:
    
    wo_df = st.session_state.wo_data
    deal_df = st.session_state.deal_data
    
    # Calculate Totals
    total_rev = 0
    # Find likely revenue column
    rev_col = next((c for c in wo_df.columns if "amount" in c.lower() and "incl" in c.lower()), None)
    if rev_col:
        total_rev = wo_df[rev_col].sum()

    total_pipeline = 0
    # Find likely pipeline value column
    pipe_col = next((c for c in deal_df.columns if "value" in c.lower()), None)
    if pipe_col:
        total_pipeline = deal_df[pipe_col].sum()

    # Top Stats Bar
    col1, col2, col3 = st.columns(3)
    col1.metric("Active Projects", len(wo_df))
    col2.metric("Pipeline Deals", len(deal_df))
    col3.metric("Total Pipeline Value", f"₹{total_pipeline:,.0f}")
    
    st.divider()

    # Main Interaction Area
    tab1, tab2, tab3 = st.tabs(["🤖 Analyst Agent", "📊 Visuals", "📂 Raw Data"])
    
    with tab1:
        st.subheader("Business Intelligence Query")
        col_q, col_btn = st.columns([4, 1])
        
        user_query = col_q.text_area("Ask a question about the business:", height=100, placeholder="e.g., Which sector has the highest outstanding receivables?")
        
        # Space for buttons
        b1 = col_btn.button("Analyze", use_container_width=True)
        b2 = col_btn.button("📝 Leadership Briefing", use_container_width=True, type="primary")
        
        if b1 or b2:
            if not OPENAI_API_KEY:
                st.error("Please enter OpenAI API Key.")
            else:
                prompt = "Generate a leadership update." if b2 else user_query
                with st.spinner("Analyzing data..."):
                    response = ask_analyst(prompt, wo_df, deal_df, OPENAI_API_KEY, is_briefing=b2)
                    st.markdown("### 📋 Insights")
                    st.markdown(response)

    with tab2:
        st.subheader("Sector Performance Analysis")
        # Try to find Sector and Amount columns automatically
        sector_col = next((c for c in wo_df.columns if 'sector' in c.lower()), None)
        amount_col = next((c for c in wo_df.columns if 'amount' in c.lower()), None)
        
        if sector_col and amount_col:
            chart_data = wo_df.groupby(sector_col)[amount_col].sum().reset_index()
            fig = px.bar(chart_data, x=sector_col, y=amount_col, title="Revenue by Sector", color=sector_col)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Could not automatically determine Sector or Amount columns for the chart.")

    with tab3:
        st.subheader("Work Orders Board")
        st.dataframe(wo_df)
        st.markdown("---")
        st.subheader("Deals Board")
        st.dataframe(deal_df)

else:
    st.info("👈 Please enter your API keys and connect in the sidebar to begin.")