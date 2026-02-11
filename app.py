import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from openai import OpenAI

# --- PAGE CONFIG ---
st.set_page_config(page_title="Skylark Executive BI", layout="wide", page_icon="🚁")

# --- UI STYLING (Fixed for Visibility) ---
st.markdown("""
    <style>
    .stMetric { 
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    /* Ensure metric text is visible in dark mode */
    [data-testid="stMetricValue"] { color: #1f77b4 !important; }
    [data-testid="stMetricLabel"] { color: #333333 !important; }
    
    .briefing-card { 
        background-color: #f0f7ff; 
        color: #1e3a8a;
        padding: 25px; 
        border-radius: 10px; 
        border-left: 8px solid #2563eb; 
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚁 Skylark Drones Executive Intelligence")
st.markdown("---")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 Connection")
    MONDAY_KEY = st.text_input("Monday API Key", type="password")
    GROQ_KEY = st.text_input("Groq API Key (Free)", type="password")
    
    col_a, col_b = st.columns(2)
    WO_ID = col_a.text_input("WO Board ID")
    DEAL_ID = col_b.text_input("Deal Board ID")
    
    st.markdown("---")
    sync = st.button("🔄 Sync Live Data", type="primary")

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
    for col in df.columns:
        # Targeting specific headers: "Amount", "Value", "Rupees", "Masked"
        if any(x in col.lower() for x in ['amount', 'value', 'rupees', 'billed']):
            df[col] = df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# --- AI ANALYST (STABLE MODEL) ---
def run_ai(prompt, wo_df, deal_df, api_key, briefing=False):
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
    
    # Model ID updated to the currently active versatile model
    model_name = "llama-3.3-70b-versatile" 
    
    ctx = f"WORK ORDERS DATA:\n{wo_df.head(40).to_csv()}\n\nDEALS DATA:\n{deal_df.head(40).to_csv()}"
    
    system = "You are the Chief Business Analyst for Skylark Drones. Provide insights based on the provided CSV data."
    if briefing:
        system = "You are the Chief of Staff. Summarize the business health. Focus on Revenue (Billed vs Pipeline) and Risks."
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": f"Context: {ctx}\n\nQuestion: {prompt}"}],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Groq Error: {str(e)}"

# --- APP FLOW ---
if 'wo' not in st.session_state: st.session_state.wo = None
if 'deals' not in st.session_state: st.session_state.deals = None

if sync:
    with st.spinner("Fetching Data..."):
        st.session_state.wo = clean_biz_data(get_data(WO_ID, MONDAY_KEY))
        st.session_state.deals = clean_biz_data(get_data(DEAL_ID, MONDAY_KEY))

if st.session_state.wo is not None:
    wo = st.session_state.wo
    deals = st.session_state.deals

    # --- ENHANCED COLUMN MATCHING ---
    # Work Orders Revenue
    rev_col = next((c for c in wo.columns if "Amount in Rupees (Incl of GST)" in c or "Incl" in c), None)
    # Deals Pipeline Value
    pipe_col = next((c for c in deals.columns if "Masked Deal value" in c or "Deal value" in c or "value" in c.lower()), None)
    # Sector Column
    sector_col = next((c for c in wo.columns if "Sector" in c or "sector" in c.lower()), None)

    # --- METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Projects", len(wo))
    m2.metric("Pipeline Deals", len(deals))
    
    billed_total = wo[rev_col].sum() if rev_col else 0
    m3.metric("Billed Revenue", f"₹{billed_total:,.0f}")
    
    pipeline_total = deals[pipe_col].sum() if pipe_col else 0
    m4.metric("Pipeline Value", f"₹{pipeline_total:,.0f}")

    # --- TABS ---
    tab_chat, tab_viz, tab_data = st.tabs(["💬 AI Analyst", "📈 Visual Insights", "📁 Raw Boards"])

    with tab_chat:
        user_in = st.text_area("Ask the Analyst:", placeholder="Which customer has the highest pending amount?")
        
        c1, c2 = st.columns([1, 4])
        if c1.button("Analyze", type="secondary"):
            if not GROQ_KEY: st.error("Enter Groq Key")
            else: st.markdown(run_ai(user_in, wo, deals, GROQ_KEY))
        
        if c2.button("📊 Generate Leadership Update", type="primary"):
            if not GROQ_KEY: st.error("Enter Groq Key")
            else:
                st.markdown('<div class="briefing-card">', unsafe_allow_html=True)
                st.markdown(run_ai("Leadership Update", wo, deals, GROQ_KEY, briefing=True))
                st.markdown('</div>', unsafe_allow_html=True)

    with tab_viz:
        if sector_col and rev_col:
            st.subheader(f"Revenue Distribution by {sector_col}")
            chart_df = wo.groupby(sector_col)[rev_col].sum().reset_index()
            # Professional Donut Chart
            fig = px.pie(chart_df, names=sector_col, values=rev_col, hole=0.5, 
                         color_discrete_sequence=px.colors.qualitative.Prism)
            fig.update_layout(showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Could not identify columns for charts. Ensure columns 'Sector' and 'Amount' exist on your board.")

    with tab_data:
        st.subheader("Work Orders")
        st.dataframe(wo)
        st.subheader("Deals Pipeline")
        st.dataframe(deals)
else:
    st.info("👈 Enter your keys in the sidebar and click Sync to begin.")