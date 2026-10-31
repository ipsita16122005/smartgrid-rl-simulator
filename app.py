import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="GRIDBOUND | Energy Chronicles", page_icon="⚡", layout="wide")

# ------------------------- THEME -------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Rajdhani:wght@400;500;600;700&display=swap');
:root { --bg:#0b1020; --panel:#141d32; --panel2:#1b2942; --gold:#f5c96a; --teal:#5de0c1; --muted:#9aabc4; --red:#ff7777; }
html, body, [class*="css"] { font-family:'Rajdhani',sans-serif; }
.stApp { background: radial-gradient(ellipse at top, #172744 0%, #0b1020 58%); color:#eef4ff; }
.block-container { padding-top:1.5rem; max-width:1400px; }
h1,h2,h3 { color:#f5c96a !important; font-family:'Rajdhani',sans-serif !important; font-weight:700 !important; }
.pixel { font-family:'Press Start 2P',monospace; letter-spacing:1px; }
.hero { background:linear-gradient(115deg,#182b48,#172238 65%,#24334c); border:1px solid #344866; border-radius:18px; padding:24px 28px; box-shadow:0 12px 40px #0005; }
.hero-kicker { color:#5de0c1; font-size:13px; letter-spacing:3px; font-weight:700; }
.hero-title { font-family:'Press Start 2P',monospace; color:#f5c96a; font-size:clamp(18px,2.2vw,28px); line-height:1.65; }
.hero-sub { color:#c1cee0; font-size:18px; }
.panel { background:linear-gradient(145deg,#17243b,#111a2c); border:1px solid #2b3c58; border-radius:15px; padding:16px 18px; min-height:110px; }
.stat-label { color:#9aabc4; font-size:13px; letter-spacing:1.5px; text-transform:uppercase; font-weight:700; }
.stat-value { color:#f4f7ff; font-size:30px; font-weight:700; line-height:1.2; }
.stat-foot { color:#5de0c1; font-size:13px; }
.quest { background:#17243b; border-left:4px solid #f5c96a; border-radius:9px; padding:12px 15px; margin:6px 0; }
.small-muted { color:#9aabc4; font-size:14px; }
div.stButton > button { background:linear-gradient(135deg,#f5c96a,#e6a94d); color:#101827; border:0; border-radius:10px; font-weight:800; min-height:44px; }
div.stButton > button:hover { background:#ffe09a; color:#101827; border:0; }
.stSelectbox label, .stSlider label, .stNumberInput label { color:#c8d5e8 !important; font-weight:700; }
div[data-testid="stMetric"] { background:#17243b; border:1px solid #2b3c58; border-radius:12px; padding:12px; }
div[data-testid="stMetricLabel"] { color:#9aabc4; }
div[data-testid="stMetricValue"] { color:#f5c96a; }
hr { border-color:#2b3c58; }
</style>
""", unsafe_allow_html=True)

# ------------------------- SIMULATION -------------------------
HOURS = np.arange(24)
SOLAR_PROFILE = np.array([0,0,0,0,0,2,8,18,30,42,50,56,58,55,48,36,22,9,2,0,0,0,0,0], dtype=float)
DEMAND_PROFILE = np.array([22,20,19,18,18,20,28,35,39,38,36,35,36,38,40,43,48,52,50,44,38,32,28,24], dtype=float)
PRICE_PROFILE = np.array([5,5,5,5,5,5,6,7,8,8,7,6,6,6,7,9,11,12,12,10,8,7,6,5], dtype=float)

def initial_state():
    return {
        "hour": 8, "battery": 55.0, "cash": 5000.0, "total_cost": 0.0,
        "co2": 0.0, "unserved": 0.0, "history": [], "last_message": "Welcome, Commander. Your city is waiting."
    }

if "game" not in st.session_state:
    st.session_state.game = initial_state()

g = st.session_state.game

def values_at(hour):
    # Small deterministic weather variation keeps the demo repeatable.
    solar = SOLAR_PROFILE[hour]
    demand = DEMAND_PROFILE[hour]
    price = PRICE_PROFILE[hour]
    return float(solar), float(demand), float(price)

def apply_action(action, solar, demand, price, battery):
    """One-hour energy dispatch. Power values are treated as kWh for a one-hour step."""
    capacity, max_rate, efficiency = 100.0, 25.0, 0.92
    renewable_used = min(solar, demand)
    surplus = max(0.0, solar - demand)
    deficit = max(0.0, demand - solar)
    charge = discharge = grid_buy = grid_sell = 0.0

    if action == "Charge battery":
        charge = min(surplus, max_rate, (capacity-battery)/efficiency)
        remaining_surplus = surplus - charge
        grid_sell = remaining_surplus
        grid_buy = deficit  # Keep the campus supplied if solar is below demand.
    elif action == "Discharge battery":
        discharge = min(deficit, max_rate, battery)
        grid_buy = deficit - discharge
        grid_sell = surplus
    elif action == "Buy from grid":
        grid_buy = deficit
        grid_sell = surplus
    elif action == "Sell surplus":
        grid_sell = surplus
        grid_buy = deficit
    elif action == "Balanced auto-dispatch":
        if surplus > 0:
            charge = min(surplus, max_rate, (capacity-battery)/efficiency)
            grid_sell = surplus-charge
        else:
            discharge = min(deficit, max_rate, battery)
            grid_buy = deficit-discharge

    new_battery = np.clip(battery + charge*efficiency - discharge, 0, capacity)
    # Grid emissions factor: 0.72 kg CO2 per kWh (illustrative demo assumption).
    cost = grid_buy*price - grid_sell*(price*0.45)
    emissions = grid_buy*0.72
    # Penalize unmet demand heavily; normally grid fills any remaining deficit.
    unmet = max(0.0, deficit-discharge-grid_buy)
    return new_battery, cost, emissions, unmet, charge, discharge, grid_buy, grid_sell, renewable_used

def recommended_action(solar, demand, price, battery):
    surplus, deficit = solar-demand, demand-solar
    if surplus > 2 and battery < 90:
        return "Charge battery"
    if deficit > 2 and battery > 18 and price >= 8:
        return "Discharge battery"
    if deficit > 0:
        return "Buy from grid"
    return "Sell surplus"

def step(action):
    hour = g["hour"] % 24
    solar, demand, price = values_at(hour)
    result = apply_action(action, solar, demand, price, g["battery"])
    battery, cost, emissions, unmet, charge, discharge, buy, sell, renew = result
    g["battery"] = float(battery)
    g["total_cost"] += cost
    g["co2"] += emissions
    g["unserved"] += unmet
    g["cash"] -= cost
    g["history"].append({
        "Hour": f"{hour:02d}:00", "Solar (kWh)": solar, "Demand (kWh)": demand,
        "Price (₹/kWh)": price, "Battery (%)": battery, "Grid buy (kWh)": buy,
        "Grid sell (kWh)": sell, "Charge (kWh)": charge, "Discharge (kWh)": discharge,
        "Cost (₹)": cost, "CO₂ (kg)": emissions
    })
    g["last_message"] = f"{action}: {buy:.1f} kWh bought · {charge:.1f} kWh charged · {discharge:.1f} kWh discharged."
    g["hour"] += 1
    if g["hour"] >= 24:
        g["hour"] = 0
        g["last_message"] += " A new day begins!"
    return result

def run_strategy(kind):
    battery, cost_total, co2_total, unserved_total = 55.0, 0.0, 0.0, 0.0
    for h in range(24):
        solar, demand, price = values_at(h)
        if kind == "Grid only":
            action = "Buy from grid"
        elif kind == "Rule-based":
            # Charge from surplus; discharge when prices are high, otherwise buy.
            if solar > demand and battery < 90:
                action = "Charge battery"
            elif demand > solar and price >= 9 and battery > 15:
                action = "Discharge battery"
            else:
                action = "Buy from grid" if demand > solar else "Sell surplus"
        else:
            action = "Balanced auto-dispatch"
        r = apply_action(action, solar, demand, price, battery)
        battery, cost, emissions, unmet = r[:4]
        cost_total += cost
        co2_total += emissions
        unserved_total += unmet
    return cost_total, co2_total, unserved_total

# ------------------------- HEADER -------------------------
st.markdown("""
<div class="hero">
  <div class="hero-kicker">✦ SEASON 01 · THE POWER AWAKENS ✦</div>
  <div class="hero-title">GRIDBOUND</div>
  <div class="hero-sub">The Energy Chronicles — command the grid, protect the city.</div>
</div>
""", unsafe_allow_html=True)

st.write("")
tab_game, tab_battle, tab_codex = st.tabs(["🗺️  ADVENTURE MAP", "🏆  STRATEGY ARENA", "📖  FIELD GUIDE"])

# ------------------------- ADVENTURE MAP -------------------------
with tab_game:
    solar, demand, price = values_at(g["hour"])
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="panel"><div class="stat-label">☀ Solar generation</div><div class="stat-value">{solar:.0f} <span style="font-size:15px">kWh</span></div><div class="stat-foot">Renewable power available</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="panel"><div class="stat-label">🏙 City demand</div><div class="stat-value">{demand:.0f} <span style="font-size:15px">kWh</span></div><div class="stat-foot">Energy needed this hour</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="panel"><div class="stat-label">🔋 Battery reserve</div><div class="stat-value">{g["battery"]:.0f}<span style="font-size:18px">%</span></div><div class="stat-foot">100% = fully charged</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="panel"><div class="stat-label">⚡ Grid price</div><div class="stat-value">₹{price:.0f}</div><div class="stat-foot">Per kWh · current hour</div></div>', unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("🏰 Your Energy Kingdom")
        st.markdown(f"""
        <div style="background:linear-gradient(180deg,#1d3553,#16243a);border:1px solid #344866;border-radius:16px;padding:18px 18px 14px;">
          <div style="display:flex;justify-content:space-between;color:#9aabc4;font-weight:700;font-size:13px;">
            <span>SECTOR 01 · CAMPUS DISTRICT</span><span>DAY CLOCK · {g['hour']:02d}:00</span>
          </div>
          <div style="font-size:64px;text-align:center;margin:12px 0 2px;">🏫　☀️　🌳</div>
          <div style="text-align:center;color:#f5c96a;font-size:20px;font-weight:700;">The Sunspire Campus</div>
          <div style="text-align:center;color:#9aabc4;font-size:14px;margin-bottom:18px;">A small city. One commander. One living grid.</div>
          <div style="display:flex;justify-content:space-around;text-align:center;gap:8px;">
            <div><div style="font-size:28px;">☀️</div><b>{solar:.0f} kWh</b><div class="small-muted">Solar</div></div>
            <div><div style="font-size:28px;">🔋</div><b>{g['battery']:.0f}%</b><div class="small-muted">Storage</div></div>
            <div><div style="font-size:28px;">🏙️</div><b>{demand:.0f} kWh</b><div class="small-muted">Demand</div></div>
            <div><div style="font-size:28px;">⚡</div><b>Online</b><div class="small-muted">Grid link</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown("**🧭 Current mission**")
        if g["hour"] < 6:
            mission = "Night Watch: keep enough reserve for the morning."
        elif g["hour"] < 12:
            mission = "Solar Surge: capture clean energy while the sun rises."
        elif g["hour"] < 17:
            mission = "Golden Hours: store surplus before evening demand."
        else:
            mission = "Evening Shield: protect the campus from peak prices."
        st.markdown(f'<div class="quest">✦ {mission}</div>', unsafe_allow_html=True)
        st.caption("Illustrative campus scenario. Energy values represent one-hour energy (kWh).")

    with right:
        st.subheader("🎮 Command Center")
        st.markdown('<div class="small-muted">Choose your move for the current hour. The simulation advances when you act.</div>', unsafe_allow_html=True)
        suggestion = recommended_action(solar, demand, price, g["battery"])
        st.markdown(f'<div class="quest">🤖 <b>Grid Advisor suggests:</b> {suggestion}<br><span class="small-muted">A transparent rule-based hint, not a trained RL prediction.</span></div>', unsafe_allow_html=True)
        action = st.selectbox("Select an energy action", ["Balanced auto-dispatch", "Charge battery", "Discharge battery", "Buy from grid", "Sell surplus"], index=0)
        if st.button("⚔️ EXECUTE TURN", use_container_width=True):
            step(action)
            st.rerun()
        if st.button("⏩ Let Grid Advisor play 1 hour", use_container_width=True):
            step(suggestion)
            st.rerun()
        if st.button("🔄 Restart adventure", use_container_width=True):
            st.session_state.game = initial_state()
            st.rerun()
        st.markdown(f'<div class="quest">📜 <b>Latest event</b><br>{g["last_message"]}</div>', unsafe_allow_html=True)

    st.write("")
    st.subheader("📜 Commander Status")
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Net energy cost", f"₹{g['total_cost']:,.0f}")
    m2.metric("Grid CO₂ emissions", f"{g['co2']:.1f} kg")
    m3.metric("Unserved demand", f"{g['unserved']:.1f} kWh")
    m4.metric("Treasury balance", f"₹{g['cash']:,.0f}")
    if g["history"]:
        hist = pd.DataFrame(g["history"])
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=hist["Hour"], y=hist["Solar (kWh)"], name="Solar", line=dict(width=3)), secondary_y=False)
        fig.add_trace(go.Scatter(x=hist["Hour"], y=hist["Demand (kWh)"], name="Demand", line=dict(width=3)), secondary_y=False)
        fig.add_trace(go.Scatter(x=hist["Hour"], y=hist["Battery (%)"], name="Battery %", line=dict(width=2,dash="dot")), secondary_y=True)
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=310, margin=dict(l=10,r=10,t=25,b=10), legend=dict(orientation="h",y=1.12))
        fig.update_yaxes(title_text="Energy (kWh)", secondary_y=False, gridcolor="#293954")
        fig.update_yaxes(title_text="Battery (%)", secondary_y=True, range=[0,100], showgrid=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(hist.tail(8), use_container_width=True, hide_index=True)
    else:
        st.info("Your adventure log is empty. Execute your first turn to start recording the grid's journey.")

# ------------------------- STRATEGY ARENA -------------------------
with tab_battle:
    st.subheader("🏆 Strategy Arena")
    st.markdown("Put three energy-management strategies through the same 24-hour campus day. All results are generated by this simulator.")
    st.markdown("""
    <div class="quest"><b>⚔️ Battle rules</b><br>
    <span class="small-muted">Grid Only buys all deficits · Rule-Based charges surplus and discharges during expensive hours · Balanced Dispatch stores surplus and uses the battery against deficits. These are benchmark policies, not trained RL agents.</span></div>
    """, unsafe_allow_html=True)
    results = []
    for name, kind in [("Grid only","Grid only"),("Rule-based","Rule-based"),("Balanced dispatch","Balanced")]:
        c,e,u = run_strategy(kind)
        results.append({"Strategy":name,"Daily cost (₹)":round(c,2),"CO₂ (kg)":round(e,2),"Unserved demand (kWh)":round(u,2)})
    df = pd.DataFrame(results)
    a,b = st.columns(2)
    with a:
        fig = go.Figure(go.Bar(x=df["Strategy"],y=df["Daily cost (₹)"],text=[f"₹{v:,.0f}" for v in df["Daily cost (₹)"]],textposition="outside"))
        fig.update_layout(title="Daily energy cost",template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=330,margin=dict(t=55,b=10),yaxis_title="₹")
        st.plotly_chart(fig,use_container_width=True)
    with b:
        fig = go.Figure(go.Bar(x=df["Strategy"],y=df["CO₂ (kg)"],text=[f"{v:.1f} kg" for v in df["CO₂ (kg)"]],textposition="outside"))
        fig.update_layout(title="Grid-related CO₂ emissions",template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=330,margin=dict(t=55,b=10),yaxis_title="kg CO₂")
        st.plotly_chart(fig,use_container_width=True)
    st.dataframe(df,use_container_width=True,hide_index=True)
    best = df.loc[df["Daily cost (₹)"].idxmin(),"Strategy"]
    st.success(f"Lowest simulated daily cost in this scenario: {best}. Always inspect emissions and reliability too.")
    st.caption("Model assumptions: 100 kWh battery, 25 kW charge/discharge limit, 92% charging efficiency, ₹/kWh time-of-use prices, and illustrative grid emissions factor of 0.72 kg CO₂/kWh. These are demo assumptions, not live utility data.")

# ------------------------- FIELD GUIDE -------------------------
with tab_codex:
    st.subheader("📖 Field Guide")
    st.markdown("The engineering concepts behind your adventure, explained in game language.")
    with st.expander("🧠 What is the State?"):
        st.write("The state is the information the agent observes before choosing an action: hour, solar generation, campus demand, battery level and electricity price.")
    with st.expander("⚔️ What is an Action?"):
        st.write("An action is the energy decision: charge, discharge, buy, sell or use a dispatch policy. In a more realistic environment, actions can be continuous power set-points.")
    with st.expander("⭐ What is the Reward?"):
        st.write("A possible reward is negative operating cost, minus penalties for emissions and unmet demand. For example: reward = −cost − λ·emissions − μ·unserved_energy. The weights λ and μ express priorities.")
    with st.expander("🔋 Why the battery matters"):
        st.write("The battery moves energy across time. It can absorb midday solar surplus and supply part of the evening demand. Charging and discharging losses and capacity limits are included in this demo.")
    with st.expander("🤖 Where is the actual RL agent?"):
        st.write("This first website is an interactive simulator with transparent rule-based control and benchmark comparisons. To make it genuine RL, the next engineering step is to wrap the dispatch model as a Gymnasium environment, define observations/actions/rewards, train DQN or PPO with Stable-Baselines3, then load the saved model here.")
    with st.expander("🧪 What should we improve next?"):
        st.write("Use real public solar and demand datasets; add forecast uncertainty; add battery degradation; model grid import/export limits; tune the reward function; train and evaluate an RL agent across multiple days and random seeds.")
    st.markdown("---")
    st.markdown("**Project mantra:** ☀️ Generate → 🏙️ Demand → 🔋 Store → 🤖 Decide → 🌱 Optimize")

st.markdown("""
<div style="text-align:center;color:#7185a3;font-size:13px;padding:20px 0 5px;">
GRIDBOUND · EDUCATIONAL SMART GRID SIMULATOR · NOT A REAL-TIME GRID CONTROLLER
</div>
""", unsafe_allow_html=True)
