import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==========================================
# PAGE CONFIG & EDITORIAL LIGHT-MODE CSS
# ==========================================
st.set_page_config(
    page_title="SWIFT Fraud & Payment Insights | UMDAC 2026",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Fraunces:wght@600;700;800&display=swap');

    /* Global Canvas & Strict High-Contrast Text */
    html, body, [class*="css"], .stApp {
        background-color: #FAF8F5 !important;
        color: #1F2421 !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    /* Fix top header bar */
    header[data-testid="stHeader"] {
        background-color: #FAF8F5 !important;
        border-bottom: 1px solid #E6E1D6;
    }

    /* Fix Sidebar background & every text element inside it */
    section[data-testid="stSidebar"] {
        background-color: #F2EFE9 !important;
        border-right: 1px solid #E2DDD2 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #1F2421 !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: #FAF8F5;
        border: 1px solid #E2DDD2;
        border-radius: 10px;
        padding: 8px 12px;
        margin-bottom: 6px;
        transition: all 0.15s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        border-color: #C85A32;
        background-color: #FFFFFF;
    }

    /* Fix Metric Cards & Labels */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E6E1D6 !important;
        border-radius: 14px !important;
        padding: 16px 20px !important;
        box-shadow: 0 3px 10px rgba(31, 36, 33, 0.04) !important;
    }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {
        color: #5C635F !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
    }
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
        color: #1F2421 !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 700 !important;
    }

    /* Fix Multiselect / Radio / Widget labels */
    .stMultiSelect label, .stRadio label, .stSlider label, p, span, li {
        color: #1F2421 !important;
    }

    /* Editorial Takeaway Banner */
    .takeaway-banner {
        background: #FFFFFF;
        border: 1px solid #E6E1D6;
        border-left: 6px solid #C85A32;
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 18px;
        box-shadow: 0 4px 14px rgba(31, 36, 33, 0.04);
    }
    .takeaway-tag {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #C85A32 !important;
        margin-bottom: 6px;
    }
    .takeaway-title {
        font-family: 'Fraunces', serif !important;
        font-size: 1.55rem;
        font-weight: 700;
        color: #1F2421 !important;
        line-height: 1.3;
    }

    /* Side-by-Side Story & Rule Cards */
    .info-card {
        background-color: #FFFFFF;
        border: 1px solid #E6E1D6;
        border-radius: 14px;
        padding: 18px 22px;
        height: 100%;
        box-shadow: 0 3px 10px rgba(31, 36, 33, 0.03);
    }
    .card-header-rust {
        color: #C85A32 !important;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 8px;
    }
    .card-header-sage {
        color: #2D6A4F !important;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Warm Editorial Palette (Canva-inspired)
PALETTE = {
    "terracotta": "#C85A32",
    "sage": "#2D6A4F",
    "slate_blue": "#2B4C7E",
    "ochre": "#D98A2B",
    "plum": "#7B4B94",
    "muted": "#6C757D",
    "ink": "#1F2421",
}

def style_chart(fig, height=410):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="DM Sans, sans-serif", color="#1F2421", size=13),
        title=dict(font=dict(family="Fraunces, serif", size=16, color="#1F2421")),
        legend=dict(
            font=dict(color="#1F2421", size=12),
            title=dict(font=dict(color="#1F2421", size=12)),
            bgcolor="rgba(255,255,255,0.9)",
        ),
        xaxis=dict(
            tickfont=dict(color="#1F2421", size=12),
            title_font=dict(color="#1F2421", size=13),
            gridcolor="#EFECE6",
            linecolor="#D6D1C7",
        ),
        yaxis=dict(
            tickfont=dict(color="#1F2421", size=12),
            title_font=dict(color="#1F2421", size=13),
            gridcolor="#EFECE6",
            linecolor="#D6D1C7",
        ),
        margin=dict(l=20, r=25, t=58, b=30),
        height=height,
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#C85A32", font=dict(size=13, color="#1F2421")),
    )
    fig.update_traces(textfont=dict(color="#1F2421", size=12))
    return fig

def render_header(dashboard_label, headline, plain_english, business_rule):
    st.markdown(f"""
    <div class="takeaway-banner">
        <div class="takeaway-tag">{dashboard_label}</div>
        <div class="takeaway-title">{headline}</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.15, 1])
    with col1:
        st.markdown(f"""
        <div class="info-card">
            <div class="card-header-rust">💡 What This Means (In Plain English)</div>
            <div style="color:#2B302D; font-size:0.95rem; line-height:1.6;">{plain_english}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="info-card">
            <div class="card-header-sage">⚙️ Reconstructed Generator Rule</div>
            <div style="color:#2B302D; font-size:0.93rem; line-height:1.6;">{business_rule}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom: 14px;'></div>", unsafe_allow_html=True)

@st.cache_data
def get_data():
    return pd.DataFrame({
        "Anomaly_Label": [
            "Romance Scam", "Fat Finger Mistake", "CEO Scam",
            "Duplicate Payment", "Account Replacement Scam", "Customer Recall (Noise)"
        ],
        "Group": [
            "True Fraud (Scam)", "Human / System Error", "True Fraud (Scam)",
            "Human / System Error", "True Fraud (Scam)", "Random Baseline Noise"
        ],
        "Records": [2476, 1940, 945, 679, 649, 317],
        "Covered_Multihop_Pct": [0.5, 13.2, 2.0, 10.8, 1.5, 11.5],
        "Beneficiary_Mismatch_Pct": [0.0, 5.5, 0.0, 4.3, 0.0, 4.7],
        "Raw_Slow_Pct": [71.4, 40.3, 59.6, 47.6, 57.8, 42.0],
        "Geo_Expected_Slow_Pct": [66.1, 41.1, 55.4, 41.3, 55.3, 40.4],
    })

summary_df = get_data()

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.markdown("## 💳 SWIFT Payment Insights")
st.sidebar.caption("UMDAC Datathon 2026 • Interactive Explorer")

DASHBOARDS = [
    "Dashboard 1: Dataset Scale & Class Imbalance",
    "Dashboard 2: The Shared Mule Pool (Hero Dashboard)",
    "Dashboard 3: Party Type Locks (ORDERING_TYPE & BENEFICIARY_TYPE)",
    "Dashboard 4: Geographic & Currency Concentration",
    "Dashboard 5: Romance Scam Escalation & Burst Dynamics",
    "Dashboard 6: CEO Scam Bimodal Payouts",
    "Dashboard 7: Account Replacement Stealth",
    "Dashboard 8: Routing & Cover Status Signature",
    "Dashboard 9: Bimodal Settlement Latency & Path Topology",
    "Dashboard 10: Operational Noise vs. True Fraud Matrix",
]

choice = st.sidebar.radio("Navigate Dashboards (1–10):", DASHBOARDS)
st.sidebar.markdown("---")
st.sidebar.info("📄 **Export to PDF:** Press **Ctrl + P** and select **Save as PDF** (Landscape).")

# ==========================================
# DASHBOARD 1
# ==========================================
if choice == DASHBOARDS[0]:
    render_header(
        "Dashboard 1 • Dataset Scale & Class Imbalance",
        "Only 7 in Every 10,000 Payments Are Anomalous—Plus 1 Hidden 'Fake' Anomaly Class",
        "Out of <b>10,000,000</b> global bank transfers, <b>99.93%</b> are completely normal everyday payments. Only <b>7,006 records</b> (0.070%) are flagged as anomalies. While the case brief lists 5 anomaly types, we uncovered a <b>6th hidden label (Customer Recall, 317 rows)</b> that is actually random normal traffic planted as a distractor.",
        "<b>IF</b> record in 10M dataset &rarr; <b>9,992,994</b> follow baseline rules; <b>7,006</b> split into <b>3 Scams</b> (4,070 rows), <b>2 Operational Errors</b> (2,619 rows), and <b>1 Random Distractor</b> (317 rows). Structural path rules hold at <b>100.00%</b> across all 10M rows."
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Payments Checked", "10,000,000", "100% Verified")
    m2.metric("Normal Everyday Traffic", "9,992,994", "99.93% of Dataset")
    m3.metric("Total Flagged Anomalies", "7,006", "0.070% (7 per 10k)")
    m4.metric("Hidden Distractor Found", "317 Rows", "Customer Recall = Random")

    selected_groups = st.multiselect(
        "Filter by Anomaly Category:",
        options=summary_df["Group"].unique(),
        default=list(summary_df["Group"].unique()),
    )
    filtered = summary_df[summary_df["Group"].isin(selected_groups)]

    c1, c2 = st.columns([1.4, 1])
    with c1:
        fig_bar = px.bar(
            filtered.sort_values("Records", ascending=True),
            x="Records", y="Anomaly_Label", color="Group", orientation="h", text="Records",
            title="Romance Scams (2,476) & Fat Finger Errors (1,940) Make Up 63% of All Anomalies",
            color_discrete_map={
                "True Fraud (Scam)": PALETTE["terracotta"],
                "Human / System Error": PALETTE["sage"],
                "Random Baseline Noise": PALETTE["ochre"],
            },
        )
        fig_bar.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_bar.update_layout(xaxis_range=[0, 2950], yaxis_title="", xaxis_title="Number of Transactions")
        st.plotly_chart(style_chart(fig_bar, 420), use_container_width=True)

    with c2:
        group_totals = filtered.groupby("Group", as_index=False)["Records"].sum()
        fig_pie = px.pie(
            group_totals, names="Group", values="Records", hole=0.52,
            title="Share of the 7,006 Anomalies by Type",
            color="Group",
            color_discrete_map={
                "True Fraud (Scam)": PALETTE["terracotta"],
                "Human / System Error": PALETTE["sage"],
                "Random Baseline Noise": PALETTE["ochre"],
            },
        )
        fig_pie.update_traces(textinfo="percent+label", textposition="outside")
        st.plotly_chart(style_chart(fig_pie, 420), use_container_width=True)

# ==========================================
# DASHBOARD 2
# ==========================================
elif choice == DASHBOARDS[1]:
    render_header(
        "Dashboard 2 • The Shared Mule Pool (Hero Discovery)",
        "One Laundering Network of 1,068 Mule Accounts Powers All Three Fraud Types",
        "Instead of separate criminal gangs, <b>Romance Scams, CEO Scams, and Account Replacement Scams all funnel stolen money into the exact same pool of 1,068 mule bank accounts</b>. Over <b>1 in 3 mules (352 accounts)</b> collect money from multiple scam types—and <b>54 core accounts</b> launder money for all three scams at once.",
        "<b>IF</b> payment is Romance, CEO, or Account Replacement Scam &rarr; <b>BENEFICIARY_ACCOUNT</b> is drawn from a shared 1,068-account pool that the victim has <b>never paid before</b> (99.9% novel). ~25% of mules are reused 2–13 times across unrelated victims."
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Fraud Mule Accounts", "1,068", "Est. Pool Size ~1,300")
    k2.metric("Cross-Scam Shared Mules", "352 Accounts", "33.0% Serve 2+ Scams")
    k3.metric("Triple-Scam Core Mules", "54 Accounts", "Used by All 3 Scams")
    k4.metric("Top Mule Destination", "Egypt (EG)", "Up to 34.1% of IBAN Mules")

    c1, c2 = st.columns([1.25, 1])
    with c1:
        fig_sankey = go.Figure(data=[go.Sankey(
            textfont=dict(color="#1F2421", size=12, family="DM Sans"),
            node=dict(
                pad=18, thickness=22, line=dict(color="#E6E1D6", width=1),
                label=[
                    "Romance Scam (500 Bursts)", "CEO Scam (945 Txns)", "Account Replacement (649 Txns)",
                    "Shared Cross-Scam Mules (352)", "Single-Scam Mules (716)",
                    "Egypt (EG)", "Indonesia (ID)", "China (CN)", "UK & Others"
                ],
                color=[
                    PALETTE["terracotta"], PALETTE["plum"], PALETTE["ochre"],
                    "#9E2A2B", PALETTE["slate_blue"],
                    PALETTE["sage"], PALETTE["sage"], PALETTE["sage"], PALETTE["muted"]
                ],
            ),
            link=dict(
                source=[0, 0, 1, 1, 2, 2, 3, 3, 3, 4, 4],
                target=[3, 4, 3, 4, 3, 4, 5, 6, 7, 5, 8],
                value=[272, 228, 441, 504, 303, 346, 360, 290, 366, 280, 798],
                color="rgba(108, 117, 125, 0.22)"
            )
        )])
        fig_sankey.update_layout(title="Money Flow: How All 3 Scams Converge Into the Same Cash-Out Network")
        st.plotly_chart(style_chart(fig_sankey, 430), use_container_width=True)

    with c2:
        mule_countries = pd.DataFrame({
            "Country": ["Egypt (EG)", "Indonesia (ID)", "China (CN)", "Philippines (PH)", "United Kingdom (GB)", "India (IN)", "Bangladesh (BD)"],
            "Scam_Mule_Pct": [13.7, 10.3, 10.0, 5.1, 4.8, 4.0, 3.9],
            "Normal_Traffic_Pct": [0.3, 0.4, 1.8, 0.3, 6.8, 2.1, 0.2],
        })
        fig_mc = go.Figure()
        fig_mc.add_trace(go.Bar(
            y=mule_countries["Country"][::-1], x=mule_countries["Scam_Mule_Pct"][::-1],
            name="Fraud Mule Share (%)", orientation="h", marker_color=PALETTE["terracotta"],
            text=mule_countries["Scam_Mule_Pct"][::-1], texttemplate="%{text:.1f}%", textposition="outside"
        ))
        fig_mc.add_trace(go.Bar(
            y=mule_countries["Country"][::-1], x=mule_countries["Normal_Traffic_Pct"][::-1],
            name="Normal Baseline (%)", orientation="h", marker_color=PALETTE["slate_blue"]
        ))
        fig_mc.update_layout(
            barmode="group", title="72.6% of Scams Route to Low-Volume (<0.5%) Countries",
            xaxis_title="Share of Payments (%)", xaxis_range=[0, 17]
        )
        st.plotly_chart(style_chart(fig_mc, 430), use_container_width=True)

# ==========================================
# DASHBOARD 3
# ==========================================
elif choice == DASHBOARDS[2]:
    render_header(
        "Dashboard 3 • Party Type Locks (Business vs. Consumer)",
        "Romance Scams Target 100% Individuals; CEO Scams Target 100% Businesses",
        "Who sends the money cleanly separates fraud types. <b>Every single Romance Scam (500/500)</b> is sent by an individual Consumer, whereas <b>every single CEO Scam (945/945)</b> is sent by a Business. Contrary to the case brief, <b>27.2% of Romance Scam recipients are actually Business accounts</b>.",
        "<b>IF</b> Romance Scam &rarr; <b>ORDERING_TYPE = C</b> (100%); <b>IF</b> CEO Scam &rarr; <b>ORDERING_TYPE = B</b> (100%). <b>BENEFICIARY_TYPE</b> stays unlocked (~72% C) across all groups."
    )

    party_df = pd.DataFrame({
        "Transaction_Group": [
            "Normal Baseline", "Romance Scam", "CEO Scam",
            "Account Replacement", "Fat Finger Mistake", "Duplicate Payment", "Customer Recall"
        ],
        "Business -> Consumer (B->C)": [56.0, 0.0, 72.3, 57.0, 55.2, 56.8, 57.7],
        "Business -> Business (B->B)": [22.3, 0.0, 27.7, 21.3, 22.8, 21.1, 19.9],
        "Consumer -> Consumer (C->C)": [15.4, 72.8, 0.0, 16.5, 15.8, 15.7, 15.5],
        "Consumer -> Business (C->B)": [6.3, 27.2, 0.0, 5.2, 6.2, 6.4, 6.9],
    })

    view_mode = st.radio(
        "Choose View:", ["Compare All Groups Side-by-Side", "Focus on Fraud vs. Normal Baseline"], horizontal=True
    )
    if view_mode == "Focus on Fraud vs. Normal Baseline":
        party_df = party_df.iloc[:4]

    melted = party_df.melt(id_vars="Transaction_Group", var_name="Sender_to_Receiver", value_name="Percentage")
    fig = px.bar(
        melted, x="Percentage", y="Transaction_Group", color="Sender_to_Receiver",
        orientation="h", text="Percentage",
        title="Sender Locks Immediately Distinguish Romance (100% Consumer) & CEO Fraud (100% Business)",
        color_discrete_map={
            "Business -> Consumer (B->C)": PALETTE["slate_blue"],
            "Business -> Business (B->B)": PALETTE["sage"],
            "Consumer -> Consumer (C->C)": PALETTE["terracotta"],
            "Consumer -> Business (C->B)": PALETTE["ochre"],
        }
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="inside", textfont=dict(color="#FFFFFF", size=12))
    fig.update_layout(yaxis_title="", xaxis_title="Percentage of Events (%)", yaxis={"categoryorder": "array", "categoryarray": party_df["Transaction_Group"][::-1]})
    st.plotly_chart(style_chart(fig, 440), use_container_width=True)

# ==========================================
# DASHBOARD 4
# ==========================================
elif choice == DASHBOARDS[3]:
    render_header(
        "Dashboard 4 • Geographic & Currency Concentration",
        "Eurozone Cross-Border Hops Add Zero FX Fees (99.98% Match); Romance Victims Cluster in India & China",
        "Transfers across Eurozone countries (e.g., Germany &rarr; France &rarr; Netherlands) incur <b>zero FX conversions</b>. Meanwhile, Romance Scam victims shift dramatically away from Western markets into <b>India (19.2%) and China (17.2%)</b>.",
        "<b>CURRENCY_CONVERSION_COUNT</b> = count of consecutive visible banks whose countries use <b>different home currencies</b> (99.98% exact match vs 88.3% for border crossings)."
    )

    c1, c2 = st.columns(2)
    with c1:
        fx_comp = pd.DataFrame({
            "Rule_Tested": ["Currency-Zone Change (True Rule)", "Political Border Crossing (Rejected)"],
            "Match_Accuracy": [99.98, 88.30]
        })
        fig1 = px.bar(
            fx_comp, x="Rule_Tested", y="Match_Accuracy", color="Rule_Tested", text="Match_Accuracy",
            title="Monetary Zones Explain 99.98% of FX Steps (Border Count Fails Eurozone)",
            color_discrete_sequence=[PALETTE["sage"], PALETTE["muted"]]
        )
        fig1.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig1.update_layout(yaxis_range=[75, 104], showlegend=False, xaxis_title="", yaxis_title="Exact Rule Match (%)")
        st.plotly_chart(style_chart(fig1, 410), use_container_width=True)

    with c2:
        victim_geo = pd.DataFrame({
            "Country_Currency": ["India (INR)", "China (CNY)", "United States (USD)", "Switzerland (CHF)", "United Kingdom (GBP)"],
            "Romance_Scam_Victims": [19.2, 17.2, 4.8, 1.2, 2.5],
            "Normal_Consumers": [2.1, 1.9, 14.7, 9.3, 6.8],
        }).melt(id_vars="Country_Currency", var_name="Segment", value_name="Share_Pct")
        fig2 = px.bar(
            victim_geo, x="Country_Currency", y="Share_Pct", color="Segment", barmode="group", text="Share_Pct",
            title="Romance Scam Victims Shift Heavily Toward India (19.2%) & China (17.2%)",
            color_discrete_map={"Romance_Scam_Victims": PALETTE["terracotta"], "Normal_Consumers": PALETTE["slate_blue"]}
        )
        fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig2.update_layout(yaxis_range=[0, 23], xaxis_title="", yaxis_title="Share of Senders (%)")
        st.plotly_chart(style_chart(fig2, 410), use_container_width=True)

# ==========================================
# DASHBOARD 5
# ==========================================
elif choice == DASHBOARDS[4]:
    render_header(
        "Dashboard 5 • Romance Scam Escalation & Burst Dynamics",
        "Victims Send 2 to 8 Rapid Payments Every ~5 Minutes, Escalating 1.5x Each Step",
        "A Romance Scam victim sends a burst of <b>2 to 8 payments (average 5)</b> inside <b>under 70 minutes</b>, with a new transfer every <b>~5 minutes</b>. Each request grows by <b>1.5x</b>—and every payment in the burst clones the exact same bank path and duration.",
        "<b>IF</b> Romance Scam &rarr; <b>K = 2..8 payments</b> (mean 4.95); gap ~ <b>Exponential(300s)</b>; <b>Amount(i) = base &times; 1.5<sup>i</sup> &times; noise</b>. 500/500 bursts clone identical route."
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Bursts / Victims", "500 Bursts", "2,476 Total Payments")
    k2.metric("Average Gap Between Transfers", "5.1 Minutes", "Median 3.6 Mins (215s)")
    k3.metric("Step-by-Step Multiplier", "1.50x Growth", "Median x4.9 First-to-Last")
    k4.metric("Route Cloning Rate", "100.0%", "500 / 500 Identical Paths")

    max_i = st.slider("Interactive Step Explorer — Show Payment Steps 1 up to:", min_value=2, max_value=8, value=8)
    steps = list(range(1, max_i + 1))
    observed = [1.00, 1.50, 2.26, 3.49, 5.20, 8.09, 11.81, 18.06][:max_i]
    expected = [round(1.5**(i - 1), 2) for i in steps]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=steps, y=observed, mode="lines+markers+text", text=[f"{v:.2f}x" for v in observed],
        textposition="top center", name="Observed Median Payout Multiple",
        line=dict(color=PALETTE["terracotta"], width=4), marker=dict(size=10)
    ))
    fig.add_trace(go.Scatter(
        x=steps, y=expected, mode="lines+markers", name="Exact 1.5x Geometric Rule",
        line=dict(color=PALETTE["slate_blue"], width=2.5, dash="dash"), marker=dict(size=7)
    ))
    fig.update_layout(
        title="Payment Ladder: Each Follow-Up Transfer Multiplies the Initial Payment by 1.5x",
        xaxis_title="Payment Number in Burst (1st to 8th Transfer)",
        yaxis_title="Multiple of First Payment Amount",
        xaxis=dict(tickmode="linear", tick0=1, dtick=1),
        yaxis_range=[0, max(observed) * 1.22]
    )
    st.plotly_chart(style_chart(fig, 420), use_container_width=True)

# ==========================================
# DASHBOARD 6
# ==========================================
elif choice == DASHBOARDS[5]:
    render_header(
        "Dashboard 6 • CEO Scam Bimodal Payouts",
        "18.3% of CEO Scams Spike ~1,200x Normal Size ($5.7M Median); 81.7% Blend In",
        "<b>81.7% of CEO scams look like ordinary everyday invoices</b> (~1.3x normal size) to slip past alert thresholds, while <b>18.3% execute massive one-off wire spikes averaging 1,200x the company's normal payment ($1.1M–$26.5M)</b>. <b>Zero urgency keywords</b> ('URGENT', 'CEO', 'CONFIDENTIAL') appear in text fields.",
        "<b>IF</b> CEO Scam &rarr; Business sender pays novel shared mule (99.8%); <b>18.3%</b> draw <b>~1,200x victim median</b> (10<sup>3.09</sup>), <b>81.7%</b> stay near baseline (~1.3x)."
    )

    c1, c2 = st.columns([1, 1.4])
    with c1:
        split_df = pd.DataFrame({
            "Payout_Strategy": ["Stealth Invoice-Sized (81.7%)", "Massive ~1,200x Wire Spike (18.3%)"],
            "Share": [81.7, 18.3]
        })
        fig1 = px.pie(
            split_df, names="Payout_Strategy", values="Share", hole=0.55,
            title="Two-Speed CEO Fraud Strategy",
            color="Payout_Strategy",
            color_discrete_map={
                "Stealth Invoice-Sized (81.7%)": PALETTE["slate_blue"],
                "Massive ~1,200x Wire Spike (18.3%)": PALETTE["terracotta"],
            }
        )
        fig1.update_traces(textinfo="percent+label", textposition="outside")
        st.plotly_chart(style_chart(fig1, 410), use_container_width=True)

    with c2:
        firm_df = pd.DataFrame({
            "Company_Normal_Ticket_Size": [
                "1. Smallest (~$2.1k)", "2. Low-Mid", "3. Mid", "4. Upper-Mid", "5. Large", "6. Largest (~$19.4k)"
            ],
            "Massive_Spike_Rate_Pct": [38.2, 26.5, 19.8, 14.2, 9.8, 5.5]
        })
        fig2 = px.bar(
            firm_df, x="Company_Normal_Ticket_Size", y="Massive_Spike_Rate_Pct", text="Massive_Spike_Rate_Pct",
            title="Smaller-Ticket Companies Are Hit With Massive Wire Spikes 7x More Often (38.2% vs 5.5%)",
            color_discrete_sequence=[PALETTE["terracotta"]]
        )
        fig2.add_hline(y=18.3, line_dash="dash", line_color=PALETTE["slate_blue"], annotation_text="Overall Average (18.3%)")
        fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig2.update_layout(yaxis_range=[0, 45], xaxis_title="Victim Company Typical Payment Tier", yaxis_title="Massive Spike Rate (%)")
        st.plotly_chart(style_chart(fig2, 410), use_container_width=True)

# ==========================================
# DASHBOARD 7
# ==========================================
elif choice == DASHBOARDS[6]:
    render_header(
        "Dashboard 7 • Account Replacement Stealth (Invoice Interception)",
        "Pure Camouflage: Amount & Timing Stay 100% Normal—Only the Destination Swaps",
        "In Account Replacement, criminals hijack a legitimate bill and swap only the bank account number. <b>The payment amount and day/time look completely indistinguishable from normal history</b>. Only the <b>brand-new bank (87.1%) and shared mule account (0% prior history)</b> give it away.",
        "<b>IF</b> Account Replacement Scam &rarr; <b>0 of 649</b> go to a prior beneficiary; <b>87.1%</b> use a new bank; <b>USD_AMOUNT</b> (KS p=0.25) and <b>EPOCH_SECONDS</b> (KS p=0.39) remain untouched."
    )

    stealth_df = pd.DataFrame({
        "Indicator": [
            "Paid This Account Before (%)", "Used This Bank Before (%)", "Used This Country Before (%)",
            "Average Amount Percentile (%)", "Average Timeline Position (%)"
        ],
        "Account_Replacement_Scam": [0.0, 12.9, 37.4, 50.8, 51.4],
        "Normal_Expected_Behavior": [18.0, 85.7, 61.8, 50.0, 50.0],
    })

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=stealth_df["Indicator"], y=stealth_df["Account_Replacement_Scam"],
        name="Account Replacement Scam", marker_color=PALETTE["terracotta"],
        text=stealth_df["Account_Replacement_Scam"], texttemplate="%{text:.1f}%", textposition="outside"
    ))
    fig.add_trace(go.Bar(
        x=stealth_df["Indicator"], y=stealth_df["Normal_Expected_Behavior"],
        name="Normal Expected Baseline", marker_color=PALETTE["slate_blue"],
        text=stealth_df["Normal_Expected_Behavior"], texttemplate="%{text:.1f}%", textposition="outside"
    ))
    fig.update_layout(
        barmode="group",
        title="Amount (50.8%) & Timing (51.4%) Blend In Perfectly—Destination Novelty (0% Prior History) Catches It",
        yaxis_range=[0, 98], yaxis_title="Percentage / Percentile (%)"
    )
    st.plotly_chart(style_chart(fig, 440), use_container_width=True)

# ==========================================
# DASHBOARD 8
# ==========================================
elif choice == DASHBOARDS[7]:
    render_header(
        "Dashboard 8 • Routing & Cover Status Signature (Cross-Scam Fingerprint)",
        "All 3 Scams Drop 'Covered' Routing to 1.5% & Eliminate Beneficiary Bank Mismatches (0.0%)",
        "Across all <b>2,094 scam events</b>, <b>Covered routing plunges from 11.3% to 1.5%</b> because cover payments require pre-existing trust agreements between sender and receiver banks—which new mule accounts lack. Meanwhile, <b>beneficiary-end bank mismatches drop from 5.0% to 0.0%</b>.",
        "<b>IF</b> any Scam (Romance, CEO, Account Replacement) &rarr; <b>Beneficiary BIC mismatch = 0.0%</b> (0/2,094 vs 5.0% normal) & <b>Multi-hop Covered = 1.5%</b> (11/750 vs 11.3% normal)."
    )

    rt_plot = summary_df.melt(
        id_vars=["Anomaly_Label", "Group"],
        value_vars=["Covered_Multihop_Pct", "Beneficiary_Mismatch_Pct"],
        var_name="Routing_Signal", value_name="Rate_Pct"
    )
    rt_plot["Routing_Signal"] = rt_plot["Routing_Signal"].replace({
        "Covered_Multihop_Pct": "Multi-Hop Covered Routing (%) [Normal = 11.3%]",
        "Beneficiary_Mismatch_Pct": "Beneficiary Bank Mismatch (%) [Normal = 5.0%]"
    })

    fig = px.bar(
        rt_plot, x="Anomaly_Label", y="Rate_Pct", color="Routing_Signal", barmode="group", text="Rate_Pct",
        title="Scams Collapse to Near-Zero Covered Routing & Zero End Mismatch; Operational Errors Stay at Baseline",
        color_discrete_sequence=[PALETTE["slate_blue"], PALETTE["terracotta"]]
    )
    fig.add_hline(y=11.3, line_dash="dot", line_color=PALETTE["slate_blue"], annotation_text="Normal Covered (11.3%)")
    fig.add_hline(y=5.0, line_dash="dot", line_color=PALETTE["terracotta"], annotation_text="Normal Mismatch (5.0%)")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(yaxis_range=[0, 16.5], xaxis_title="", yaxis_title="Rate (%)")
    st.plotly_chart(style_chart(fig, 440), use_container_width=True)

# ==========================================
# DASHBOARD 9
# ==========================================
elif choice == DASHBOARDS[8]:
    render_header(
        "Dashboard 9 • Bimodal Settlement Latency & Path Topology",
        "Payments Clear in Two Modes (~25s Fast vs. ~25 Mins Slow)—Scam Slowness Is Geographic",
        "Transfers settle in two distinct speed tiers: an automated <b>Fast Lane (~25 seconds)</b> and a delayed <b>Slow Lane (~1,470 seconds / 24.5 mins)</b>. Controlling for country corridors proves <b>~90% of scam slowness is simply because mule accounts sit in slower-clearing cross-border corridors</b>.",
        "<b>PARTICIPANT_COUNT</b> decays geometrically (~0.37x/bank; 62.9% direct); each hop has a <b>5.2%</b> chance of being hidden as <code>...</code> (<code>CONTINUITY_QFLAG='N'</code>)."
    )

    c1, c2 = st.columns(2)
    with c1:
        hops_df = pd.DataFrame({
            "Bank_Hops": ["2 Banks (Direct)", "3 Banks", "4 Banks", "5 Banks", "6 Banks"],
            "Fast_Lane_Pct": [64.1, 55.6, 46.0, 37.1, 27.6],
            "Slow_Lane_Pct": [35.9, 44.4, 54.0, 62.9, 72.4],
        }).melt(id_vars="Bank_Hops", var_name="Speed_Tier", value_name="Share_Pct")
        fig1 = px.bar(
            hops_df, x="Bank_Hops", y="Share_Pct", color="Speed_Tier", text="Share_Pct",
            title="More Intermediary Banks = Higher Chance of Slow-Lane Clearing (35.9% -> 72.4%)",
            color_discrete_map={"Fast_Lane_Pct": PALETTE["sage"], "Slow_Lane_Pct": PALETTE["slate_blue"]}
        )
        fig1.update_traces(texttemplate="%{text:.1f}%", textposition="inside", textfont=dict(color="#FFFFFF", size=12))
        fig1.update_layout(xaxis_title="", yaxis_title="Share of Payments (%)")
        st.plotly_chart(style_chart(fig1, 410), use_container_width=True)

    with c2:
        scam_slow = summary_df[summary_df["Group"] == "True Fraud (Scam)"].melt(
            id_vars="Anomaly_Label", value_vars=["Raw_Slow_Pct", "Geo_Expected_Slow_Pct"],
            var_name="Comparison", value_name="Slow_Pct"
        )
        scam_slow["Comparison"] = scam_slow["Comparison"].replace({
            "Raw_Slow_Pct": "Observed Scam Slow Rate (%)",
            "Geo_Expected_Slow_Pct": "Expected From Country Corridor (%)"
        })
        fig2 = px.bar(
            scam_slow, x="Anomaly_Label", y="Slow_Pct", color="Comparison", barmode="group", text="Slow_Pct",
            title="Country-Controlled Proof: Scam Delays Match Their Cross-Border Corridors",
            color_discrete_map={"Observed Scam Slow Rate (%)": PALETTE["terracotta"], "Expected From Country Corridor (%)": PALETTE["muted"]}
        )
        fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig2.update_layout(yaxis_range=[0, 82], xaxis_title="", yaxis_title="Slow-Mode Share (%)")
        st.plotly_chart(style_chart(fig2, 410), use_container_width=True)

# ==========================================
# DASHBOARD 10
# ==========================================
elif choice == DASHBOARDS[9]:
    render_header(
        "Dashboard 10 • Operational Noise vs. True Fraud Matrix",
        "Separating Typing Slips (10^k), 2-Hour Duplicate Clones & Random Recall Noise From Fraud",
        "Not every anomaly is a crime. <b>Fat Finger Mistakes</b> multiply amounts by 10<sup>k</sup>, while <b>Duplicate Payments</b> fire 2 to 5 identical copies inside a 2-hour window—both keep normal bank routing. Meanwhile, <b>Customer Recall (317 rows)</b> scored <b>0.495 AUC (pure coin flip)</b> across ~1,500 tests, proving it is random baseline traffic.",
        "<b>FAT_FINGER (1,940):</b> amount &times; 10<sup>k</sup>, k &isin; {-2,+1,+2,+3,+4} (~20% each). <b>DUPLICATE (185 clusters):</b> 2–5 exact clones in 7,200s window. <b>CUSTOMER_RECALL (317):</b> verified random distractor."
    )

    c1, c2 = st.columns(2)
    with c1:
        ff_df = pd.DataFrame({
            "Multiplier_Shift": ["Divided by 100 (/100)", "Times 10 (x10)", "Times 100 (x100)", "Times 1,000 (x1,000)", "Times 10,000 (x10,000)"],
            "Share_Pct": [20.4, 22.1, 20.8, 17.7, 19.0],
            "Direction": ["Deflated (20%)", "Inflated (80%)", "Inflated (80%)", "Inflated (80%)", "Inflated (80%)"]
        })
        fig1 = px.bar(
            ff_df, x="Multiplier_Shift", y="Share_Pct", color="Direction", text="Share_Pct",
            title="Fat Finger Mistakes Follow an Equal 20% Law Across 5 Power-of-10 Shifts",
            color_discrete_map={"Deflated (20%)": PALETTE["ochre"], "Inflated (80%)": PALETTE["sage"]}
        )
        fig1.add_hline(y=20.0, line_dash="dash", line_color=PALETTE["terracotta"], annotation_text="Exact 20% Rule")
        fig1.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig1.update_layout(yaxis_range=[0, 27], xaxis_title="", yaxis_title="Share of Fat Finger Errors (%)")
        st.plotly_chart(style_chart(fig1, 390), use_container_width=True)

    with c2:
        dup_df = pd.DataFrame({
            "Copies_in_Cluster": ["2 Identical Copies", "3 Identical Copies", "4 Identical Copies", "5 Identical Copies"],
            "Share_of_Clusters_Pct": [20.0, 23.2, 26.5, 30.3],
            "Avg_Window_Span_Mins": [47.9, 56.6, 71.7, 77.0]
        })
        fig2 = px.bar(
            dup_df, x="Copies_in_Cluster", y="Share_of_Clusters_Pct", text="Avg_Window_Span_Mins",
            title="Duplicate Clusters Fire 2–5 Exact Clones Uniformly Inside One 120-Min Window",
            color_discrete_sequence=[PALETTE["slate_blue"]]
        )
        fig2.update_traces(texttemplate="Avg Span: %{text:.1f}m", textposition="outside")
        fig2.update_layout(yaxis_range=[0, 36], xaxis_title="", yaxis_title="Share of 185 Clusters (%)")
        st.plotly_chart(style_chart(fig2, 390), use_container_width=True)

    st.markdown("#### 📋 Master Decision Matrix: How to Tell Fraud, Human Error & Noise Apart")
    matrix_df = pd.DataFrame({
        "Anomaly Class": [
            "Romance Scam", "CEO Scam", "Account Replacement",
            "Fat Finger Mistake", "Duplicate Payment", "Customer Recall"
        ],
        "Classification": [
            "🚨 True Fraud", "🚨 True Fraud", "🚨 True Fraud",
            "⚠️ Operational Error", "⚠️ Operational Error", "✅ Random Baseline Noise"
        ],
        "Who Sends It?": [
            "100% Consumers", "100% Businesses", "Normal Mix (B & C)",
            "Normal Mix (B & C)", "Normal Mix (B & C)", "Normal Mix (B & C)"
        ],
        "Uses Shared Mule Pool?": [
            "Yes (378 Mules)", "Yes (634 Mules)", "Yes (462 Mules)",
            "No", "No", "No"
        ],
        "Routing Signature": [
            "0% End Mismatch, ~0.5% Covered", "0% End Mismatch, ~2.0% Covered", "0% End Mismatch, ~1.5% Covered",
            "Normal (5% Mismatch, 13% Covered)", "Normal (4.3% Mismatch, 11% Covered)", "Normal (4.7% Mismatch, 11.5% Covered)"
        ],
        "Main Signature": [
            "2–8 rapid transfers (~5m apart) growing 1.5x each",
            "18.3% spike ~1,200x ($5.7M med); 81.7% normal size",
            "Amount & timing 100% normal; only destination swaps",
            "Amount shifted by /100, x10, x100, x1k, or x10k",
            "2–5 exact copies within 2 hours (all labeled)",
            "Zero pattern across 17 columns (AUC = 0.495)"
        ]
    })
    st.dataframe(matrix_df, use_container_width=True, hide_index=True)