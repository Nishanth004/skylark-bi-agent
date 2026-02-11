import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from openai import OpenAI

# --- PAGE CONFIG ---
st.set_page_config(page_title="Skylark BI Agent", layout="wide", page_icon="🚁")

# --- CSS ---
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; color: #1E1E1E;}
    .metric-card {background-color: #f0f2f6; padding: 20px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🚁 Skylark Drones Executive Agent</div>', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    MONDAY_API_KEY = st.text_input("Monday API Key", type="password")
    
    # CHANGED LABEL TO GROQ
    GROQ_API_KEY = st.text_input("Groq API Key (Free)", type="password")
    
    WO_BOARD_ID = st.text_input("Work Orders Board ID")
    DEALS_BOARD_ID = st.text_input("Deals Board ID")
    st.markdown("---")
    load_btn = st.button("🔄 Sync Data", type="primary")

# --- FETCH DATA ---
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
            if 'errors' in data: return pd.DataFrame(), str(data['errors'])
            
            items = data['data']['boards'][0]['items_page']['items']
            rows = []
            for item in items:
                row = {'Item Name': item['name']}
                for col in item['column_values']:
                    if col['column']['title']:
                        row[col['column']['title']] = col['text']
                rows.append(row)
            return pd.DataFrame(rows), None
        return pd.DataFrame(), "API Error"
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- CLEAN DATA ---
def process_data(df):
    if df.empty: return df
    
    # Clean Numeric Columns
    for col in df.columns:
        col_lower = col.lower()
        if any(x in col_lower for x in ['amount', 'price', 'value', 'budget', 'masked']):
            # Remove currency symbols, commas, and handle "Masked" text
            df[col] = df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- AI ENGINE (GROQ VERSION) ---
def ask_analyst(query, df_wo, df_deals, api_key, is_briefing=False):
    # SWITCH TO GROQ CLIENT
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key
    )
    
    # Truncate context
    wo_context = df_wo.head(50).to_csv(index=False)
    deal_context = df_deals.head(50).to_csv(index=False)
    
    role_desc = "Chief of Staff" if is_briefing else "Senior BI Analyst"
    
    system_prompt = f"""
    You are the {role_desc} at Skylark Drones.
    
    DATA CONTEXT:
    1. WORK ORDERS: {wo_context}
    2. DEALS: {deal_context}
    
    INSTRUCTIONS:
    - If the user asks for a Leadership Update, provide: Executive Summary, Revenue Pulse, and Risk Watch.
    - Note that 'Masked' values in data are treated as 0 or missing. Mention this caveat.
    - Keep answers professional and concise.
    """
    
    try:
        response = client.chat.completions.create(
            # USING FREE LLAMA 3 MODEL
            model="llama3-8b-8192", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq API Error: {str(e)}"

# --- MAIN LOGIC ---
if 'wo_data' not in st.session_state: st.session_state.wo_data = None
if 'deal_data' not in st.session_state: st.session_state.deal_data = None

if load_btn and MONDAY_API_KEY:
    with st.spinner("Fetching..."):
        wo, err1 = fetch_board_data(WO_BOARD_ID, MONDAY_API_KEY)
        deals, err2 = fetch_board_data(DEALS_BOARD_ID, MONDAY_API_KEY)
        
        st.session_state.wo_data = process_data(wo)
        st.session_state.deal_data = process_data(deals)
        
        if not wo.empty: st.success("Data Synced!")

if st.session_state.wo_data is not None:
    wo = st.session_state.wo_data
    deals = st.session_state.deal_data
    
    # --- METRICS ---
    rev_col = next((c for c in wo.columns if "incl" in c.lower() and "amount" in c.lower()), None)
    total_rev = wo[rev_col].sum() if rev_col else 0
    
    pipe_col = next((c for c in deals.columns if "value" in c.lower()), None)
    total_pipe = deals[pipe_col].sum() if pipe_col else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Active Projects", len(wo))
    c2.metric("Pipeline Deals", len(deals))
    c3.metric("Est. Pipeline Value", f"₹{total_pipe:,.0f}")
    
    st.divider()
    
    t1, t2, t3 = st.tabs(["🤖 Analyst", "📊 Visuals", "📂 Data"])
    
    with t1:
        q = st.text_area("Ask a question:", height=100)
        c_act, c_b = st.columns([1, 4])
        
        # NOTE: WE USE GROQ_API_KEY HERE
        if c_act.button("Analyze"):
            if not GROQ_API_KEY:
                st.error("Missing Groq Key")
            else:
                with st.spinner("Thinking (Llama 3)..."):
                    res = ask_analyst(q, wo, deals, GROQ_API_KEY)
                    st.markdown(res)
        
        if c_b.button("📝 Generate Leadership Briefing"):
             if not GROQ_API_KEY:
                st.error("Missing Groq Key")
             else:
                with st.spinner("Writing Briefing..."):
                    res = ask_analyst("Leadership Update", wo, deals, GROQ_API_KEY, is_briefing=True)
                    st.markdown(res)

    with t2:
        st.subheader("Sector Performance")
        sec_col = next((c for c in wo.columns if "sector" in c.lower()), None)
        
        if sec_col and rev_col:
            df_chart = wo.groupby(sec_col)[rev_col].sum().reset_index()
            fig = px.bar(df_chart, x=sec_col, y=rev_col, title="Revenue by Sector", color=sec_col)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Data mismatch for charts.")

    with t3:
        st.dataframe(wo)
        st.dataframe(deals)