import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from openai import OpenAI

# --- PAGE CONFIG ---
st.set_page_config(page_title="Skylark Executive BI", layout="wide", page_icon="🚁")

# --- UI STYLING ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .briefing-card { background-color: #e3f2fd; padding: 20px; border-radius: 10px; border-left: 5px solid #1976d2; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚁 Skylark Drones Executive Intelligence")
st.markdown("---")

# --- SIDEBAR: AUTH ---
with st.sidebar:
    st.header("🔑 Connection")
    MONDAY_KEY = st.text_input("Monday API Key", type="password")
    GROQ_KEY = st.text_input("Groq API Key (Free)", type="password")
    
    col_a, col_b = st.columns(2)
    WO_ID = col_a.text_input("WO Board ID")
    DEAL_ID = col_b.text_input("Deal Board ID")
    
    st.markdown("---")
    sync = st.button("🔄 Sync Live Data", type="primary")
    st.caption("Connected to Groq Llama-3.3-70b (Free Tier)")

# --- DATA FETCHING ---
def get_data(board_id, api_key):
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
        res = requests.post(url, json={'query': query}, headers=headers)
        data = res.json()
        items = data['data']['boards'][0]['items_page']['items']
        rows = []
        for item in items:
            r = {'Item Name': item['name']}
            for cv in item['column_values']:
                r[cv['column']['title']] = cv['text']
            rows.append(r)
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

def clean_biz_data(df):
    if df.empty: return df
    # Clean numeric columns (Masked amounts, Rupees, etc.)
    for col in df.columns:
        if any(x in col.lower() for x in ['amount', 'rupees', 'value', 'billed', 'collected']):
            df[col] = df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# --- AI ANALYST (UPDATED MODEL) ---
def run_ai(prompt, wo_df, deal_df, api_key, briefing=False):
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
    
    # Use the latest Groq model (llama-3.3-70b-specdec is current)
    model_name = "llama-3.3-70b-specdec" 
    
    ctx = f"WORK ORDERS (Top 30):\n{wo_df.head(30).to_csv()}\n\nDEALS (Top 30):\n{deal_df.head(30).to_csv()}"
    
    system = "You are the Skylark Drones Chief Analyst. Use the data provided to answer questions. "
    if briefing:
        system += "Prepare an Executive Briefing with sections: Summary, Revenue Pulse, and Risk Watch."
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": f"Context: {ctx}\n\nQuestion: {prompt}"}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Groq Error: {str(e)}"

# --- APP FLOW ---
if 'wo' not in st.session_state: st.session_state.wo = None
if 'deals' not in st.session_state: st.session_state.deals = None

if sync:
    with st.spinner("Synchronizing..."):
        st.session_state.wo = clean_biz_data(get_data(WO_ID, MONDAY_KEY))
        st.session_state.deals = clean_biz_data(get_data(DEAL_ID, MONDAY_KEY))

if st.session_state.wo is not None:
    wo = st.session_state.wo
    deals = st.session_state.deals

    # --- TOP METRICS ---
    # Find specific revenue/pipeline columns
    rev_col = next((c for c in wo.columns if "incl" in c.lower() and "amount" in c.lower()), None)
    pipe_col = next((c for c in deals.columns if "value" in c.lower()), None)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Projects", len(wo))
    m2.metric("Total Pipeline", len(deals))
    m3.metric("Billed Revenue", f"₹{wo[rev_col].sum():,.0f}" if rev_col else "₹0")
    m4.metric("Pipeline Value", f"₹{deals[pipe_col].sum():,.0f}" if pipe_col else "₹0")

    # --- TABS ---
    tab_chat, tab_viz, tab_data = st.tabs(["💬 AI Analyst", "📈 Visual Insights", "📁 Raw Boards"])

    with tab_chat:
        st.subheader("Ask the Business Intelligence Agent")
        user_in = st.text_area("Question:", placeholder="e.g. Which sectors have the most projects?")
        
        c1, c2 = st.columns([1, 4])
        if c1.button("Analyze", type="secondary"):
            st.markdown(run_ai(user_in, wo, deals, GROQ_KEY))
        
        if c2.button("📊 Generate Leadership Update", type="primary"):
            st.markdown('<div class="briefing-card">', unsafe_allow_html=True)
            st.markdown(run_ai("Leadership Update", wo, deals, GROQ_KEY, briefing=True))
            st.markdown('</div>', unsafe_allow_html=True)

    with tab_viz:
        st.subheader("Revenue Distribution by Sector")
        # Map sector columns
        wo_sector = next((c for c in wo.columns if "sector" in c.lower()), None)
        if wo_sector and rev_col:
            chart_df = wo.groupby(wo_sector)[rev_col].sum().reset_index()
            fig = px.pie(chart_df, names=wo_sector, values=rev_col, hole=0.4, 
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Sector or Revenue column missing for visualization.")

    with tab_data:
        st.subheader("Live Board Previews")
        with st.expander("Work Orders Board"):
            st.dataframe(wo)
        with st.expander("Deals Board"):
            st.dataframe(deals)
else:
    st.info("👈 Enter your keys in the sidebar and click Sync to begin.")