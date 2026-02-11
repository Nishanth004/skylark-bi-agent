
---

# 🚁 Skylark Drones - Business Intelligence Agent

An AI-powered agent designed for founders and executives to query real-world, messy business data directly from **Monday.com** boards. This tool integrates project execution data (Work Orders) with sales pipeline data (Deals) to provide high-level insights and leadership updates.

## 🚀 Live Prototype
**Hosted Link:** [PASTE YOUR STREAMLIT URL HERE]

---

## ✨ Core Features

### 1. Monday.com API Integration
- **Dynamic Querying:** Does not use hardcoded CSVs. The agent fetches live data from Monday.com boards via GraphQL API v2.
- **Read-Only Access:** Designed for secure, read-only data retrieval.

### 2. Data Resilience & Cleaning
- **Messy Data Handling:** Programmatically cleans inconsistent formats (e.g., currency symbols, commas, and "Masked" values).
- **Fuzzy Column Mapping:** Automatically identifies key business metrics (Revenue, Sector, Status) even if column names change or contain extra text.
- **Null Safety:** Gracefully handles missing records or incomplete data rows without crashing.

### 3. Business Intelligence & Insights
- **Conversational Analytics:** Executives can ask natural language questions like *"Which sector has the highest revenue?"* or *"How many projects are currently stuck?"*
- **Leadership Briefing:** A specialized "Executive Update" feature that synthesizes project health, cash flow (Billed vs. Collected), and pipeline risk into a structured memo.

### 4. Visualizations
- **Executive Dashboard:** Includes high-level metric cards and interactive donut charts for sector-wise revenue distribution.

---

## 🛠 Tech Stack
- **Frontend/Hosting:** [Streamlit](https://streamlit.io/)
- **Data Manipulation:** [Pandas](https://pandas.pydata.org/)
- **Intelligence Engine:** [Groq Llama-3.3-70b-versatile](https://groq.com/) (Chosen for high inference speed and executive-level reasoning)
- **Visuals:** [Plotly Express](https://plotly.com/python/plotly-express/)
- **API Communication:** Python `requests` library (Direct GraphQL integration)

---

## ⚙️ Setup Instructions

### 1. Monday.com Configuration
1. **Import Data:** Create two new boards on Monday.com. 
   - Upload `Work_Order_Tracker_Data.csv` to the first board.
   - Upload `Deal_funnel_Data.csv` to the second board.
2. **Column Types:** Ensure "Amount" and "Value" columns are recognized as Number or Text types.
3. **Get Board IDs:** Note the ID for both boards (found at the end of the URL: `monday.com/boards/XXXXXXXXXX`).
4. **API Token:** Go to **Profile > Developers > My Access Tokens** and generate a v2 Personal Access Token.

### 2. LLM Configuration (Free Tier)
1. This agent uses **Groq** for high-speed processing.
2. Generate a free API key at [console.groq.com](https://console.groq.com/).

### 3. Running Locally
1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install streamlit pandas requests openai plotly
   ```
3. Run the application:
   ```bash
   streamlit run app.py
   ```

---

## 📂 Deliverables
- `app.py`: Core application logic and API integration.
- `requirements.txt`: Python dependency list.
- `Decision_Log.pdf`: Detailed documentation of technical choices, assumptions, and trade-offs.

---

## 🧠 Architecture Overview
The agent follows a **Linear Data-to-Context** architecture:
1. **Fetch:** User triggers a sync; Python pulls raw JSON from Monday.com.
2. **Clean:** Pandas normalizes "messy" columns (Revenue, Sector) into clean numeric/categorical types.
3. **Analyze:** Clean data is converted to CSV format and injected into the LLM context.
4. **Respond:** The LLM (Llama 3.3) interprets the executive's query based on the cleaned data context and generates a natural language response.
