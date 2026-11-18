"""
claude_dashboard.py - UMDAC Datathon 2026 - SWIFT payments: reconstructed business rules

Ten dashboards, one per feature group. Every page shows a quantified takeaway against a
baseline, a plain-English summary, the reconstructed IF / THEN / FOR rule, interactive
filters, hover tooltips and the numbers behind each chart.

Run (Python 3.9+):
    (python -m) pip install "streamlit>=1.32" "plotly>=5.18" pandas numpy
    (python -m) streamlit run claude_dashboard.py --theme.base light

No data files are needed: every figure was computed from the team's extract files by
build_dashboard_data.py and is embedded at the bottom of this file (_DATA).
Observed facts and real-world interpretation are kept apart on every page.
"""
import base64
import gzip
import json
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------------------
# Page setup and light theme
# ----------------------------------------------------------------------------------------
st.set_page_config(page_title="SWIFT Payments - Reconstructed Rules", layout="wide",
                   initial_sidebar_state="expanded")
try:  # best effort; the --theme.base light flag is the reliable way
    st._config.set_option("theme.base", "light")
except Exception:
    pass

try:
    _V = tuple(int(p) for p in st.__version__.split(".")[:2])
except Exception:
    _V = (1, 0)
ST_NEW = _V >= (1, 50)

INK = "#0b0b0b"
INK2 = "#3d3c39"
MUTED = "#6b6964"
GRID = "#e8e6e0"
AXIS = "#c3c2b7"
PAGE_BG = "#faf8f4"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

TYPES = ["ROMANCE_SCAM", "CEO_SCAM", "ACCOUNT_REPLACEMENT_SCAM",
         "FAT_FINGER_MISTAKE", "DUPLICATE_PAYMENT", "CUSTOMER_RECALL"]
SCAMS = TYPES[:3]
LABEL = {"ROMANCE_SCAM": "Romance scam", "CEO_SCAM": "CEO scam",
         "ACCOUNT_REPLACEMENT_SCAM": "Account replacement", "FAT_FINGER_MISTAKE": "Fat finger",
         "DUPLICATE_PAYMENT": "Duplicate payment", "CUSTOMER_RECALL": "Customer recall",
         "NORMAL": "Normal payments"}
# Fixed categorical order (validated palette); colour follows the anomaly type everywhere.
COLOR = {"ROMANCE_SCAM": "#2a78d6", "CEO_SCAM": "#eb6834", "ACCOUNT_REPLACEMENT_SCAM": "#1baf7a",
         "FAT_FINGER_MISTAKE": "#eda100", "DUPLICATE_PAYMENT": "#e87ba4", "CUSTOMER_RECALL": "#008300",
         "NORMAL": "#9a988f", "ALL_SCAMS": "#6250d6"}
COMBOS = ["B→C", "B→B", "C→C", "C→B"]
COMBO_COLOR = {"B→C": "#184f95", "B→B": "#3987e5", "C→C": "#c43b3a", "C→B": "#ee7d75"}
COMBO_TEXT = {"B→C": "#ffffff", "B→B": "#ffffff", "C→C": "#ffffff", "C→B": INK}
COMBO_NAME = {"B→C": "Business → Consumer", "B→B": "Business → Business",
              "C→C": "Consumer → Consumer", "C→B": "Consumer → Business"}

CSS = """
<style>
.stApp { background: #faf8f4; color: #0b0b0b; }
[data-testid="stHeader"] { background: rgba(250,248,244,0.9); }
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #ebe8e1; }
section[data-testid="stSidebar"] * { color: #0b0b0b; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp li, .stApp label { color: #0b0b0b; }
[data-testid="stWidgetLabel"] p { color: #0b0b0b; font-weight: 600; }
[data-testid="stExpander"] details { background: #ffffff; border-radius: 10px; }
.eyebrow { font-size: 0.8rem; letter-spacing: .08em; text-transform: uppercase; color: #b4501f;
           font-weight: 700; margin-bottom: .2rem; }
.takeaway { font-size: 1.9rem; line-height: 1.25; font-weight: 750; color: #0b0b0b; margin: 0 0 .35rem 0; }
.baseline { font-size: .98rem; color: #3d3c39; margin-bottom: 1rem; }
.baseline b { color: #0b0b0b; }
.card { background: #ffffff; border: 1px solid #ebe8e1; border-radius: 14px; padding: 1rem 1.15rem;
        height: 100%; box-shadow: 0 1px 2px rgba(11,11,11,0.04); }
.card h4 { margin: 0 0 .5rem 0; font-size: 1rem; }
.plain { border-left: 5px solid #eb6834; background: #fffaf3; }
.rule { border-left: 5px solid #2a78d6; background: #f5f9ff; }
.rule-row { display: grid; grid-template-columns: 58px 1fr; gap: .35rem .6rem; margin-bottom: .25rem;
            font-size: .95rem; color: #0b0b0b; }
.kw { font-weight: 800; font-size: .78rem; letter-spacing: .05em; color: #ffffff; background: #184f95;
      border-radius: 6px; text-align: center; padding: .12rem 0; height: fit-content; }
.kw.then { background: #b4501f; } .kw.for { background: #3d3c39; }
.rule-sep { border-top: 1px dashed #c9d8ee; margin: .55rem 0; }
.rule-name { font-weight: 700; font-size: .85rem; color: #184f95; margin: .1rem 0 .35rem 0; }
.kpi { background: #ffffff; border: 1px solid #ebe8e1; border-radius: 14px; padding: .8rem 1rem; height: 100%; }
.kpi-label { font-size: .8rem; color: #3d3c39; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.kpi-value { font-size: 1.7rem; font-weight: 750; color: #0b0b0b; line-height: 1.2; margin: .15rem 0; }
.kpi-sub { font-size: .85rem; color: #3d3c39; }
.chart-note { font-size: .88rem; color: #3d3c39; margin: -.3rem 0 .6rem .2rem; }
.sidebar-title { font-size: 1.15rem; font-weight: 800; color: #0b0b0b; line-height: 1.25; }
.sidebar-sub { font-size: .85rem; color: #3d3c39; margin-bottom: .6rem; }
.tag { display: inline-block; padding: .05rem .5rem; border-radius: 999px; font-size: .78rem; font-weight: 700;
       margin-right: .3rem; }
</style>
"""


# ----------------------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    return json.loads(gzip.decompress(base64.b64decode(_DATA)).decode("utf-8"))


# ----------------------------------------------------------------------------------------
# Small helpers (no scipy needed at run time)
# ----------------------------------------------------------------------------------------
def pct(x, d=1):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.{d}f}%"


def num(x):
    return f"{x:,.0f}"


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def binom_p(k, n, p0):
    """Exact two-sided binomial test (sum of outcomes no more likely than k)."""
    if n == 0:
        return float("nan")
    if p0 <= 0 or p0 >= 1:
        return 1.0
    logp = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p0) + (n - i) * math.log(1 - p0) for i in range(n + 1)]
    ref = logp[k] + 1e-9
    return min(1.0, sum(math.exp(v) for v in logp if v <= ref))


def ks_uniform(x):
    """Kolmogorov-Smirnov test of x against Uniform(0,1); returns (D, p)."""
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n < 5:
        return float("nan"), float("nan")
    i = np.arange(1, n + 1)
    d = max(np.max(i / n - x), np.max(x - (i - 1) / n))
    t = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * d
    p = 2 * sum((-1) ** (j - 1) * math.exp(-2 * j * j * t * t) for j in range(1, 101))
    return d, float(min(1.0, max(0.0, p)))


def fmt_p(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    return "< 0.0001" if p < 1e-4 else f"{p:.3f}" if p < 0.1 else f"{p:.2f}"


def mult_label(v):
    """10**v as an 'x' multiplier label."""
    m = 10 ** v
    if m >= 1:
        return f"{m:,.0f}×"
    return f"{m:g}×"


# ----------------------------------------------------------------------------------------
# Chart styling
# ----------------------------------------------------------------------------------------
def style(fig, title=None, x=None, y=None, h=400, legend=True, ygrid=True, xgrid=True):
    top = 30
    if title:
        top += 34
    if legend:
        top += 30
    fig.update_layout(
        template="none", height=h, paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family=FONT, size=13, color=INK),
        title=dict(text=f"<b>{title}</b>" if title else "", x=0.01, xanchor="left", y=0.98, yanchor="top",
                   font=dict(size=16, color=INK)),
        margin=dict(l=12, r=24, t=top, b=12),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=AXIS, font=dict(family=FONT, size=13, color=INK)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                    font=dict(color=INK, size=12), bgcolor="rgba(0,0,0,0)"),
        bargap=0.35, bargroupgap=0.08,
    )
    ax = dict(zeroline=False, showline=True, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
              tickfont=dict(color=INK2, size=12), title_font=dict(color=INK, size=13), automargin=True,
              gridcolor=GRID, gridwidth=1)
    fig.update_xaxes(**ax, showgrid=xgrid, title_text=x)
    fig.update_yaxes(**ax, showgrid=ygrid, title_text=y)
    try:
        fig.update_layout(barcornerradius=4)
    except Exception:
        pass
    return fig


def show(fig, key):
    kw = dict(theme=None, key=key,
              config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})
    if ST_NEW:
        st.plotly_chart(fig, width="stretch", **kw)
    else:
        st.plotly_chart(fig, use_container_width=True, **kw)


def table(df, label="Show the numbers behind this chart"):
    with st.expander(label):
        if ST_NEW:
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


def note(text):
    st.markdown(f"<div class='chart-note'>{text}</div>", unsafe_allow_html=True)


def header(n, group, takeaway, baseline, plain, rules):
    st.markdown(f"<div class='eyebrow'>Dashboard {n} of 10 · {group}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='takeaway'>{takeaway}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='baseline'><b>Baseline:</b> {baseline}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.15])
    c1.markdown(f"<div class='card plain'><h4>What this means in plain English</h4>{plain}</div>",
                unsafe_allow_html=True)
    parts = []
    for i, r in enumerate(rules):
        if i:
            parts.append("<div class='rule-sep'></div>")
        if r.get("name"):
            parts.append(f"<div class='rule-name'>{r['name']}</div>")
        parts.append(f"<div class='rule-row'><span class='kw'>IF</span><span>{r['if']}</span></div>")
        parts.append(f"<div class='rule-row'><span class='kw then'>THEN</span><span>{r['then']}</span></div>")
        parts.append(f"<div class='rule-row'><span class='kw for'>FOR</span><span>{r['for']}</span></div>")
    c2.markdown(f"<div class='card rule'><h4>Reconstructed business rule</h4>{''.join(parts)}</div>",
                unsafe_allow_html=True)
    st.write("")


def kpis(items):
    cols = st.columns(len(items))
    for c, (lab, val, sub) in zip(cols, items):
        c.markdown(f"<div class='kpi'><div class='kpi-label'>{lab}</div><div class='kpi-value'>{val}</div>"
                   f"<div class='kpi-sub'>{sub}</div></div>", unsafe_allow_html=True)
    st.write("")


def notes(interpretation, rejected):
    c1, c2 = st.columns(2)
    with c1.expander("Real-world interpretation (not observed in the data)"):
        st.markdown(interpretation)
    with c2.expander("Rejected hypotheses and limits"):
        st.markdown(rejected)


def filter_row(n):
    return st.columns(n)


LOG_TICKS = dict(tickvals=list(range(-4, 6)), ticktext=[mult_label(v) for v in range(-4, 6)])
DUR_TICKS = dict(tickvals=[0.301, 1, 1.477, 2, 2.477, 3, 3.477, 4],
                 ticktext=["2 s", "10 s", "30 s", "100 s", "5 min", "17 min", "50 min", "2.8 h"])


def dot_ci_chart(rows, base_p, base_lo, base_hi, title, xlab, key, base_label="Normal payments", h=360):
    """Horizontal dot plot with 95% CI per anomaly type and a grey normal-baseline band."""
    fig = go.Figure()
    fig.add_vrect(x0=base_lo * 100, x1=base_hi * 100, fillcolor="#d9d7d0", opacity=0.45, line_width=0,
                  layer="below")
    fig.add_vline(x=base_p * 100, line=dict(color="#6b6964", width=2),
                  annotation_text=f"{base_label}: {pct(base_p)}", annotation_position="top",
                  annotation_font=dict(color=INK, size=12))
    for r in rows:
        p, lo, hi = r["p"], r["lo"], r["hi"]
        fig.add_trace(go.Scatter(
            x=[p * 100], y=[LABEL[r["type"]]], mode="markers", name=LABEL[r["type"]],
            marker=dict(size=13, color=COLOR[r["type"]], line=dict(color="#ffffff", width=2)),
            error_x=dict(type="data", symmetric=False, array=[(hi - p) * 100], arrayminus=[(p - lo) * 100],
                         color=COLOR[r["type"]], thickness=2, width=7),
            customdata=[[r["k"], r["n"], lo * 100, hi * 100, r.get("pval", float("nan"))]],
            hovertemplate=("<b>%{y}</b><br>%{x:.1f}% (%{customdata[0]:,} of %{customdata[1]:,})<br>"
                           "95% CI %{customdata[2]:.1f}% – %{customdata[3]:.1f}%<br>"
                           f"vs normal {pct(base_p)}<extra></extra>"),
            showlegend=False))
    style(fig, title, xlab, None, h=h, legend=False, ygrid=False)
    fig.update_yaxes(autorange="reversed", categoryorder="array",
                     categoryarray=[LABEL[r["type"]] for r in rows])
    fig.update_xaxes(ticksuffix="%", rangemode="tozero")
    show(fig, key)


# ----------------------------------------------------------------------------------------
# Dashboard 1 - Dataset scale & class imbalance
# ----------------------------------------------------------------------------------------
TOTAL_ROWS = 10_000_000   # full dataset, as counted by the team
NORMAL_ROWS = 9_992_994


def page1(D):
    rows, ev = D["rows"], D["events"]
    anom = sum(rows[t] for t in TYPES)
    incidents = sum(ev[t] for t in TYPES)
    inv = D["invariants"]
    tested = sum(i["rows"] for i in inv)
    header(
        1, "Dataset scale & class imbalance",
        f"1 in every {TOTAL_ROWS / anom:,.0f} payments is an anomaly: {anom:,} of {TOTAL_ROWS:,} rows "
        f"({pct(anom / TOTAL_ROWS, 3)})",
        f"normal payments = <b>{NORMAL_ROWS:,} rows ({pct(NORMAL_ROWS / TOTAL_ROWS, 2)})</b>. "
        f"A model that always answers 'normal' is {pct(NORMAL_ROWS / TOTAL_ROWS, 2)} accurate, "
        "so every rule here is judged against normal traffic, not by accuracy.",
        "Fraud and mistakes are needles in a haystack: about 7 in every 10,000 payments. "
        f"Two kinds arrive in batches (romance bursts and duplicate copies), so the {anom:,} flagged rows "
        f"are really <b>{incidents:,} separate incidents</b>. Three bookkeeping rules about bank routes hold "
        "for every row we checked, which means the routing columns can be trusted in later dashboards.",
        [dict(name="Class balance",
              **{"if": "a payment record is drawn from the dataset",
                 "then": f"it carries an anomaly label with probability {pct(anom / TOTAL_ROWS, 3)} "
                         "(6 labels; the largest, Romance, is 0.025%)",
                 "for": f"all {TOTAL_ROWS:,} rows"}),
         dict(name="Route bookkeeping (structural invariants)",
              **{"if": "any payment",
                 "then": "PARTICIPANT_COUNT = number of banks in BIC8_PATH (ignoring '...'); "
                         "CONTINUITY_QFLAG = N exactly when the path contains '...'; "
                         "TRANSACTION_TYPE_CODE = Direct exactly when 2 banks",
                 "for": f"every row tested ({tested:,} rows, 0 exceptions)"})])
    kpis([("Total rows", f"{TOTAL_ROWS:,}", "full dataset"),
          ("Normal", f"{NORMAL_ROWS:,}", pct(NORMAL_ROWS / TOTAL_ROWS, 2) + " of rows"),
          ("Anomaly rows", f"{anom:,}", pct(anom / TOTAL_ROWS, 3) + " of rows"),
          ("Separate incidents", f"{incidents:,}", "bursts and copy-clusters counted once"),
          ("Route invariants", "100%", f"{tested:,} rows checked, 0 exceptions")])

    f1, f2, _ = filter_row(3)
    unit = f1.radio("Count anomalies as", ["Rows (records)", "Separate incidents"], horizontal=True, key="p1_unit")
    logy = f2.checkbox("Log scale (shows normal traffic on the same chart)", value=True, key="p1_log")
    use = rows if unit.startswith("Rows") else ev
    order = sorted(TYPES, key=lambda t: use[t])
    cats = order + (["NORMAL"] if logy else [])
    vals = [use[t] for t in order] + ([NORMAL_ROWS] if logy else [])

    c1, c2 = st.columns([1.35, 1])
    with c1:
        fig = go.Figure(go.Bar(
            y=[LABEL[t] for t in cats], x=vals, orientation="h",
            marker=dict(color=[COLOR[t] for t in cats], line=dict(color="#ffffff", width=2)),
            text=[f"{v:,}" for v in vals], textposition="outside", textfont=dict(color=INK, size=12),
            customdata=[[v / TOTAL_ROWS * 1e6, TOTAL_ROWS / v, (v / anom if t != "NORMAL" else float("nan"))]
                        for t, v in zip(cats, vals)],
            hovertemplate=("<b>%{y}</b><br>%{x:,} " + ("rows" if unit.startswith("Rows") else "incidents")
                           + "<br>%{customdata[0]:,.1f} per million payments<br>1 in %{customdata[1]:,.0f} payments"
                           "<extra></extra>")))
        style(fig, "Anomalies are 0.07% of traffic (" + ("rows" if unit.startswith("Rows") else "separate incidents") + ")", None, None, h=420, legend=False, ygrid=False)
        if logy:
            fig.update_xaxes(type="log", title_text="count (log scale)")
        else:
            fig.update_xaxes(title_text="count")
        show(fig, "p1_bars")
        table(pd.DataFrame({"Label": [LABEL[t] for t in TYPES], "Rows": [rows[t] for t in TYPES],
                            "Separate incidents": [ev[t] for t in TYPES],
                            "Share of anomaly rows": [pct(rows[t] / anom) for t in TYPES],
                            "Rows per million payments": [round(rows[t] / TOTAL_ROWS * 1e6, 1) for t in TYPES]}))
    with c2:
        rpi = [rows[t] / ev[t] for t in TYPES]
        fig = go.Figure(go.Bar(
            x=[LABEL[t] for t in TYPES], y=rpi, marker=dict(color=[COLOR[t] for t in TYPES]),
            text=[f"{v:.2f}" for v in rpi], textposition="outside", textfont=dict(color=INK),
            customdata=[[rows[t], ev[t]] for t in TYPES],
            hovertemplate="<b>%{x}</b><br>%{customdata[0]:,} rows / %{customdata[1]:,} incidents"
                          "<br>= %{y:.2f} rows per incident<extra></extra>"))
        fig.add_hline(y=1, line=dict(color="#6b6964", width=2),
                      annotation_text="Normal payment: 1 row = 1 incident", annotation_position="top left",
                      annotation_font=dict(color=INK, size=12))
        style(fig, "Romance and duplicates come in batches", None, "rows per incident", h=420, legend=False,
              xgrid=False)
        fig.update_yaxes(range=[0, 6])
        show(fig, "p1_rpi")
        note("Romance: one victim sends 2–8 payments (mean 4.95). Duplicates: 2–5 identical copies (mean 3.67).")

    st.markdown("#### Structural invariants: checked on every row of our files")
    inv_df = pd.DataFrame([{"Source": i["source"], "Rows": f"{i['rows']:,}",
                            **{k: f"{v:,} / {i['rows']:,} (100%)" if v == i["rows"] else f"{v:,} / {i['rows']:,}"
                               for k, v in i.items() if k not in ("source", "rows")}} for i in inv])
    if ST_NEW:
        st.dataframe(inv_df, width="stretch", hide_index=True)
    else:
        st.dataframe(inv_df, use_container_width=True, hide_index=True)
    note("The team reports the same 100% match on the full 10,000,000-row dataset; the two files above were "
         "re-checked independently for this dashboard.")
    notes("- A real payments network flags very few transactions, so rare labels are realistic.\n"
          "- Batching mirrors how these problems happen in practice: a scammer asks again and again; a back "
          "office resubmits a batch.\n- The invariants look like generator bookkeeping, not behaviour.",
          "- Row counts overstate romance and duplicate incidents by 4.95× and 3.67×; per-incident tests are "
          "used wherever independence matters.\n- Totals for the full dataset come from the team's count; the "
          f"charts on later pages use the extract files ({tested:,} rows with full routing fields).")


# ----------------------------------------------------------------------------------------
# Dashboard 2 - Shared mule pool (hero)
# ----------------------------------------------------------------------------------------
def page2(D):
    v = D["venn"]
    lp = D["lincoln_petersen"]
    nb = D["n_benef_accounts"]
    exp_shared = (v["tot_R"] * v["tot_C"] + v["tot_R"] * v["tot_A"] + v["tot_C"] * v["tot_A"]) / nb
    reuse = {int(k): c for k, c in D["reuse_all"].items()}
    n_events = sum(D["scam_events"].values())
    header(
        2, "The shared mule pool",
        f"All three scams pay into one network: {v['multi']:,} of {v['union']:,} mule accounts "
        f"({pct(v['multi'] / v['union'])}) receive money from 2+ scam types — chance predicts about "
        f"{exp_shared:.1f}",
        f"if each scam picked its accounts at random from the <b>{nb:,} beneficiary accounts</b> in our files, "
        f"only ≈{exp_shared:.1f} accounts would be shared. Observed: <b>{v['multi']}</b>; {v['RCA']} serve all three.",
        "Romance, CEO and account-replacement scams look like three different crimes, but the money lands in "
        "the same set of receiving ('mule') accounts. One account in three is used by more than one type of "
        "scam, and some accounts receive money from up to 22 different victims. A bank that blocks a mule seen "
        "in one scam type would also stop it in the others.",
        [dict(**{"if": "a payment is a Romance, CEO or Account-replacement scam",
                 "then": f"the beneficiary is drawn from one shared pool of mule accounts "
                         f"({v['union']:,} seen; estimated total ≥ {min(lp.values()):,.0f}); a mule is never "
                         "paid twice by the same victim, and mule banks sit mostly in low-traffic countries "
                         "(Egypt, China, Indonesia lead)",
                 "for": f"all {n_events:,} scam incidents (500 romance bursts + 945 CEO + 649 account "
                        "replacement)"})])
    kpis([("Mule accounts", f"{v['union']:,}", "distinct receivers across 3 scams"),
          ("Shared by 2+ scams", f"{v['multi']} ({pct(v['multi'] / v['union'])})",
           f"vs ≈{exp_shared:.1f} by chance"),
          ("Used by all 3", f"{v['RCA']}", "Romance + CEO + Account replacement"),
          ("Reused mules", pct(D["reused_share"]), "receive 2–22 scam incidents"),
          ("Estimated pool", f"≥ {min(lp.values()):,.0f}", f"capture–recapture range "
                                                          f"{min(lp.values()):,.0f}–{max(lp.values()):,.0f}")])

    c1, c2 = st.columns([1, 1])
    with c1:
        fig = go.Figure()
        circles = [("ROMANCE_SCAM", 0.37, 0.62), ("CEO_SCAM", 0.63, 0.62), ("ACCOUNT_REPLACEMENT_SCAM", 0.5, 0.38)]
        r = 0.255
        for t, cx, cy in circles:
            col = COLOR[t]
            rgb = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
            fig.add_shape(type="circle", x0=cx - r, x1=cx + r, y0=cy - r, y1=cy + r,
                          fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.16)", line=dict(color=col, width=2.5))
        regions = [("R", 0.25, 0.70, "Romance only"), ("C", 0.75, 0.70, "CEO only"),
                   ("A", 0.5, 0.20, "Account replacement only"), ("RC", 0.5, 0.75, "Romance + CEO"),
                   ("RA", 0.355, 0.42, "Romance + Account replacement"), ("CA", 0.645, 0.42, "CEO + Account replacement"),
                   ("RCA", 0.5, 0.545, "All three scams")]
        fig.add_trace(go.Scatter(
            x=[x for _, x, _, _ in regions], y=[y for _, _, y, _ in regions], mode="text",
            text=[f"<b>{v[k]}</b>" for k, _, _, _ in regions],
            textfont=dict(size=[15, 15, 15, 15, 15, 15, 17], color=INK),
            customdata=[[nm, v[k], v[k] / v["union"] * 100] for k, _, _, nm in regions],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} mule accounts "
                          "(%{customdata[2]:.1f}% of pool)<extra></extra>", showlegend=False))
        for t, x, y, anchor in [("ROMANCE_SCAM", 0.12, 0.93, "left"), ("CEO_SCAM", 0.88, 0.93, "right"),
                                ("ACCOUNT_REPLACEMENT_SCAM", 0.5, 0.06, "center")]:
            tot = {"ROMANCE_SCAM": v["tot_R"], "CEO_SCAM": v["tot_C"], "ACCOUNT_REPLACEMENT_SCAM": v["tot_A"]}[t]
            fig.add_annotation(x=x, y=y, text=f"<b>{LABEL[t]}</b><br>{tot} mules", showarrow=False,
                               font=dict(color=INK, size=13), xanchor=anchor)
        style(fig, f"{v['multi']} mules are shared across scam types (chance: ≈{exp_shared:.1f})",
              None, None, h=470, legend=False)
        fig.update_xaxes(visible=False, range=[0, 1], showgrid=False)
        fig.update_yaxes(visible=False, range=[0, 1], scaleanchor="x", scaleratio=1, showgrid=False)
        show(fig, "p2_venn")
        note("Circle sizes are not to scale; hover a number for its share of the pool.")
        table(pd.DataFrame({"Region": [nm for _, _, _, nm in regions], "Mule accounts": [v[k] for k, _, _, _ in regions],
                            "Share of pool": [pct(v[k] / v["union"]) for k, _, _, _ in regions]}))
    with c2:
        # Baseline: uniform use of a pool sized so that the expected number of used accounts = observed
        lo, hi = float(v["union"]), 50_000.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if mid * (1 - math.exp(-n_events / mid)) < v["union"]:
                lo = mid
            else:
                hi = mid
        lam = n_events / lo
        keys = list(range(1, 10)) + ["10+"]
        obs = [reuse.get(k, 0) for k in range(1, 10)] + [sum(c for k, c in reuse.items() if k >= 10)]
        pm = [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(1, 10)]
        ztp = [p / (1 - math.exp(-lam)) for p in pm]
        expv = [p * v["union"] for p in ztp] + [max(0.0, v["union"] * (1 - sum(ztp)))]
        xs = [str(k) for k in keys]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=xs, y=obs, name="Observed mule accounts", marker=dict(color=COLOR["ALL_SCAMS"]),
                             hovertemplate="<b>%{x} scam payments</b><br>%{y} mule accounts<extra></extra>"))
        fig.add_trace(go.Scatter(x=xs, y=expv, name="If every mule were used equally (Poisson)", mode="lines+markers",
                                 line=dict(color="#6b6964", width=2), marker=dict(size=8, color="#6b6964"),
                                 hovertemplate="<b>%{x} scam payments</b><br>%{y:.1f} expected<extra></extra>"))
        style(fig, "Some mules are far busier than equal use predicts", "scam incidents received per mule account",
              "mule accounts", h=470, xgrid=False)
        fig.update_yaxes(type="log", title_text="mule accounts (log scale)")
        show(fig, "p2_reuse")
        note(f"Equal use of a ≈{lo:,.0f}-account pool predicts almost no mule with 7+ payments; "
             f"observed: {sum(c for k, c in reuse.items() if k >= 7)}. Uneven use also means the "
             "capture–recapture estimate is a lower bound.")
        table(pd.DataFrame({"Scam incidents per mule": xs, "Observed": obs, "Equal-use expectation": [round(e, 1) for e in expv]}))

    st.markdown("#### Where the mule banks are")
    f1, f2, _ = filter_row(3)
    sel = f1.multiselect("Scam types", [LABEL[t] for t in SCAMS], default=[LABEL[t] for t in SCAMS], key="p2_types")
    thr = f2.slider("Low-traffic country = carries less than this share of normal payments", 0.1, 2.0, 0.5, 0.1,
                    format="%.1f%%", key="p2_thr")
    chosen = [t for t in SCAMS if LABEL[t] in sel] or SCAMS
    cnt = {}
    for t in chosen:
        for c, k in D["mule_ctry_counts"][t].items():
            cnt[c] = cnt.get(c, 0) + k
    tot = sum(cnt.values())
    nshare = D["normal_bc_share"]
    low = [c for c in set(cnt) | set(nshare) if nshare.get(c, 0) < thr / 100]
    scam_low = sum(cnt.get(c, 0) for c in low) / tot
    norm_low = sum(nshare.get(c, 0) for c in low)
    c1, c2 = st.columns([1.4, 1])
    with c1:
        top = sorted(cnt, key=lambda c: -cnt[c])[:12][::-1]
        fig = go.Figure()
        fig.add_trace(go.Bar(y=top, x=[nshare.get(c, 0) * 100 for c in top], orientation="h", name="Normal payments",
                             marker=dict(color=COLOR["NORMAL"]),
                             hovertemplate="<b>%{y}</b><br>Normal: %{x:.2f}% of payments<extra></extra>"))
        fig.add_trace(go.Bar(y=top, x=[cnt[c] / tot * 100 for c in top], orientation="h", name="Selected scams",
                             marker=dict(color=COLOR["ALL_SCAMS"]), customdata=[[cnt[c]] for c in top],
                             hovertemplate="<b>%{y}</b><br>Scams: %{x:.1f}% (%{customdata[0]} incidents)<extra></extra>"))
        style(fig, "Scam money goes to countries normal traffic rarely reaches", "share of payments (%)", None,
              h=460, ygrid=False)
        fig.update_layout(barmode="group", legend=dict(traceorder="reversed"))
        fig.update_xaxes(ticksuffix="%")
        show(fig, "p2_ctry")
        table(pd.DataFrame({"Destination country (bank)": top[::-1], "Scam incidents": [cnt[c] for c in top[::-1]],
                            "Share of scams": [pct(cnt[c] / tot) for c in top[::-1]],
                            "Share of normal payments": [pct(nshare.get(c, 0), 2) for c in top[::-1]],
                            "Lift": [f"{cnt[c] / tot / nshare[c]:.0f}×" if nshare.get(c, 0) > 0 else "no normal traffic"
                                     for c in top[::-1]]}))
    with c2:
        fig = go.Figure(go.Bar(
            x=["Selected scams", "Normal payments"], y=[scam_low * 100, norm_low * 100],
            marker=dict(color=[COLOR["ALL_SCAMS"], COLOR["NORMAL"]]),
            text=[pct(scam_low), pct(norm_low)], textposition="outside", textfont=dict(color=INK, size=13),
            hovertemplate="<b>%{x}</b><br>%{y:.1f}% land in low-traffic countries<extra></extra>"))
        style(fig, f"{pct(scam_low)} of scam money lands in low-traffic countries",
              None, "share of payments (%)", h=460, legend=False, xgrid=False)
        fig.update_yaxes(range=[0, 105], ticksuffix="%")
        show(fig, "p2_low")
        note(f"Low-traffic = each country carries under {thr:.1f}% of normal payments ({len(low)} countries). "
             "Move the slider to test other cut-offs.")
    notes("- A shared pool is what a professional cash-out (money-mule) network looks like: the same "
          "recruited accounts launder money for several scam schemes.\n- Destinations where accounts are "
          "cheap to open and money is hard to recover fit mule recruitment.\n- The country list is a property of "
          "this synthetic data and is not a real-world risk ranking.",
          "- Rejected: each scam type has its own dedicated accounts (352 shared vs ≈1.5 by chance).\n"
          "- Rejected: mules picked near the victim's usual corridors (account replacement: 12.9% already-used bank "
          "vs 14.3% when mules are shuffled between victims).\n- Pool size is an estimate: pairwise "
          f"capture–recapture gives {min(lp.values()):,.0f}–{max(lp.values()):,.0f}; uneven mule use biases it low.\n"
          "- Mule overlap counts accounts, not people; two accounts may belong to one person.")


# ----------------------------------------------------------------------------------------
# Dashboard 3 - Party types
# ----------------------------------------------------------------------------------------
def page3(D):
    P = D["party"]
    nrm = P["rows"]["NORMAL"]
    header(
        3, "Party type locks",
        "Two scams are locked to one sender type: Romance = 100% Consumer senders, CEO = 100% Business senders "
        f"(normal: {pct(1 - nrm['ordB'])} / {pct(nrm['ordB'])})",
        f"normal payments mix <b>{pct(nrm['counts']['B→C'] / nrm['n'])} Business→Consumer, "
        f"{pct(nrm['counts']['B→B'] / nrm['n'])} Business→Business, {pct(nrm['counts']['C→C'] / nrm['n'])} "
        f"Consumer→Consumer, {pct(nrm['counts']['C→B'] / nrm['n'])} Consumer→Business</b>; sender and receiver "
        f"types are drawn independently (p = {D['party_indep_p']:.2f}).",
        "Only individuals fall for romance scams and only companies fall for CEO scams — the data never breaks "
        "this. The receiver, however, is not restricted: about 27% of romance money goes to a business account, "
        "the same share as ordinary payments, even though the case brief describes the scammer as a consumer. "
        "The other four labels have the same sender/receiver mix as everyday payments.",
        [dict(name="Romance", **{"if": "ROMANCE_SCAM", "then": "ORDERING_TYPE = C (Consumer); BENEFICIARY_TYPE "
                                 "follows the normal mix (C 72.8% vs 71.5%)", "for": "500 of 500 bursts (2,476 rows)"}),
         dict(name="CEO", **{"if": "CEO_SCAM", "then": "ORDERING_TYPE = B (Business); BENEFICIARY_TYPE follows "
                             "the normal mix (C 72.3%)", "for": "945 of 945 payments"}),
         dict(name="All other labels", **{"if": "Account replacement, Fat finger, Duplicate or Recall",
                                          "then": "both party types follow the normal mix (all p > 0.25)",
                                          "for": "649 + 1,940 + 185 clusters + 317 records"})])
    f1, f2, _ = filter_row(3)
    unit = f1.radio("Count", ["Separate incidents", "Rows"], horizontal=True, key="p3_unit")
    metric = f2.radio("Dot chart shows", ["Sender is a Business", "Receiver is a Consumer"], horizontal=True,
                      key="p3_metric")
    U = P["events" if unit.startswith("Separate") else "rows"]
    kpis([("Romance senders", pct(1 - U["ROMANCE_SCAM"]["ordB"]), "Consumer (normal 21.7%)"),
          ("CEO senders", pct(U["CEO_SCAM"]["ordB"]), "Business (normal 78.3%)"),
          ("Romance receivers", pct(U["ROMANCE_SCAM"]["benC"]), "Consumer (normal 71.5%)"),
          ("Labels at baseline", "4 of 6", "no party-type rule")])
    c1, c2 = st.columns([1.3, 1])
    with c1:
        cats = ["NORMAL"] + TYPES
        fig = go.Figure()
        for cb in COMBOS:
            share = [U[t]["counts"][cb] / U[t]["n"] * 100 for t in cats]
            fig.add_trace(go.Bar(
                y=[LABEL[t] for t in cats], x=share, orientation="h", name=COMBO_NAME[cb],
                marker=dict(color=COMBO_COLOR[cb], line=dict(color="#ffffff", width=2)),
                text=[f"{s:.0f}%" if s >= 7 else "" for s in share], textposition="inside",
                insidetextanchor="middle", textfont=dict(color=COMBO_TEXT[cb], size=12),
                customdata=[[U[t]["counts"][cb], U[t]["n"]] for t in cats],
                hovertemplate=f"<b>%{{y}}</b><br>{COMBO_NAME[cb]}: %{{x:.1f}}% "
                              "(%{customdata[0]:,} of %{customdata[1]:,})<extra></extra>"))
        style(fig, "Sender → receiver mix: two scams break from normal", "share (%)", None, h=470, ygrid=False)
        fig.update_layout(barmode="stack")
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(range=[0, 100], ticksuffix="%")
        show(fig, "p3_stack")
        table(pd.DataFrame([{"Label": LABEL[t], "Count": U[t]["n"],
                             **{COMBO_NAME[cb]: pct(U[t]["counts"][cb] / U[t]["n"]) for cb in COMBOS},
                             "p-value vs normal mix": fmt_p(U[t]["p_vs_normal"]) if t != "NORMAL" else "—"}
                            for t in cats]))
    with c2:
        key = "ordB" if metric.startswith("Sender") else "benC"
        bp = nrm[key]
        _, blo, bhi = wilson(round(bp * nrm["n"]), nrm["n"])
        rows_ = []
        for t in TYPES:
            k = round(U[t][key] * U[t]["n"])
            p, lo, hi = wilson(k, U[t]["n"])
            rows_.append(dict(type=t, k=k, n=U[t]["n"], p=p, lo=lo, hi=hi))
        dot_ci_chart(rows_, bp, blo, bhi, f"{metric}: share with 95% confidence interval",
                     "share of payments (%)", "p3_dot", h=470)
        note("Grey band = normal payments' 95% interval. Dots outside it differ from normal traffic.")
    notes("- Romance fraud targets individuals through personal relationships; CEO fraud impersonates an "
          "executive inside a company, so only businesses can be its victims.\n- A business beneficiary in a "
          "romance scam may be a front company or payment service used by the scammer.",
          "- Rejected: romance receivers are only Consumers (27.2% are Business, equal to the normal mix).\n"
          "- Rejected: account replacement targets only businesses paying invoices (mix p = 0.58).\n- Party type is "
          "a property of the role in a payment, not of the account: accounts seen as both sender and receiver "
          "carry the same type only 37% of the time.")


# ----------------------------------------------------------------------------------------
# Dashboard 4 - Geography & currency
# ----------------------------------------------------------------------------------------
def page4(D):
    fx = D["fx_fit"]
    hc = D["home_ccy"]
    rg = D["romance_geo"]
    header(
        4, "Geographic & currency concentration",
        f"Currency conversions = currency-zone changes along the route ({pct(fx['zone'], 2)} exact), "
        f"not border crossings ({pct(fx['border'])})",
        f"<b>{pct(hc['NORMAL']['k'] / hc['NORMAL']['n'])}</b> of normal payments use the sender country's home "
        f"currency; romance victims are led by India and China, normal consumer senders by the US, Switzerland "
        "and the UK.",
        "Every time a payment passes between two banks whose countries use different currencies, it is converted "
        "once. A Germany → France → Netherlands route crosses two borders but needs no conversion because all three "
        "use the euro. Most payments are sent in the sender's own currency. The one anomaly that shifts geography "
        "is the romance scam: its victims sit mainly in India and China and pay in rupees and yuan.",
        [dict(name="Conversion count", **{
            "if": "any payment route",
            "then": "CURRENCY_CONVERSION_COUNT = number of consecutive visible bank pairs whose countries have "
                    "different home currencies; hidden '...' hops add none",
            "for": f"{fx['all_rows_fit']:,} of {fx['all_rows']:,} rows (all labels); exceptions involve rare countries"}),
         dict(name="Payment currency", **{
             "if": "any payment", "then": "CURRENCY_CODE = sender country's home currency (else mostly EUR or USD)",
             "for": f"{pct(hc['NORMAL']['k'] / hc['NORMAL']['n'])} of normal payments; every label within 3 points "
                    "except Romance (94.0%)"})])
    kpis([("Exact match", pct(fx["zone"], 2), f"{fx['n_continuous']:,} unbroken normal routes"),
          ("Border-count rule", pct(fx["border"]), "rejected: fails inside the euro area"),
          ("Hidden hops", f"{pct(fx['broken_fit'], 0)}", f"{fx['broken_n']:,} broken routes add no conversion"),
          ("Home currency", pct(hc["NORMAL"]["k"] / hc["NORMAL"]["n"]), f"of normal payments ({D['n_ccy']} currencies)")])
    c1, c2 = st.columns([1, 1.15])
    with c1:
        rule = st.radio("Test which rule?", ["Currency-zone changes (accepted)", "Border crossings (rejected)"],
                        horizontal=True, key="p4_rule")
        M = D["fx_matrix"]["zone" if rule.startswith("Currency") else "border"]
        cols = sorted(M.keys(), key=int)
        rws = sorted({r for c in M.values() for r in c}, key=int)
        z = [[M[c].get(r, 0) for c in cols] for r in rws]
        lab = lambda s: "5+" if int(s) >= 5 else s
        tot = sum(sum(r) for r in z)
        diag = sum(z[i][j] for i, r in enumerate(rws) for j, c in enumerate(cols) if r == c)
        fig = go.Figure(go.Heatmap(
            z=[[math.log10(x + 1) for x in row] for row in z], x=[lab(c) for c in cols], y=[lab(r) for r in rws],
            text=[[f"{x:,}" if x else "" for x in row] for row in z], texttemplate="%{text}",
            textfont=dict(size=12), customdata=z,
            colorscale=[[0, "#f6f9fe"], [0.35, "#9ec5f4"], [0.7, "#2a78d6"], [1, "#0d366b"]], showscale=False,
            hovertemplate="Rule predicts <b>%{y}</b>, data shows <b>%{x}</b><br>%{customdata:,} payments<extra></extra>"))
        style(fig, f"Rule matches {pct(diag / tot, 2)} of unbroken routes", "actual conversion count",
              "count predicted by the rule", h=430, legend=False, xgrid=False, ygrid=False)
        fig.update_yaxes(autorange="reversed")
        show(fig, "p4_heat")
        note("Cells on the diagonal are payments where the rule is exactly right. Normal payments only.")
        table(pd.DataFrame(z, index=[lab(r) for r in rws], columns=[lab(c) for c in cols]).reset_index()
              .rename(columns={"index": "Rule predicts"}))
    with c2:
        f1, f2 = st.columns(2)
        tsel = f1.selectbox("Compare anomaly type", [LABEL[t] for t in TYPES], index=0, key="p4_type")
        what = f2.radio("Compare", ["Sender country", "Payment currency"], horizontal=True, key="p4_what")
        t = [x for x in TYPES if LABEL[x] == tsel][0]
        if t == "ROMANCE_SCAM":
            a = rg["victim_ctry"] if what.startswith("Sender") else rg["victim_ccy"]
            b = rg["normalC_ctry"] if what.startswith("Sender") else rg["normalC_ccy"]
            blab = "Normal consumer senders"
        else:
            a = D["sender_ctry"][t] if what.startswith("Sender") else D["ccy_mix"][t]
            b = D["sender_ctry"]["NORMAL"] if what.startswith("Sender") else D["ccy_mix"]["NORMAL"]
            blab = "Normal payments"
        keys = sorted(set(list(a)[:8]) | set(list(b)[:5]), key=lambda k: -(a.get(k, 0)))[:12][::-1]
        fig = go.Figure()
        fig.add_trace(go.Bar(y=keys, x=[b.get(k, 0) * 100 for k in keys], orientation="h", name=blab,
                             marker=dict(color=COLOR["NORMAL"]),
                             hovertemplate="<b>%{y}</b><br>" + blab + ": %{x:.1f}%<extra></extra>"))
        fig.add_trace(go.Bar(y=keys, x=[a.get(k, 0) * 100 for k in keys], orientation="h", name=tsel,
                             marker=dict(color=COLOR[t]),
                             hovertemplate="<b>%{y}</b><br>" + tsel + ": %{x:.1f}%<extra></extra>"))
        ttl = ("Romance victims shift to India and China" if t == "ROMANCE_SCAM"
               else f"{tsel}: {what.lower()} mix vs normal")
        style(fig, ttl, "share (%)", None, h=470, ygrid=False)
        fig.update_layout(barmode="group", legend=dict(traceorder="reversed"))
        fig.update_xaxes(ticksuffix="%")
        show(fig, "p4_geo")
        note("Shares only for listed values; values outside the top entries are left out. Unknown values show as 0.")
        table(pd.DataFrame({"Value": keys[::-1], tsel: [pct(a.get(k, 0)) for k in keys[::-1]],
                            blab: [pct(b.get(k, 0)) for k in keys[::-1]]}))
    rows_ = []
    for t in TYPES:
        p, lo, hi = wilson(hc[t]["k"], hc[t]["n"])
        rows_.append(dict(type=t, k=hc[t]["k"], n=hc[t]["n"], p=p, lo=lo, hi=hi))
    p0 = hc["NORMAL"]["k"] / hc["NORMAL"]["n"]
    _, blo, bhi = wilson(hc["NORMAL"]["k"], hc["NORMAL"]["n"])
    dot_ci_chart(rows_, p0, blo, bhi, "Paid in the sender's home currency: only Romance stands out (94.0%)",
                 "share of incidents (%)", "p4_home", h=340)
    notes("- Correspondent banking: each bank in a chain holds its own currency, so a change of currency zone "
          "forces one FX conversion; banks inside the euro area pass euros along unchanged.\n- Romance victims "
          "concentrated in the two most populous countries look like a draw proportional to population.",
          "- Rejected: conversion count = number of border crossings (88.3% fit).\n- Rejected: hidden hops hide "
          "extra conversions (3,803 of 3,803 broken routes match the visible-hop count).\n- Rejected: any anomaly is "
          "restricted to USD, to the domestic currency or to cross-currency payments.\n- 'Home currency' is the most "
          "common currency for each sender country in the 50,000-payment sample.")


# ----------------------------------------------------------------------------------------
# Dashboard 5 - Romance escalation
# ----------------------------------------------------------------------------------------
def page5(D):
    R = D["romance_rows"]
    df = pd.DataFrame({"burst": R["burst"], "step": R["step"], "K": R["K"], "amt": R["amt"], "t": R["t"],
                       "gap": R["gap"], "btype": R["btype"], "vmed": R["vmed"], "vn": R["vn"]})
    df["rel"] = df.amt / df.groupby("burst").amt.transform("first")
    S = D["romance_stats"]
    header(
        5, "Romance scam escalation & burst dynamics",
        "Romance victims pay 2–8 times in about 18 minutes, each payment ×1.5 the last "
        f"(×{S['step_gmean']:.3f}; 95% CI {S['step_ci'][0]:.2f}–{S['step_ci'][1]:.2f})",
        "the victim's own <b>median normal payment</b>: the first scam payment is 0.42× of it, the last 2.2×. "
        "Gaps are compared with a purely random arrival process (exponential).",
        "Scammers start small and then ask for more, each time about 50% more than before. All payments in a "
        "burst follow the exact same bank route and arrive about 5 minutes apart at random. The first request is "
        "below the victim's usual payment size, so it does not look unusual; by the last one, the victim is paying "
        "more than twice their usual amount.",
        [dict(**{"if": "ROMANCE_SCAM",
                 "then": "the victim sends K = 2–8 payments (≈ equally likely) to one new mule; gap to next payment ~ "
                         "Exponential(mean 300 s); amount(i) = base × 1.5<sup>i</sup> × independent noise (×/÷ 1.34); "
                         "every payment reuses one route and duration",
                 "for": "500 of 500 bursts (2,476 rows); amount rule fits steps 1–7 alike"})])
    f1, f2, f3 = filter_row(3)
    kr = f1.slider("Burst size (payments per victim)", 2, 8, (2, 8), key="p5_k")
    bt = f2.radio("Receiver type", ["All", "Consumer", "Business"], horizontal=True, key="p5_bt")
    x = df[(df.K >= kr[0]) & (df.K <= kr[1])]
    if bt != "All":
        x = x[x.btype == ("C" if bt == "Consumer" else "B")]
    if x.empty:
        st.info("No bursts match these filters.")
        return
    lr = np.log(x.amt / x.groupby("burst").amt.shift())
    lrp = lr.groupby(x.burst).shift()
    m = lr.notna() & lrp.notna()
    ac = float(np.corrcoef(lr[m], lrp[m])[0, 1]) if m.sum() > 10 else float("nan")
    gaps = x.gap[x.gap >= 0]
    first = x[x.step == 0]
    last = x[x.step == x.K - 1]
    hist_last = last[last.vn > 0]
    kpis([("Bursts shown", f"{x.burst.nunique():,}", f"{len(x):,} payments"),
          ("Median step", f"×{math.exp(lr.median()):.2f}", f"{pct((lr > 0).sum() / lr.notna().sum())} of steps go up"),
          ("Noise check", f"{ac:+.3f}", "step-to-step correlation (rule predicts −0.5)"),
          ("Median gap", f"{gaps.median():,.0f} s", f"mean {gaps.mean():,.0f} s (rule: 300 s)"),
          ("Last vs usual payment", f"×{(hist_last.amt / hist_last.vmed).median():.1f}" if len(hist_last) else "n/a",
           f"victims with history: {len(hist_last)}")])
    c1, c2 = st.columns([1.25, 1])
    with c1:
        fig = go.Figure()
        steps = sorted(x.step.unique())
        fig.add_trace(go.Box(x=x.step + 1, y=x.rel, name="Observed payments", marker=dict(color=COLOR["ROMANCE_SCAM"], size=4),
                             line=dict(color=COLOR["ROMANCE_SCAM"], width=1.5), fillcolor="rgba(42,120,214,0.15)",
                             boxpoints=False, hoverinfo="y"))
        med = x.groupby("step").rel.median()
        fig.add_trace(go.Scatter(x=[s + 1 for s in steps], y=[1.5 ** s for s in steps], name="Rule: ×1.5 per step",
                                 mode="lines+markers", line=dict(color=INK, width=2, dash="dash"), marker=dict(size=8),
                                 customdata=[[med.get(s, float('nan'))] for s in steps],
                                 hovertemplate="Payment %{x}: rule ×%{y:.2f}, observed median ×%{customdata[0]:.2f}<extra></extra>"))
        fig.add_hline(y=1, line=dict(color="#6b6964", width=2), annotation_text="No escalation",
                      annotation_position="bottom right", annotation_font=dict(color=INK, size=12))
        style(fig, "Each payment is about 1.5× the one before", "payment number in the burst",
              "amount ÷ first payment (log scale)", h=450, xgrid=False)
        fig.update_yaxes(type="log")
        show(fig, "p5_ladder")
        table(pd.DataFrame({"Payment number": [s + 1 for s in steps],
                            "Payments": [int((x.step == s).sum()) for s in steps],
                            "Median amount ÷ first": [round(med[s], 2) for s in steps],
                            "Rule (1.5^i)": [round(1.5 ** s, 2) for s in steps]}))
    with c2:
        mu = gaps.mean()
        edges = np.arange(0, 1560, 60)
        h, _ = np.histogram(gaps.clip(upper=1499), edges)
        expc = len(gaps) * (np.exp(-edges[:-1] / mu) - np.exp(-edges[1:] / mu))
        ks_d, ks_p = ks_uniform(1 - np.exp(-gaps.values / mu))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=(edges[:-1] + 30) / 60, y=h, name="Observed gaps", marker=dict(color=COLOR["ROMANCE_SCAM"]),
                             customdata=np.c_[edges[:-1], edges[1:]],
                             hovertemplate="%{customdata[0]:.0f}–%{customdata[1]:.0f} s: %{y} gaps<extra></extra>"))
        fig.add_trace(go.Scatter(x=(edges[:-1] + 30) / 60, y=expc, name=f"Random arrivals (exponential, mean {mu:.0f} s)",
                                 mode="lines", line=dict(color="#6b6964", width=2),
                                 hovertemplate="expected %{y:.1f}<extra></extra>"))
        style(fig, f"Gaps between payments look random (KS p = {fmt_p(ks_p)})", "minutes until next payment",
              "number of gaps", h=450, xgrid=False)
        fig.update_layout(bargap=0.1)
        show(fig, "p5_gaps")
        note("Gaps longer than 25 minutes are grouped in the last bar.")
    c3, c4 = st.columns([1.25, 1])
    with c3:
        bursts = x.drop_duplicates("burst").sort_values(["K", "vn"], ascending=[False, False])
        opts = [f"Burst {b} · {k} payments · receiver {('Consumer' if bt_ == 'C' else 'Business')}"
                + (f" · victim has {vn} normal payments" if vn > 0 else "")
                for b, k, bt_, vn in zip(bursts.burst, bursts.K, bursts.btype, bursts.vn)]
        pick = st.selectbox("Explore one burst", opts, index=0, key="p5_pick")
        b = int(pick.split()[1])
        y = df[df.burst == b].sort_values("step")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=y.t / 60, y=y.amt, mode="lines+markers", name="Scam payments",
                                 line=dict(color=COLOR["ROMANCE_SCAM"], width=2), marker=dict(size=11, line=dict(color="#fff", width=2)),
                                 customdata=np.c_[y.step + 1, y.rel],
                                 hovertemplate="Payment %{customdata[0]}<br>%{x:.1f} min after the first<br>"
                                               "$%{y:,.2f} (×%{customdata[1]:.2f} first)<extra></extra>"))
        if y.vn.iloc[0] > 0:
            fig.add_hline(y=y.vmed.iloc[0], line=dict(color="#6b6964", width=2),
                          annotation_text=f"Victim's usual payment: ${y.vmed.iloc[0]:,.2f} (median of {y.vn.iloc[0]})",
                          annotation_position="top left", annotation_font=dict(color=INK, size=12))
        style(fig, f"Burst {b}: ${y.amt.iloc[0]:,.2f} → ${y.amt.iloc[-1]:,.2f} in {y.t.iloc[-1] / 60:.0f} minutes",
              "minutes since first payment", "USD amount", h=400)
        show(fig, "p5_burst")
    with c4:
        kc = df.drop_duplicates("burst").K.value_counts().sort_index()
        fig = go.Figure(go.Bar(x=kc.index, y=kc.values, marker=dict(color=COLOR["ROMANCE_SCAM"]),
                               hovertemplate="%{x} payments: %{y} bursts<extra></extra>", name="Observed bursts"))
        fig.add_hline(y=kc.sum() / 7, line=dict(color="#6b6964", width=2),
                      annotation_text=f"Equal chance for 2–8: {kc.sum() / 7:.0f}", annotation_position="top left",
                      annotation_font=dict(color=INK, size=12))
        style(fig, f"Burst size 2–8 is roughly equally likely (p = {S['K_p_uniform']:.2f})", "payments in the burst",
              "bursts", h=400 + 70, legend=False, xgrid=False)
        show(fig, "p5_k")
    kpis([("Route copied", f"{S['route_cloned']} / {S['route_bursts']}", "bursts reuse one path, currency, duration"),
          ("Last payment is largest", pct(S["last_largest"]), "of bursts"),
          ("Burst length", f"{S['span_median'] / 60:.0f} min", f"median; longest {S['span_max'] / 60:.0f} min")])
    notes("- Trust-building followed by rising requests ('one more fee and the money is released') matches the "
          "×1.5 ladder.\n- Starting below the victim's usual payment keeps the first transfer unremarkable.\n"
          "- Real romance scams unfold over weeks; this generator compresses them into ~20 minutes, which should be "
          "stated as a property of the data.",
          "- Rejected: each payment = previous × 1.5 (compounding): consecutive step changes correlate at −0.494, "
          "the value expected for a fixed ladder with independent noise (compounding predicts 0).\n- Rejected: strictly "
          "rising amounts (17% of steps go down).\n- Rejected: fixed time between payments (gap spread equals its mean, as "
          "for random arrivals).\n- Only 156 of 500 victims have normal history, so 'base vs usual payment' rests on them.")


# ----------------------------------------------------------------------------------------
# Dashboard 6 - CEO scam payouts
# ----------------------------------------------------------------------------------------
def page6(D):
    sc = pd.DataFrame(D["ceo_scam"])
    nm = pd.DataFrame(D["ceo_normal"])
    M = D["ceo_model"]
    C = D["ceo_counts"]
    n30 = nm[nm.vn >= 30]
    n_1000 = float((n30.lr > 3).mean())
    header(
        6, "CEO scam bimodal payouts",
        f"{pct(M['share'])} of CEO scams demand ≈{10 ** M['log_mult']:,.0f}× the victim's typical payment; "
        f"the other {pct(1 - M['share'])} look ordinary",
        f"the victim's own normal payments: only <b>{pct(n_1000)}</b> exceed 1,000× the victim's median, and "
        f"{pct(C['normal_ge_1M'])} are $1M or more (scams: {pct(C['ge_1M'])}).",
        "A CEO scam tricks a company into paying a stranger. Most of these payments are ordinary in size, so an "
        "amount check would miss them. About one in five, however, is a huge one-off transfer — typically $1M–$22M, "
        "around a thousand times what the company normally pays. Smaller companies are hit with these giant "
        "requests far more often than large ones. The payment text never contains words like 'urgent' or 'CEO'.",
        [dict(**{"if": "CEO_SCAM",
                 "then": f"a Business pays a mule it has never paid ({C['novel']} of {C['scams']}); with probability "
                         f"≈{pct(M['share'], 0)} the amount = victim's median × ≈10<sup>3.1</sup> "
                         f"(×{M['mult_ci'][0]:,.0f}–×{M['mult_ci'][1]:,.0f}), otherwise close to the victim's normal "
                         "range (≈×1.3 tilt); no marker text",
                 "for": f"all {C['scams']} CEO scams ({C['victims']} victims); amount rule measured on the "
                        f"{M['n']} with 30+ normal payments"})])
    f1, f2, _ = filter_row(3)
    hmin = f1.select_slider("Use victims with at least this many normal payments", [1, 10, 30, 50, 100], value=30,
                            key="p6_h")
    thr = f2.select_slider("Call a payment 'massive' above this multiple of the victim's median",
                           [50, 100, 200, 500, 1000], value=200, key="p6_t")
    s = sc[sc.vn >= hmin]
    n_ = nm[nm.vn >= hmin]
    lt = math.log10(thr)
    big = s[s.lr > lt]
    share_s = len(big) / max(1, len(s))
    share_n = float((n_.lr > lt).mean())
    kpis([("New payee", f"{C['novel']} / {C['scams']}", "never paid by this victim before"),
          (f"Above {thr:,}× median", pct(share_s), f"normal payments: {pct(share_n, 2)}"),
          ("Massive payments", f"${big.amt.median() / 1e6:,.1f}M" if len(big) else "n/a",
           (f"median; 5–95%: ${big.amt.quantile(0.05) / 1e6:,.1f}M–${big.amt.quantile(0.95) / 1e6:,.1f}M") if len(big) else ""),
          ("Model fit", f"{pct(M['share'])} at ×{10 ** M['log_mult']:,.0f}",
           f"95% CI {pct(M['share_ci'][0])}–{pct(M['share_ci'][1])}"),
          ("Urgency words", "0", f"in {C['scams']} scam texts (30 words checked)")])
    c1, c2 = st.columns([1.3, 1])
    with c1:
        edges = np.arange(-5, 5.01, 0.25)
        hs, _ = np.histogram(s.lr.clip(-4.99, 4.99), edges)
        hn, _ = np.histogram(n_.lr.clip(-4.99, 4.99), edges)
        mids = (edges[:-1] + edges[1:]) / 2
        fig = go.Figure()
        fig.add_trace(go.Bar(x=mids, y=hs / max(1, hs.sum()) * 100, name="CEO scams", marker=dict(color=COLOR["CEO_SCAM"]),
                             customdata=np.c_[[mult_label(a) for a in edges[:-1]], [mult_label(b) for b in edges[1:]], hs],
                             hovertemplate="%{customdata[0]}–%{customdata[1]} median<br>%{y:.1f}% of scams "
                                           "(%{customdata[2]})<extra></extra>"))
        fig.add_trace(go.Scatter(x=mids, y=hn / max(1, hn.sum()) * 100, name="Same victims' normal payments",
                                 mode="lines", line=dict(color="#6b6964", width=2, shape="hvh"),
                                 hovertemplate="normal: %{y:.1f}%<extra></extra>"))
        fig.add_vline(x=lt, line=dict(color=INK, width=1.5, dash="dot"),
                      annotation_text=f"'Massive' cut-off: {thr:,}×", annotation_position="top left",
                      annotation_font=dict(color=INK, size=12))
        style(fig, f"A second peak near 1,000× holds {pct(share_s)} of scams", "amount ÷ victim's median normal payment",
              "share of payments (%)", h=450, xgrid=False)
        fig.update_xaxes(**LOG_TICKS, range=[-4.2, 5])
        fig.update_layout(bargap=0.08)
        show(fig, "p6_hist")
        note(f"{len(s):,} scams and {len(n_):,} sampled normal payments of the same victims (20 per victim).")
    with c2:
        if len(s) >= 60:
            q = pd.qcut(s.vmed, 6, duplicates="drop")
            g = s.assign(q=q).groupby("q", observed=True)
            labs, ps, los, his, ns, ks, meds = [], [], [], [], [], [], []
            for iv, grp in g:
                k = int((grp.lr > lt).sum())
                p, lo, hi = wilson(k, len(grp))
                labs.append(f"${grp.vmed.median():,.0f}")
                ps.append(p * 100); los.append((p - lo) * 100); his.append((hi - p) * 100); ns.append(len(grp)); ks.append(k)
                meds.append(f"${iv.left:,.0f}–${iv.right:,.0f}")
            fig = go.Figure(go.Bar(
                x=labs, y=ps, marker=dict(color=COLOR["CEO_SCAM"]),
                error_y=dict(type="data", array=his, arrayminus=los, color=INK2, thickness=1.5, width=6),
                customdata=np.c_[ks, ns, meds],
                hovertemplate="Victims with typical payment %{customdata[2]}<br>%{y:.1f}% massive "
                              "(%{customdata[0]} of %{customdata[1]})<extra></extra>", name="CEO scams"))
            fig.add_hline(y=share_n * 100, line=dict(color="#6b6964", width=2),
                          annotation_text=f"Normal payments: {pct(share_n, 2)}", annotation_position="top right",
                          annotation_font=dict(color=INK, size=12))
            style(fig, "Smaller companies get the giant requests", "victim's typical (median) payment, six equal groups",
                  f"share above {thr:,}× (%)", h=450, legend=False, xgrid=False)
            fig.update_yaxes(ticksuffix="%", rangemode="tozero")
            show(fig, "p6_size")
            table(pd.DataFrame({"Victim median range": meds, "Scams": ns, "Massive": ks,
                                "Share massive": [f"{p:.1f}%" for p in ps]}))
        else:
            st.info("Too few victims at this history setting to split into groups.")
    kw = pd.DataFrame(D["ceo_keywords"])
    kw["Scam texts"] = kw.scam.astype(str) + " / " + kw.scam_n.map("{:,}".format)
    kw["Normal texts (same victims)"] = kw.normal.astype(str) + " / " + kw.normal_n.map("{:,}".format)
    table(kw.rename(columns={"word": "Word (whole word, any case)"})[["Word (whole word, any case)", "Scam texts",
                                                                      "Normal texts (same victims)"]],
          "Keyword check: 30 urgency and executive words in the sender text")
    notes("- Spoofed executive e-mails ('urgent, confidential acquisition') push finance staff into one large "
          "transfer; the ordinary-sized majority would pass amount-based controls.\n- Smaller firms may have fewer "
          "approval layers, which is one candidate reason for more giant requests; a generator design choice is another.",
          "- Rejected: every CEO scam is massive (≈82% are ordinary-sized).\n- Rejected: massive = an ordinary payment "
          "× 1,000 (would spread over 4 orders of magnitude; observed spread 0.28).\n- Rejected: a fixed dollar band "
          "independent of the victim (spread grows from 0.33 to 0.52 when victims are shuffled).\n- Rejected: keyword "
          "markers in the text.\n- The file had no timestamps, so timing of CEO scams is untested.")


# ----------------------------------------------------------------------------------------
# Dashboard 7 - Account replacement stealth
# ----------------------------------------------------------------------------------------
def page7(D):
    A = D["ar"]
    nb = D["ar_novelty_baseline"]
    header(
        7, "Account replacement stealth",
        f"Account-replacement scams change only the payee: {A['paid_before']} of {A['scams']} go to a known payee, "
        "while amount and timing stay at the victim's normal pattern",
        f"the same victims' normal payments: <b>{pct(1 - nb['new_payee'])}</b> go to a payee already paid before, "
        f"{pct(1 - nb['new_bank'])} to a known bank, {pct(1 - nb['new_ctry'])} to a known country. A scam amount "
        "sitting at the 50th percentile of the victim's own payments means 'perfectly typical'.",
        "In this fraud a genuine invoice is intercepted and the bank details are swapped. Everything the victim "
        "expects — the amount, the timing — stays exactly as normal, so nothing looks wrong. The only change is "
        "where the money goes: always a new account, usually at a bank and in a country the victim has never used, "
        "drawn from the same mule pool as the other scams.",
        [dict(**{"if": "ACCOUNT_REPLACEMENT_SCAM",
                 "then": "BENEFICIARY_ACCOUNT and BENEFICIARY_BIC8 are replaced by a mule from the shared pool, chosen "
                         "independently of the victim's history; USD_AMOUNT and EPOCH_SECONDS are left as an ordinary "
                         "payment of that victim",
                 "for": f"all {A['scams']} records ({A['victims']} victims, {A['mules']} mules; {A['reused']} mules reused)"})])
    f1, f2, _ = filter_row(3)
    hmin = f1.slider("Use victims with at least this many normal payments", 1, 100, 20, key="p7_h")
    view = f2.radio("Amount shown as", ["Percentile in victim's history", "Ratio to victim's median"], horizontal=True,
                    key="p7_view")
    vn = np.array(A["pct_vn"])
    pa = np.array(A["pct_amt"])[vn >= hmin]
    pt = np.array(A["pct_time"])[vn >= hmin]
    _, pa_p = ks_uniform(pa)
    _, pt_p = ks_uniform(pt)
    kh = A["with_history"]
    kpis([("Known payee", f"{A['paid_before']} / {A['scams']}", f"normal: {pct(1 - nb['new_payee'])} known"),
          ("New bank", pct(A["new_bank"]), f"normal: {pct(nb['new_bank'])}"),
          ("New country", pct(A["new_ctry"]), f"normal: {pct(nb['new_ctry'])}"),
          ("Amount percentile", f"{pa.mean():.3f}" if len(pa) else "n/a", f"0.500 = typical · KS p = {fmt_p(pa_p)}"),
          ("Timing percentile", f"{pt.mean():.3f}" if len(pt) else "n/a", f"0.500 = random · KS p = {fmt_p(pt_p)}")])
    c1, c2 = st.columns([1, 1])
    with c1:
        mets = [("Payee never paid before", 1.0, A["scams"], A["scams"], nb["new_payee"]),
                ("Bank never used before", A["new_bank"], round(A["new_bank"] * kh), kh, nb["new_bank"]),
                ("Country never used before", A["new_ctry"], round(A["new_ctry"] * kh), kh, nb["new_ctry"])]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[m[0] for m in mets], y=[m[4] * 100 for m in mets], name="Victims' normal payments",
                             marker=dict(color=COLOR["NORMAL"]), hovertemplate="%{x}<br>normal: %{y:.1f}%<extra></extra>"))
        cis = [wilson(m[2], m[3]) for m in mets]
        fig.add_trace(go.Bar(x=[m[0] for m in mets], y=[m[1] * 100 for m in mets], name="Account-replacement scams",
                             marker=dict(color=COLOR["ACCOUNT_REPLACEMENT_SCAM"]),
                             error_y=dict(type="data", array=[(c[2] - c[0]) * 100 for c in cis],
                                          arrayminus=[(c[0] - c[1]) * 100 for c in cis], color=INK2, thickness=1.5, width=6),
                             customdata=[[m[2], m[3]] for m in mets],
                             hovertemplate="%{x}<br>scams: %{y:.1f}% (%{customdata[0]} of %{customdata[1]})<extra></extra>"))
        style(fig, "The destination is the only thing that changes", None, "share of payments (%)", h=430, xgrid=False)
        fig.update_layout(barmode="group")
        fig.update_yaxes(range=[0, 110], ticksuffix="%")
        show(fig, "p7_novel")
        note(f"Mule bank already used by the victim: {pct(A['obs_bank_known'])} observed vs {pct(A['perm_bank_known'])} "
             "when mules are shuffled between victims — the mule is chosen without regard to the victim.")
    with c2:
        if view.startswith("Percentile"):
            edges = np.linspace(0, 1, 11)
            h, _ = np.histogram(pa, edges)
            fig = go.Figure(go.Bar(x=[f"{int(a * 100)}–{int(b * 100)}" for a, b in zip(edges[:-1], edges[1:])], y=h,
                                   marker=dict(color=COLOR["ACCOUNT_REPLACEMENT_SCAM"]), name="Scams",
                                   hovertemplate="percentile %{x}: %{y} scams<extra></extra>"))
            fig.add_hline(y=len(pa) / 10, line=dict(color="#6b6964", width=2),
                          annotation_text=f"If amounts were typical: {len(pa) / 10:.0f} per band",
                          annotation_position="top left", annotation_font=dict(color=INK, size=12))
            style(fig, f"Scam amounts sit evenly across the victim's own range (KS p = {fmt_p(pa_p)})",
                  "percentile of the scam amount within the victim's normal payments", "scams", h=430, legend=False,
                  xgrid=False)
        else:
            ls_, ln_ = np.array(A["lr_scam"]), np.array(A["lr_normal"])
            edges = np.arange(-4, 4.01, 0.25)
            hs, _ = np.histogram(ls_.clip(-3.99, 3.99), edges)
            hn, _ = np.histogram(ln_.clip(-3.99, 3.99), edges)
            mids = (edges[:-1] + edges[1:]) / 2
            fig = go.Figure()
            fig.add_trace(go.Bar(x=mids, y=hs / hs.sum() * 100, name="Scams", marker=dict(color=COLOR["ACCOUNT_REPLACEMENT_SCAM"]),
                                 hovertemplate="scams: %{y:.1f}%<extra></extra>"))
            fig.add_trace(go.Scatter(x=mids, y=hn / hn.sum() * 100, name="Same victims' normal payments", mode="lines",
                                     line=dict(color="#6b6964", width=2, shape="hvh"),
                                     hovertemplate="normal: %{y:.1f}%<extra></extra>"))
            style(fig, "Scam amounts have the same spread as the victim's own payments",
                  "amount ÷ victim's median payment", "share (%)", h=430, xgrid=False)
            fig.update_xaxes(**LOG_TICKS, range=[-3.5, 3.5])
            fig.update_layout(bargap=0.08)
        show(fig, "p7_amt")
    edges = np.linspace(0, 1, 11)
    h, _ = np.histogram(pt, edges)
    fig = go.Figure(go.Bar(x=[f"{int(a * 100)}–{int(b * 100)}%" for a, b in zip(edges[:-1], edges[1:])], y=h,
                           marker=dict(color=COLOR["ACCOUNT_REPLACEMENT_SCAM"]),
                           hovertemplate="%{x} of the way through the victim's history: %{y} scams<extra></extra>"))
    fig.add_hline(y=len(pt) / 10, line=dict(color="#6b6964", width=2),
                  annotation_text=f"If timing were random: {len(pt) / 10:.0f} per band", annotation_position="top left",
                  annotation_font=dict(color=INK, size=12))
    style(fig, f"Scams strike at any point in the victim's payment history (KS p = {fmt_p(pt_p)})",
          "position of the scam within the victim's payment timeline", "scams", h=340, legend=False, xgrid=False)
    show(fig, "p7_time")
    table(pd.DataFrame({"Measure": [m[0] for m in mets] + ["Amount percentile (mean)", "Timing percentile (mean)"],
                        "Account-replacement scams": [pct(m[1]) for m in mets] + [f"{pa.mean():.3f}", f"{pt.mean():.3f}"],
                        "Victims' normal payments": [pct(m[4]) for m in mets] + ["0.500 (typical)", "0.500 (random)"],
                        "Test": ["", "", "", f"KS p = {fmt_p(pa_p)}", f"KS p = {fmt_p(pt_p)}"]}))
    notes("- An intercepted invoice keeps its amount and due date because the victim believes it is genuine; only the "
          "bank details change.\n- New bank and new country are the practical red flags: 87% of scams go to a bank "
          "the victim has never used, against 51% of the victim's normal payments.",
          "- Rejected: an amount threshold triggers the scam (percentile uniform).\n- Rejected: the scam copies an "
          "earlier payment (2.2% share an amount with a normal payment vs 8.7% repetition among normal payments).\n"
          "- Rejected: only the account number changes and the genuine bank is kept (account country = bank country "
          "in 261 of 261 IBAN mules).\n- 'New payee' alone is weak evidence: 84% of normal payments also go to a "
          "first-time payee in this data.")


# ----------------------------------------------------------------------------------------
# Dashboard 8 - Routing & cover signature
# ----------------------------------------------------------------------------------------
METRICS = {
    "Path ends at a different bank than the beneficiary's": ("ben_mis", "Beneficiary-end mismatch"),
    "'Covered' routing (share of multi-bank routes)": ("cov_multi", "Covered routing"),
    "Bank corridor already seen in normal traffic": ("known_pair", "Known corridor"),
    "Sender and receiver bank in the same country": ("domestic", "Domestic"),
    "No currency conversion": ("fx0", "No conversion"),
    "Path starts at a different bank than the sender's": ("ord_mis", "Sender-end mismatch"),
    "Route has a hidden hop (flag N)": ("flagN", "Hidden hop"),
    "Direct (2-bank) route": ("direct", "Direct route"),
}


def page8(D):
    S = D["signature"]
    sc = D["scam_combined"]
    cp = D["cover_pairs"]
    nE = S["events"]["NORMAL"]
    header(
        8, "Routing & cover-status signature",
        f"Scam routes never miss the mule's bank (0 of {sc['events']:,} vs {pct(nE['ben_mis'][0] / nE['ben_mis'][1])} "
        f"normal) and are almost never 'Covered' ({sc['cov']} of {sc['multi']} = {pct(sc['cov'] / sc['multi'])} vs "
        f"{pct(nE['cov_multi'][0] / nE['cov_multi'][1])})",
        f"normal payments: 5.0% of routes end at another bank than the beneficiary's, "
        f"{pct(nE['cov_multi'][0] / nE['cov_multi'][1])} of multi-bank routes are Covered, and "
        f"{pct(nE['known_pair'][0] / nE['known_pair'][1])} use a bank corridor seen elsewhere in normal traffic.",
        "'Covered' is a special routing method only available between two banks that already have a working "
        "relationship. Whether a route is Covered depends entirely on the pair of banks at each end. Scam money is "
        "sent to new mule banks that normal customers rarely use, so the bank pairs are new, the Covered option is "
        "almost never available, and the route always ends exactly at the mule's own bank. Fat-finger, duplicate and "
        "recall payments route like everyday traffic.",
        [dict(name="Cover status", **{"if": "a multi-bank payment between first bank X and last bank Y",
                                      "then": "TRANSACTION_TYPE_CODE is Covered for every payment or for none: a fixed "
                                              "property of the bank pair (16% of pairs)",
                                      "for": f"{cp['consistent']:,} of {cp['n_pairs']:,} bank pairs with 5+ multi-bank payments"}),
         dict(name="Scam route", **{"if": "Romance, CEO or Account-replacement scam",
                                    "then": "last bank = BENEFICIARY_BIC8 always; Covered almost never; cross-border",
                                    "for": f"{sc['events']:,} scam incidents: 0 end-mismatches, {sc['cov']} of {sc['multi']} "
                                           f"multi-bank routes Covered, {sc['domestic']} domestic"})])
    kpis([("End mismatch, scams", f"0 / {sc['events']:,}", "normal: 5.0%"),
          ("Covered, scams", pct(sc["cov"] / sc["multi"]), f"normal: {pct(nE['cov_multi'][0] / nE['cov_multi'][1])}"),
          ("Domestic, scams", pct(sc["domestic"] / sc["events"]), f"normal: {pct(nE['domestic'][0] / nE['domestic'][1])}"),
          ("Cover pairs consistent", f"{cp['consistent']:,} / {cp['n_pairs']:,}", "all-Covered or never-Covered")])
    f1, f2 = filter_row(2)
    mname = f1.selectbox("Routing measure", list(METRICS), index=0, key="p8_metric")
    unit = f2.radio("Count", ["Separate incidents", "Rows"], horizontal=True, key="p8_unit")
    key, short = METRICS[mname]
    U = S["events" if unit.startswith("Separate") else "rows"]
    c1, c2 = st.columns([1.2, 1])
    with c1:
        bk, bn = U["NORMAL"][key]
        bp, blo, bhi = wilson(bk, bn)
        rows_ = []
        for t in TYPES:
            k, n = U[t][key]
            p, lo, hi = wilson(k, n)
            rows_.append(dict(type=t, k=k, n=n, p=p, lo=lo, hi=hi, pval=binom_p(k, n, bp) if n <= 5000 else float("nan")))
        dot_ci_chart(rows_, bp, blo, bhi, f"{short}: scams vs normal (95% CI)", "share (%)", "p8_dot", h=420)
        if key == "known_pair":
            note("Corridor = (first bank, last bank). Reference set: bank pairs in 428,494 normal payments of the "
                 "recall-account file. Customer recall is inflated here because those are its own accounts.")
        table(pd.DataFrame([{"Label": LABEL[r["type"]], "Count": f"{r['k']:,} / {r['n']:,}", "Share": pct(r["p"]),
                             "95% CI": f"{pct(r['lo'])} – {pct(r['hi'])}", "p vs normal": fmt_p(r["pval"])}
                            for r in rows_] + [{"Label": "Normal payments", "Count": f"{bk:,} / {bn:,}", "Share": pct(bp),
                                                "95% CI": f"{pct(blo)} – {pct(bhi)}", "p vs normal": "—"}]))
    with c2:
        labs = [f"{i * 10}–{(i + 1) * 10}%" for i in range(10)]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=labs, y=cp["random_hist"], name="If Covered were decided payment by payment",
                             marker=dict(color=COLOR["NORMAL"]), hovertemplate="%{x}: %{y:,} bank pairs (random)<extra></extra>"))
        fig.add_trace(go.Bar(x=labs, y=cp["hist"], name="Observed bank pairs", marker=dict(color="#184f95"),
                             hovertemplate="%{x}: %{y:,} bank pairs (observed)<extra></extra>"))
        style(fig, "Covered is all-or-nothing per bank pair", "share of the pair's multi-bank payments that are Covered",
              "bank pairs", h=420, xgrid=False)
        fig.update_layout(barmode="group")
        show(fig, "p8_pairs")
        note(f"{cp['n_pairs']:,} bank pairs with 5+ multi-bank payments: every one sits at 0% or 100%. "
             f"Random assignment at the overall {pct(cp['overall_cov'])} rate would spread them out.")
    notes("- The cover method needs a standing correspondent relationship between the sending and receiving bank; a "
          "fraudster's bank is a new counterparty, so the payment goes serially through intermediaries.\n- The 5% "
          "end-mismatch in normal traffic may represent accounts serviced through another institution. Its total "
          "absence for scam payees is likely a generator artefact: a strong feature in this dataset, not a rule to "
          "assume in real traffic.",
          "- Rejected: anomalies use longer or more broken routes (direct share and hidden-hop rate at baseline once "
          "geography is controlled).\n- Rejected: Covered depends on country, currency, party type, amount or route "
          "length (all flat; only the bank pair matters).\n- Rejected: fat finger, duplicate or recall routes differ from "
          "normal (all p > 0.1 on mismatch and Covered).")


# ----------------------------------------------------------------------------------------
# Dashboard 9 - Latency & path topology
# ----------------------------------------------------------------------------------------
def page9(D):
    pc = {int(k): v for k, v in D["pc_dist"].items()}
    ntot = sum(pc.values())
    hid = D["hidden_rate"]
    G = D["geo"]["slow"]
    base = G["NORMAL"]["observed"]
    expl = {t: (G[t]["expected"] - base) / (G[t]["observed"] - base) for t in SCAMS}
    MM = D["mode_medians"]
    header(
        9, "Settlement latency & path topology",
        "Payment duration is two-speed (fast ≈25 s, slow ≈1,470 s); the destination country explains "
        f"{min(expl.values()):.0%}–{max(expl.values()):.0%} of why scams look slow",
        f"normal payments: <b>{pct(base)}</b> take over 5 minutes; {pct(pc[2] / ntot)} go direct between two banks, "
        f"and each extra bank is ≈{np.mean([pc[k + 1] / pc[k] for k in range(2, 6)]):.2f}× as likely as one bank fewer.",
        "Each payment is either fast (seconds) or slow (around 25 minutes) — there is little in between. Longer routes "
        "are more often slow, and some banks and countries are much slower than others. Scam payments look slower at "
        "first glance, but that is mostly because they go to slow destinations: once the destination is accounted for, "
        "only a small gap remains. Every hop has about a 5% chance of being hidden ('...'), which is why longer routes "
        "are more often marked as broken.",
        [dict(name="Route length", **{"if": "any payment",
                                      "then": "number of banks follows a geometric law: each extra bank ≈0.37× as likely "
                                              "(62.9% / 23.5% / 8.6% / 3.2% / 1.2% for 2–6 banks), redrawn per payment",
                                      "for": "all 50,000 sampled normal payments"}),
         dict(name="Hidden hops", **{"if": "a route has k banks",
                                     "then": f"each of its k−1 hops is hidden as '...' with probability ≈{pct(hid)}, "
                                             "so P(flag N) ≈ 1 − 0.95<sup>k−1</sup>",
                                     "for": "all normal payments; every label at baseline after geography control"}),
         dict(name="Duration", **{"if": "any payment",
                                  "then": f"TOTAL_DURATION is fast (median {MM['fast']['2']:.0f} s direct, "
                                          f"+≈10–16 s per extra bank) or slow (median ≈{MM['slow']['2']:,.0f} s); slow "
                                          "share rises with route length and depends on the banks involved",
                                  "for": "all normal payments; no time-of-day or weekday effect"})])
    f1, f2 = filter_row(2)
    tsel = f1.selectbox("Overlay an anomaly type", [LABEL[t] for t in TYPES], index=0, key="p9_type")
    t = [x for x in TYPES if LABEL[x] == tsel][0]
    pcsel = f2.radio("Route length", ["All", "2 banks", "3 banks", "4 banks", "5+ banks"], horizontal=True, key="p9_pc")
    groups = ["2", "3", "4", "5+"] if pcsel == "All" else [pcsel.split()[0]]
    bins = D["dur_bins"]
    mids = [(a + b) / 2 for a, b in zip(bins[:-1], bins[1:])]
    hn = np.sum([D["dur_hist"]["NORMAL"][g] for g in groups], axis=0)
    ht = np.sum([D["dur_hist"][t][g] for g in groups], axis=0)
    kpis([("Slow (over 5 min)", pct(base), "of normal payments"),
          ("Fast mode", f"{MM['fast']['2']:.0f} s", "median, direct routes"),
          ("Slow mode", f"{MM['slow']['2'] / 60:,.0f} min", "median, direct routes"),
          ("Hidden hop", pct(hid), "chance per hop"),
          ("Scam slowness explained", f"{min(expl.values()):.0%}–{max(expl.values()):.0%}", "by destination country")])
    c1, c2 = st.columns([1.3, 1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=mids, y=hn / max(1, hn.sum()) * 100, name="Normal payments", marker=dict(color=COLOR["NORMAL"]),
                             customdata=np.c_[[10 ** a for a in bins[:-1]], [10 ** b for b in bins[1:]]],
                             hovertemplate="%{customdata[0]:,.0f}–%{customdata[1]:,.0f} s<br>normal: %{y:.1f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=mids, y=ht / max(1, ht.sum()) * 100, name=tsel, mode="lines",
                                 line=dict(color=COLOR[t], width=2.5, shape="hvh"),
                                 hovertemplate=tsel + ": %{y:.1f}%<extra></extra>"))
        fig.add_vline(x=math.log10(300), line=dict(color=INK, width=1.5, dash="dot"), annotation_text="5 min",
                      annotation_position="top", annotation_font=dict(color=INK, size=12))
        style(fig, "Two speeds: seconds or about half an hour", "total duration (log scale)", "share of payments (%)",
              h=440, xgrid=False)
        fig.update_xaxes(**DUR_TICKS)
        fig.update_layout(bargap=0.05)
        show(fig, "p9_dur")
        note(f"Route length shown: {pcsel}. Anomaly line counts each burst or copy-cluster once.")
    with c2:
        rows_ = []
        for x in SCAMS + TYPES[3:]:
            g = G[x]
            rows_.append((x, g["observed"], g["expected"], g["p"], g["n"]))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[LABEL[r[0]] for r in rows_], y=[r[2] * 100 for r in rows_],
                             name="Expected from destination & origin country", marker=dict(color="#c9c7bf"),
                             hovertemplate="%{x}<br>expected %{y:.1f}%<extra></extra>"))
        fig.add_trace(go.Bar(x=[LABEL[r[0]] for r in rows_], y=[r[1] * 100 for r in rows_], name="Observed",
                             marker=dict(color=[COLOR[r[0]] for r in rows_]),
                             customdata=[[r[3], r[4]] for r in rows_],
                             hovertemplate="%{x}<br>observed %{y:.1f}% (p = %{customdata[0]:.3f}, n = %{customdata[1]})"
                                           "<extra></extra>"))
        fig.add_hline(y=base * 100, line=dict(color="#6b6964", width=2), annotation_text=f"Normal: {pct(base)}",
                      annotation_position="top right", annotation_font=dict(color=INK, size=12))
        style(fig, "Scams are slow mostly because of where they go", None, "share slower than 5 min (%)", h=440, xgrid=False)
        fig.update_layout(barmode="group")
        fig.update_yaxes(ticksuffix="%", range=[0, 85])
        show(fig, "p9_geo")
        table(pd.DataFrame({"Label": [LABEL[r[0]] for r in rows_], "Observed slow": [pct(r[1]) for r in rows_],
                            "Expected from geography": [pct(r[2]) for r in rows_], "p-value": [fmt_p(r[3]) for r in rows_],
                            "Share of excess explained": [f"{(r[2] - base) / (r[1] - base):.0%}" if r[1] - base > 0.02 else "—"
                                                          for r in rows_]}))
    c3, c4 = st.columns(2)
    with c3:
        ks = sorted(k for k in pc if k <= 9)
        ratio = np.mean([pc[k + 1] / pc[k] for k in range(2, 6)])
        fit = [pc[2] / ntot * ratio ** (k - 2) * 100 for k in ks]
        tr = D["slow_by_pc"][t]
        tn = sum(v[1] for v in tr.values())
        fig = go.Figure()
        fig.add_trace(go.Bar(x=ks, y=[pc[k] / ntot * 100 for k in ks], name="Normal payments", marker=dict(color=COLOR["NORMAL"]),
                             hovertemplate="%{x} banks: %{y:.2f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=ks, y=fit, name=f"Geometric rule (×{ratio:.2f} per bank)", mode="lines+markers",
                                 line=dict(color=INK, width=2, dash="dash"), marker=dict(size=8),
                                 hovertemplate="rule: %{y:.2f}%<extra></extra>"))
        tk = sorted(int(k) for k in tr)
        fig.add_trace(go.Scatter(x=tk, y=[tr[str(k)][1] / tn * 100 for k in tk], name=tsel + (" (6 = 6+)" if 6 in tk else ""),
                                 mode="markers", marker=dict(size=11, color=COLOR[t], line=dict(color="#fff", width=2)),
                                 hovertemplate=tsel + ": %{y:.1f}%<extra></extra>"))
        style(fig, "Each extra bank is about 0.37× as likely", "banks in the route", "share of payments (%, log scale)",
              h=400, xgrid=False)
        fig.update_yaxes(type="log")
        show(fig, "p9_pc")
    with c4:
        nb = D["N_by_pc"]
        ks = sorted(int(k) for k in nb)
        obs = [nb[str(k)][0] / nb[str(k)][1] * 100 for k in ks]
        cis = [wilson(nb[str(k)][0], nb[str(k)][1]) for k in ks]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=ks, y=obs, name="Normal payments: flagged N", marker=dict(color=COLOR["NORMAL"]),
                             error_y=dict(type="data", array=[(c[2] - c[0]) * 100 for c in cis],
                                          arrayminus=[(c[0] - c[1]) * 100 for c in cis], color=INK2, thickness=1.5, width=5),
                             customdata=[[nb[str(k)][0], nb[str(k)][1]] for k in ks],
                             hovertemplate="%{x} banks: %{y:.1f}% (%{customdata[0]} of %{customdata[1]})<extra></extra>"))
        fig.add_trace(go.Scatter(x=ks, y=[(1 - (1 - hid) ** (k - 1)) * 100 for k in ks],
                                 name=f"Rule: each hop hidden with p = {pct(hid)}", mode="lines+markers",
                                 line=dict(color=INK, width=2, dash="dash"), marker=dict(size=8),
                                 hovertemplate="rule: %{y:.1f}%<extra></extra>"))
        style(fig, "Longer routes are more often broken", "banks in the route (8 = 8+)", "share with a hidden hop (%)",
              h=400, xgrid=False)
        fig.update_yaxes(ticksuffix="%")
        show(fig, "p9_n")
    notes("- Real payments often clear instantly when banks are online and wait for a cut-off or manual check "
          "otherwise; a two-speed process is a simple way to model that.\n- Hidden hops resemble intermediaries that "
          "do not report status.",
          f"- Rejected: scams are slow in themselves (excess over geography: Romance "
          f"{pct(G['ROMANCE_SCAM']['observed'] - G['ROMANCE_SCAM']['expected'])} p = {fmt_p(G['ROMANCE_SCAM']['p'])}, CEO "
          f"{pct(G['CEO_SCAM']['observed'] - G['CEO_SCAM']['expected'])} p = {fmt_p(G['CEO_SCAM']['p'])}; small and unexplained).\n"
          "- Rejected: duration depends on hour or weekday (flat).\n- Rejected: an account pair keeps its duration "
          "(0 of 19,793 pairs with 3+ payments repeat one duration).\n- Not resolved: what sets a bank's slow share.")


# ----------------------------------------------------------------------------------------
# Dashboard 10 - Operational noise vs true fraud
# ----------------------------------------------------------------------------------------
MATRIX_COLS = ["Who sends", "Payee", "Amount", "Timing", "Route", "Batching"]
MATRIX = {
    "ROMANCE_SCAM": [(2, "Consumer only"), (2, "New mule (shared pool)"), (2, "×1.5 per step"),
                     (2, "Burst, ~5 min apart"), (2, "Exact bank end; rarely Covered; copied"), (2, "2–8 payments")],
    "CEO_SCAM": [(2, "Business only"), (2, "New mule (shared pool)"), (2, "18% at ≈1,200× median"),
                 (-1, "Not tested"), (2, "Exact bank end; rarely Covered"), (0, "Single payment")],
    "ACCOUNT_REPLACEMENT_SCAM": [(0, "As normal"), (2, "New mule (shared pool)"), (0, "As victim's normal"),
                                 (0, "As victim's normal"), (2, "Exact bank end; rarely Covered"), (0, "Single payment")],
    "FAT_FINGER_MISTAKE": [(0, "As normal"), (-1, "Not tested"), (2, "×10^k slip, k ∈ {−2,1,2,3,4}"),
                           (-1, "Not tested"), (0, "As normal"), (0, "Single payment")],
    "DUPLICATE_PAYMENT": [(0, "As normal"), (1, "Same payee repeated"), (1, "Identical amount copied"),
                          (2, "2–5 copies in 2 hours"), (1, "Identical route copied"), (2, "2–5 copies")],
    "CUSTOMER_RECALL": [(0, "As normal"), (0, "As normal"), (0, "As normal"), (0, "As normal"), (0, "As normal"),
                        (0, "Single payment")],
}
CLASS = {"ROMANCE_SCAM": "Fraud", "CEO_SCAM": "Fraud", "ACCOUNT_REPLACEMENT_SCAM": "Fraud",
         "FAT_FINGER_MISTAKE": "Operational error", "DUPLICATE_PAYMENT": "Operational error",
         "CUSTOMER_RECALL": "No signal (random label)"}
RECALL_AUC = [("Processing columns", "Logistic regression", 0.495), ("Processing columns", "Decision tree", 0.497),
              ("Processing columns", "Gradient boosting", 0.477), ("Text fields", "Words", 0.490),
              ("Text fields", "Character patterns", 0.490), ("Text fields", "Token sequences", 0.504),
              ("Text fields", "Token values", 0.493), ("Text fields", "All text combined", 0.490)]
RECALL_SHUFFLED = {"Processing columns": (0.447, 0.547), "Text fields": (0.481, 0.537)}


def page10(D):
    F = D["ff"]
    U = D["dup"]
    w = {int(k): v for k, v in F["weights"].items()}
    header(
        10, "Operational noise vs true fraud",
        "Three of six labels are not fraud: fat-finger and duplicate errors follow exact mechanical rules, and "
        "Customer Recall cannot be told apart from normal payments (classifier score 0.48–0.50 = coin flip)",
        "a coin-flip classifier scores <b>0.500</b>; normal payments define 'as normal' in the matrix below.",
        "Fraud leaves a trail: a new payee, a special amount pattern, an unusual route. Operational errors leave a "
        "mechanical fingerprint instead: a misplaced decimal point (×10, ×100, ÷100 ...) or a payment accidentally "
        "sent 2–5 times within two hours. Customer Recall looks exactly like an ordinary payment on every one of "
        "17 columns we tested, so it is best treated as a random label, not something to detect.",
        [dict(name="Fat finger", **{"if": "FAT_FINGER_MISTAKE",
                                    "then": "amount = intended × 10<sup>k</sup>, k ∈ {−2, +1, +2, +3, +4} ≈ 20% each "
                                            "(80% inflated, 20% deflated ÷100); nothing else changes",
                                    "for": f"all 1,940 records (k shares measured on {F['n']:,} with an account median)"}),
         dict(name="Duplicate", **{"if": "DUPLICATE_PAYMENT",
                                   "then": "2–5 identical copies (same payee, amount, route), each timestamp = window start "
                                           "+ Uniform(0, 7,200 s); every copy is labelled",
                                   "for": f"{U['clusters']} clusters, {U['rows']} rows"}),
         dict(name="Customer recall", **{"if": "CUSTOMER_RECALL",
                                         "then": "no field differs from an ordinary payment of the same account",
                                         "for": "317 records; 17 of 19 columns tested, ~1,500 tests"})])
    tabs = st.tabs(["Fraud vs error vs noise matrix", "Fat finger", "Duplicates", "Customer recall"])
    with tabs[0]:
        f1, _ = filter_row(2)
        show_cls = f1.multiselect("Show classes", ["Fraud", "Operational error", "No signal (random label)"],
                                  default=["Fraud", "Operational error", "No signal (random label)"], key="p10_cls")
        ts = [t for t in TYPES if CLASS[t] in show_cls] or TYPES
        lvl_bg = {-1: "#ffffff", 0: "#efede8", 1: "#cde2fb", 2: "#184f95"}
        lvl_fg = {-1: MUTED, 0: INK, 1: INK, 2: "#ffffff"}
        lvl_name = {-1: "Not tested", 0: "Same as normal", 1: "Copied / partial", 2: "Distinct rule"}
        cell = "padding:.55rem .6rem;border:2px solid #ffffff;border-radius:8px;font-size:.88rem;"
        head = "".join(f"<th style='padding:.4rem .6rem;text-align:left;color:{INK};font-size:.9rem'>{c}</th>"
                       for c in MATRIX_COLS)
        body = ""
        for t in ts:
            body += (f"<tr><td style='{cell}background:#ffffff;color:{INK}'><b>{LABEL[t]}</b><br>"
                     f"<span style='color:{INK2};font-size:.8rem'>{CLASS[t]}</span></td>")
            for j, (lv, txt) in enumerate(MATRIX[t]):
                body += (f"<td title='{MATRIX_COLS[j]}: {lvl_name[lv]}' style='{cell}background:{lvl_bg[lv]};"
                         f"color:{lvl_fg[lv]}'>{txt}</td>")
            body += "</tr>"
        legend = "".join(f"<span class='tag' style='background:{lvl_bg[lv]};color:{lvl_fg[lv]};border:1px solid #d9d7d0'>"
                         f"{lvl_name[lv]}</span>" for lv in [2, 1, 0, -1])
        st.markdown(f"<div class='card'><h4>Each label's fingerprint across six behaviours</h4>"
                    f"<table style='border-collapse:separate;width:100%'><tr><th></th>{head}</tr>{body}</table>"
                    f"<div style='margin-top:.6rem'>{legend}</div></div>", unsafe_allow_html=True)
        st.write("")
        table(pd.DataFrame([{"Label": LABEL[t], "Class": CLASS[t], **{c: f"{MATRIX[t][j][1]} ({lvl_name[MATRIX[t][j][0]]})"
                                                                      for j, c in enumerate(MATRIX_COLS)}} for t in ts]))
    with tabs[1]:
        f1, _ = filter_row(2)
        comp = f1.checkbox("Show the five fitted ×10^k components", value=True, key="p10_comp")
        lr = np.array(F["lr"])
        c1, c2 = st.columns([1.3, 1])
        with c1:
            edges = np.arange(-5, 7.01, 0.25)
            h, _ = np.histogram(lr.clip(-4.99, 6.99), edges)
            mids = (edges[:-1] + edges[1:]) / 2
            fig = go.Figure(go.Bar(x=mids, y=h, name="Fat-finger amounts", marker=dict(color=COLOR["FAT_FINGER_MISTAKE"]),
                                   hovertemplate="%{y} records<extra></extra>"))
            xx = np.linspace(-5, 7, 300)
            sd = F["sd"]
            dens = lambda m: np.exp(-0.5 * ((xx - m) / sd) ** 2) / (sd * math.sqrt(2 * math.pi)) * len(lr) * 0.25
            fig.add_trace(go.Scatter(x=xx, y=dens(0), name="Unchanged amount (no slip)", mode="lines",
                                     line=dict(color="#6b6964", width=2), hoverinfo="skip"))
            if comp:
                tot = np.zeros_like(xx)
                for k in sorted(w):
                    yk = w[k] * dens(k + F["mu"])
                    tot += yk
                    fig.add_trace(go.Scatter(x=xx, y=yk, mode="lines", line=dict(color=INK, width=1), opacity=0.5,
                                             showlegend=False, hoverinfo="skip"))
                    fig.add_annotation(x=k + F["mu"], y=float(yk.max()), text=f"×10<sup>{k}</sup>", showarrow=False,
                                       yshift=10, font=dict(color=INK, size=12))
                fig.add_trace(go.Scatter(x=xx, y=tot, name="Rule: ×10^k mixture", mode="lines",
                                         line=dict(color=INK, width=2, dash="dash"), hoverinfo="skip"))
            style(fig, f"Amounts cluster around ×10, ×100, ×1,000, ×10,000 and ÷100 (never ×1)",
                  "fat-finger amount ÷ account's median normal payment", "records", h=430, xgrid=False)
            fig.update_xaxes(**LOG_TICKS)
            fig.update_layout(bargap=0.05)
            show(fig, "p10_ff")
            table(pd.DataFrame({"Decimal slip": [("÷100" if k == -2 else f"×{10 ** k:,}") for k in sorted(w)],
                                "Share of records": [pct(w[k]) for k in sorted(w)]}))
        with c2:
            ks_ = sorted(w)
            fig = go.Figure(go.Bar(x=[("÷100" if k == -2 else f"×{10 ** k:,}") for k in ks_], y=[w[k] * 100 for k in ks_],
                                   marker=dict(color=COLOR["FAT_FINGER_MISTAKE"]), text=[pct(w[k]) for k in ks_],
                                   textposition="outside", textfont=dict(color=INK),
                                   hovertemplate="%{x}: %{y:.1f}% of fat-finger records<extra></extra>"))
            fig.add_hline(y=20, line=dict(color="#6b6964", width=2), annotation_text="Equal shares: 20%",
                          annotation_position="top left", annotation_font=dict(color=INK, size=12))
            style(fig, f"Five slips, about 20% each (equal shares not rejected, p = {F['lrt_p']:.2f})",
                  "decimal slip", "share of records (%)", h=430, legend=False, xgrid=False)
            fig.update_yaxes(range=[0, 30], ticksuffix="%")
            show(fig, "p10_k")
        note(f"Digit proof: all {F['usd_up_zero_cents']} of {F['usd_up']} inflated USD records end in a zero cent digit "
             f"(other currencies: {pct(F['nonusd_zero_cent_share'])}), as a shifted decimal point requires.")
    with tabs[2]:
        f1, _ = filter_row(2)
        model = f1.radio("Compare with", ["Copies scattered in a 2-hour window (accepted)",
                                          "Original first, copies follow within 2 hours (rejected)"], key="p10_dup")
        span = pd.DataFrame({"n": U["n"], "span": U["span"]})
        sz = sorted(span.n.unique())
        obs = span.groupby("n").span.mean()
        se = span.groupby("n").span.std() / np.sqrt(span.groupby("n").size())
        pred = {k: 7200 * (k - 1) / (k + 1) for k in sz} if model.endswith("(accepted)") else {k: 7200 * (k - 1) / k for k in sz}
        c1, c2 = st.columns(2)
        with c1:
            sizes = {int(k): v for k, v in U["sizes"].items()}
            fig = go.Figure(go.Bar(x=[str(k) for k in sorted(sizes)], y=[sizes[k] for k in sorted(sizes)],
                                   marker=dict(color=COLOR["DUPLICATE_PAYMENT"]), name="Clusters",
                                   hovertemplate="%{x} copies: %{y} clusters<extra></extra>"))
            fig.add_hline(y=U["clusters"] / 4, line=dict(color="#6b6964", width=2),
                          annotation_text=f"Equal chance 2–5: {U['clusters'] / 4:.0f}", annotation_position="top left",
                          annotation_font=dict(color=INK, size=12))
            style(fig, f"2–5 copies, roughly equally likely (p = {U['size_p_uniform']:.2f})", "copies in the cluster",
                  "clusters", h=400, legend=False, xgrid=False)
            show(fig, "p10_dupsize")
        with c2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=[str(k) for k in sz], y=[obs[k] / 60 for k in sz], name="Observed (mean ± 2 SE)",
                                 marker=dict(color=COLOR["DUPLICATE_PAYMENT"]),
                                 error_y=dict(type="data", array=[2 * se[k] / 60 for k in sz], color=INK2, thickness=1.5, width=6),
                                 hovertemplate="%{x} copies: %{y:.0f} min from first to last<extra></extra>"))
            fig.add_trace(go.Scatter(x=[str(k) for k in sz], y=[pred[k] / 60 for k in sz], name=model.split(" (")[0],
                                     mode="lines+markers", line=dict(color=INK, width=2, dash="dash"), marker=dict(size=9),
                                     hovertemplate="model: %{y:.0f} min<extra></extra>"))
            p = U["ks_modelA"] if model.endswith("(accepted)") else U["ks_modelB"]
            style(fig, f"Time from first to last copy (model fit p = {fmt_p(p)})", "copies in the cluster",
                  "minutes from first to last copy", h=400, xgrid=False)
            fig.update_yaxes(range=[0, 120])
            show(fig, "p10_dupspan")
        note(f"All {U['clusters']} clusters fit inside 2 hours (longest {U['max_span']:,} s); estimated window "
             f"{U['W_mle']:,} s (95% CI {U['W_ci'][0]:,}–{U['W_ci'][1]:,}). No normal payment with the same payee and amount "
             "exists, so there is no unlabelled original.")
        table(pd.DataFrame({"Copies": [str(k) for k in sz], "Clusters": [int((span.n == k).sum()) for k in sz],
                            "Mean minutes first→last": [round(obs[k] / 60, 1) for k in sz],
                            "Scattered-window model": [round(7200 * (k - 1) / (k + 1) / 60, 1) for k in sz],
                            "Original-first model": [round(7200 * (k - 1) / k / 60, 1) for k in sz]}))
    with tabs[3]:
        fig = go.Figure()
        for grp, (lo, hi) in RECALL_SHUFFLED.items():
            names = [m for g, m, _ in RECALL_AUC if g == grp]
            fig.add_trace(go.Scatter(x=[lo, hi, hi, lo, lo], y=[names[0], names[0], names[-1], names[-1], names[0]],
                                     fill="toself", fillcolor="rgba(201,199,191,0.35)", line=dict(width=0),
                                     name="Range with shuffled labels (pure chance)" if grp == "Processing columns" else None,
                                     showlegend=grp == "Processing columns", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[a for _, _, a in RECALL_AUC], y=[m for _, m, _ in RECALL_AUC], mode="markers",
                                 name="Classifier score (AUC)", marker=dict(size=13, color=COLOR["CUSTOMER_RECALL"],
                                                                           line=dict(color="#fff", width=2)),
                                 customdata=[[g] for g, _, _ in RECALL_AUC],
                                 hovertemplate="%{customdata[0]} · %{y}<br>AUC %{x:.3f}<extra></extra>"))
        fig.add_vline(x=0.5, line=dict(color="#6b6964", width=2), annotation_text="Coin flip: 0.500",
                      annotation_position="top", annotation_font=dict(color=INK, size=12))
        style(fig, "No model separates recalls from normal payments", "AUC (0.5 = coin flip, 1.0 = perfect)", None,
              h=420, ygrid=False)
        fig.update_xaxes(range=[0.40, 0.65])
        fig.update_yaxes(autorange="reversed")
        show(fig, "p10_auc")
        sig = D["signature"]["events"]
        rec = sig["CUSTOMER_RECALL"]; nor = sig["NORMAL"]
        comp = pd.DataFrame([{"Measure": METRICS[m][1], "Customer recall": pct(rec[k][0] / rec[k][1]),
                              "Normal payments": pct(nor[k][0] / nor[k][1]),
                              "p-value": fmt_p(binom_p(rec[k][0], rec[k][1], nor[k][0] / nor[k][1]))}
                             for m, (k, _) in METRICS.items() if k != "known_pair"])
        table(comp, "Recall vs normal on routing measures (from the 57,006-row sample)")
        note("Tested: amount, timing, payee, currency, routing type, duration, path, flags, party types and the "
             "sender/beneficiary text fields (17 of 19 columns). One borderline result (hidden hop 11.0% vs 7.5%, "
             "p = 0.018) does not survive correction for ~1,500 tests. Scores from the team's analysis log.")
    notes("- Fat finger: a decimal separator typed in the wrong place (cents read as units or the reverse; decimal "
          "comma vs thousands separator).\n- Duplicate: a back-office race condition or batch resubmission inside one "
          "working session.\n- Customer recall: a real recall is a cancellation request sent after the payment, so the "
          "original instruction looks normal; a generator that labels random payments fits all evidence.",
          "- Rejected for fat finger: multiples of the account median (ratios do not cluster at exact powers of ten "
          "because ordinary payments already vary ~10× around the median).\n- Rejected for duplicates: fixed delay; "
          "copy of an unlabelled original; original first with copies after (p ≈ 2×10⁻¹⁸).\n- Rejected for recall: "
          "negative duplicate, fixed time window, link to other anomalies, duration outliers, broken paths, text markers.\n"
          "- 'No detectable signature' is not proof of randomness: effects under ~4–5 points would be missed with 317 records.")


# ----------------------------------------------------------------------------------------
# App shell
# ----------------------------------------------------------------------------------------
PAGES = [("1 · Dataset scale & class imbalance", page1), ("2 · The shared mule pool", page2),
         ("3 · Party type locks", page3), ("4 · Geography & currency", page4),
         ("5 · Romance scam escalation", page5), ("6 · CEO scam payouts", page6),
         ("7 · Account replacement stealth", page7), ("8 · Routing & cover signature", page8),
         ("9 · Latency & path topology", page9), ("10 · Fraud vs errors vs noise", page10)]


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    D = load_data()
    with st.sidebar:
        st.markdown("<div class='sidebar-title'>SWIFT Payments<br>Reconstructed Business Rules</div>"
                    "<div class='sidebar-sub'>UMDAC Datathon 2026</div>", unsafe_allow_html=True)
        choice = st.radio("Dashboard", [p for p, _ in PAGES], index=0, key="nav")
        st.markdown("---")
        with st.expander("Glossary"):
            st.markdown(
                "- **B / C**: Business / Consumer party.\n- **Mule**: account that receives and moves scam money.\n"
                "- **BIC**: bank identifier; characters 5–6 give the country.\n- **Direct / Indirect / Covered**: two "
                "banks only / via intermediaries / via intermediaries using a cover payment between banks with a "
                "standing relationship.\n- **Flag N**: the route has a hidden hop ('...').\n- **95% CI**: range that "
                "contains the true share with 95% confidence.\n- **p-value**: chance of a gap this large if there were "
                "no real difference; below 0.05 is usually called significant.\n- **AUC**: how well a model separates "
                "two groups; 0.5 is a coin flip.")
        with st.expander("How to read every page"):
            st.markdown("1. **Title** = the finding, with a number.\n2. **Baseline** = what normal payments do.\n"
                        "3. **Plain English** = why it matters.\n4. **IF / THEN / FOR** = the rule, precise enough to "
                        "reproduce.\n5. Grey in charts = normal payments; colour = the anomaly type.\n6. Interpretation "
                        "and rejected hypotheses are kept in separate boxes at the bottom.")
        st.caption("Data: team extract files (all 7,006 anomalies; 50,000-row normal sample; account-level files). "
                   "Built with Python, pandas, Plotly and Streamlit.")
    dict(PAGES)[choice](D)

# ----------------------------------------------------------------------------------------
# Embedded data (gzip + base64 JSON) produced by build_dashboard_data.py from the extract files
# ----------------------------------------------------------------------------------------
_DATA = """
H4sIALE1/WoC/+y92a4cR5Yt+CsCX243bijgNpsl0A8kRVFM8lBMDsqSLhIEJbEqiZRIgaKyKm9Br93vjQb6g/pP7pf0XmuZDxHHYzgUqSFL54SFx+DhbrZt
z4PZf157/erfv7/2h/+89vDTi+v3b956+ujm9Ytrf/Cx5M21m7c+7e9bTJtr12/e/PTJ/cdPH956cO/6zVsXt+y1vs6xba59fP3x04/v3L996+HTizuPHl+/
e+vaH1yLw+baR08e3Ltz8/rjW08fXP8cP7NfFPvFzSePHn96Yec/vHXz+r171/4QXNlcu//pw4vr9iYN9vfj5trzvz9/+Walj/b9e+2iq2m9i9anFy///uz1
i2fs1//4z2vfv/rh9VfPr/3h2sWzFy8/+P7Zt9998/yD/+3ZN998UDbDkD949vLVt8++efH8+w/++wdpsI+GD16+em0f/e/XNn0GUrETN9ceXH/4+M7NOw+u
W8c5lA/+jw/+/uL7F1/aBb989vJv85kff/Ps3z64/8H/+r/+nw/+23a7/W8f2J2/e/bmr9MJH714/fyrNzzh+X88++rNN//4wO9c48fNoucPn39l/f3w2Vdf
vfrh5ZsP/vUFRhB93cQWP0AX567ap/bhWX0dTz3c2fGMY73VOT/+ZXPtu2ev3/wDqDCi7Ygs/3mN/eZnN/7X//l/3zQcrsNgc453N2w2nYvO5lPfleL7mxuY
Ut9sTl92lLO7PP379081Qdf+8PKHb77ZXHv1+ms7c9iWGjbXvnz+8ibfuGhA3EPLlZ4MUy+GqQeuurkHOSd1QHS3c/9hO8y3HxY3Dy56l2Oprg05/LikhZU+
ZHS898JnP/VjmDoxqAuko50euG1srpXkiq/JHu75hymPfXI7ffLeTgvT84/HKHKlk6HMoHKhzsAayjxbUf0kQe9BKlUfQkm1GHSjS345b75En6sbYik51SUc
Yyu5Vuty83nA1dfYxEpv3dDq1N0IsPXu+pan7rrBqb/iM3sd9jlFH5LN5ZBcDhjm1OOWQh6qYUT01vEl1tWUchncEIbmS/1xlXutQbfNKEDgjNB1Yequ770l
f97Hw6HkUL2PqcYh+5Dz3Ns62FCGlopvg019XnQ3Ju9Cis1mxuALnLjEVNeAu8DXHKa+YtLHrnp1lUJjr6sl5owZdTUn711cgLXkwSfrfGphSK3tEFTNzrVa
QnVlCD/uyJ7fLKMJOc7IGPJ0/3PZjK+/s5bfWcsJ1uKgcIzdnak1zCjQEY9K1V5P41Bb8z4lHw3IJaQlW0lx+VjC1vBgfvjfEFv5sesxT1+8/Pr5d0+/Iwxi
CC7F0GorA0jgX//j6bfP3rx+8R/o/P989fI5jkN/Sjb1m2vOOrm55klogc+Rz0kE5/rJni+9caJjZ/t+9rC4bjP9YvXksHPysLisr2H/5HjwZJ3ZBj+dm06c
q6tG08Ht5C8N+M9fL+FifKGPNmXHH3vMbACJ8PfhEnR0J2NbRT9wxqT1C1/4E8yy/cZdgpF6ZwQTeX5qOj9rNPk4mFJKPNtQnqeToZ2CVGnqv3GHq8HqR+LT
v754MyPTsG2tVaN+47qmQUafZoAa3dUQTKts2RA6kR2+fPrVq5dvXrz84dUP0Mizw3C/fP3qb89fPgW11CFM73kjcm8zKZ5CVddHKTewr/HDyQxB5778x9M3
//ju+a6o5a/U0yiSeP4MTGQbYg0en2D8W+PhKa7Ix7kfi5/GWqcfmtKyJ9ymO9ZmkJued69gXN0UmvF5eTlnCvniOZyQUvPdYmrOdK5kMA9h924mCrKJPOM6
NhWYpulug7Hp6nIeTzkoX1YBYYhejY81wyoTaTHM4DRGlENzJflUCi+7KgXWr7rDr4c8X3WXYbu4zrHXL1rr4Hx21cRfWnTU9C7rqakGoRWznKiy/fXVt8+f
fvXVP3Yx6W8QoxlY9HL2LOzjC06CmqBT9jDDvqwkBOoxJyb2b+AHcVQmDs6LneYK5rsL8UOQxnlgaBKg64D7G5hvHEUXIPHy1UsAA19+/9dnr58LZBmEc+vJ
Q0qdYDgXodqYtDfdZXPtyaOPqDw4iGLDgGB0XptU0ae62rA1aPtmIs2sgYpZsXsZwJ9+K2E1A73fxa7jpytDqt6+8YAIbCLRhvLJx3qDfj26zZOGkCGQ73+u
N/bFJ3f1hUNf/vhAXzgYy9ef9G+AGDev9zcurMzvnfsP1YU6XdxB/eldG/C695mv73z0cOrA/dv3p9cP7upzDx3t4b3OSez1R4/12s65+Bed7/bV5xEoAyys
ESgJXGSEBJndCKMCNBrBIq9cB4tpwjNcfFjCxa786Lr6SDE2geWk3jxNWZp7Bz6zmLS8mDQi0zxPi64aZ5rnxi/6Vhe9dsHucvfhn8c3Bwll7JaprDPQsm9z
T8oO0OqyJ9Ut+5gW3QJspr7UvOzlEpfaIbocu2XsbO5WhXUx9SSVBbTiEquBhVMf8eb6rY9mOI492ekidIs79x6Nb9YZQe8UWOUCVsMCVtUvOgjEnfDLzTc2
FFh01i1xDdbPg+s3OtnVRZ9Mnv5IXQH818Fugd5gOvhrc34ag0IvXpsv9OVXz5/+2/NX6O7fX3z15sW3T7968/ofolH2txGvRK1kHupfBfFNdHjnowV5Ti9v
LIjzowU9ThN763EHoL28Pb18dF0vaQNS4785dUq3d2YvAYgiUk9GpnkFKX90i68TiO/jh/01WZp6Bsy992SG5sd3OjDt8xu3ZsDe6TwEWPTJ3Zm4BQ0bi71+
cn0azB8fdFZol7x/r4/GhnPnor8G8o9Dc8D9Tmx2/r07/bUB4tHINzfX/tRPh4PyQX8Ne+N6h5tdXP0dYOdcH18HkHJ/DYALc4zJT7AdQGIPn/TX1oGL/hpT
fKGrk/F+dLe/tnNufNJfG+xvPJpf3+3XBzu6c6+/xmD75zCiHvTPIRoei8sMpMF+fcrxEQG/+scvKiMmnFM/JkacD3G81hYcr/olNwkLYvVLkQHknKUnCOv6
Jx1P4kKUhiX7w2j+NEoTSIKR9IfaZqY1QK0eWTkn+uLzjg1gN6M4GiDBLjr8Boxt5B19UvvVIH4+utunCSzm/hfjN6CXT8Y3CQh1YznL/RuQ241HizePH3bE
oH/i3oP+xl5/0W8DYfTg3v35zb/c7L8PwOFb42mYxT/334OMrj/sIwDcO/7YG8PFi0/H06CM9CuDcXwxgoPs/cnH/Y1d+e44APkhnn75w+vv4cGQQvr9c3MZ
vJ740qxqdQ5lVsTEocyamDkUgDtyJbCBkVuhZyOHajOXCTHOnIiuqM6h2szFgIsjg5p5D04YeRJIfORDQIKR95RV3eyX5vsTUNwMK7x8/HAWDEtFbhQKdQZ5
zXUGOVBjBDMY0wj+NEGcsqJDmQ66kceDfEbQwr0wQjyGCbgegxtnBa9H7twWc7EQA+2E4tdHU6n5fDIrd+NoAKpxBGWBP3XqdcQpo4SbhVpIMyrx9Yhu0HJ6
9+hn6r3m644pfhIpxKURr/JhRXGkA7+gA2mG6i+41EQHeRpHjHXqWHTzmAK8QmPn/Tw8+vtHkmhzf+NMCZyUcRJdnicOYnWclnJIs+zj2Ok76LmPSa873NGx
PqYYZo2Dr7tcp37ZxyrAP55fj4PC6+uLc8aBlHmeymIYeTm8dVV0nA03603UN8cZyHVBIjPppGGmkRj9YjYW9BLnvnTttNNO3NWnRtqhbnWx1Fnn1yNjShXq
61ev/m489rtnL17Tc/xyfGnukIxvX37/4vs3FheaP1mcX3G9v9oJlhgAd+5m2Pu3EyyQjZ/AD2a/1UQb/ZvbxXnzmnjygtfPXn796tun/VLOQgkbU/LixqK+
cRNsJmD/OTdY27hN2gx/gXx48W8vn7354fXz9Rg5jPhvXyBngYFm+kH+Qif2+HEy9W782Pr29NsfvnnzAl9AvzMiLM6+sH49//7Ni6/sc+tWm35At8z/SKGU
6aO/vXz17wIgLxLjfPl/tZyA+7gEXIfjh18zDQCf2jjHK6+Ii3kkwwZj2RnF9NFyBGFj7s7dzhsA+4nquXHp/n6n26aljKf1LgP5+0dThx3SGPjhnpxYdtWc
LTs9NWTRR8uelk1IYbenZkjoPHXUj1fa6afxqn5S72Yerz51MjVd6IQwWHbZjNadLofYP9oFrh/ybpfH09Rjsyv0dheyeTyp99jQQx9MPYZjEh8d5PhzXxHK
gxdtp7vmIxw/XHbY5EDObR/IdTy1g9korX+w023zl08n9o7DnuofzRiBmAI/PMTl575b1MSsyF1Ap/7RDqANRfdp0HiQTlSvTSvX213aM1TrZ42wHn82w3rQ
OevMfAHotDGf3i6YY/9o2Vk7z4VhD8iln6jOmozS293O2kz0s0YmMd5yhm7VlQ6F6f85eV3aG8T4yQ7YDen2um4zkRbddqG/3emyzWHa6W0cT5t7OrCfv7O4
31nclVlcBU3tdLz1T3Z6vSlxr8+5n9Z7nPrbXcTw40lTb/sHc1+hKNX0W+Nu0Oq+emb+qVfffvni5fOv0dmR3xmnUkqE+jmwg0hB2lzrvSyWbrroYEAY+7uv
nn5NrfI/ETIW82HE2xWYOxEJl8bWGGmm3ZcRqTUVu+COdqwI2m+uNcSxLfhsI7WzndIGHGLodggKmf/1xddfW/deP3vzXKq9RyjTsMssTVgC9xH4/e6r3heD
qfWAPfoLu2S4bfo8O/YX9ux/ZGOg6N5f2D+DsM2zdfIv7KXho7GsgmkvZAVGs3hTKdw2hq2Y/a9/eP3UQEna3/qNOdmsRWumRG+zNUva3ZrivjX8tECk2xre
2HkWhrRmvbHznJ3n7Dxn5zk7z9t53s7zdp6387yd5+08b+d5O8/bed7OC3ZesPOCnRfsvGDnBTsv2HnBzgt2XrDzop0X7by4pcpqHf5rn7FZwHnyLgcmZGaF
pcBs4OvzZhlaupihpjmrnQWM7VOLTgTLy9t4y16yJzvLgtp+kwG7hkvYz8yrBcvUW+DNrJBNAg+06G0t4MNlAweSRQg3zfiZI8OxkKG9qrA/zF1Rjd4Q7fWm
QpiRYlDZDH0KR8PH7GG7oeFaA8uBAp03Fr3dWPrUxtJ/7DoWL7BkJRNpFdSMG25MmbHrAwM2CElhKMhYCg2/hRSxkRvth4REZZNNDV03kYzEZYcb4rfeXm8K
OtGRaOwSLKcAA8rcBTZgMy+R2QXtPtiHCBx5GzP6hYcJCpsRbwxqY14uByDb0RtCOusGDEk2DM2gCF+rz5FXdJC/hgEGp96L9N8X3Rj/DYTsjOGJQckuC15H
K89GZKCD3WfDxYQb3Mykt0QQ652B24ybptNJD149snmxwA9/bucD3KOduK9i+EVvDGutJxVziOttwEkNCTaZAMMZ1st+jscJGU8mr726CETakGkbzL0uuocK
I/Q9L1h5Mfz7PieOnzt+lnlr8G7HDsHWxf3Gy+xN6TD1UkffLzv0S47N9++i/es2qd98ODZFa7eZcWnsve9gwi08Rzledk9xWsLdFAUgozEOzDqxION1JHAz
x1Hsol5YUgkQ4CCh3oAYdioIpOKXBqu8gFHYQXs9R81fn2OCFcAYATfCH6gAyh6nuXSUyP3s9UkYFugiMMeN7zM8dCglfuP7d05zFQm4k7MwwltQXkwdgMhP
QwdanFCg9+mUbrhLDWVDrAMXaoCt59yAzgpBpImOABEmJYzABIfjmQ1ki3kFI+Bph2li6NMMdEx89tN0AWKZ34GOjQl1qsj8ZMKyA3MxQw1XdqvY6/v943TF
dM5UzHTlF5cdSXjsehinudPeRBDrSu84CbxA0TgtwGLcNJPhUZUFSCGloGcBfxIB5Dg3Ejb2uf3KOC90LOuCiafER9hQF+7I5laJJGhKecUASUM6i7w60bfw
jmSAlLmckcC3ZIAgxQG0ksg0D8+P79zQzBnckQRH8hsmIiwkl8a7oj+4bCSy+1NTNM9tFgP1E0/UXGTeVhMvokkLKjyk249TNM+80y1859pl6pxOMfgR9yRi
HG+ZebNhwXjDKidxG0FRHGOfB4+AGPHYz/A+SRPj79c+HSYEXnL24WpCwl0SGG6HUoZdyjlgoSyhra5AGsABnDrL8U6S0U0AA1Ay2Ujpz03CPOzccB3mgmKR
uJl/spSdubPf1AXdsGS1R4A+XidPbHye5lkBCBOc/NWAHhcXW0oHt8frhiXQYWh98+rfZ4NkV9U2NdK4ztI2SZ4cfbZNPJKeFsaJQ4BxYZ1ki5y1oRxSwJAd
Yw6WfvUGeRz7lY15xemq4DXjFTd5TaUIxqNMFR5tKOr3vl/KFIRS+6WgOLh+KXDTcwSjR19i6NcmI25jL03uprGXMNNHqwyKynFOHxPYBiHJLlcAcuxyheY3
XhjafesXNm0khKPsCSaFG69q08WOR5n03vVLGrMae7pxR6gPtkAt/WIGBvoXxouNMAVznq4WiVbfvvr6ueWyfm0Fo3RS/uuzyfr2aauc7cAXsL1h++FKKeOF
XaeYddmRs//KZrT231nYwfdfWpzN9d+arQSzEr92Ldmn6EZPuBqvs4+Cr778/vnrv8PBwIIj86r+x3fmjNAHOcPqS5bcZibbgMDsdz25w/IujTTMVrSc0FDD
gezZ5cUteFlycdPz7p2S2W8RCSCxWsUCEoj7nVCx0qyKwVLVc2NA/6xU3J07F6uW9PbbWJFznffvbBRutTyGMFbqgwjrdz0Ia+ZmRH5EGyrzjU6k9S5vGXsp
jVmqCXnVafeekbnrA4YaG/OpVA6CblpnbHatVgdJEScyhHduWayGZ36U/Tt6lun50hCjHkc5WKY3IpCWku9iH+PBXOOdu9kUJhtey9bbBNfTzt0snG79sVPs
0mFEm2Rp55bRnRKKA8EVx6zlzYLp7kLRUo5JSnJrHcfegGSTZS8M+JYUl2q2sgHDGDcilUVVUZjos927Vh/Owd6wzP235z3whmwKqZGPlfGEyGxlTagxYMMD
y5ew5PfsSnwL7LVOGm6issC8ZDaUtD9IwyQDKyvlSivjrRHMt6IHw+BqdDO0ciX8tUwgK05YlIvt3bQ4FDqYk8OKP5lZ9F3P0TBHjuFDtIR6qyFx5WoYvA9T
q3KwFAbLfzHOUMab2MelmR/KKCdHJiyfj7O7lQPl0qAsx8TiNwZP4wVuhKQ5VaxCzmpfbAot+c+dRFu7UCTa3j+FssyYW/ZhQFlOtfBSaoMhTxnptFUrvk3A
2opMgXMwdljwWjzv34lcwkCC0VY/8SBz+Rl0URhljMnn8hYYO+RdnE2X7mzJ0ibArDCOZXX9zlZa1wxpiuXTtGQlOPlKGGslNFammefilks3jcbFLScQ5YZl
ZEkosDFGkAyslqZUargSwg7W153H/j2tCtckjkX/mtVc1JH/1GxM0KqbIgQdM0fOxWCTxrtIfHmQRivRXLx2D2aCd7oEqM3zatl19jWT0U7gsGVsWo1W573P
mXr4dC6r3MdpJNblnpuUevoYeAZS9nj8E4IKytBD1g6y+sZ8uzEFD/T24BNU4FkW0Ec6Xv9Ux4svFN5Asl9VknFVnm9Rrh8WEHnAA1Kf7E6f3eLh0ec8PPyU
B6QNZmUEIkfxvg63eEByNUZwhwekByIJ8AsePrvPw0ef8nD7IQ9I/0TS0cc8ICcpKr0IyW6PGBV5/BEPSGbD4c88IGPPDhcX+vABDw/6D3QmEqSRnX2Thyf6
7hN9iKQlQOgWD3ce8nDzCx0+5eHizzw8/kQf3taHOtzVmXf1c6SII2u5v/uYQZyLz3T4iIcvLni4+VCHz3n45LG++zMPjz7Vu+s83Nbh4h4Pd3Tmdf384j4P
927w8EAXe6BT7l9X7GinauY25r8nqLJmGxgFMYrJix3TUAYNzAk9BzREYRxycYFpvuebAROBLLggsMX39FGzJ4gvUC6JeaVjXscVYCYx1QtNgIlAJddz4t0g
SOIIMDchbBOGVgGoCHGKJtkOdz+Z8LUIpbNmsKNtEt4hX/6hMPQRDx0LO8JhrqNQJQqwUTMxYy8wdEbGjmn3b03YFEQfSAm+L/S7x8MdIeMd4SsII2giOy4j
6VHY9ES4BeSYkfH25ztYKEQFYXghVc/ynJHxkZDxhpAY6O6U3zdjGrIJgWJCowuh5p+EcI9vC9OEd/c/nZFK1QdA1C+EkzrlX3Rp0DEu/WQFJz+6u0Tbz2/p
TJHJLaE0Cjp6lQSqgXSHi34x/eCPny7p6pGuCcJ3okd3qjrLRoake+B+7vnC4LbE+SAaAK6DJnznsn7ksk0473qtCo7AeTdy5ShaAI6TBpxwvifMdoqoQvgF
zxW6Xhe6Ahuy8C2LBJIQO2nG04Suna9ixmeGCtSKIq2Z2YI8gkgnCIuCqKyXqgQRWRDDCROaX4jLPrq1RN7bwtqPhcNfXJ+w3YscvUjOCzeQPqp3mKQZo0FB
Mwv95MmS597Z4cfXdXiiMy/07oGuef1jffjZEjc6Zu6y15vC6IefLrH9tijhujDshgjiyaMlKnek71h7X0h49/MZM3+cCk+efvnV014lOuXtNhbxjbntLi3S
wZP3izTePCfP26ITi6KnhoTvMXs3ga1O6btxztMN8FdNibo1zLnHFsJc1DJV1L/1uimHaPRc/YSr9Qxg06jyIqW3zMVNYVEL5VD6MSaXD3lOoIeluahYYonp
rbFkaVG/hAj6WIhl+p1fVC2FOBVODQiijxVVljkf5+Ip9KxXYAGEc8VUgji7uNnfuC7jWK1S53oEe4OyyltzhctYBQVfGlFb1S5RrFBv/Fw4FZALP1ZdMWF/
LGNBZ4DpKnCJwuLpzVhUFSBlx6qqgCtf/Km/8SLeXvkyVmSFuZiLy5g8HgtiWOJ6a1kQM9bDeCE93ySR2Pj67hfz67GOzLMO5M9jAU0WqemNfXFjfn2zD0KV
B58u3vTaEaueAE528ABz7/brsjSsl5Wo1u7248WbR31KmVh+95PFm7HqzKHY4N70xosB8Q0xZ/wN4NUhylyZBw8Xb25Mb7q05xv085PxG3L0DiWuJ/Pg8eLN
o39ZvLl3c/nNxfim6xN6A+r/ZPGm19DozYM+fSwDu/OnxZsn42mwej7qkB4Aw3ufjW8wuNuLN73AR29ujN0B8VxMFwDBfbF48/nYgyLJytcoKvj0YvHm8TgC
lhOO98xiqnzN2oBH4xsYELcXb/443h/McKx2Y33S/duLNzcfjm+AHrcWb8aStCF2A0JvvLj09Ob28s1YXwaWdfFw8fru/Prmnfn1kxEu1IM/X7z5l/EXKGK7
f33x5vo4MLLi64s3d28tv5muhk7eXry5e3/x5osRMlAUL+bXN0YMhCb++Pbizc3PFm+ejHcBpl+/vXhz88nyzXhl0MDFR8s3txZv7o8oDMK//efFmwd3F2+u
L7/56GLx5uLe+MbO+mJ+feP6/PrWrfn1nYfz64vPFq/H82lf3Fu8uXt78ebBON2j2TG9ufHHxZtP7i/ePFr+5vEXyzfTbyA7Plu8uX9n8WYsdeSbG58u3jy6
Mb7pytH05sb9xZvbHy9PGyFgEvez6/PrR5/Nr+9ezK9vW1fq8w+RXHj7Ynr5xfzyoz9OL2/+eXqJEtXx09vTS+hq/SUUw/Hc+RaPoazq5Y0vppfQ5vvLB/NL
ug/6z+5NL6/PJ9x+ML1EJWt/CW019p9dTC/vPZxeQrPrL6GX9ZefWSd9v+5H08sb86cf/3E+4U/zy8/nEy7mT69PLz97Mr28+GR6SdO393f+9OGt6eUf54vR
lYCXqJh+/vIlnT+wImCGmBYNuQ1tE8LgoX0A5eQh9PjUTWK4bR/iFXSIN6/ePIUmDjGA11hFLvTP8SMI/h9evnj1kkuL1cnvr4W+vnnx8qtX31g+7fM3z19b
SSz6Ys6C/+//NduJVvpgeZkWw5n+Nvr6IUSBLRriUcqPWkCLZSJfEjbX4/nryHDb6+c/fP/8qdVo4eqW25ohWBCxC8qW7cs9wYOG9Zuigm0DM09BxZXGS6PN
4/oyXE4Hr0NQpmzkwXuZf7rtYjWkY/YgUm4hVLAOVV9YKiqIqLWf1Cd1iX1ZZOYuvSsOII9a80ujg7CIcoAkmnvThSKHNl9u0OX2HYEYKsS/l6UadK2pa05X
/HEaMW2Pp0psfvrKMobxaY9FQsmxgIdF0SrQS189nda0iQHLoDaEBiKWQkXx3PPvnj9787SX9tuCvM+Rtv2cKdK6H8CrS3x/HMrmjrbl1qqfnt0Sdlhnz1Bt
uT7RPizsFHMqtzQ/1zGne65bObFw8d4yx5cWQv5xXlZjrPpj4filxMgxi8VPOZeR2WTzf+7/Ze+/8r9N/24YH258LLMJLz8iH2nxyOOjHHjUS4+280A24oC0
l5WHP/AI4yMuHunAI196lPFRF4+28kC+2PLh1h5+fIQDjzg+0tojrz3K+KiLR1t/mMN05+EOPPyBR9h9xMUjXXrkxaOsPSofrT+QCD493IGHv/QIlx5x95F2
H3nxKGuPykdbf1h69c7DjQ+/+wjjIx54pLVHvvQoa4966dFWHpbJv/9wlx5+8Qi7j8hHWnvkA4+y+6h8tPWHCTA83O7D8xHWHnH3kdYeee1Rxkc98Gj9YbUR
Ow934OHHR9h9xN1HuvTIa4/CRz3waOsPlmSsNrfX/EoLR1rca2mv5UUrR1o90drhRiGz39yR5ldaWLS419Ki5SOtrLS60trlxvR5NLfS/IEWTrR4oqVFy4tW
jrS619p6Q1ozm+vNH2lh0eJKS73lE60caLW3NjeUex1s7kjzixYOtHikpb2W91o50uqiteONFUdjc3vNH2hhpcVFSystn2jlSKtHWtttqFNic4vmT7Sw1+Je
SwdaPtDKSqu9td1WhkVze833FlZaPNHSiZZXWumtLlqbG4r0jjbXm1+0sGjxQEtHWl60cqLVA62tN9QsHm1ur/kDLey1eKSlEy2vtHKg1ROtXWq2Budec4vm
V1pYtHikpZWWD7SyaHWvtd3mhgPNLZrvLay0uGjpQMsHWtlrda+1ucF+nJo70Hxv4UCLB1o60fJeK4tWV1o73MJwpLlF8ystrLR4oqW9lg+0stfqorXDLQ4H
mls0f6CFEy3utbTX8l4rK60eaO1wM1mt5k40f6KFEy0eaOlEy4tWDrR6oLXdZrL8eHMHml9p4USLR1patLzXyolW91o73spwoLlF8wdaWLTYW+otH2hl0eqi
tfVWhyPNHWl+0UJv8URLB1peaaW3umjtcMNSBkebW2n+SAsrLfaWDrTcWznS6qK11Wa1NL253vxKCyst9pb2Wl5pZa/V3trl5obe3JHmD7SwaLG3dKTlvVZ6
q701NZR5HWzuRPMHWli0eKKlvZYXrfRWj7R2uME1fKm5RfNHWjjQ4omWDrS818qi1QOtqZlsvtzcovmVFg60uNdSb3nRSm+1t3a8YaGQ1eYWzfcWFi0eaOlE
y4tWFq2eaG23may83NxK8wda6C0uWlpp+UQrB1pdae1yK8OR5k40f6CFRYu9pd7yiVaOtHqgNTWTl3NzK83vtXCkxQMtHWj5RCsrrZ5obbeZDD3c3InmT7Rw
pMW9lhYtL1rZa3WlNTYLCh9orjd/oIUjLe61dKLlI62stHqktblhAYijzR1p/kQLJ1pctLTX8l4rR1rda229mayfm1s0v2iht3igpRMtr7Sy0uqitcvNZPh6
cweaX7Sw1+KBlhYtL1rZa3XR2vGGCDCbO9H8XgsHWlxpadHygVZ6q721uZnMvtxcb/5IC73FEy0tWl5pZa/V3trlZrL6cnOL5o+00Fs80NKi5ZVWjrS60trl
ZrJ5bq43v2jhQItHWjrS8l4re60eaW23mWyem1s0f6KF3uJeS3stH2jlSKuL1g43k7Nq7kTzKy0sWly0tGh5pZUDrZ5o7VizhTBsqfTvtFJhXzMmbcbX41oy
brEs2Po5+ixzEb/5N4ELvexew+/9Ynndte/L6l3jpf7kEz05fdX1M/dHsvv5qdFf7te5vTrW3/UzT8/Ocm29c6GyBvfD980r81IOYMPa+7WxHurT23xzuc/n
4tH6uWXvs2NXOx8rjtPSOd8fh8z5uHUIYpfHcYyGz53f45+fd4dDr86BTTkK4ePjjtMiae7E3J6agctUeh7GnDMvV8G3Y/R/Lp863KfjlH+8D4fkwOX+vy0/
PTzv5ej350P52JjWYXGcr5+WIudKkOPc+di1T8/e2pycy6uPwfztYPp2vPk0Tp3SpQ5Lqavgw3HO/NO4/jE8XddzztcND2sUhznIqSuer91dxsVD556nXeQD
+vE5muvbUHE+IklOy541GXWMl+5zh3P1pkMw2b/WVbSvdJbMOHXFc7lbuoJWdHgOjvGZdWl4Hh6t49D52ks5yj1OaSNXpeu3meHTHOvcXl7NMjjfEruKjluO
ameHeNwp+j6tkV5V276KNlfO1B/P05v9Wd6GY7NzDq0dt/YPz8Zxq++09I8nOfEpznqu7XeMt/sT1z1XK1q76tvIzPNw5PQMnLIW8lmjP+ypOBezVmjCHGx3
tQ7w9B/7f1j8e661fPmcuvevs+diwHDpf7co0Pf1+uf77V9xedf5up6rV18uL9zvyaF+Lq+6e+buVec77n6+3te1Ea797lCv5rvVE//zmeO11mbnMqzPh8o6
3C/f9/I9Dvd1HTv2z9+94rIfb/PNGlyugke75+5/q1X8D1/tEP6cj02HcWL/+8sluJchszaGY1hwGWK714t7/2sUcHx+D115H0uO3SEd/d+do+XoTkHiMN9a
ozrf/9fm9jgW7V/lXD5yeJ735+V8fFsb2WEKPj63632aR7j/6/1en+ZHl+XH8i5vw0/n3q33cf/7w3NwWp4dw8Xz+frhsRy7/mVOvs6dD1HaYQm61vNZi9i/
/ilevaaN7NPLVWG6P9LTlLbGV64yY2uwvAyfc/q+//+uuP4xPF3nFKdm7jxN7jgHOa6vnK/drePiPu6cR9drPTzF1df4y7lUfIgC93t/SPasyahDcvIyVq3z
08v3WofwYQmwLi1Pz+Rxmr58xeNaxeExnKMVrcP3sLRcu4ZfbF7nT+LRfOZpjnFMil2e5/Veznc6TLGnLIWrzvAhOByeq7VersvKcyXFaS5/fFTH+74m09Zt
k2OSbv2ab6dtn2OJnactH9c8D+sGx7wNh2fnPFo7rKsc6sdxn8Qadp6jN69x4jX74LT0PoTth3j7Id/L5fGfljv7V13nRudYAsdx5JQWfkzfXMPuq3sqlv9v
ZUGad+3Zt1hEy/bvxea8SDbfYlda22apbbEkRdmieG+buVWvrZ+ztVzQukWysW1fscVyMkPbWj6nbeZh+wdj/YuC86wUd2sZt7a21xZJ0GlrqbG235MlsdqK
iHF8wjuHF4E7E9tKM1ssyVHxobftg1HazM2EUQi2xe68toVw2WIphLpFwV/EL71tRGwr7NhWw1hmZZv4K5RAsbPO8/xhy511tyhDTlsUY9kYsdTBFkUe1g2k
WG5R5Ii9J/ArJK8HDsltuVjDFmWx7KFdDNslY9kRnGCbGtts204ygJlxuC3XAdui6sSW2kMd09YyFLPtrYxFh7ZYSCfjCmmL5XC2qOAfeLstFmmwi/PnXOgC
Wy1nDDVhZxRb1AfXs62vrCvFLmJvbDueLXdkHCqHbvvmYOKsnhobyKBGjOCNGTfLHLqtObPF8gZ2TWSsAtIACqoeA6cbuzYnGwa7iznecpWTtEXxJfbgQi1V
BeTsV1jzA18ELFRndZi4m93H4FKw0Y0tLrBFbal9UQhvFHN6zE8O+MJAhLRlbFBinUWHbMkeTH2zmcD8FYcNpa2OO3ActskU0MF2+om4SLWk2y2XWfF1y1rO
wH3FDOZ2qZwxXYZ+jdssb7FgSY2AhK0hgfnHZlJ44u7YqCzjnFhyNO6VbGMxj8Wm8hYrwNiyD1us5GO7zGxReWvlk8BJW50ub5lhbt83riJkoDAKqbZOwZbl
A4Akpi7xtkAj17YomLZfYIkuA7DNtm2bApDaKj0JO2rbKilbzM7Aq9reXXnLtZsKaTV59Ml+j51yy7Zx1R980YgiVqq9RQWiIQVOTljGz5af8hw6bosSeKsT
2XJb6y2Td0GpNqgtqy+3XGANv8oFXS0Dxx6J1raIA7DR6vcw5TY/KFoNuC+6BVyzYbeG6bV1N7Yoiy28LpByIMZhGYghcGtxDyiGgZTSQAfVcdfywU/MAuzB
hYlbgAIDvgXFo69YYmnLHWux5wwKTTGbxXM2ky2hbQDF3kbog8NmQBpFtvuh5tcK3gNoz4ofbE6NCVZb0imDDm2/HJtd5L8DIBUYZyyRSwBuuRIEBmJoYj+2
q3PNogQMx+Ly6F8bkQscxBZiV587/8CyUWA82DEOO7Lzs9z3VQe14iPsytS3b0er3FPd8AGbtHtMGRgT1vowUAJtkTbNzdwdd3LHmZl8kZ3TnXhPj85kbAdv
DKmCl1st9LZwuQOcZpU96GY1jM1c/yjivrZDHK/cBrISW8pCDFesxJAIzMsKf0HstrMRWZFRDJAncON4SgsJCeNjWMXJIF25wMJWa2yxD0bNAyuLgakpinnY
IhWAhn1np9i2gFjTBXjHbcC3nluoY3N5I3t8YwdQnOEsJrkkkacDGYHvo8Acz4YNXKuM5FUArcoJHeneSgps93rrsY0IF0wQKMA68AvMgOG2cYtGbhcJ4oqr
pC13kBe4wIHsdi2OkI9uRA1UT1PKgbuCA1BK2eJmQJWKbQ5tMRBKDRCK9RzLnBXMDS5o97FfkgmwhIAUjonE+k7gLgZrqzkBXoNHZIDJAI+lwIwdRDJYjN/Y
i01MbSR5fmLLf4FX2UpHoG9bgAhzixEjix83S1mgrCBQWzwB3bB6sS33tjTc2mDLxwxKBOJJqKLnKP/wABaYV6REAkgj5tjGlTvQjDtU8mXgKDAWghKckbeD
9IUAQxkORxNJHGBNWHrDJtvmKwGvsXgL5tMA0bB/+BbaypZ3KRsiKlCvcdRgSiTsAihHqTSRVCkoVUy1YSyWCDP4YXUzmxzHBa1IjQ6EYHgKgQCQFypUxhex
ONaQ9EMbKlbu2bIAFrzIQMnt7j25gDFQVCRHjNioBpPo8X2lePTAIusOqzXJEBwmvQp+VXMSiUN5y+5jW1Z+XMCvoY6g+Ba4k0nqjhoWNCUvjuQxMxncLuIt
xYUNE+KzALxATmOl1W+5WbR4t4EcxZaFmgS1KGo12GBy5DkRbwO+RYkJYYxLAWUjqdOWRgBO2ioR+KntLQE6se3bOHCbWshoKJzgF5E4BaT0wMlMkUWCJluh
Jgh8pzaFsn6wQA/5UPjKWIbRri2WjL6Ac9kajhFypTkKAVtqJAIuVgLmt1yEkRhie6sZ3mOho0SeYDqD8TdUZ0FFMazERoRkh4MYvp7Ayak6YiR468g/oTmM
og58fgCshjoxaXwb4vhUKUWI/USBgfjMZSfQw+wk3xM+MhZNzt+oRhl4C08GX0hbrpIAXmOEiOr+BNpN+kEkJwK9Y+0cR2hT3XbsnqlRXHcAyJKpXkCzJT+G
UE3Ut4v4lafmjeUmPFhJ4JVNOIjGPakKC31QE/SUURHoQhSC3g35DmUrEAAR96f4LZgB0C8u0zbiVJHmQDaKgh40CDkHqLDA20EqV6JiaLoPEX/wNBuq+CZU
WHIVCDpSb6DSaewCwsVAAdy3n6J415FwwWgaS6LVj4FEM9BiCpB7jRI0krPYOZCYVDqs0N1wHDLXAclaJoU2GCcQI4ZjkVqz9Ro3gSiz3Q2pi1RQSQB5RHFz
L5ofqHWYIG24rVVfE8WkN0CxpAJK7oah0RoLRClwKixTQjvFqpwxTCsoxdVKFJ4Gap3obFdYQxH/djTTADEMx5at462M/3BRgkhEpWZJ6QCqbviMip4ngjvZ
MbyiI/9zID8ne2YAhVSpBuwsZ9dl2SKcI4dPsNEwSk2hDCVaGeDIeVYksfbIoBHa4lRUK8DsA5RWGx20vgwlHfXWkZzLthjMZIwDZBzpy4tZ2R6yjUZqyriv
p4CiUBU5kWVLY5T04yLKVLPt0oVLUaBvrZCwWiAFOYhiYpHx8oFr3ZAfWW1ggmlaIePBBsU4rYye5rIBypgeVC5Ut9skDBw9rq8bgxYj+t8kfbZlAoofebQN
01ANgoKGLGwd8hBqs7boGDGr0kawEXBNX9rVQdo9tZFKNIMiAGSiupigFZACsG6gLTxDHAEbAlP0k0oPLo8ric80vJe5ZjNjkIBZgfnaktQH+iUSfQQoVw5A
fyMN608ldBuxzywoYNrITsdbUZ0ORTe1yzsu0AqF0eoiQXTG5qkxGjvXgGjE20AShVUGp+PKsDQ8CxmJLVe0pRFeiMCDox5pHKNstQhZBteyWadmk23zWNzJ
9mD23VmApcsaTVYSryPFgwodxZYtY5DphIHWgMWBW5XWYYaegxJk6xwGQapRo8y5UUFP4CTkDpgRrJVne90C+rYwENiuo7GLhT1hoQ9k4E3MHj6ILBSK1Nls
7qpk+8IgG/VZn0d7p7ld9ApwlQAL24boHKBIJXJU+YoSURVeCEkDmqzUl5zUE/SIhhs171KFOFKjcVuqLd6PAjLFSelIo74hm3H8nGIV7I9mgOxuWSMyAzy8
Q4WcpYGbwJqXoePJSaATB1k/quvF3W1bLvK+sOW6OTRExdQdfWpBxjJ1BCAKVvAEp5LQRL0rPFZ2v0KR4mBLwN40NkQkKZ7qLngQFvFwUp9NrBnt2r7L4nVO
EwMsgEdvoDi1BSMwF6ahUF80dG+cDuN/2AwCFAcrDK6fbLsaA7zmZklU2gs2r5VmazvzeoE0Fdmw2FN8Q5KDwlagTmJd6LbV6pNgfh5kCA24VNrmJnIHcpPm
Mh0jxvQS5T82GIiYqEwMp1JPZQLEU8hwPIw1+mIoRGzhFjoyjC9h6Q0YMliNnIDBBmyYZ9s5ueEkkFzlujy4qe2zrunMQnJbqog+HMIcVj9cYBneE5hOiRa2
0SDnoya6BiBeKheLpBpCfwy9Slz8FczM1qUhf8KJXN2XMst6yZXxG+caHjmckuhiK3AIQboZLWKRRGMU9EtE6i4GKHL2QfaK83Ib2nKz1PY9xAQ8peiFYWdq
jkqfyS6gjWEk1/9NUngSJB6kEZ22NhVAV3OAUFXBjGMdXvIacG0PvYvKnKNKBmlaMQCbAaCPfmboDl0PBjdWG8pAcUgAw3sY05B0kRZIJvtutCUbsdt7Th7Y
Xg7CeeqaiTyKiGtMA74OyslGNp+o+JuxMIhaG91CzhH34aiEJ6GR6eRC4jTVnJJowFxC8cmQdoZgsBkpTkHtjiS76fwmsEtRot+cRzKGDFFAL7b/HfUjOLxt
dk39wULPqY4doRNOylCm6WR7IYO64eNL8KxirV37KMtT6rhCFBkIsMbOq/xVMbEAAVrk5qiBozHSijA0QQAGnmzOQWBoAXuCik2WSj1E7rUYJJ08e+fJtWyR
sa3WvKA2ZwgYuZK6p4PESX4JKPAmYt38Sn7go7BuIKuMncqrtGLorTgnyflpI6SZ4jz9OR7OZRuUkYkxkQwhCRIK8iZDUwdUagEtGu8K6icDBPTMwKXsCK8m
lyp8+JEue7iRDAeTp0+6BlHI4OnlcnDmRShSsiQGUiS2ioYENDdgo5WSjckMAL2JUA92JsZi5MTPvRAlwvTAQiXkUbmR4bdC5myr/tE9VOmjtjV9qKdD3NHF
BG4CxT7S0KWxSo8keIMTwWGZhELj27RR8AThEM0t+YiGDcMAjaCg0wVepkhnB9aooSHCkAZ4JjDTyQlO/inPLRRgLsw9kNf7Kve0cZAAuigDvLdGZ4mqIX6V
udQ6hV+memWed5k3KZD7mNObbpEAtxkXh6MTklpN8YqnkJ8WzgGMei33TRVSfJAkYLwl0XIgU5FIKdIw3I58j/QnKBTjFEqiU7+lbvLQBMRSZ4g4wNM1gGmZ
9ZQYBrGNBAPxMMDvAofJQKuPBhWWXqveydoYKD4LmCeYiKFmFv2SHdNBBBOSEZ9AX4NxTbrNqQXRksqOQQX4T7E0pG1ISB49UDfPmMJMx7VdpQ28jc0B1nXJ
dLlXXr/A5WKss9CUNKJw3CEB9JggTYG9WRGumoDz4C6tR4Yq+q/lczqn9uiYZDs8+3GTumeZnM/6SHcILgw9LVHftoVeC00zIK0hRwEvBfSwcSkHnaEsgQf4
gZTS5Kcyx4KT0oOQHVZeMzcLDUnGY2Acdf2yjG7SEmTTQPl2JBt6DyNUBWzqwc4y+uGaPNz0DGGZfCEFRoHThXhUsyVRbA49RQqUN4TRjExgIFfqIGlgV6qJ
nQZ3diGjwWgzJo9eXsffQdGD85KyhR5dWZq0yBPZCJhIo3MG3oUKBt16xAfaG7XOxMiXabjUgeEllEOdBiXMImAWnIYMiQHKUfYmXTQDXcT072TffSJG740B
N0hs6jrwITS6QblbBFVNuBfJDjIDqrZIHGjTQ3bDMQPBjjWGgEGgqgHKJzymdAxTzcIzVsah0eK685QuTZqyro80ky0178T1IBmhLhlKwQsMAxeXHWRy1WJy
AjNrC+5SG7T9calFQDGBdLK5A+yFgBHiE4vm0z9PmwHyXlpyVZcoqRis6V555zvvwLLIMk5iVoiZfiuaa5KMVG3odGVQyQQyXG2Gu1ipGR4/hr0T5WcB74YT
xVw1mMDqJQloDQ1yKkZy70rGm8HjGV5zCsAauKDRREfRGMCJBnqgDFLYl4duBmipmWKfkdAmH7KtKCwxYPQPVmTcG9qFWYzSTeU58RRT9I5HBkQL7+gkNxFL
LNJjsA4b1FP4Q2CBwZ8xkIWD2mJmfKLCDKbvyEZOhxAJE8EQev0gJyujFzB1Iz1OWoxVYrJRq2GEkHr9lh74qrC3gbOQtiU/YUFxQeAmhpHJ+jcMHTM0Fhm2
knkq30aanABxxwKcHasMLdBLxRQIBueLlzuCLNnT3+lJZFAxwIOVcCBlJSHk5MFEsK4rBQuTH8DpI4UBfCn0WRjya+FMKonmeZb3BS4EwBS7/IIa5FORBCNX
i0QpRKgSGHSG5mygBk0ArX2T8zcwnhqFx41Bg9xZPDSqgX4u5XbgLbS7yjkzJaBIHxucDJzUomwGOB658PjWd8s2B9nBA2O/xE7PUE+krlRo5cIO0p4OEoqR
VlFSuICO/tCdFAyIDuRM0D0KXYeEK50SUB/BSA3/GBJyU1iB+oAvoyWa6TTHK3p+glvggKMO6OndhQLawIW5vUSiUZKqlK8K6ocCaTBJDOc0emkqx0ejppMB
7UrZ6jTMpPtKeWMkx6ie2yTQxsw0XXtkqgZGzRw0HkKoyNYvvDv8k1hnFFwP7jYGk6C3GVQifcgk8Ui8YPQBmnqSXwKqXtPcgG9JaYFezCgeHdRetni2icZa
awgkb5DIg7kskV4VCG8aV7Q5A1QiaeyMtSFNADQo/hRBwQY728yckZKGgCVwNcqDZnykUsE1jYMKsXWzcQ8UKmBF7uNGIZVtpDBdevZHhDABfGjh2H3JXyvM
LUgIwNaRIgfuxQERC/dJovshcN1DmjetSxzHcI+DMZ7SyFJs0wTACEwbB8dQVA2MQjS6NGyZajEdeg8Yl8pgqTK7SFVGuElk46RqJwAH2pOykWxlb0qZKCNN
+QqB9jS8B9z3xq6AYSRG+8wbLUdyi4ykGI4guk2u0RhBMtpg9JdqpylyWe6dTFg3dpXpLn7y1iVlThhBIhTumd0FU0SrZVO1GJICuI5dIirIiQ/vIn2dzPah
Z0PsMdCpDH8dUYU5JbCuyUyLNPI6qnEMC1Ls8pVyqOAe5N3slMT0IhI/p0jObKqFeQ6i4bdYhh3sO0CEcpiFVgzQmLlssgjJZ5hDxaQEdI+eVkfl10HJIU6C
k0NaZepdiBVwzx0v680wxlMrox3K/CDGGkJWylPCvBaaxcRj8ywx/D3QJW/bZ2b5uJDPA3V8qIGTmAYIAu7AAiOf3uKMeBzW+m0KjtpCma1JPZVhomyxWnty
B+yWyEwYeqsztzwjL4XCJhsdc+ZJxHCI2WSlQLykRcj9AKghSScvhjzgdVV4XhkRogEQuN1MkoXF+aBe3vjUpInKy+C7zkadBwpNT59zjFrT3kCYjsELBwU1
MCQOVCv0b8XCZKPIHiUkQ9FPCncN0ymaUpJcU0CAVkCWRe/om+K95XGDCz0q4NloDtREJ1HJQkFbQp8GpjFL+DRC6w4BMiZFDqMy4hw6QQ+9o2vKQ8GFxyMo
NqKIdaWSmBUpSFQAKhXKprRDYTuiiULWwAwjSBN6eAkMxoa7awsJTJ2D+25mKS1MmXm0/uEtAcuhWxtGtJI8qIbDyo6UsJjyzDATGBJ88rGK7tnXgry+Dc0B
OufhzVbELtCiTgzMyzclBxsMr54cEKhlB9JeyeI7s/K1CAksgwORPEh+LQp1T6MDFhXu6ZmGSQWWfmaqPMq1pOymgULiD63nMoCxklw8ky3hqQOrl4dVhDts
KPMlDXzu6SZYc5uoojREplC4MQTU6CaEi1LJa0RlZi/A1517RD5TZ0VuBM18+NqKzD16m9lPwFEaj1fkhaKJmobyD3rcW/ms8h84AgOqEB0FiWMqimExKucQ
HAycYmo5cllkqR6JFAedBlZqY45HoLUaGFqtXviuwDRhToURXKfRDwBUbew0ZD9+6KLSW6gFVV3aI/juXUdD76Qz0FeLGJC8xFTsPHlYYCYGrF7oqfAiSN/c
BqI8tq5gPJO5EIrZMV1uSqEg9y+KTZnlJ0hkwdIc9EO3QoyEErEjM2UDoS6QLjQ67FQESWIbH2DcBT5SpEpGBQbBSbBRKW0pO5X6V4D+ROz2UWYLhZGjCYQJ
ywqOMAI7jKYJZCyAlOFXxIQHR0vGxH+k+ReY3IqweUnSwDtYI0IwcNd7qGFY/LZRDlokWHG0RJODybmNER+L5SOCYav+SwgnZB4x5SuMaYqKgRtTH5SAGcBC
wa2q3VaWUgHttqxkq552BU2Z3mryewQKqKLC5RF7isUQFCFOjgkZpToKCLMv6JOpUM0c81BBANBRsCc5c76HQKeiOSA8+UIJzIMDkdguDYOyZeTd80o96HY5
7MwtmSATL5V3tBlkItIWoMUHSULxXJgbUDW9zgtVbUrocKi5m2KJBr8pnZSDEQFhm6fGxFeQb6I6C/9wJbHRURagFXO7IRBBoosQtjm8wxzloCToRHvc4rKc
sOAphw0nmHUY4COBz4kukFoDh2ggUxwSTg5udiqPWmHqMxR4pPPK2kE0u4lMm9zzRq2tKmG7MB/HkIE6i4MbGrkxmQQWGX3hPnn0rzhlmUXy2tidmTnTuoXO
DToFwiIjmBakWY7MnklNeipsUowJsUVIM9ukhWjjwZyKIqo6BaOn7x85teiQ7J0ItzoyeXMX0xlpIIZZAzVwG+tAgwQOUewXmRlINc2N5j0TtEA2xdFvUpAK
mrj/YlYeaHRynkAkIqvdM3+pIGRLdxf1Sge3nLHPrPQphg6R7Ix8JuhKjOwPYxIw7RGySPLiwogfdn02ZQ2SJyfZpHS4R6Vk2cLLoLkcFW8Vu8xMAKTHxEEI
9lxM2ZsIXsHGlKnYmDPgo2Dp4R/yMAczPTzR9aoCbDYP6CUnv0thJBYJWEIneCq5M4tMNvJoTDf9pZGKO/kKPUFUvp1TykT16hjiCXQsK+U11UQeywngHhI9
3UZRQy+RnZGtDwMpUFQnckVog0NXISlRQ2awDGmGgSQqbTOCeVFdZ+KLRc/o20hA5cal05N88AgnOXqnm/KXGhR3qrWCAUFFjzRisw0aD/Ylpi8FsWyH5IUa
la/iGO/zueeSGKMpVOZalg6s7Ci5RWlggHGKeSdlXTmWaUCJkjB2c5pdosxXtmwil/V8Zl3D0FVsQ3o4mgK3N0PyPyz4QoZrhiMM2w1MGPowm4eTsFFBRpJj
RMWNMvg5OPlsmMVJgxGZvZGB68oAD2WR6znTjEoqb3SgU9YxygIcRv6Go+TKyiIkHShxvCib3IYKsxH+RroAkBILpSL31C2EO7gLoywGeGUKd8VjcKmlQX5k
BqVLYLgoMO0ZGFKIOGXIdFVVMBUa+5khDkMBZiBanhwdaObDVPoFQuNg1eIpMMq50aMjz/EYJjaOQHEBsjyNICgDMsV+8XzLMLAS6TPLLpA052kVtSAAQIj0
AgIWCNXcs5ozvP3MjKN0pWNcHl0yMebOwR3GSqoMx6Iwh45umCyOy9YzgZ3UiHFDK4fOztFBi1ZphOkerDkxzklXQEA8hOlDiAwimzwnGSrYr01qljJVp3oM
SlZF4brxxxRIEj6pJHQrFQn5tYk2mlKVzW9MQ8RWcY9iK8VTw7FYuZLMvPzF5FRQdxPAMyi1p5UxpMOOxJ6RwnRKKuCMdaNHPROOXoCBdhbUb+TyUsqAM3Mr
A+WPIJCALkNZMgOhBAU2lKDguifJOI7KSBqdNR66QuUeRLTLYi9IsNwEReUyuKrSRjFFYOHspHOq04CXCHPsqHMFRFPhqkAxEbfrRh4r02i9ipKgnCj4b90m
ftkdCJiCHFLJUF+VIw53GRM2PONNxtnh2/AorcK2RJImJlWZX9WQZQFjvCnRKCCptXA5f/oGrNCpFzo4Oq8inN6VmRE8P8GjwYoczq2n/46iJBIp5fFMJAbj
1yqEQlbEQPvfV6XPwEYeOoRpJZqgZS1iiopdAzRMbG6U7g5Zm5W7SzmqQcpDrspYpA+Q8le5s40hDwS0uDcwaAa5UqztCMxbhlOJAQQoMll1Apn2Co0vx3o4
ZOyWbRxLExtT5Ij8ib4vpgZSbW6dwIsMFaY+0bRhYYN6Rn+lLELFVhlmU6YSPWHM8gCnVtYYPSvoEXTMKP0bznZmzwb42U1jzoiQwCkYC3MvKjOA4GuGp5Up
9zkN0i0qs0sg8UnVUOwZnQbfYFoO9IQsrVr1j1XedadcaZri8kJwTrwyJEPS/FXi/cASJ6QQQ54m+nXhSUVIzasEjhkGjSYZCHog10DmjfF+FL4VbqjDWjak
/zOcSglWq5czTo5nogg3Z09bVi6qCsUx1he728HVLmqL8tJk09mGqNTnTD1vCpcr+huR6cuE8uZY5umY44IfDHQR284uFc73YaAnyhQQ5pDVrELahCwtvIDX
npt0h6D7laSAbOGgG3KxArU0mfdIBlPVALRfQxxkEEmDod/C3FvKkSaUER1jQh8jBAh/VuZWImZErw90UtbesVrTsfzUS6Ag76Q56X+MFBSm8TJ1QgkmnllZ
qB+ECmYDgdrgVV+V6C8F+0aAJLNPDtlXKBuOcv91+zY2uugD67kMZLAHpEEMJCPMsX2f/SBvTRcjbhDgAMYinaUpSdVAI30CRg89YkrKYVIpkvsNfWuUXUT3
BzK4euYJ9VkvlyRtq0QPamY5F+QO+CaJs1f3wjBn+g1JI5Iu5TVodLN66TIoMfAqqsukDu6YzdfSlGCCqmAaiiyqNbj1Ft2YiYUVLirCg+gJ98XtaloMGwXR
miKinl4NBjBZVeE4Xla/iffBemDiLgsKWYHCejpWSRK0VLnjIB1mq03TOMYA+KaBWc74jPvZVzIvi4aom55pB5g85gAQCtTaM60lTl0RCZp8p64W4cZkhS00
w0bSbkBomrMEVoAZhi2weoClFpUyW40mrEyrXX+jfVewZxXkLEwIcP7C7a65lGSiU9l6gcUtI3eIHgByOCU22kl90J5MiPjQr0rdDHDa9G1QsXXkwA3bK71L
9Gyx4pV7SsIh0uApQYWpGVVcGDNqt98SEHTlPaxTCS4j6z7mpuGsQXu0D9xNxvDRfg2pDYrkXsGR3cYW9vbjxEQs5izyt4n7WOPK3OTV4A1qAFdnIilLb/FD
JCjbxkyWsGjpRUij5fqbHq5e6KYMpuEyvBWMXyA53WeQRNjTyLx6+A22Ei2QQbYlVZV6CbxGxMk0XZwAvT8Q7ggXELk5Ddj8NhsATLCj40w2Z0IsIYWfakv1
yq2CLV/ICAAAMsZgv8MrjM4oNpJscT4EIPygRq+VmX34sWc/PR3wcBg7+gAxkwyd8hsDOthf4rbznIXKzbXQS+4kCaBXFOYrcZ9bdWMQGe4o5HBoz3GKXWRK
QcLCFYtLEMisYIGYxv6hUMYwJ8QBBNcRLjFAwNAKVA9xRdYew2dMBAQXd8zYhcsRvnPYjpiz2oGQiRgJSeeGEiWx2AWWjVQqSBUkThH34BJkdh4AxjrbrK99
JK5it12Aqzg6Vjh9sD8Ryh4Iz6RtptDflCUpMRoGQ5jSJNzpu9pn2HeeXjW6ZojqqXD9V+z4ajiG2zIPlduGGziQykbFE57rxIBV0NAhfkmoRVuHIwQBUiJW
IGvNplwdQ9kPkQ2p9ugVkn8x2UAymAyFniSAABg2cJvcqnzY3LEXO8o5bL9qGbasoGusEscAOMSBYyuchkxHM9VPO50BvETU9KxR5E6HhdQNMCYUKhC3cqbO
mhjwA2pv4Jnkhti2lgMj36CfQVzIlCeWzfP2RdwMSQOALnpAyzQQuK6OEA708QWq2UADbLqbEFig6Q2rpLH6iowNv6oCnnndjDUBiMiVY3glcEZACYGbTwde
DvcRVRPZB1JFRhIgfQssCoZhjsQMuyrDnXT48tpw5waZVhAmhIwj7DBi/KhBOgVmDsD/ig3VhYOmgTAB1QujzcMGuEMLCyJmbpWG4Dd8QzUR+iAw6wa6jW3M
XWDJDdPRWLykXpFEHRdgYO00SKdBaG70PUAUCCaTMMh/BGesFChwOMF4Q9p25jjg64UKZVSFqjnTvomw3EWawWIEB6G+dKQCSwDoCAWuUoHiZRIk5HtjPSb4
eiEymjZMdEJcg0XwTFslyVNFpb0JqzHRTZiJ/U1SBbyLyiQpj2eyrBwznUVBFeqP65MoKZJhAEDvgtsHyZCwujfMWQYWuI5vCXabZaf26YJkgz7J7e6A+KDw
Fpg1LMT02mUShSas92DRY2YoAKCAHHJCUNKvXZvigH5AApaeDeSdw9+D2AJG5bmvNmg9RUG7unF6wUrFPioB7Sl9ShcA5FPFoe4Fy2tAH+cSAMRmkhnIF1Yv
mDkK65lOTXu0Cv5BGyea4CmMdjDUQ5bnQK2JO0DD/2T2NyEU2Z+mYDyRNNO/Tr5p4ICjCxeJ5GWearvIkLxbkgf5gNRmELNiKgmyZphSDREGs9a0OPZCO4k2
qn0ES0aoj2vcBCo47FYGdgRUvzBaJEkJ9YXEj33XsSYEGY9dgLk1fV5dJAJARbHlIpA/DwhSGwPnpGZDRmLM3eDMdAPTQjJTZ0A1TP5PYvCNPAQGFQmLOYSR
pgjNCyrQDPVz7F6MFMxqmPZPbeCoULRs7iiHM7otQo1S2+ya0GOBvQliSToRwsZSjsDjh6icOPpsqDEVCQYQX4LimrRcApejgB0gnsbAr00QkuboWaM2F8iV
HKli4JaWiTlwFAGFZh994mLtiZulWwY6khNQI9c0B5QcCIarL9C7PXGEuheqSKS8DoHiKrN6FPiDTkFge97AwwSCS9GRv0N6Qetn1zyiUh5MB5M/UHd1Tuo1
VlUg84cK3riQEf1qjjGl0tl8Eq9ApnYUHsG7nzoVRi4zxHrK3OWEk7bgxeHMOQxllsgN+kzUSqDam+lr8APuivcD8Qv0IPAsI2pmsYEEMLyKpCOUzVGBsBmi
KwSXr1RcctfsElK6mKGHcdLHQCafMHboxgR15pggg7MUFKXrclwVqOZJKFBNc+58mUopiQs7kotlddUboWm48rl+EM0E4KtUMlVHoXMUZYUyw7XxFjQCLMGO
IIbfdCPWaUPnjtQD0c9YENNuadcMXXY0Yj6EKYhGU12p1jE9lL5AyFYoCt0YqVRsE1UPIGnTCk2s4gM8cWdG4DYUBUOSwUVFA9Mr3sIFnHwHIEwx6AgNLGIY
mCTFZQjIrcgHONEUw7h1pAkTGKBAH5BV1+e5yWzLcpfgzgPxDezZS4XzXCuEuGBnweKqcHUBATyAbnRAO6R1k6exYrKVrtRDLxYThV4MQ0GgTRSTSElTORgT
eftQChOUpEJigZ5RMg8j0lPToWBhTQjpDlyuUiZQh4MSGZCGhKgWpTaYTaHWAyiQM0Ib9o7pniAPKpCBUsaQqFQpgdKKUE8IZ1Jg0rccVES7LDV0KNSmmEri
WBKADNbRbM2QtUm8HZ+gOBHAgX+eQOC0IaRVtI+3CZrWp69QDGFDdG4EbN2BrBWkfL8DOS8910qudlSUiapMAAudxScNnVjtudgPCZpf2V0J04GcHvHmRI5V
WDpI+xKL9xAVMq8GW2dDTBqSYBap+zRmdao2GvDAbCSZ0QjoRrLzBn5XaAijGgOdKZ1tYOorVUnPLcCLdDh225Ns4zCqYAPlg+OkZYTs6dmHXciAotwWUJkG
sKMqZhNId44OVBkYjjo7pFBGgplMNpYOgszFsejpkFJTQU8GDIgSiXmURVMu0Eqn+WihB/JrrPyD24Dq6UQEwiUak5VpOF2T5z7zqDjpfItyDDq/MAAZR9Cq
scAMPS9KgoRQorpBKwZ73aN6sFtIxlBIvswphv5NaDF447lXNpAWVcJkh1CKGzHNQ3h7x8W+CqUy6lTAr2mlMR+bfBk82HfNtEBvJBdjsjWnC4iPYDP0hCL5
bEYI/HfwW3exGNg9Tj3UC9+VRNIEC+AQraDYh9xzPot9etxHLAIgTWBNrPeV9YcCWFaVQqaGwnKRPEpXOHRwDuNCG+jxMJytYNumkQnbuXtGMk19MD3XVc4A
zJFNjgozKs12CaqctIcbfkmoQRrI8KKsbapRlm1q3InLDoCJAY/pOclcaKB2Rh4oKgM5NVyA5NPFSREzcGMYDJHCbRfJ7yVxFasj068EGgi7sdxhUL4O3G1E
BXAOGU2VYU5m+Mr5gAFixtNo8kdZHwA0vTsQ9tQTg9gQ1m4Brxi6CRbpsSFv8AgJUDVtVM2KyBu7cQ9iS41VSJwhWJniBiBL+MSkIUNfc/A7kMPRFKG7wVO5
iVRJsHIAEwEpZIhZ3RfBkryuHSZWuTbmBCDDiB4ZD5uNeCEtgI6krN5R06crzMsD6WVSok7Pj+LGqRUyTiIAtPUK5YhOPCYd46YSvFxJk0oTXVFc9Q8xOCpM
AZU5WG5uQ2MetjE4BTxumWv1MYIFlZeClJy1DWJQdId4R4QoTFyHpjNwAb6kXlMJNeTIYqqBthfyubgyBoZDoU1BQeMdie4UPrhLg2ovEoIzCUpOG60CcIUo
/5RjHjilAVjeQJ5Bt36lwZmIynKBWrIljbIMDGKqDDUKuXx4CQwMOrOHkuSB3+bhomZTO34gfIA1PBNTnSTyB7r7ZMqCgdD/AjOdvjOqA/S3tChPlpc17pM8
UY67nmcZbvQyQc0jUzRfd+l44pG9IJWStMuCFiTEKHVEXZP2BtcvWHHGGnqDllTitTkdUHWgrYhooFxESjDyZzj0ElLg4I93TA+gFAfVe7E9mkIQ1Jzk0G1V
0RFYUmWYkZ6gVEcUcY3oAo9wgA0Asg2QOwHGQpAhEOV6IXfHqIZJffF0BLsuShzrDTP1Os86fxAw6peEx8AcDH+QIKJ2LCVYEwFlARmNtAngqA3UwaGoWPaa
rKkhqrYP6k4kBmUSaaXiRJsVmJjlW89RK0V0nIGmFxIXGJBOEqRmwItCqhq6BxWF9t3jRO85DMraWIXnuxLnwIIRDUGGJA0LaNjyhtPVQtuvpW7xIS6QpRlT
KlNL4+jIBR3VYPEGuwnRB/1rdKYAosydkiGe5KOp8gLRo5/7baAdVIUtHCkM4kPWd0xhxCb4bBKDB8Ya2acg9z9la3dqI9cuJQZKfJRpD9tcpob8fJuuPmba
UvK6gZcNhAe4ZSXHhjqWWfzmSL7IaR5GB3CqsspgisqNg+wmOh+HSYQm6oi5uy0N/knCHXBGPLibV/JF0AHHUKc0dk8dEhKQFSC8FtfZJTsXJmP0kr4giEQS
N8QPoyqAPBVmTcIFD8EdGivSpQhXLFDFNFgmuqcuJhCDh2nSBFRo451DyKVXZd8VkhZXv2LAVEKAa7xWihCGERzUEQ/7A2Xp3QSFek+2grJUOTxtEEV+4igf
PykBphZltUnmIOcjaqiha8AxIQRGiK4b26iVY8pW6Eapg0PDVaaE88fkn7InMkNWwExM5NAHJB+fZ6RDXnmooK312ImCB+xS6faq3ZcTB0rSZ7gVjd6KbDPl
NnPOuMQGs1kBsEFUYr56yAgiPsRCtysx4aFqqnpMBB4DqLKO67sYydIWobMdGt4YAkXyxBjGgMrsEnkX3e10FWQQKDXPylUlKGe7ZrvhIhKJsacMtIZan6gI
wTXPaGhulHCV8G790gVLX8jXxSIWUay8F90dxGmhHyGDG+c0Oby9l07gyHIKVNjWvSDEoW5PYdCORcZcoaVqqhiYgtUMwTdw8Uryauq2YBeJnYQyRQMbRhXs
ADhAaT+ys4UDZ/RBGffMj4bsT1QbuJZAj8ooYpwHP+pIXPk6j8Et+eTgP1bgCS6jYegoWPjk4fBrWu+r8zY/0JfM0EhitYaTRtxoYCGnG64DCHMKPUgxdR1+
X5juCLzBAycXDw0pJ84fKJ/oiaKw0nx2xyNFN3ASjhY42F0lRtDNIHULPCHALZ/EOqDsJS4wpaXHQnf/0FRhqK7KrzkFdAvvAodXZd2aIoFcSSZ2IqS3nSVJ
9N+h/xQ+RYOE4yII+xsZfkCZPSLjUC+lOyJ1tI3ihoo3Y6rdfG7ySNPcgPfASEbpAYMcukbScL/CBytvD20gSWcyrZhlhHG1DWqDmdHIRNOpbVo3lfKmA57u
PjpsicOQRY3aHVMAyuhO50L1THWDnC0yp2mlwgphGhYQlU4E6jWRIQCKEscJ82T9pD3or7FLY0nVRHdzZqo1fL1hClYHOaLoN0BWRWBOHVTSQXzY9+g6gxsb
xenoQIHzEZEhhbeVp4BCfqaC+A53z9hjlS9OYTNIQlqFEXTuFTwIRckJ5IO8VGTqmLikl8KFVABiKA0VRZ8cCYMqDlZKU/gCvtTAMgTBBw5hDob5+6zpGsaA
JV3+8jdT/NAdoZlhdkGdAsT0lJAYqCLRxIiCBxJihbeMjYC5crm/KJaemVbQgsrAQSlYVQUrRdHsGzqcM7sRFIHtPuqB5nqUGc/VfdLkyOPyx1xSBuvJ9Eg3
XRARvo9SmJ0iByQESXeKOjpvXSrdgAycNilYmcHZyuSi0f4WtHE1OLrkO6FKSxdPSj3ynWUJWRIWmasLzMzJWpemxxyUB4FkCjlAuUY7vmJ8lBGYwFXPRPM0
eTRtcAiB+ICa8teKxefubIOxZGmkBASsfPhFmkSPlx9mw5ibMkActAQ/cCEODgMREBZis5CgpyMUGrNYpajHtHOSnIAhM0hJDN0r4xQbrrObk1CDLEN8mBkp
XHeNmJW7V2Cgj4SaWWYcF46sBD8TtHjTj7F/x789+86yoD50nUzhVU30X1o68wYfwzyoTMCwd5Fz+iGRkalAeGnDwlfQ+ysdtoitGS/Ap0iXQE1n45m1KjTi
IvORHJ3Xg7TkD+VMgweXvXEK4BTmgfIGhSYBXiIHSh2C7dHvjyyQJuyDcl/ESXhbdgV3DKgjq06/ZBKErtzzcVikjOXiCe9+r0RyQWYBPBL8KfL3IWqwIQ1+
H/gp/BdcSWxgQLMxwYK3RhzA0lA3nFLrACoWeD6+ozUwCKiV12ao8EOup4VleMl+SpQ5GelU/pDlWht4j2lmOAEY7Ezwg4sUSSW6DvO6kCXL7AGKCSPGD113
pAXyMwhczBgug5wFyDzjM023o+MsqFe8ik0cPwn0suJ09oABNp4W6DRnBIzxPNQdcB5gnUWwWJpGdBnxzqAN892yE3CswH/JO8LqhselycWIaW2MuhBnsMgw
nGhIieAnqMaXyoZ4Eq4K53vhl8hoCqzmRlYfvcpcqIYzwR0mHLEC9EokQYZER18EbBjhA3ajQoWddlzRbtNpwbGoaQNPS+ICThTn6FXHVzj7LHzP6xGGsEgw
4kZnbZP+T1c7sGyoIjGkldLjDXeQsI0OEuXxbXQ9Rd+Q4AedhVTUhNqFGclCRU8nnlOHmXM30PMCYVSQacTu6vfILUE0Fn5TwBDRJRA+b4eMM/BLetqJkZEc
B1Dhul9Otp8XgZZOUAqwZwYiMxO5wKFB7LgjxZuy/GClo56iIyDzk+DySVRDeEtmFQ0sKqabKymdlDOtSFPg6uaQ9+xXpS3owCUCg/0KHvBSmg5sUkChKCzO
YhjoBPJBBLWqhXg4RLI++MO5SPgmdq5ZBV3PyUZAIrC+1tOOY0/giSNHQfYN5BeqI6t+TndaIe72S6k7wFhUiaAaMdEp57gAyNCh7kZGhNVE6GS2SjvhPU/w
TDiMcmznxtJuXtezj0ztYMcRxdvQjsYaC33GAxOlGNVhfIjefCd6ZZhSVEzcYnxO+i4taDB04BVPwGmMzCuOC8GJy2tJL04ZpgEBcz8OAKpU7cwB8kipIFBw
hPtVOTumd9Fq0qCs7wo3Ajb8KCl/ZVDkNrPqdpwOChGKGNgsjovUVcJkEKdmChwhgIVJiTAgQ8IGSA39Br2ixMdnlagXRUyRkBGmg09gJF5qOmtTN1z0Y5Ik
cJWwT7TFizKlOvvtt+TyPBD4pFsutNl5A/SiDZPVuClC6qF5ITpXbozkkYjiMpFeYgKBMCSHoWpXzJ55zbLLkfzF+uAgfkYFq1BZF+9DsLtTJcU/3NrkxyPH
YGoROA64OWwvLLevO3tiVdJaHpwp7LEVE43OjtwgLihwlFYSSdQF6Cfl2gX6BKg9sJCZlmjnB+CU8LiwnixwbgIVOcJU0wNBI2cPM1xy7py2OREWBSIGCKW7
UPOAkMpUoT/sU5tGQUel3SDI/Sjo9OIwCIoR46Vb5iiHYWM5q+tqR/8BN2Bije9GrCAKu8DSycehIMBs6CFM9o8RYCYvgA+I5JLwkFlDmlwuXk19Hg5rcinB
Cv5Nx1VREqcy0fOsueLCnh0HaCYaiTKJyU+Qpv95oO5PdTt3rYRzLDOL8rZR+jkJOaJo6Ga0LK2g+WSeeAdpYeyON0ZYYEM+JNqGLNc8qYypYx0kNEU+l7ve
SFYx04sq9qBo6Yeyv5w0Udc5a+CSnJKFCDQycMu4BVOpmKYrjIATlztCQDXCTHBlylERgjrBCPJAsSNdIDXlUmpWuk6AZZTDMOoenvujoFxZUpa+KKk5QNQk
7x0ZNnwdjBJ3jRTromFiCxk4lQgsy82VWmBhZsYWyEZkPnlm+bNjtetyND2kwsKEdOo3nHxNuyuRiQ0jP4ejiI7FzrKxABrZS6RmSnWfmjB/BxswNiW0Cqyg
yA9dz/8JUKFEAt0AgLLRWenArV5GgEEwa+2SDfM/J80f2hIPwAKxJsQJRHtgcshZ0yLTVHNksCCvDMD2UZ7j1lVBz2p2YUrcKMWa7mBKfWoHbtT2c5Z7CjAc
ORziWPBUo8CsZLF2XqLQsQGwRuYfa8wMfSuoxNszwYjhN8Y0pW+TCopSe7oKBi8ZS3Qz1To4tHEr7p9AFlLoXqanQbfCWoNYtWGUVBALiemDiZgRNJ8Mv8Fa
zvK0oYCC1QCzKYbcOioSnY9wNc40qnB0bLneGyYLOHrV+7x0sQbNAUYqF52TTdgNNq4WxGRJ5A5Ip3Tc3Qg/kCBH3KvoJogFVhkD1DyI3ughCZy6OTzCTBcV
U4YxnUZDipjolYfTtWmjEX7Lgm0usd+VQ7GURiaNWGekmtYVDiaYdHp3qmoRSrAItWtFGiMtXnqW6EqP/cpV1h3iWLSlkZOlXzqvohd4ncljUpeA0GXB8GMd
1V3+1HVDAQxOUop5PMENo6UMyz5yQSApGZk6hh8tOSwYKp2PJzEV3CsYg1kOGnYdOiCZQqZIZu5KC8AVYDqPyjMVBYaM4ZWSl8/LXCPPG9zIGWA6FK4NT9c+
QO5HPSqyhEGc2o8Elmmi0A2HXjsurSB8w+reG60C26UejPfcrSRwcHgpCq0Xpst8qIgXLUh6/ZlS45RfMPpEQKGjM0Nmie9YjTXDiNFkzzbSxiXC6TDp9J64
CQH5hxOmOepehbEHKmsInI0uCH5PR0hk2AcsnMagzABGOWnbU8fQMrNdD/ZckoK6CoKekCqsrhNrRJoO04eZpdDo6OvqD7cewO1h6ILrUdSVkdmODJA/c0MH
ZOzyCnmM8L3CPRRkSEGKMRefHLl2V0HjdT3X0GgsGEOvYPoGlW5Vjo5g645dp1oqGTlEG2atYsFTOspcx3bknmQqvXCbRGkXhEgb3UGNDDamrhp2N3DtyIzV
HJlc0hUFL1TIk0aE6Ab9GgxEdIWm8evSA161p7fmUc53FYjxEuJFlv+ic3XPPTjkM+B7KdawnnHgb7rtAHVM5nnsSiZlAuMNcPU3cUM6QAc6BaIX5XSjqTAb
pnIVPxXfhK6rxkk3F7OAviDabT3hj36tkRWyfhGhGoOIzCH4o5CSiLwpoUz3FuDuvdfIWs4MTOTczRaROIumIN+dqgCZAudkTCPpBr7SyF1JRcvcbomyAiYe
6mGkKXHNFK6tMnHfrk8jckWBCkQUyouLoOOZeztAnNFbF7otVUdyB0oq95jGQBZNFJnX3dUXuZGEYyywW3PMtUFuEZc9kiHluxQeuCLwaM0y2waInehEaCMi
sL9+tikQSnesPUQ1pet965qSZ901gxbMlJMPi5u4Yutn4J+66rihV+o+E3bK0VmAqeXqU8RikjD3YKEuRRmqiQ2jEdeJhA5sLjo9ULcI3VZotZd7QvMJPes6
s+JDqDEwv4uWYncsahHnkdMXFQoi1QF7XMGvV7tqRFdpN80a91qIkuoCPHeRg2RQxpZ0RSTWZA7DdSPDdbdi97l4JezxBirTkcXN7UCoZpInUMEe0sijKjkv
Ygy+u3igsHBt9O6Jxtr+3MUujJqT3SVTnw6hz69cuZJWyKUpfrKK6JdDCLGOQqZ0DQn6VOWahpJ8UPdHvZpb1AHKjv6Mrogh7BJ51RLH6zO/vZtXXc6yHFYX
HV0ck/0dVVaF8lrNe3fsgtlBTaAkIinJpCU7mpzejDQUEV9iYSc1Bkfzp+v9XB9MeWMsnmA6XCXn6M7JID5FH87ks4iSfXBRhCBbwY0ut8YsVAGX8Ubn6iRq
4U3C3HOlNNnTCGglrj9HfpD6EMXJgBlRrLMqQyfU0Tyj253KNVUULqswjN4baK2BiihEpR9FWqJuELt1MEiiMetRwrMy+TJw3TJl6oVu1g50W8UgIs5cAAjB
2cnqhtoAMUmDX6yQyXAjklO4d8bOlBk4TuCdqiwoiOO3mSEGORIDeUDojhOuOssQGG2nERWFoirtI+7Jwe4Y86hdlWC5T+3e+6wwInNDN2EEMICjihhGT7o3
OshBMVSeLyqm7ZDGIk14vqM0yW43l6E70sLIY0iAjl52j5Axnf/dSqCItblwPTYGcUcncVEaeR7VSiQlxCylmrx3tMlNBeXkDEVAQvQvdT8Ll3fbcDHNpFDK
MF4vsBI3d5dlnxs3OfKo0YkYkQ9TqwRntzG6px2qAxeyQK6S7+xYTFxbCpCts3yr9dDBhtl8fI+7dfs/KErle5TEcZk3+tk8tmfaQHiqK438scnB6pmJK96a
aBuKoUrD8Awl0XsFbGhxVJSxtn7p7mhl4GJpJPkePMu5kAwjeDBli7o/dsoahXKgEwRefE8WQpTj1Gnwg4L+cFsi60vOzy7IB+6NNrpYqj6R4dYUbu7OZEaf
sXRrU+WB7xK7yPbq8SW4FBjsTwy/pMnRIVaQmPOjwTBrWCaU2A+ru2AbIAVaOwRMRATpDXVcm8SDf3RAkxEwKbUJFkOUpzu7zvpg2HZ6plGumJnc4xhfUyQV
eozvCjdNr8wEFyZQ+m5jV7plu+XMlT17PDbS/qa7nplAMjraaEhzS9eurkdWdvo4iYmu0zQRgKOThavIoKuCqtgKJAEULsQooXFuwH4Fy8bajh7Aa/QzO92k
KzVMaRmYdh25mP8Yn3TSRhksh3EFCCPV0rslbXUzm/gu7PCERiqjL7Y7YItS9liHWhlxzoKRVFKuz4aNU4SHCk930xZWj3RdprNQ5YtMkyNBYdFPirg5uEGf
Z+MPJSRZ/wfDqosZqIWxm0MIEECuIS7JGoQxlt0VsykNE5kclX3oPKhrgFhgW5pdpxAWeQ8qh+B+z1y5vrNdQJ8bIlKf/JBspqhuoxsATAkSAXSPLEN7o8+I
kTRkQ8Dx2rGOVshAA3hQToqTHQaPN8mudXUIlMSfyJgbjS6pkJ27cu8l+lWU+ceYEzsv8d+RDmeILJgo3G0q5n+x3J1RMVxJXqAg/xf3F2+kCc5toiQTUrUe
FkbxOSutxwmiR7duel5Q95FgxRk/xQGb9CxWwYxo2bEZHLuvIcOtWgRs3yMTZbSCekwREWiJ0DaGN+jQ7pydAVZAuEtkskZqgFg/qTMxlhdyZ2bxjlK7Din7
UhmhmZtHU9QjSG8hOMtS+fLNP757bnkq125e27yTduNAu/kbaVfp8423aD/leu/jt+/yfj/3HLwLmP9acO1d9/+XHv/PNS8/9bo3fkL7JXDhXd3/feHGu+zb
LwH7n5Ou3ifu3vwnar/mcf4W+Oz75Cvvi+/e/Cduv7Ss+TXj87uG7bsY10/Vpd/1WN4HH7j5K9UFfgu49c/KC961XH6bsd34FcmY92Fj3/hdv3on/qTfAn38
0nrFzd/bz+Zvu/FP4J963zbIf2Wc+7X7Gt+Xb/uX8JP8mnyTPwe8fm8/H53+VnnbT6Xpte9/a3D4Nc/d+4ol/pK640+5/s/hs7zxnujit2a33fgF2y/J336N
vrN/hjj2z8Fj3uY6v1Vb5JfKMXkfOPs+Y6k/Jz/6Ldm6N96hLP5lxmCZa3//9vnXXGBpixS4A09WwaINmVcOtmWvTzvPx6/1+9M/2ZOVvXHLxasefvKNsbUw
Nm89+/DPOgHcBvvy87m/tz1csSvpscPveH4eRlq115YVzucdf44+RccN3M8//D6R/wWeInfgPv10xqWscpbbJV/18OsiXO7Afsbze+5IwPbHV3j+LeJejthP
/fznn7d3VuezTSvP70hWWynd1vu3Pr5vVWLQ9upHDkmq1/hkVWrczn3t8AtzOBT/buMR5cUKC6mPnj6cDb+yZZXy2c+2JBxvs3e8+nAL9za//HwCSLZj5BaL
r/Tj++Zu2OD9jKe3JV0rH63Qq97uxTsnJls3ZsvNu692tFVht9iHfO2wOuxCeXr+4R0xyrBFhf+l57eF1hal79PTT4d+HbZcBeTcw+9q4WV6tZU9tlxPefe4
fm4Bv+mHw3yqtm27wvNvV8M2QGBthNOHt1BXt9g/7/STlbdv3VkHWw9wW/w5h7MFUtrmuvL8NkpJq9tQr3z8TfpyzDbyce/ws6i91RCBiyqdd7R9F7bYHmvn
gK0lOGErh59jEMVU0lr3Dtjab8sF/s482vKgW+5WcN7xZ2HEthj91pfpaEuCxC1WCDjz+I5wpA1wEK0ebKM38JHdwzGXJfcMOv18Rrdq2X3yZYsVgI4cbCVE
A0s+efy5/bitbLms6e7Rg7SOP7Utdug99GRrelw+vCvE3GJ5jkvPtlDsFmtorR3eqb16mOGc4EK2qeN2iFc/vHM9AWZ0OudwNlDMX8Flh5aHX6e482C4a0/v
8Za2jBJM70NHW6Fmi81Urnr43V44U8HZcgeE089HKGab0xWef4lRBlmyVz3YKlzQXI8dzlGDzG+KLQSOHGwbtu0wHd7ndJsbittVn3f8FWOuN/C3g89Xk5rF
XCXYBODM4yWp5yMQezza1lLmNbzCwZZFCkS3A8c136lhaNpidbh+PGeYtm3n1l/9YLvqQdKecfido743ZPcUimuH3+HzX1qA23LQWyzteOLYYEAdfHoLPRm2
G3Z5e8tjQHzj4NNhQsgmmcHlTxxtK2Hzb5W3fWFrZ26zv/rBlrKMW+6IeN5xb3S2xyWtRB3q4JHR1w85FgQLrnw4Sz0yFCnnHJahNQuZ0WG5e7QFCgOcZKeO
thriFtsprB1s3VBmNJ59+J0R/KZc8SnCBB4P5tvBQpBnHGwzlq0fD7bHRtxygejzjrZ2qCkz7srHALcP9hg4cISOxm3DrniwrRLylhtQX+34XyTUtbXVRxdP
EQxx7Tm7LZfkXT/aWsRImzr/YFvLbqNbP9jaopa3Gs4/hrzlqrrLg610am7weOloG35aeG35/PNlWzVLf8S6xSeOttbt0Jj9cunF23KCmgZS9plHR9ppl46e
lLHynGwx7u35R9sZYJt2niOEb9g72IrcnLq1w6+YpioYbjh6sJy6qXnoQtgq6dyjLVqMiOR4tGXtt9ilQwdb5h/XXDzbHjgWUjh6+F1avjerwbKR6lUOtlMN
VbMTR9uoaVvb0QNUyRr2DgsN32KXu88n0hdxVXeFgy05D1X2/INtSwOLZfXgITbcgYMxThLEFY+23VeGZnHoeCmzwW+1j9ji0BKjI1c+/CKiHtubzE/J/P7x
CgcDmkWx9GwuOIM9M/l+0otirhXsrXHkcClP1WJ7be/wrjK70hbbh171YOks7YwnVJ29tJozbPk1/of+zyXuN8M/xb/f+z/3zPfbm/3P3fT/y0ApLP7fDrK/
fUxxe/9X+fZt7/Kucfh90cbl/9j/3x6i5/7q7SGO3ermd3nxf+qehf/Herf/2bvAsbfDEewZc+lR9obg1h7n9PTYt+8Wy98tHa/PjX9vXOvUVd2Z/1eZh/fJ
Fd6Gn/nx0fr/1W4ZF//YQnb3cZVrnYt8I+j2Bd+xKUl7/2+H5v5SP6/K8q7GHtvOP3/v1x8/BdGvpkAcH9VVzrbYzerj16BIvCsVIu79n6eoXLW/w3ubvWXf
Z4G8O6YRP8crnFbDfp0qqPunMqHWRedhmIe9/3X8wi7ti4c/+n/5EtzqkFv3Yk/59cdxNHdpfCwEWN5pv6Qa8xMNOm52uuT50AZ3QFpWHvXA/wyrxeP9U9Ao
Y/9/5t5017LlOBN7F/4+p5DzoFfwIzQaBK2WuwlLokBS3TYMv7vjGzLXOlV1ecluCjBu3b3PXvPKjIzxi4j90/8Awb//0vf/dKYf/68Vbq8HaF///QUKiIjU
d/8eLvbDf1fS/h1J6/ul9rMF+JXB7o///9rd57/HWstfBEL+C8zmL3OPn7Olt1r3v2Yf5NdIX0X2F5/quf6v3+sH4T9/+u8//78fv/njH/7ld//6j//02z/9
+Xd//tNv/uH/+c3//u9//BP+Qsva2Ps/4s+CXpq/+d2///kP//iHP/7xN//wGd7+HX1T+xwRFMuRsxMQkt/86c//9G+//a//8k+/Cz8h4qrR83itaMQaDcV3
AB61/x9/H05EeE+je/GIVuHRnr6wzeu3Hu1WI9kgmnfHhp3Hf/YZUevq97pkXOO//g4b8LOmqJcT/T+jc2mPBqqRL+OdOjqamoZTlJv+9F9wdAB+ZjT/jG6h
JdooR/9N7vs///Tbf/vNP0SOXIpunxGEqtF/NRBzeNp/+92/PvdOA3E+b/zd//Wbf2h5w+v6m//Nj4PCGwU//+23//6vv/8//vDHf8Fl046m4NGFPnqyprhv
8yj96bf/zruuwLnM6Mu5o09tQhPL3/zz7/7059/+8+/++F//6U9/5hHBS37z33//j3/+/b/86bf/4/d//m+//W+//9Of//DH/zueKdJ2f/Ovf/j9n2Lu/kts
/leegJbAMWv//ud/+u0//vMf/hV1wjyR2PSa25j6f/ynP/z2T//4u3/BrP/zH+Hc/YZu5TG7A4UAIlIZ05Kia2dC/k1sRoPjiIBiZ2KGUtBBRO3iK3UegM7l
8YWm2TWKCYRU/Iapj8cK+HLkLKLX6Te2Ff22EEfADXmZcETHXQFcqDEXC+cFGgNXImmg02rETfE3WrriUdB+OM7m3TM72wbJ8fHQzzvy8fVAOIgXRwvieA6k
bH9DJ964Jw4p8cz4sSD/v6E5NYm7I0UHvYQjXoC3WI0vNjqOwovFiaXzujEA8Ylu1AWFL+KgxIt09N/9ljLPIIWnGIT4e/KNx9bAIUP3GzvdxtPxndEiOJ56
Ytwq275GlBpXGZv3RTvqeM2C++7FZ0z4G+2k40mRTPkNjXDjPADlMs5pgKt9Y1PhGA9eufKNqmZsDdygVT4aur/HPStepg8SBJroxqaF51ub74dW2xjhyQsU
XdTUgGj7N7bF/Ya23Xh1zHzjHCRltrSsB2AT6Zj0gvGHmvAtTdJBaniAlTiRsZA+sAlPhm7vlZSDeD9mm/3iI8yjwUIr3W9VU1mRgBevh+s2YOlweU4DfsSM
6cVUsWRwmBdiPN86xxeN7eMmuuLQJ4+pely8zySFsDN9DJ0GBSlbsSiwewNi8A19hQ/9kFjilTmaM/EBANuOqdVqmBpGEB1WBYmqcR7Yc1jPHo+FNr+B/W4i
CxJMR3PzGHrcp5TycRYjeufigRtHESQyi6acuftzaDD4huhTz+mJk3lQKrzfAHOIG6GJfEw/+ELWY4HKsSLQWzpocnGEcNuUuFpXnxoW7E/6UTXXHLbEZ0e3
cmSR8A1ArzuJtjJpnHTSOL6dTyAaZ2NiHEQ+tcQQ+BmCh6+AHWtwmXZcdvSztEAmHaMDi+IbeizjibhiOgem8E5jYKa0Ipsqq+F6ZENauByModtu8izwkMoF
EVfhFHQ9deUUJC2rhPNK5XkFZZYAoYnL8kacky6SGJiNEg9YOGTxKo1cgHRYyaOdE1KaTgPVeaniTQYJoG2tY8zqFoRWDeCdcLrJJBfIAG3dsVj1uJyIqTIf
XkeNz0TqRIPmZEZbSdBgT7hG0eJdlAcYRXESsjIMH6kDDciDLDSUXPV1SSzovouTJMZuFsUG2nFwwZDFiQjaj5cIAsOLG6OTNWkfgkgMYWnpLD4qZqRzsc7F
kamVjDZz7njClnCp4kM9btxI1qAd8qnBM5P4YNXEsn0610M8EV+vkgBBXODgje+jBwJCNSaPS4PjnwEVDnIgAZKVTu3lXacobxURTeEdOP+KJefG5ULhtSQ+
EvkUeoRz3ZEF8CmVUjpJ3kMUMMSW08bIZj7PWJx2tOrGujcfg4zlBrzRJEsZFh+PwEyNm2rlA3QMgWhHD4BpBG/kvRrfXVTQgBv7NsQHG1lJSxiJuEU9MmVT
fmepCwn0PopeUewvaTkOpifyttYKut6xFaom3KQpSYurT9rOEJ/aW3KQe4roGcONV8C0Y61kU4oUgno4A+aEgp/UUPnUUzdCwceYt0J+Sb6imgGF4oyPMUnC
SxpZ07hUSnf0mAfFUt5TKoncl964cz7XoBpBGTS4gMjZYgfvl+tddMGaNh8KEJ1Y/WRDGqkkllyvIjdULKatflYZlyknNvGpM0Wf5h2iIiCYwFrGrTjak8K/
chl0vRIZN6l9avWI2ZEEMmUglgrexVpopUYpDqpV3bsmnqqTVlHn4IY6jy2Zw4bhCYLRsycJ+CpdDp3rve679cJElQ4SEMJSOguZ7hjtMuNNmualsmTPFs8N
W4IrgkNXJOS0wJBvjQUYakkXuF/EKd6w9aNKiZQKUakcSaKyz73UtkzJAVVRi4zaZ6HQW5ncpkiDp4grz96t1TeruYCWaucqpHK0uL7r5nXX3lR6tbj3FInx
LtSjh6guzCuyd11aj19IiZT6RcJT/Fysuom3LYlYqhugZY072FH9Jv4uQbWkaUtk6goY3uRnToWMTYW4OtnB5o4sITIoozARVLJJ2FVrdVEvxUwf1Slv8lUK
NOpsuT2aWZbKlQ/H7eSDWXoLBQPnq1LxABkG9xdjgjGhJcI10Glf8JUXWYDWpywcUqZ4tFSj7IXdZYRQJ92VdNCtMEpYVzJV8fYso2AWmgxUDQL1jKOk0/HN
5958RoodXndwZpsWDJ8XwpRvW81D+dIWDeAc8e4eo541N5JiGGeQIN6I2l8VT+dX5rTDFsKCo0K6zMMalyLnSi+ZpHZAdWjcBhuLpK0BAzWCcBK3dUm2JuZe
r6lRadjEutYa6OQMmww1kxNRZpZv1E47VdlJ/jfOE+sl92ULeJlJ5iX5W0h0UifKIovGB/ibNB3RAtS9uE+a1lUldSneZDkl6SKmhqU3WaaZwiWG+1DP07Iy
56CalWhQWGtOJMVE83tI6omBgMkBUFdtS+J8Lu1Cnr3JkiSOKvlWm90mNfBtjcokmVuhprGpDaxtRj2koFM59Bvy6SZ5BZiYXilx8ml5601snIq583xxwtXp
WaAWi0eYktG0W3Iys0mk+svYIC0/rxbDUetkla0JPDxprWrwGiZokBC2JHKjhlvIBHOS4iwmgDmfzLntdDzgyTpFnWw6eRwo9St1pyTbkTJ+7k5i28+amHz2
qsHrGtC8rVpQU5X+DffFpwqu2Zo2E870muCVuC6GRGQV7+ASzPYqkHhp5ncqeklqBWaS0n9RZW0SXtIK+IpyAPBWmepHFulJxjSZTlJ3htTxCg28WKmkgpHJ
BCEKcHHxFCqwi8OeAdmPNUdWtmk4UWUtXPZGAWuM4C/BapA2p0V+XDhLKpemXobdourNG0p4W9GTHWlNTtn6m2xTw5i4OiZtONicQd9rnKp3q5s3Ua7KAdHE
fHI9SkuhFge9pkqLKFT+uDo2lclJJbNl0TgXMNmIbL3a5eTgQtOK7uao9fhgQD7Cm3bqFyIL+3pI7iREmVey+tN+GBEYunx3ZR5tAOuk+IFoVMv5pUXF0Rp8
4L3FqKpJvB7xnGhzDqkMrpDJ1y1aDZtCjz6pMS1kk+ma+vCxEMW5GjVaU3XmmCyOm5VcuVU2xZgfM095xqjqUZVsez6aScu0DaTcSadJMvc6eZtEZRXv7aTb
YfVuSwiLRfDg0SW5utUhuvJ0rFj4ZJ4SRfEgeUqIJBleWEkyscH4qIVRIZEeLHsMnsdKBxaGr38cU2dLSbAFTI21cepKo2Kx5mFb4uykzm22lkl3WCy2gMDf
qfbn7sGjNOLccLwntaNK/lEo2BINbeschau2zHZAwyXmGJTYCTVTeDDisMjjBbAsLgDdtoBrovb5R2EBMAZHIstkMbo24IpBBikClZh81N7EB06J42tHXimy
jRjAmah7GMfDEI/o3kSKAhN/kfb1UZgoGJOLZY5qTQwMYbnD7oGSB99RjrlACd0P1qfDo8K0hYct06HLqCHGuVCHjchTTBUfF/Qd92bVqo34S4/KrvEQNSZi
8rB45I7VC4GTwWGQZP0BqoTqiRRY/A5DF/lMUdJfj4A7AX8eB2kIQRBIIshAuONZG8cXF0ZlNdii8SLxE+5y0FCUxI4HgpjGWIEfwwQfvBD18YnA7+LIUrtC
OK3EO4L6R4WcmHidBssubqHpQFLuThwsGDZRZfijI2KOh4QvPaaIqW6MKcONE6kRwL+3D14PU5cjiBSZdQNVyTKg8XFokAJW+Yq7IEsvnoG5cAMvX2rVDeI5
4m2QlhQnsLI5RjqCwKhwh2kIvA8eAIMQEzZBhKhXkzFh0OZQSTHeH/mDQEeylBjuihH4qFDo8box8R9wPC+RR4iBGIt44gmTKgqhILk7ZjoGHOK2c8zyjihZ
pGZPROQyDPWMylAR8gWNYNERV9W67oTck49KMojHio0ZtERFH3pk8Gx4EzBxSCUfqAQch0EVi8ePJ6o4fEBbK3HhAb1mK/iO1YVxmp77gjPiGpgHzBOmG57Q
zDQ5LMHgWUFmdFBgeWQ+/yRhQscBT8rEUvC4nklliQtcmwo0ugx/62wc6UbSbFAg45FiaXUo7Ig06QTcCiwUDwkhvpDYEwSLpSxWMDFGOhgaDGgXXs04toE2
wT1AOuQHEIlYBQPvA+d5uI8SqI0pDx2ksbDaYrKgQ5asx5mY9ca0Mw4GSsgvEiLIHOkkII8YiMhpxJBC5yzwl4LB8Fmx9BdsiGAMMfekQHyC2CdnDrMBf8zk
7IS6h1uh6h/YW8V8NMabsZ5BJME8g2RiJGMtdNBijDFZIU8tTOWI8wsmclXCD/CwIFxUd2RRRTACrs0Zp0wWGMMsVyg1mE9kKHv8YeFnuMILByDSREAcXOoY
qcb1kJGiPFB3Mf4NPEwsBRI68iPBmXjvGIW4FHgr+FcMHLIxwcbIFLmuKo5EJKPBHYflGHMe/CMIRNcDz0eSV2cIfoG6J2E89M3jafD84OCge16Vy4bjiuUf
gwMuQv6SYWENEUo89oION7HkmPuNUZ0WJU0regAEkeE3jBw0ZC2ivufHxqKFnAHZc1GgfF6QwkewuVjOg3xnN4MRMP9IAwtODS6WUX8x1iZUXM5fvNNmYlHD
7cEyNicY7KiRzFhcASOQRR5BAUXruUJeYv1Ohfkb+RuwCZvMIkYBtEyHNHkGKCEkCqy2hfmNdRCTgbEphUAYrOKYbiwdWEbIbcPATiY3x9Mn3LtTqEGUYp1T
riL9fGudaZGOXg/pkY9gRoAyGhiqmBJYkVgLDYIR18oManCksVJhi+HlICM4DHEIOQ3kDUY+7kYOxRHGGJAngrIaJqBmoh/AGUHAHfUDP6AqgcpIMayN2sk4
KkXaQnI3XEOYRbLKDL9n5kLHTAOCCOqIMZlkxw1wI8RnO2s6YanOozPA0oH7eELZyaRHTO/EA4AzIigOzmQGup5FjfnN4CqMHnIXZyV2N3GQePMNgfiBgOTS
PBe9Z1wT7xRPBoYLbwJ4NYVQW0KyYO7wypyneJlFDjCoOqHsBjrLYEwRTWQ2JDQWhD6SdK64GQaXchmXQ8+hGJ0lqoD4JM8/vB02LdcYdjUY5FXqFZm9GCA0
iSSSg95Dpa5IbavodwQKwPDHHNOhDAr5gN83831RSLRragoHaiRxMLBaIA5gQ4BDLDH4TS4AzZMqyeRqxw1jhTa+EgUSVmTjGxBXLtUOvEFsEHy0YzLgFgkK
gFFLrbYrHZasOaZOy6BikUMJaeL/cBVBIcGatZpUSWk7k+lDvoKUJMchTrAmg1cs3EhPIX2UaiqicIiigIoWKnd+MOzPuE0h78TaIy8BxyGnQQEZ6BoFHBpL
bcJMyhTPrN8CdlWp5cE0qV7LKDZF3jayRF+wsUnqKtBHOULQkaHQMGe1kweD4qDuk3HBZCgSIdSYhhgTnkXqkvR+VPGESjk9iHA1gvvgZXFkg0jCBA4xLkzB
xjkFxuGa5zwsby5Ki0nyrIIVBAYLQSD1F6IOkwsLYXJqIOvEhyZZPZ6nP234QtBH8nq8YKxBZugWNGYgVywdfsRwuowOgxD1TFHQNHoGwJCMAyIpHvpF8Gqm
1waTQDWeEJxOqA4jZTP+HYNJ7/hqKaqEA7wVVjnOmRHOYFFO1GAId1S422KICpuwtIh0f4NFMZqrm0QMkC1JYqzgXIg7hawDUiN8PWG/hZBHeYLQMAq99lG9
UNndNTM3eqFmRUdfgyiX0nVBlCmJiDDcy6hCFNVvg7dFbimM9RDkNPxDReoYmo2y/VCOI6iKB43SyNHcAARWgLKAQZLhBognz0CuADuFARo7qgXAYInxmHDI
h9DZsK5DOR58Q5RhiZlOKGwMM2Iykh4O/PDOhawr8GLGZaLuX8GKjUGkPpxZbbWikAAUjWBsHdHyCMywc0PYhpN/hEwYKFAQLLswBTpWUWHnrYFqzRAEYdst
bmgqNI30WiiZjVnIYeSz/MFGhWTcKYKhQD3FnVkGZGJkIHgWzoNtCZIB48AUwiRGeZFgtguOuxiY2AxjLPwQ6xstiSJiC121krhiLDG4A4NcWVobZf5BbbG0
WKEiXgrRx6DxykHHpGDWY7Zj+qFyDlb0iFdtqGUbqLEBnECINc1ShrWB12kbNZmCPaH5D8YPWfRYbEFdLHgRYcMBAgh1NDN7PaQcXgtsmpV+Y8myUmYIL9aJ
WHz44E4ROgZwKGg7BgZKcPgjcctYM77FGipAGsgnhJawulBjKpZlpFfHldpmzanQXxqLoQM5CKfTzoztBFYniLPgGVPihcIDvjmUQQb0mgUSIMgMbHjHN0Bw
sSL2N5b/GazChSYd1Hg7RxyNP6BWhjDh5o1FyrouAY0K/w0MurgHGBcoFhIkGDAmNHBtqtgYLJgl0HojXWwUFdkoNsDhigWIkF7IJFZCC9kQpBwMINw33yh9
WxTaKrBTg0uAPMJ4q1iJEcZrb1YUZ5J+4o0CMUk7saKtDO3bqJELVXRhECIWNDG3HRM6wGI2a2sFYXOGYwQGgrwQoMyOH7gyHi2hois0gahbCgURLx7EFRwE
NmmA9kCUAZEkJ1ggY1Qor6j8hHhscOJO52+wVczB9IOPhTkh7xgIAIQgnJi1uA95QTCrhXBfhAwWRzSQZFGhBkNbUV0MyvsgE4wbxMqNhRsVR6Bzhhs7Hjxe
I7EW2QBP44w0EX1YAVjT8cfmmwUpTq71iXU1sNgHq3yH3VlAJbFu6PMMUuX6CDVXXCAAeY0FMXZQQRN/RRgxeAkWfwRpMtmiJ2uAKUCqLi0WsKA8DpeLdb/Y
SDLESiKRndOCOrTYItzPwq0TXKdQG0LrD8jBkHyo8lMXewqFg0w9hsLgiIUNfgniAdPC5IBooUgFzWSG9SImCczHB9huTBXuA3M0FGIQVxxPubRBAtAvwzu9
cLd4YPAf1IJJcMbFaa2cst9Bkh1Hh4GK+QDQmAIvWCH7LCTIxlD7NmoUhL61WUa7Ep4RHZlATClOmfT1hFQKGdLBAPbKFDY7dqOcT3hQgsJg3RTMU2XV8PWN
untJJPawRUjjdWg5BUulyC8o8g05nolMCTV5UCwGyW9I6cN7FsrzQWkNVYTVKNAnBX76CLFjQoLy9jeOJ8QeHA6gXdRlDwpDsCGcARkHVI5MDPZgZfzAR7FM
4pnoylZBcZFZuch3yABqIKlhEcGBMtmsKQwWTDzUp8JRvZcMUf6NmgmxKA0UC77j3TFzIRTQeUL1LWI3/P8sZYH6VF6bqAUV2jBYNZTGCR4OHTG8/5QGwYnB
vEKOUBz74mGVlMzxh5yGMqmZjnuoOVDdkDKZ2sNgcTVyvwZeAp9Gp44UPJH9TzPQ6dh/rx+IXcQ/g0U0qklzJcq1kSgYa7AqLqAwPxqrcaGKB2xG1OzN8LCq
OnsMO9CmWKcbrCUIh3RWcaNCJxPGAws5nEBQjILWpCVkqGTBhABax9oN5pRVS3JWMhHQAMlzUTdCtkrw1TzOoIW/NrhLh7TeKi4DWospWmkw7B3LHzoGVmEs
crw1iodhNAOixp4wEVvHlaQ5NprCmNNWLDwinKFSMiE1OB6htGzwrRC5sVLjvXpDhOROwCQrDsMEehYcTAWrEHwmnoWXXOjWhZGrM3HoA4nPHiQgnOAYoT6A
kS2oEfRfx4WhSERQbrCochgwIPxCDrkpVaghd64wWLPUBibb80CWxzDDciEpZjgKYopgyR+eBEt6f6O7Zk1xHQxDO9x2wjU5WFozQPHUZnu3VolVDFF4nyaU
FY59LGPgKGIdxGQ1KvZqn4BZj7mK2BS1xyCsiVkPfsHtMfSLDYCs5ITPKoHnhXmCgGyAmAiFyVCng7EvtPWD1KgIA4Wa0amvhJY8INcWaGuNu4zghu6oqBVk
HUQXd9kU9RN6HrkMnwWqGR6lN9Vygi6BRYuLoLJoXBw+jlLI64L8JqgsnCyJnTY7mp3BbwIuGyMhFeiIjFAm+ayhJXCKg7MtVknLEEWgiASFICbwGz0dUAPo
LmI1qA6Jtqmz8aywC3pmc6tmCwUWFGRyz7a9Jjgu7O+IlEJNCE7YwKnC/lQvHFhtQSmB/dEglsmuK1fGhTpIm2my/Dbt3lBoECKfVUI542GQOLxY8DtUmcEF
GOsnSRAXqGcxMeAjNMfBTeG02NjfIawQ1Qp+DcU1EIUVgu6QVTwxcSjBMwr7mGaUuoJqdnSt8JhQewrKJecfKLFNARuxHozPgBYZ6yAcuwgTf5ANwYkQBIE4
RYSqO+2aoAxqbVXq4WPhRV+m9I1HUj8NlWdI77PIaZm8I4aJLCMGgU8Ya0UGG0xROI4CU0H2tVUFHZoxawNWtg3rvVA/TnNQH4mlRyYXknfjRUOQDUpimKsY
4pJuWacJJ/Uk8grZRjSLwibIrMUXXl/x11gkZBQTCjYc2x1KGGIcoZ3gkWKyGiY+ZFViXaZwyWxeJGAobPAY6weNUmBW1qG+aTHKFV0b42mgD4XatGn90TpB
X4wNEaT2uRAUMS/fFKsjIghyEdO2gyD61afgfYAtA+cH7F94cRttlw5dl25sKxgxb526X8QyEhtlxGtAsxt8VIqijfdDvUgMNdZSZRFLDLnqg1PNhb0K+/Oa
7DFTg8pjJgc72lMYwFC0gkH7AcBp6RrOtL7CZcQJj6FYHF7w28pylWKzG8rWYCemomrI4aajdIm3H98UlSCxlpVo3MRK5Pbg3Q1GcLBb6t2hDYEh4yGSqCpK
AwOXE+pz+UY3ZVsy4Gw2oRorYCvWYq67AWU3h+xbuGWO1L6KQ6jndNRcI1TE/wgAeAWox4HPwxCmERuzWQhfGrAPQd8Vy4C2CvKHgiywnDaXk4T6amrr3WgA
5CPU2cGLkRz0koIsqupjAhUajooEaw3No2aiChL8kVaL9TkEdBZbSaA5Kgq5Bbej+6G7Pm2mx4esiQHoptbJIVC5jqDQoDhkQjZByI3gGoiRU17G1FO9z1bv
B1gnw/hdVcWDtcDpDw6s8E2n8rwoh2B8bPIgemkQCAyaoRBfeAcoPlwdx1SOuSBXLWI2dJfFU0LdhncliPia/GjzgjBa3kQbB8HAugRJJTlvFlQlEHNf8uqg
uHSGoU93FVg9XN9BJ4T7bPjV7kpq0BKQr4iX3fH4HFEovXQ5mSVggZITorcrXn6TFCZ0jGBHIwF0Gww3lkUoMNuDMyi2GJQKEgvON5FwCPR7oH2/KZQ8yb+C
FZLYgrTgkngU+EpCgVPyRanBoAjEDIJcErvsBDZAD0QExNiCHsPRT8upwvMxEPahA2/iG3aeNTUQMpNy4rEgvmPz+EY4wSIlpMG9EZztIO+YGCCMIC4WNJU+
5Q88IwrTVXI8YI8LKg5NYESHsKQrnTSiuQQPHRTKoCmsXwyul2UUj68vKym0ULjzKpzBzeUq2f8HkdwOrZuUIUUucg1I/2nQng1nxZZWjlGG27lAyiPqvBNV
ParlofriDSptB2YzButJ1BqRoco3iictLF0fg0FFCfImo2Vmlc6bCMGB4Q1MZ6HlFSPWPd3wCTTz1dLPaeclY7xYyL1BNQQIAfxhwsU58JQh9OhmjMMbiaTw
IsFoN300tJQQWMM6l8XcKcg4/yCIhS0J8nOJ0K16hPHE/QUtyjBRduXGN12uaJID/gbXILAh0EBgu/VjAFR6m4LBUGVNsFPjqgHpIh+0JwE+SHpEIlpHpx2k
FgJbCTVpUW/Riv/RbcPQQtu4wXVCp0sAcyakSgi4GAP4A5fg2lj0rJAZ+yEsOiTZWPISJ7os4+HIFAv4S338J90uIjoygKOZZLpg8mQXiT7eeBRoM+AVibzC
S7XCU5lgLk0SW/C5InUhw6kMKhhYVhPVlated8vpj9WMZQjLF1G7PcDp4OfbqIkLggUDgQKQu1SoBU7AsH9XS4eBmQBBxcPBv4pIw74iriGWAHfpeYTgM5Ni
Oax0teyMb/mVrmdshSBAaAf+EqJEGv0nYakKfhj2N8cNid9MNgumCKwneg/S0T8hhxC+1k+4p+g/b9C4En03/J6oXgkwGSaXooKT3eHSiUU3oAfCgD/++5lV
eLZJlESgkg6ssHjlzwFjCDYUzk6Vbk6ViUHBrjRGgG9wgUz4yVhmVaXAN4YLJNGh8TUNRiEgec5Gp09BZXqAHGY9WgCUa0gZOmEWDLhvjF/xuHhXJJufYMWE
uxGh0sBIfiMEbBAjOSBIEPoOX7QKybI8cwxC6VV+rkkbAJAmFVleaviJhsBwT7IvZZZEActYSy3jQ739RkhCPd5HyYAKj/oeh83emEiFEwiTB9lCFTGodLP6
bQN3X4g+QaIxVS9Y/map+oWpYwiu8elCZ5oMTW9JkiR/SOirZNUdSgciMOBkxQYeFJ9BHTxULjKc4FOwKDJcZlpUIA34MhjBoqb+UPkEv9lceoqDAXFDRanD
qQpfVFgwfMsOVkrn54DySFavcriw4qUMw9pnSLNN+i/iIZOORdCb8iMcPjS6nyeQVjNhCcForJgtID+P7+BqqWEVDDqWKWRgFjeptRmO5wnzgMpbhcMCSidW
IyzdeF6Y3HBXJyixwUxwp4nYEct6x1AvoiAcxmBDaITfeNksMycinr/7lygy8J/qRqwA6yTwELTWuNgXRSEWE2OKh0xGTGiN5UyPHGzukJ2DDxJ+ChZgD2VA
Vs5UTCBWZUPrE8ih4AsVBIHQCBVHAHJCmYGeAj1DjsR4RfB9IB5C82NsPCQ+A5JQZMCaSRyxNCYtQwT1IZFoc+4tkRo+5ET3PLs2ANDEqOBCCAJ6DETeprYR
OwCLC1pEbA24maCSwlzIDIUOIdGACcJqYEBpI7RQqdZX+Y8z7WIMcStkYGRHHe5Z+I0a+rIQLTLpwgyigRtwYTGVTVsytN5wejTy9qAqmlADdiWASRSOQXNB
fUgpWXTYIcStjuDQh2GqDZ4dGgXUJ4a36FWJ952UuyG3Kj2gwe1kJCfcgSp1zAqsKvCJrKgCvdjoFBDfialFwSwn1Tc28aDlmZn8sCA6AefkUatRImeoHxyV
jNVO93Q46WD0xVOGhhMLA4GeRpV1Y4V2Rsc3rY1AZm+pvrAkKkMHAQVZVIsCcqFXT7hT+Hg2/Y6htMiURIgboGmwU5JtTHKjL9O/J1zv8Gs1ahNbHuIJRZcx
UqylLbQjRyPGKVwqchghaoPRHZuzELwmsM5UChfuAh5IOsY6RIO/xdY5s1KVBuNJ1OXoYe+It6F3EeJo4LVwVisAGqTeFS5ANZEINjGgGhYFZqXB7UtHMl03
ZOCNjDcY5Uo02MKbVjka8CTCIMEiRYsDYPLgxecbNljbiHly7Tfa3HDRhhKJDWfAQJ8QCID2xalUHRiaI4yKTxxeU3suCywtTAcRDMS5wTVKdGXIjVQV4w7G
GiBtRvph2TO6l2jKxxKeyRZLmXLswnaGypnoruGlED6ACQ3xXJN8SpkWNcZM3SMq/R+hSHUNRkO79U2Nm2si8rmpDoZ8BlMgR2PcKjhgZw+MCFjFTRZ8e2sz
RT4sEPvNetBsF9FVLndCiTcUbTaMiXctTb4ByOdK37nCCvTDFYBZGHND5Jsx2OCXg46qBb8FnK0DbuWKaBzFL51mQZK4DlSUQbcqkABYGwgFwfuAm6/d5EkO
xiIoR3WvFGiNQkHChoapiN6WWJewvWDIhpSqS/Y43ZChTsWgdrZ5iBsGDyIbD+6Q6XCmqpqpoUYGOO12LgrqS4jaxIqXySXfPqNwxIvCmoQOtiv9rIU2gOKs
ipknhOVh5yNyT84SIiyz3cqhzgBLDfmWwxcK3zaUz6IOIsH9GOghww1LDGCTDi/A3PTfLkgZgGYW1IqhWuqM8mwHmmYnDwnrW25ANPDEmywIAgKkggwwssAz
TRki4fWYeLPFAO3C6EKvXOCTtN3RAxoYF/iUoFRRzgS0KGYLkW4gBqjNDvps00dWZ3QJoaAwql3A31b5fAZgCohBTWRbTHrMYA8HBcUy3Kp1L2bIeBKgnjKJ
YNOGOFublmyYxCZuyE1ErjL6a07qD2mzMw6wupEr9U2w1Uq3HBqdx5PfcE6HNY1u6ci2CpEDpyiceuQDByiEFbNJA5OBowa+PAkSDo8BfdprG6MTNnFcfwJt
ziUTnLAg3tngb9lc5uG/QDiYVkxlUB52E948PGMdf6PeYJUwrrDRO5WMQkjDwVAk4JLlVtlJCCspa4SlJbY+C8aVlsy4dOz+TUgIEmqwfpra2AS1oXk0Agrx
ApWDAEwZzWnoG7DjYbhgxUbURDIeWALYTlD3NiMXGy8PREfIeThlgbRHH9B8pxUuJcDrQ1/ceBx6rieIm5lHyEgI2UBmCrfhYqIJbYWKOCbhHBGZiUUxmbaR
2aY8xhRAOIVYcDgMq1irCvYu3CjINjQExs6DIRKoA8+kkDFhHS8sghD9Q2CZGSPRijAXnfoyeBg8CdBVG+M3AzHZhOgJ2yogblrptQfj6oQbJtaxAtU3dpQP
1wMZ+QmfdyA+4JODIQ7s0yK7oIO4M73WNjB81YyMwr7EGg6ehoDdIgRgSR2B9IDoA+NhJgEcOCTCAKJQh0Lhr4lpmYTn0OInGoEhz2B/Gsx0WVaTtwwCmyZN
K1m+pjzJ92aXaVjApLl2QppMOvI6/CBoHMz+SJmImBBw7FEeekAXYCC0CfL0eOqYVXbNC146Eb1NsNE7HBnwOwSjGt+YiY/wRQi+OakdDbg6GCQ9LvLUmAAN
LothCXfVWor2biwGWmpEEMAqwSMDX0PztxWSTlijHVMOsF8dHNvw1AidMKTlzWrsG+qtgTwxhDSh4MIBow64Y13uKG+rpEibSVffO9ZR2TKzgawFT2zw7FIS
Ml4q9wZmbjCeD06J6YKWL3MmaGDLSdHxMNCuF+2FgdhjAw5G3bJDHEgCRtCRPGIQqgN/R1wCrFixAx5H7wOtXLaHW0XugfAm0m8YZ3RGuhAsBHpSGRpU1JCc
BTkYE9SJlKALjHtCFwGS7INuk1BMM2QpI/bBr+iZDhxUg2rH1txxXRBOCJhe2IgFnTpD8/6mpLwh/X7Rh1OACSKkrVKQVuGQEGGDG2Zv4TIJyRMgEQCNQgAY
0Fix2PJUGGbTGKBpBXrHUXILwW+DIPNErArayWRsCLiKbpBW3Iw2LaSUwhQFoa+4bijYNR33Y+byGxALi+B5+ElNxLQeFrHnaSjgiBlklAxlDNGkOSAAm1mf
IfPR5Ys9YMgFq3BqABcRmAgsLYghwiGjyh0d7jvIJUSOLPS/0UvIcCYC+ZlqzQBJVgqJChkHbE0wdzi9AG5GSG7KV02OXHAw4WSdHqmKWATF+ojVWGkgx5vQ
EQrZtRREC/WmcoLgHwuGP0npA6th5xdwMMTjEgtvk1HNWNiDKI9CfBoCeFiItDDDdNboA+TVaSiELiTsMEydIluDStvetskQPWNeUZNWJPc0MITBugGpgmM8
gfxinIHKqNIXwYqhBWaiUuCknCRU9PubMOtbJeAMGt1kcB9chixmYzoXE0tgKG7AHIvU4A2pHWizi6VjgKUq9s4kQ7in6Eon5r1jRjcEk3zWYfMVzkdY30W4
25WFD1+EjDN7FaMLKQGHuAK9PasECTMXY+3AAiV+Ndj9WIQ8FTn9kcE6GPnYXa7tQeBU77IkAhciJ1fMZcw6/W2AJgAxHdiDLCpHopH81cH4slQjeClAdaFh
NkFc8ezMIk2dDL7Bs4a4RAVDQgJohadCulQDDBgkGoAIojCAsaW3sUDbAZtrkEnwUcLBUojZATKDCbMIaSEHELb5JK0XxEeqoDP0NXRCfshFF6DZnag24JCK
HE3UOMEmGIYvcsLBLBjCqcCdCNcaOg+DNW3aKNbwIpYjPwJE3SIEoOH+wKAlIVEQxl7qVVYo74F1Q27rRtpVh2AA1nUpNEoPqXDv8EQgNBZ4r9DHSBBNPuqC
uCR9hXJzhfhtZLoh8BeA0exeWGEfC4wfQRCCxkMphjbBAjHdmGvkV3P9ZSsTCZ3WYC10Aj9izJkUkO0gxtCmRRwYvOFUTZdehS6NJPgAzOVQeOC8GmCZ8PNu
YiNDRcR9MyJkMMDhSIxFNYTPp4ESKRgFvk0uVnlZBKceAqTPcKDAFAOn3wjP4DkRe9HSW3YFUKkJTwC6k3UA4RhrWYR7wJ4A3pgqd+hLUG5R6Agg5Ym0wZ3U
2TP8GJvLNLQsRX3lvA6hPrtAi30zNlwR21X8nohV+NtKI7AwhHElvdDDSbj+JqwCghO5tiAWJsBSwBDNiiAKVJYEBzdVkDCLQquAgyasEwA/EU8tFCIMo2yQ
LBjOoEM8prcC0b8Z8IbUIggK2CxoyAjqb87QwhqDvhtcvSjMLFAT8SJw+lDgR7UqOsAHAVnBQ6qMOeO9G2vogVu4oWXFosJfQIgM8MpvsEEr7XzMBBLJOymw
Gey+pT53FBaeXFjlqrkNr4qvteGWRCQlosgRoUGFBeIXugQ7XK7BIoN3hqTsxsESfw3Y4OK0NiYDQEQxcEFlrQ7OO5GnoRMTnbLh04KQnhA+mxma+eDe6fVB
nHUjLRVKIVRNoOY+KLhgnCIaipzZcPMAarWIz+zq8BeuOET4YJx08GsBfmh6D2DElWQQUoLqI1R2tvmGuxPxN1q3I1EDDH8qDXBiXOVCFzYtOBm8FOTMwN93
KBgQrexYnpFVwr5/FE0DOjp031oJAghPRGeCT85CaATDEf6wIHtsVGPMDlIHa76AXzKbIgg32QmaqQEi4QERUXjRUtULbGYT0Ayq21Gu3LqCnIhGY8QQqgEW
oqttdwKupLHPJxUC6JNM+7NlcQimCWXc6OFOcHLBywD/KED5gzZuQ8kPaOD9Yn2kZIQas5WQwOgOzE8yP9iTTeCeRpt10Xxm4DnRarG9Lq91kuYf1hv0HCoI
odYBS7iYo7sRE4ZGBZlKDEqo4h0wcKoIEBYb4cxhAHIipBjeiNaku4VTLaKmwLFLlGa4Q8nfsVKgwsPQpw4IUYHXQZoG3BGsa7FIx0FtQXv0ePYiCDKePxNs
URGngXobq3xolQdH2XTSh0G4IFUX034SPMXA8IAxIajLFxa2cCnppSnqS6cS0isa0KlMk05wc0Pd3Ax7D0Q20gcVLmbCQp2ERbXptY3Zbwy0YV+X1YXnVUL+
JPAjC2gOeHFRVg/AzGgijzxGYAcnVPRGtBzjMGFKwpiAUwoKCOuF7KHoeqx1nEg50ygAqZoI2sEAac5ybCNMAiQ8gzywdJHMnRwlTI3JHMQdoqJFXzToAbWC
42IQzDqprzYGtbF4mDI/D98rgEESD4uceoQKOrUimMCAf3fqeAyEFSxTJlApCXECvpiUhUBxASYkKEsXqr1fRz3WJuK3FVg9QAWADGdAYSNwW4X5CVYfV2DS
vR17NM1lctiIbkBewTeOEFlSIiN5cgQfsHyZS+G7RtxIKwUuD3g0EDJU23PA2ZrB7IkibHGBxYLpxE0WADAIXSdVR6SdWH14mknMGJgJaxvog5mp6S6Y74SC
06gKFYCvh1gTog4wmIA270PubzCRUKc7iboxDY0IU/q6QUfwUXIgsG47/S0BW4BAyMSmyT4DdyIVwCdLm7/Ah8ciF3T+rC5jHVYCkLdtiEtn4OC0eGvikwYM
vGXFpp0EODLVDkOEwpqvpHiYq0iEgEW6xpN2CgMJcJVMkGy4/fIQcDWkXQSL1xbkeoBVwKKpUAXiQgDwwWM5gBYGwxmripk3IALw7K1DeUQYOPyCrQpU2QFH
XQRQhC5I+5eoEEBAEbcIs30qhaHAm001HEIBMcGtrAbMonBS0I7I2QsFB1PXYOgyU5tYVZbk4ZOHcQaesplvWZT0FaPCHD4YUJGpRVAAgLzEJkL5hf5XmLXd
iWFmoJgL26MHVOeApcMO38T1VCMfQ1AiNAwTLDOlDd5+J4EFfZE0I37+h//+T39U/4D/9LURxI/NAb82pftLnz+2lfjbmlC875v/qivkv2Jv/oVjv79D/uHI
/De+T/7VLfmvaLqYX///+lE/ztpfc638K3fNP5mVn52dP36Zev7aO//P7fnlVom/Nibph+5mv0y/P18P7//zL85v/hspJf/K8/7suvkvrMP8V63A/Atj+D19
5V+difw3rfP8F9bHL81g/hX6++W5+llvs/w38aTvm/j8eo/Dv5Wa/5Zx/EvtNv/y2v21Pm8/u8IvtY3Nv7rS/lfkwF8vXfLfMAv5b+CrX7b9Z/ep+dfoqPO7
f351qukqSoziHJ+nGKJ6oiz1ZGClLlae/3Q5XNSRHLdxRmLFT3yqOiNLKG6VN+8qizxVExaG47fGGpqqc4+anbe+q1u3sEA/Ky8mdRFR8VsV/mxTjW9YNFvl
SgeriibV5MdF1HxHpUA/71uoAcdktclUhz+5X+9wPlVn1zuS6mC/fyT2KUjuVqCavNr+/ScHY50vneEfvgmQ22wFkrcKdrIg+zpdYzKrviJSnv03O0uwLYSK
VrLG5VIVW76gm+JslfvsquGqUakcO5WOrSrljQZN+UymStom1rRkLfykwqpZdUI3yx2rDU9i+Vo2K9F+nHd37v5cg7TzusG5npoMIXyxVSRa5WtVtbi7tCge
lHcq/b19qd790sFtnaFjVXWW6VSJ5Kmq8LgRy7l+nP2Df3cSHxuPqEzp88XK219+6cDsbgSN9dDfn8/F/Jg6+33Q++TPU2x9q8w7+0Rdolgsjpu5kFQFe5Xv
dp8dlQXDs2uUs1RpVnHcXsqXo3yXc63kOseqXTzUL4lzqEru7pKjIeZ5vb07BLATzemYlFldF+3HPgtbK3ApqQ8DmwBxv66vq3BxYmjVXglx4m+V5LNVX3/x
8lPFa0E56irk6uNMhv50pdbMgsdsPlDOqXr2dErOLhb7T9U9mliCepwmKyyCqy4nqnLMkr27ns9PdTwC82vnYLc/4kCoZQufwKXVeQQqqO/nEu5RIDaKtjWI
FqhWd1MBc1ezH+N8oc/QOrvw4zaCwgjm9T6OuwaXotrOFI9Cf1aHqxx3NgjZGqbG10xsn1FZjFn1x9l759mEBMJxOvR8qsS1vxLrSp9Plf9WH59OubD7uc/z
5erFGnvWhscTsDSh6b788PF5O0OwROX7uPTDaV8PvudUES9GBUtk3zHK7Ougz7NHX+pihqrI+ev+swOf98rst/Plyu/zb5uN6TYqauXxw7a/+evLRfTjFzeZ
V//d/j8UrK5jYLicxqny/yLdoQrMbjYhGVXcsEzFsKknuIGGBLuVkF0+jgRrLHZPzSGrewV5hcpNs8uAippTIngriXScL272IZ/q3aLT3juQivRsT/f3uJdh
vwNRwPIOFRcHQ3HxalWFJhlt6T9TK6iP9xGsBl1VlpzCmA1g3gdmibvmbgdf+mcMdjhCZ55PBqjjIfjk4o7ZVe5x3ab2B6k163cs6O963NJYzPiHeluMt56n
utZqFOeeadI91J6kWt3Ql3m32ExiyWy1W0MDJ/Jf8ifOnZqXZel4ljBZBFvmc4o7Ymhc3Dcx8QmyumRRZ1rsMJDd6E5iiFSQzjOoNd85fopRWMhsNRLM7ifo
mu7qXzKtfwx3LYLg66fpVzqCxcO6b28Y6bm38caQ5nPagHhCdZLfXdXoXd7e5dKnGyup3Pi8fMYLwg3tqEHeFdmb+urt+5nuoadAvcq4z5//nX44EpfBgh7u
SpKfbhNsL3YUE+kMakjy2vGcmjwzfZyNQB/Pc/g97nWJr+eW09/QbWPcR1NiWR0ptGZUGT/nK+PzUVp9TmfPsKH+FSW/FDNfwRfVas9k5L5cEx9oU+C9/HRt
zGz3UJqUJs21+I26TE43aCP9ds1nfo5D6ld1EwOIcdffL+duIKSq3j0f7ulXe79rX71vZDu9dqb1tB5I54jnK6/23v/9qb6ZtdXeqpvxMaEusVsH1y9XJEvh
d/VzcF+/5pYu2jW05teRAre1yBQRcxEst3AUb2upu30VyImsIatDCQ9WC0jbcOrRImMDXXjI9tyEAYOn9qfUIqXENl6vc5lYO2Zrm1IeQ2ZIXbKFonYYJbsT
XhbZS6+59l5WY8+qniBuEMRmC2xkU9X2j8belB3WT79TPjk183UawNz2VkXMfVImVS1W0tpwNyh1cZq22ty9SA0+2P0BMGi3LXA3zK12Ui17srQ+x/LMuN8U
bM8umU5u6wWgPg9ZvFdXUIsy9QB0h08Rq5pnqhmeerWUfWxxdMEg0VIgSjh6DbKpZMvuekjuQ1OBzVxoaBR3iZqmluVuo1QnxJWlBzY2i1IvuuRWhGoYIVZV
SNtdusKqt4VV9sS7fVxvX7f92o+fXOYXj/p6m8yGIG4Vh/VWTtPYzOYhtETyXTZFM9XF0txnR4qA2j4mNUKj8C37iPzs7jbiIbZBDqPmyC8xKpvOso/d60e2
q7tsyaqQ9uU2LlS9RzZjUodYz766lckyqi9n0pANo/tIxnsHl8pa7lV6hR4C5ofooYcUt9GTVlXUFkWeklTmS94X8ZnKFxtcVI1LDy09+F7cpCtPsZhNFiJ9
TzoEtpBXjPvry5e6ino96jr56HLe5q8+7sI90mWqOwzJtKljpjrKTbKW7H6gFprtXAWcaRwPHn13Ysn1jIt/UBxy/VEp6tWNUz5v20VxCffZXPIcVDdy6mee
8IrZm9w4KLn/mW3NLDvROmPPj/1aqTKl3U5vXqlxpxlddh/aYzzLP2fiV5sa6g/ZrZzk+pDbps/TpFhdop4LJDWhPBvJ1Kp6FuuFZ33dfLmHlnhSclPX22Ln
CjTWTKejkitIq/VwIs3NUVD3bXTqLs464Sqmbh8ro0a6Y2K3ns4u1FX3aKdd0Tr9Ds9I7yQ3XrbuQk6vgZAJ1tSKUvPabfqoXw8FGJthVrtD1n+E5Vjc31Bf
ra7XF+2/yo6VbC+U25et788fzj2XSO+zkzvT6VMujmKbQtSqNnSY/mzjPakbcFWzNzWM2zJsqvsk5+M0G3Z5SRVgLzWbRHb+ZKmRsi5147RP71+UBc9ubry3
WQKbG6nZuPRWdy4T72qi984eUlWNiKQ02wA0z6Z9m7N7RX2qGd5rFvTTPPn58d2me+jPz/j57nuXLz4j+PCXO8e57Xxya+/J3pVZ/FQePevicqyT67rHsdyW
bhWe3CeNDa/liZY+ytme7m4tYsnNy5MTdTrDf15nXdWs1LPH9l46fSLdPm1Stxl84mGTgySppmH9SiyMSKNDTT4E0Vm24kgfGum6lP3SVdRgvYldDHmW1HSq
SMd10MMnuVcYO2VX9a/bW3obqdstScXZB4l0SBSyN64V/dmbPWpVfpGiHn7l5bPRtHnbKM9qXWpNqQ7E896IQ92OkE/s/X59ac2BEL0dtdLd3G40HzftaC8V
YWgQ/AsPU6hHcqHVc2X9+FT4wf0Mm8Iy7o3pbnrWTOztT3JC0cDcshikyFY3Sy6vKzQ7N+1qzBbd6uq1vvuRqaj5i4UFijW8ojCJdSIL7SKVhYK51pfXSu2r
NyWv92xyrNTvD3BAOtY4m6vmh1y6VusaX/0F321c42894/uNuTV/Qt+TRLMHsMht/9qIfnztr9n13qarf9n/5bbuTHnYjBSoHz97OuoVHF/p6ijnh1VuXcTa
S1Pcrr2P69//kHvPLpwvP/6Kr5+c/Bcu8bNd9yT1mVQT9b/849c2/ZVnfj0sUWJ+2k0Ays42rhNVy+z+hlOBz6zQQDlaT7K3famRp9sCWl1jA9MqDW2UI5FP
n9csc4g4ZFOpTKW/5vPXtj50f66v1V2kj51WwnIgqiEjP9zqmy1Mc/eYsQt8VSxLbh/rL+Sqq98LQ9uUVNgnHp9OD2Ldy/q55WH1VR0sHwx1kDbd0leSkB2l
2Eg6215xf2ixnCWrwz2KdYZU6kIt20FBr0OFfYq7xVL62pVd1rONLbb4HufzxonH6Sj8mU/AcDhQKktiOOBgyMG9nu50uuMmjZFazs9mn/dr/2sDZd2S3C7P
FvkgHRhcJ5xOaVnT8ZX5NO+ejN6qe/CwOSz/WOKe49WQ3bm9XhUxzBonCed5e0MOkZS8njbNZpf7EJdMfOlK96TCo0UdUKnCLvsWFT0e0g+Ku91SyMi0aWoa
36SkyiVUm/qt0oayk99GtJS5IuNAoQ91xpVhT92B79FEgnWuu0lIAbVLbgwON2kqRSAEq3ftNMzUj3QwEOqh6Ut9qBM3/FL6wBDJ4T/PBoWLkhSN7iPOwW71
y0DOOH/6WvxFE3p9ucNqbqV+nCLUAurTlHyTJfTx6h7bFfPe4lZewHnfky4GRu3SE8crtf7czkZ7k27iKKfd7dOtYxEHt63H2BAbXevT+o5tYZnPQ/5T+c0q
Y5zqlZurVAqRgQ34bu15WUUiITj6Nc9X8pCPq8qlj2scpTI+TnBehyiCWJ6d3x3tvfxUNEyxts9CdVOZdjaq1Pu1yttcaE9IbA9BL97qwKLzZO3sftSfx65O
DhRqHmmVVfs1p/t0H3WHzsTrhXvtvFt1SBb0p+d+3e/vo59t+nwZTWPIgye3/90qdt0E0EnXJUhGuY5eeNyEU0u2kNSKFlolVmTItjBkh4FZ+rU+sxv7Jofw
2Cb7y/YfDvmyUY78dV5FrjRfoefx9cpFRql8xM2drG1L089Saj0kixVxOxIz4TI97pJ5TjnOk2x3mzQLd4ImGdFE8YnpbYhkRaUkpcFvClUSuHT2GW1FpdTQ
Htdl9IXiZ2mNL06v2iFXrVAY9riwLPdFSp8yLOywp/elvhxFM5/gytfPXzzU26r7lX/5Suo67UDLPVxUlx2NKGgIdP1w4jDGpRRVqeBzd4mSzSmY/Cyy/Gho
tH1iYpYgnxeCpKdl3zFGMMpx9StctJqdWOVCfJKQd44wy1OSSbsSAsSzjb0+LsAs6VUk+wxTwp0chEqFhKNW5rUdcAj4t30XWiDkAieSXk77by4T+UGpqG06
TYVhUVNn++5nU665og7SYw1+EQhDgwzAJWFBWqJJpqpMR/LBcXphi71DOpCJkPI9KVo3kv75+i/sMG+SxBKihudYlJPbFzm71YY7n6BQZmAHL2v0EmdMKlmR
Bqjl3eQ72A9rm3w0x47bE2cCJm2ci/kGsq4yi3boZfNZ7dLRmhxkxaqvJl4qxn7Lnya7bIq3iNalbUoZMOavuwO9Njyu2dwtFCXZ6tVd89EihTZQ1/exzsFH
Wm4xeDu9Ff3Q8h/LEvR1Kcdo7HqUskKFzU3jNxvbK2SY7Y9XqIWhmnTCdVT3y+sqBj1gToJtoZ4iP8kVu91qiphhXVuKy3GjMGG/HDIx0FI0cdbMp9VZjYst
UgPsOFkaBXoaDZZYovmu1cjVy5btxZHHJzD+9cu09N2fry36X0rl8/kL1/r+MBg8slskVx19lka09V4yO2q7ynr+JtU1G/ginngFlwxXKUPHPaughLCFFIPt
gVgKu1M0SewTrxbwNhzd8t4Ai2FS5vq0kbDfX9PWv86S43WU50LylQuNdZWLA63G1JD6pKWkYy3LJVm+nCJteR0TWLtLsbnuvzMFrOKsT7R1n2CUfFhCp2r3
gz2wW/z1Bbs0fznnASx8d8B+DtDRXb76bFEA5kSDheSov/t2LPEoK69zRnk+dbSusqzmfh7YI8lB3ggB3FuSt4gLUUiO3L3l86zqNe8mUIKV/+pTPsXlPw10
UTTjXKdRLK7pCHmxCYWB0TDLB0vqfz6948v+X9/2k8v98ibqEvtI4wNq71z6+ox0/u93CwAxpZomTUiX3pH2OVpn+vrZfvPd89fLpCOymkIuvphsSUW0hkBy
mhX5mpcUDmh7w2g9e/0c7ZR7XgpGd6g820Vc/ZBLgs8ieFrUSv0RTENeDqcXOAQh9Uuk2IWMU6iKYAir+G93Ng+dtIPO53poqkvsLDEZSbc+BNZax6LgE1Ef
lWFDyulEwB5v53Q4hdgLmo+KB2jaO82i0Yyttf5eP64KI6ymQwPNOAFZp01IXGne+yD6EPVcx/+dKQI5+9dKvgck8VJDrXlPu5+kEWw+wR5+AepM0ksvzk+c
ElvKEVLQHRxQNlTKMZz+WKB5GfsmHJ/sAcaxHPdX2FSOIQcXOFxGenugkia1Gr9rt+V4uePkvukycRQLrJT2yc4ffRVpl/XBfRlv1soZAlbJobLVj+UwsiA2
Uu7f8SSxwKG453L0nH4J0gdtIb1VnS/Ap2ai9fZdhLcbLvb6+dr43Z5fPvBnZ9bR/MAk/HkBNMJuoAUxSI2+MOGNlBSUhDfdwhRuu/VIXPMFbliKxu/Uz69r
adVi7dMAlnG+DpapKotHzuBaDdcsH3ZhFQa0Xx5Yx/d0ia+H5LP+8gEJCxWRlyzAZRv0U+BcskbnCHj1SBRSFsu3lCk3qizemssRH2SVQ+V9hIKTEx4bphHa
2aiUSTZrZVHaSpMHnww0OWvEoGERqjMrmtXn5OSIyvfBm3wWGyxNFlEr5uLGTpMCCGNbFvBz2RTVJhalNBLtfCWHFvpx4NrElxtLXkvHCNs52tNFhrufyUsf
J8IwSn39/pSilakVfx4wU5bfTLQig7TeaHjrP9s6DlTv68VYlJUf9Nc2wlO0ekr/OAbWpAFqZH2n5TaF7KHep7On4VSEGMhS2uZoInQpsj7R/n0poJNLbFTJ
b5s/sijo9qALpClOUWXZFvnUlihgKvJgBaG8jttGoWvElgGl7ZxEg9JW0RPUF5g/yV2QxNinHkIKQSk20tuxm560my5h3V9XkFY2Z/24DuddRKDU+o46JpNW
vnMul0Zt15AypcMkigS7/ulIKpbDUwlaVupM0hJjwkuIzTm6zdU97Mo8VPLI/btZm9IPSkH/si99PcE/fvnaW14UYTjNL+VtkylCe/L4xOzSlptvGkpHlqiJ
pM+uMNqHOZF7WhJzOBBwF3khS7AlM8UF/FUZ9CsnSCJJIGpWZT9ZAxbTwjLKmV75NIpsCa+xZd+OdVHQN8HO5wsXWoUFMnPWGrlG0ljOZaw3jzULpqJsoq4P
Bu/Kc/Lc98rpqtf3yGGTcx7LhkpLOZZmPkslH8+LdAvHEyQS/asfOT0PyAkwUPJzpzlIkYBUQMJaF0dR0JHyssu3JCuLylanw0MGv5yeBqcrR9bRLR1kT4Jv
paxdDhUtXaOxhkJv8hPtV5yhkHctwaJnNl68e1kURiXKYZVVIYxNabUt2alKrirl8cktSbu+QrROFIMqlPnCDsEUGzfbaaCGJDjJQwbqLiedJB1PkB0icjOv
ddTXm260DK+WJuKgJFF9PrjU/wiknbVNpwqIkxkk9/zpg8p3m4tPeZ94/y4/2Szh+qnQKCs+i6DAA8wJqlNpnCOqBONC98rDmxQQWn6KLcU0HzpX9OpTuptQ
BIQ5y8lH5UOmhB3gwvHnC7uTYO/byDpN/HyweXJVSJ2YDu5Kv6r2GYh7TJlX5KObWGUfloYSFZUJYkyqqDM5mnso1clH1DRl+B66b+tI/sSkumRFbXOBKssq
e/qahKfisMxLdTKB1NrmQImivrKwWpbqWn1OUSBJWlJiEO1TN3Y+mLzR98xOiLCt5XSwS64ccCbs8j8DYW2b8W2pWeyTt76uK9tgJ4dEeRe7duTdzZopWUBE
/Q0nXlnXazbMMxOYr4HqH5L4/Z30PPa7IkA/jH5fI0rkqNWqUVYI26G3LsuSiSUMvuoZlT140MbyBhq4wASGbt4+P07irDJK9OlDHfUfYq+aaF9yPtpqUabL
OPl08yLaMofqYvqtqp1lRv+REJ9KId5KtmBeIofbQJD6QEzSrclw7b6h7Pv91DcY0lHR/JWOq8/jJev9pEdddowk62zGOetNUMzO6Nl5HC5yUBt7yhE9jjv9
wkWqoohW0DuVFac6VQNF5b2XxiddbSr8P1M9Wnex3c/zV9nPVfbBusjiz/fKWWgJBy732fJL23/pmB+P//HzfRYJKJ+vRLe/Pr9s+tUfP/36yeE/OymdhA3F
zl4/vmx7f/7s4L/px9dP5YQ6MEWpky5ufUk512+pOHKoTRndHFYd1PL+uOkbVdFzp9gLMnjj3TcA0vJ6kMxwCc56NlfR0t33qRwn/27WnX9+fvnhlGr7rFWJ
Rmlbr7yC5VgB62sIk5OouKWTwpYNURC/aoZ4GKO3s7MSL1t0Is2ojy9kKIty0m83hG5SIKmTapfzt1QaY9tJ9ZlcDiLLT+aSM3KXqeQINWw5ko74a4+70TAq
JcnKD0ld3ubdMseWy+78Uj6GAcSOU9R7RKK5l50x0cgjHWUjc8H2QmdgOS7BWR5Ql76EOnwCg0MIUBpw84XvWf0F0BPie+bXfoZni5MRDpPVFEtvTlWjm19J
YnIJSQXqngoH7tv5EqxCSrLxQ0nc2IK9+mEYIhEWO7mkSX+l3mSbthyNWQ8y+3ivwNTPjl5OUprD/nA5tCcXR+vNiQ7j8RAnGkDS3bX/MWOE6mecW6l/kurK
CCje/EDOKb5cgkcZaYrtGdrjVIILQXJ+v6B0hvhRe5CqoIcj5a5T3efHEIl3OQm6KNzwkYyH3XpB/j3ogZ5lPxffpxaTPAD91qpIzoTYyodQOQIFw52r+XHS
PJ5cM52ixSvImDQ+5a/sZkS/g4QGPezr8ZM4PlEvGcZcjJXpqwoi7zkctlZFFWvz5ZR/MX5sCW+iagV4r2pNYij7Yhho7rwLDaFBDPWkUZsB3IzOfiIs+X5h
oe+rVzQl8/qs3uuTkF2FP+TCyDc5TpeWtucr3qoxdiHajFw3r0bcUQOg2glOcyuq7NTs2pgnDygfBGhXEJWOdr25prSQiNsqFxzpiK/q+5wE/KKIGHObCjPO
s7MLxLTFw7Q6D6d1rhOp+mDKnCLEKScLr/RdSD9yomW3ncqwRBNGU85a5xw7S0qsXDUmZDVvYbYcoBkHcWLXj1LCnQhKZN6H6lGQZtpNInb9B+fIPpvyQZjX
cvb/8KU6PvRNZCFL7pabuZiNPv3+Yn93OxyGkJB/DsyRJElzdXycMg5TDlJB6aYc/0ZgSuask/r+eOnru0pI5+LsdIjmOR5rD/CzQpdRpqOtOFVqfb8zCRFi
uJpTzx0U9FfaB+uY6GdR2sfS1XROOd4p+zzWRX0WycW0bDOrQhuBKh/CJdtUYL6/MVLjCdYZHqGQJBWG3W4tEmlrx4qgN6kY8rcN3JNztbwKcTTpdFL6Zjqu
MqPOnlACdR5HYCQVfQHBS9o22nk8buq/ty9nUX215jkPzK8/WUeyppdAR02MlpK7CKbjkjzGIglVe49U7SbnEcuHKnVb4ptwFXKup7jdYy6/fh2QmlCvTR41
e29Ws6V4dxu5Im/tZdv6ysZbOrvQLFeS09V75PasUl2O6T6colDeinp5leSbfAIlUazZnuDHPBXiPk8mxDYCrr7CeqWNswK5UbfL63rJnSG3hZCkAmY0FoM8
J4tR/nDB97tUDqmrx8f6qURUXNA4M//93vJLn+8jf7zCL13t/ffBopkzdwkLaSndYZLxYSAvMIP1pFnf6kIy9PXpTMl+DrqXdxqBfCO7vgRDMfL849QOE4NQ
+tCS2Ek3tVOOxQO9WvJ/2M5ZLlSw+scTIijGc5Q3wzsPpCI6UtPksVb8cz9/WhOxLNv767afHPb19OcGd9+T+VJdNclqc1ZA5vGsuQSfhjOX+bhKlcFsW03h
+e3Cj/RLaukr9GdzK6Unp1zxUiW2HwhFdtlAQWl32nfPqOXZlNN6zh9CV9T85VgHPV0cb369RVZoP1OLOEArrliZDTJdytkQJKAAfHv577KsgKNhZon7C6dl
JRhZfuVuU2UGI9vs3HXsVP6gsV57v35+d8575y+ef885afpb7WmbsJd0vzlX+MBLP9n12SdcqEdx8Y8DjLkpC9oNCq9PrL6dA1QB6UI4EmWbaqBptyKis5db
VGDOk2qaWNkDaRhbFRmpHK6zRj8FNM2mHwEzRDBaJ618KSmg/GY5YBSjSs7oms8OpxHbc6N4lZ7Xb+VN98yzW3+3p/6RRFCWEPlS/uhXth2z7tc/f3LCua6j
3+WUEVB5AYdZV/351ylHVg317q9EiV/7+nJ1/zCS6X5ZUL5/ZQIUzleyG7+U1yYf/tINs+Xe1+v5AKkXrqvlI4TrPvWsng/v+uGIv3rDL107/Z3/L3t9+WTG
5fyf2PRlx5f9f+FHcrahi6C8ir49W+5B793PQd793aW8xxUIXwc8X/kFMPg7arhO8ZgXHMO/3p9fDv3ujHPETzbfTenrcXUpnuicUzLNUU94yoCx2V+lsrPW
X3ZZpi/JcMzB6sZTqaiz3PXOAHGViPXyXzhubIyjtCYXf2utOPsk2bU3GctszEtyytEBR6rOtbJSDl7dQaJCoz8dSI7rxwg2Ok5GbFEec3Ga80j7+2Tn1/57
WLopTk+m09f9PznmqQtHx4aRO8ZgOWWu5X4gfrRry0nH+XSt2mM5W06PfjN/s/Emqmg05823za7YaaHnGpe3AMXn8ZP2fapBpVMDacvGXRfi6qJyKlwBWENh
zaJ0ijVs+0eVVCBldz9SSyUFhYLJp5xWvmD7Nh+W2Vv+8nlDabI7D95VeS4tvzjvTDfw9pRAqace1z7uoqRIeTbMZg15+qnCHWX8GlQqCCZ8dL5lGV3ZVRxq
UlnuS4CMYjywXOqfJ8qrND67aopLR7f9FEjMCh+5qp9cS8PbvReLZ/5wFZcOff163y3/h/h3zI2U2/Z53RBK1FHKoWvnOWE/e8ezqT2FIrf12fVcykbsdpw9
XVvmXkC5P0hi0+eXTf5xPMZ91yfju8vVbof8+AvX+skpB0C2Tw2em2A8tUBUw2w6ObS//uZrGXXjOuVCLihsaEomhzAQZEvx2NJBuVSL8vzGBQrfvO495h12
Z8Aa0i0nmsIQw9eQ6ywfrLFdTtu66d6POnUd/f1dYk3l81SQzdF5NBEL9ttfKpNKw9tlN+V3kiNSGc2u3Nybs47L4685DvXxIO+zMMCCnj0BwOmiEKqLveqr
eiw8Oafi+BOCWPtk9NMDYuDyOh4OlRH6PKl0euxJ0ktu8HCEIBXuVF8FOEdSBoIzME+5Dwbh6pN+M8/ue5RjAeXGkE+gcQvlIu9PO/cwUiIf93Oxpz4f28RV
KI6/bBoVbcRgftULyi43QtJQk4F0qmc4kRcvIcfF+16q/8L/tYaNbPckKX/Y0k21n344Xkr6D2cY/O6EbxVIMpPoY536COeHrWxX0X0nEpE+jy7iQrfiVK6Q
yCv3Uh2lFcAoH6i6K64lBYt8y7MObgn9TGRYa+/dgiwXAQXXZQ/JOIaDk3NM6ikZnx1iolRshu0N1n1SstrJ22wnI7UcMtmnOsCnyrCc1I5sR53ebwh9o5gK
Pcg7l9M5IJ3STA5jlCqaWE4tPuUwrLsUS/WZzNEdO9snjguiL6f2ZD5oKOs9yytVVz/1g8c9UPfKpwqJYF7LJYXzLd1cVB+HN6j5S21ol4F4jjj7nl+va/3y
SQaruajEVN5Acw2744xR7lxVNty8BXDyqRnfnl+CZaAnxTzVtpPr1L5ulV17cTzBLKf/ZmfubSYeiMaF263rVbzTZXkzubi6x4hufJjrtdV1P7caIKTxJHX+
fdWGG2b3dOc9X79+3Hhlx6/sOtVOMqPltfWfbDmnGwx2o+enCH29lbSLKqpcxHh1NJ6imFqNK+0Sq+eawnOfgOmFVc50Chjlg1Murgsg8M165Rr/+HWPcG2H
u+kkt+SjPt5LPlt+eqQusUyJ+6Ty25DTnvSqA5MI1b2dRorgBK5lu8epzGjY0XNyGfVWbTw3ciVO24ez3vYZRCSoNEJ1dciLoskCcgtKzZwGtwA4yeDOPy4+
3RUHszPTDQNNddxuIdm1R5QQLJ4sAVzlfqN2UE4g0N1jmn2Atyh1srQv6wFYLPfcoVCd9Va6rE69ULKKCs168DQTxR5DojjGbdjw+QSLvii0xnkIhO3mL9uX
PoPRVju3ubbeXAo6P87QcQLpSsw7uP1T7UjO45rqS13SsdMZ6K7BPof1lM/T7iAZhqQVYP+ZSjVxQWpKdTMt0X486e1C1U+63pLPVzJLSRuWU6csYTuBK+pZ
dO1aJ9TrULHccme4aZIhTMX5tlVVqfpR6z9PyfHmCIuzz2jka2l13klut6lOWzaqicX1Us+avANQmP3jgoyt8qvyuFA16aAYnPVPi+ngz1X42wrmC4rzBZfz
3bVPvs6+yPZyesK0B45h/djC3w7O+vSCyETFnbBQMy5smDmeIiNaxs2BUaGIXIdSQ6nsbUNNZdlvRVztHlGJjKQq9byhE/eE4crGv7sjkCvfd6eiZtaAk72T
TyUBtYIy/1MtvXn8IPmpT+dWQQpzLt+6Pt6WU2ipHCVd4LCnOOd0cS2t0WmYVz15kogXne4/W0I4P2Ursyq1iGa3QrWDfEKYJM2Ag/zHdJTpdQ2nmzBdHUg0
VrLaGf5xa8opzLuc7+aqzEdzmK+N67UvG0zfHGO0/5C6UH7tFwBqCVXg6do+T1vwHMtpxVcXWcquE6sZLFlR6vq4JZOU9lRMre2pgrhSve46o76IJ3LEehox
0U+WzOcdz1QfwJjEhYI/tkVFeC6acqLUFvvzlanU+dpmiLJgXaJESV5zPhd1EmIWjnsrg7d9nIsMVypr9knUpxyv6w46k7O9ep0d2GJ9GuG4NU81REZ9hJpA
4/t0kdqsSSRgu3KfJMnLfDyU0yUa88szmdL8cvBNS+5PBNOHKoSb1MRiv6B8MgpcAD4xHF1VlVS4RibI2OOlxCyb+McZ0B4IW3cSg8JedT5nTvZiUu5Ly+0/
QJldqhyU/ef1CJ0OLUrWyO8jDWjTllsrxF8WPO9ftzLAe582ngLbTpVYvd7sijzn4+x0ToxL38lZ2KytjtPCROfk09VRbeDWfiUnjHVqLDLH7O89mjdVqip3
1bixdsrAfwo6Te1STiqnYgnks1VZnPxSPdesSK+zClUH6vMULG9Kz1MiZn78B1Jucz7A0nzBdN3K2nLRrVtCx/VniviPDhCKJjtT+5SKFaag3gs9FQbGoZ8H
9rwkKN2uio8yXKuw/XCU0llcWKqraMAp7u/PfG6y9KCdaZ5qsaMAglsvaRFKNI3DM4thYsdpYn9Xm/N4JZPbnKpR5QHoufCYc5+VzjPmueZnOsDMkeWarCdr
7oDetoN6o76+rAzKihdmdhNv6MqHaazHkh3iBydZyMVzyoWlqNp9P9DLpzSilVE1U11FsS6RYu03s20Jz+eUBtXp0LVUH07Nfgzd36neRf3UFUnKFFJsYfWX
tr9kpAqIZlygdH4HBM6n9CH3TXOmT3a+mKyBXPtznv04uZbrp1pOFk3jJTJtKLhf0cFs3Nzu6RxeFyUTZKGffPCrs9opXMsD/HKyidLthdw5jfDayU0+eJmu
Et8MFaxbG3M/RR8e/7kBZa51fzxNFCEGPgvN5UJrAvrWdeoSp+PHG8fdIsWzjQd65Ny/6Xly8bX0/jp1WlwMaL8ObG29nr2sj9OQorOblh1vAijWcjPv/Lcg
YXbDOi1jXeZzTnRdwh9PVx1ae0H23XK8fi54nPYL09TLLQmVRGBSCtJtXWaN+VPePgHCT5kR1Tsi4rU4daE44X08/ZCy8ElLkKl6kpGeOjIqB3bbKamTlQua
XeWovMuA7WMqQJVwheUyvehc2R7xClcBGoLobJfSKS+VQvbfAfr0fJJUHy+GHSpO3LYDozudwbnuuj4NB8teORLltVgujixPkwZ77Ns9RizstHlLFNrF4G2l
DZyc5/yqZ1klvVL5OPDWrH5mdjeP/vyorbzO1EXnOJ2V8i2w3E5JhHQaCg/XilAq03jyUboYkdJbJJ99/qjNlZsfwq2nwcB1jx+GZd7i3s7uotaf3oCuXOna
7GpeSovazY3B4pDcwIC1vAZG17pylISl6wPY1B7ZpaEz/f7X/Sqdszzm3Wc6zZAdDfk8HQvsaNof14uk0oT2WahwgBUT46uboXGyAtbN3JZFrMCR+4bT9SDS
UOcEw5a4nWqnlm/p97PLFhIzNJaeSkVm0qoiIrZqjS77bsvpr5YPYvnLsV+2Pxt+vMzPr6Y0rKVotyNjB7VVP24tT0dQD07WXhwl2Tod6P5Ipw6FNhVPVP26
O5/FrSi1IaGF3WgUjYGL9zQ6bGLTTjSZN3Xl9NdW2r9wvuPp8ofVUJw6r1Q41cRrdi7LTHWJdMJzx8ct/y7rZVQtq5P7T4eEbG4toUQuq6WW17lglnGYT3KM
4cGONink6nYdezzh3H0C9O3Z5XSu/N3+u00VAdUK67XpJ3ueSopS3N2zKV/MrpzM87TYVhNQadHO/FbV2Y9TfGA5jUjJdNOXeDp/6TT1mZe3AVIPAtcZ6h+q
fQC/RH9aYSps735Jgofq1ha7S5MrJxWB/8LtOuzptgeik11v8sh3uPr2gng8P9zU4EBLnk3n8ws05MtFus2n5+vLxc7XLbVvVmk3W/4e6lb7heqcnT/782eX
0annAtkYn4sF6/6hHWf3gSqrSsL2MUddPdkRilypupBKau8vVzvH63O5XBaLpAhXXg5OWMiJdou0THfEdJ9mxX/b1ahvqxzjEYajEQrFyUPmrI2ntPRJBXo+
qU/suyn9hb++O/SHTffHU7+078fVMlyVV5nUTHc1aPS4iZmq6HtqhpJKls6PU7kvn0p6p5AkE/LLOwIw3Mnu8965uXZyf7WW28q+G+3Crtzx5rSek5BXvY48
7rG+ip5m5PXD9e00UNleJZ86uVJgbYk4dU5StINYAmt4dj/IYnFf9HqPcj1Ya8oqUL3nWw04ZbzvZfItq+Ai9cr5MYZkn6qa54By3JBpPYcth5IPQ8vuoXZg
QCLGU1eeUsSWnRdhfyGVjv9cNYvmvlj3sW7hGerO+cENeZeyWPfOd+yeMuuF/qKLPkmPw9wwRhmvevD6/fZZTxHaU/Dm/bXHOffzHKBN6bX9CI5nRzrNtB0P
S+ePn/zSHDnz8vX1Oi69L/m+spIoMwGDWhoESuRTaM2pLRyxVlz6/fkS1ZwgkhAxvEYvxQGVT2Wwn01bDTW/gJHlY05PLrE2nM1Xy3S9tx+//sIR39/Ffk47
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
F8+/8vOvU9c7xqXLmdqlh/l3T9TUPMyZfkJTr0j90oVLXni/K5c4rl1SGJcuV+vmxlEuXRZk5enXo3bTKYzhmTqRi/Mkp/rqiTngDK7+TI3OKZy5cMJfuJzh
Z1ghk6dfWcasC5ckw+qFy4qDjpevAkSFX7k6Uyt4BhO4AjiXLguQfekSVTPrwuViG+mMbREFL3nhcooD9lFb6sRYcmYue7T2/2pO/DN8fWdq7B7Wbj2jGfYo
19UJ3chH63pjSNcuJ14t50uXNU6kV68W/3Z99aosPaYrl6txFE14Fi5cYhXgzmtXaeVdr1zKFADEa1dJJpsXr67GW1y+nCkVTvnSJSvf0HXLwxzYknu+cOmS
87lwqWVeupzBzJb5/CvqIH/hcoLjo0WZ1F67knzvlcvD+tgn9JjzwuNcudTx/Otyn+mMPExqly6ndNLnvHQ5k2uL8erlRJ8+kds+o1swlw9y5ZKl/uvCJYqP
fuFyBkdx6vk+yp9z4vWX0jI9M072VtKrV2XxLFy5PPwsgwSoXrs6E8+Rae7ZV5zXLqkpwcFLV2f675n4y+LrzK9eneFQW5QFT79UwPnCJSoP04WLDFEXLquU
6ulX6hcvZ9pkkKTWa1eP2vyPxpXPzN1l2TpXLmLuPfvqy/+7csnLb79yOeNr9IWBuXKRutsrl4f/n8EeqS71hYvwu164nOKODmG+epWXPXDlcopnUfJyVy4X
201RclwXLm213yuXM/f+FIbvxNxYRKnkwqWveNqVy4oHvX51MXam5H7pItRTz75EmvrZ16n4wRmN4ZJev5KimQuXBTt+/hWff3Wpy7xwOXMuV/sfp7Qb4vOv
M8/y6rzfGZ2fuXzMK5dTusP9+dcpG66kS5ePownyl3mdafdncK99zReXLhf/f7Sm61Rt0KOc2hfn/U7xOwKA+dLVo3iuh3OuF8el5sKOXLmc6YN1+ZNXLldz
OeZ27XIqT9zjpcuY9dIlpnLpcsquu5gz8wx/e1px7kuXi3nfYk2XLg9rI4hG05XL1VxcJ/rqw5he0R6+cDlVx3KifkakVZ99RdF+vXBp8flXXTG2K5dH8eNn
dNcfzndfrN21JLyff52RITtTcvDg/9LDpcsZm/UUDkBJMa9c2qXLo3PFufn3RB72Yr3ZKGS1Fy4PK+ee8HWz4MYuXB6uUxozvHpVy5roX7waIgzy4tUU8NyL
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
bNQqwwQs4frx439NBwyUCEcGAA==
"""

main()
