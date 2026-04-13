import streamlit as st
import pandas as pd
import random
import math
import plotly.graph_objects as go
import json
from supabase import create_client, Client

# --- CONFIGURATION & SECRETS ---
st.set_page_config(page_title="Titan Operations", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- CSS ARCHITECTURE (NATIVE GLASSMORPHISM) ---
def apply_css():
    st.markdown("""
        <style>
        /* Apple System Font Stack */
        .stApp { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        
        /* Frosted Glass Metrics */
        [data-testid="stMetric"] {
            background: rgba(128, 128, 128, 0.05);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 12px;
            padding: 15px 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
            transition: transform 0.2s ease;
        }
        [data-testid="stMetric"]:hover { transform: translateY(-2px); }
        
        /* Clean Tabs */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background: transparent; padding-bottom: 10px; }
        .stTabs [data-baseweb="tab"] { 
            background-color: transparent; 
            border: 1px solid rgba(128, 128, 128, 0.2); 
            border-radius: 8px; 
            padding: 8px 16px; 
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] { background-color: rgba(128, 128, 128, 0.15) !important; border-color: rgba(128, 128, 128, 0.4) !important; }
        
        /* Login Card */
        .login-card { 
            background: rgba(128, 128, 128, 0.05); 
            backdrop-filter: blur(20px); 
            border: 1px solid rgba(128, 128, 128, 0.2); 
            border-radius: 20px; 
            padding: 50px; 
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1); 
        }
        </style>
    """, unsafe_allow_html=True)

# --- PROFESSIONAL COLOR PALETTE ---
CORP_COLORS = ['#0284c7', '#059669', '#d97706', '#dc2626', '#7c3aed', '#4f46e5', '#0891b2', '#0d9488', '#ca8a04', '#e11d48']

# --- CONSTANTS ---
GREEK_TEAMS = {1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta", 5: "Epsilon", 6: "Zeta", 7: "Eta", 8: "Theta", 9: "Iota", 10: "Kappa"}
BASE_MARKET_HEAVY, BASE_MARKET_LIGHT = 15000, 25000
MAX_WEEKS = 12
COST_OVERHEAD, COST_INTEL, INTEREST_RATE, EMERGENCY_PENALTY = 150_000, 25_000, 0.02, 0.05
MAX_DEBT = 15_000_000

FREIGHT_RATES = {
    'Economy (2 Wks)': {'FTL': 1000, 'LTL': 1.50, 'base_lead': 2, 'rel': 0.80},
    'Standard (1 Wk)': {'FTL': 2000, 'LTL': 3.00, 'base_lead': 1, 'rel': 0.90},
    'Express (Instant)': {'FTL': 4000, 'LTL': 6.00, 'base_lead': 0, 'rel': 0.99}
}

# --- HELPERS ---
def calc_freight(qty, mode):
    if qty <= 0: return 0
    ftls, ltls = qty // 1000, qty % 1000
    return min((ftls * FREIGHT_RATES[mode]['FTL']) + (ltls * FREIGHT_RATES[mode]['LTL']), (ftls + 1) * FREIGHT_RATES[mode]['FTL'])

def get_lead_time(mode):
    return FREIGHT_RATES[mode]['base_lead'] + (1 if random.random() > FREIGHT_RATES[mode]['rel'] else 0)

def get_env(week):
    mkt_h, mkt_l, c_met, c_pla = BASE_MARKET_HEAVY, BASE_MARKET_LIGHT, 10, 5
    msg = "Global market conditions are stable."
    if week in [4, 5]:
        msg, mkt_h, mkt_l = "📉 RECESSION: Demand collapsed by 15% globally.", int(mkt_h * 0.85), int(mkt_l * 0.85)
    elif week in [7, 8]:
        msg, c_met, c_pla = "⚠️ SUPPLY SHOCK: Raw material costs have surged.", 15, 8
    return mkt_h, mkt_l, c_met, c_pla, msg

def get_db(table, col='*', eq_col=None, eq_val=None):
    q = supabase.table(table).select(col)
    if eq_col: q = q.eq(eq_col, eq_val)
    return q.execute().data

def has_submitted(tid, week):
    res = supabase.table('pending_decisions').select('team_id').eq('team_id', tid).eq('week', week).execute()
    return len(res.data) > 0

# --- LOGIN ---
apply_css()
if 'role' not in st.session_state: st.session_state.role, st.session_state.team_id = None, None

if st.session_state.role is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<div class='login-card'><h1 style='text-align:center; font-weight:800; margin-bottom:5px;'>Titan Operations</h1><p style='text-align:center; opacity:0.6; margin-bottom:30px;'>Strategic Supply Chain Simulator</p></div>", unsafe_allow_html=True)
        mode = st.radio("Access Portal", ["Student Team", "Instructor Console"], horizontal=True, label_visibility="collapsed")
        
        if mode == "Student Team":
            t_id = int(st.selectbox("Firm Profile", [f"{i} - Team {GREEK_TEAMS[i]}" for i in range(1, 11)]).split(" ")[0])
            pwd = st.text_input("Access Key", type="password")
            if st.button("Initialize Systems", use_container_width=True, type="primary"):
                if get_db('teams', 'password', 'id', t_id)[0]['password'] == pwd:
                    st.session_state.role, st.session_state.team_id = 'team', t_id; st.rerun()
                else: st.error("Authentication Failed")
        else:
            pwd = st.text_input("Master Password", type="password")
            if st.button("Access Control Panel", use_container_width=True, type="primary"):
                if pwd == "admin123": st.session_state.role = 'instructor'; st.rerun()
                else: st.error("Access Denied")
    st.stop()

# --- INSTRUCTOR ---
if st.session_state.role == 'instructor':
    gs = get_db('game_state')[0]
    t_teams = gs.get('total_teams', 10)
    
    with st.sidebar:
        st.title("Admin Console")
        if st.button("Log Out", use_container_width=True): st.session_state.clear(); st.rerun()
        st.markdown("---")
        st.caption("DANGER ZONE")
        if st.button("Hard Reset Simulation"):
            with st.spinner("Reformatting Database..."):
                supabase.table('game_state').update({'current_week': 1, 'status': 'lobby'}).eq('id', 1).execute()
                supabase.table('pending_decisions').delete().neq('team_id', 0).execute()
                supabase.table('ledger').delete().neq('team_id', 0).execute()
                for i in range(1, 11):
                    supabase.table('team_state').update({
                        'cash': 5000000, 'debt': 0, 'quality_index': 1.0, 'metal_qty': 5000, 'plastic_qty': 10000,
                        'heavy_qty': 500, 'light_qty': 500, 'east_heavy_qty': 1000, 'east_light_qty': 1000,
                        'west_heavy_qty': 1000, 'west_light_qty': 1000, 'transit_pipeline': '[]', 'last_revenue': 0, 'wasted_materials': 0,
                        'fac_hours': 5000, 'raw_wh': 40000, 'hub_east_cap': 5000, 'hub_west_cap': 5000, 'transit_limit': 5000
                    }).eq('team_id', i).execute()
            st.rerun()

    st.header(f"Instructor Control Panel - Week {gs['current_week']}")
    
    if gs['status'] == 'lobby':
        st.info("Simulation is in Lobby State. Students are locked out.")
        with st.container(border=True):
            t_teams = st.slider("Participating Teams", 2, 10, t_teams)
            if st.button("Deploy Simulation", type="primary"):
                supabase.table('game_state').update({'status': 'active', 'total_teams': t_teams}).eq('id', 1).execute(); st.rerun()
        st.stop()

    tab_ctrl, tab_data = st.tabs(["⚙️ Game Control", "📈 Global Analytics"])
    
    with tab_ctrl:
        subs = [s['team_id'] for s in get_db('pending_decisions', 'team_id', 'week', gs['current_week'])]
        st.subheader(f"Submission Status: {len(subs)} / {t_teams} Ready")
        
        cols = st.columns(t_teams)
        for i in range(1, t_teams + 1):
            cols[i-1].metric(GREEK_TEAMS[i], "Ready" if i in subs else "Waiting")
            
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Process Next Week", type="primary", use_container_width=True, disabled=(gs['status'] == 'game_over')):
            if len(subs) < t_teams: st.warning("Awaiting final submissions.")
            else:
                with st.spinner("Running Market Engine..."):
                    all_decs = get_db('pending_decisions', '*', 'week', gs['current_week'])
                    env_mkt_h, env_mkt_l, env_cost_met, env_cost_pla, _ = get_env(gs['current_week'])
                    t_states = {t: get_db('team_state', '*', 'team_id', t)[0] for t in range(1, t_teams + 1)}
                    
                    utils, tot_u_h, tot_u_l = {}, 0, 0
                    for dec in all_decs:
                        tid = dec['team_id']
                        if tid > t_teams: continue
                        s = t_states[tid]
                        
                        s['cash'] += dec['net_fin']; s['debt'] = max(0, s['debt'] + dec['net_fin'])
                        capex = (dec['cap_prod']*50) + (dec['cap_wh']*2) + (dec['cap_he']*5) + (dec['cap_hw']*5) + (dec['cap_tr']*10)
                        s['cash'] -= capex
                        s['fac_hours'] += dec['cap_prod']; s['raw_wh'] += dec['cap_wh']; s['hub_east_cap'] += dec['cap_he']; s['hub_west_cap'] += dec['cap_hw']; s['transit_limit'] += dec['cap_tr']
                        s['quality_index'] = float(s['quality_index']) + (dec['rd_spend'] / 250_000.0)
                        
                        u_h = math.exp(-1.5 * (dec['price_h']/100) + 0.3 * math.log(max(dec['mkt_e']+dec['mkt_w'], 1)) + 1.2 * s['quality_index'])
                        u_l = math.exp(-2.5 * (dec['price_l']/100) + 0.2 * math.log(max(dec['mkt_e']+dec['mkt_w'], 1)) + 0.8 * s['quality_index'])
                        utils[tid] = {'u_h': u_h, 'u_l': u_l, 'dec': dec, 's': s, 'cx': capex}
                        tot_u_h += u_h; tot_u_l += u_l

                    for tid, data in utils.items():
                        dec, s = data['dec'], data['s']
                        transit = s['transit_pipeline'] if isinstance(s['transit_pipeline'], list) else json.loads(s['transit_pipeline'])
                        new_t = []
                        
                        # Process Arriving Goods
                        for t in transit:
                            t['weeks_left'] -= 1
                            if t['weeks_left'] <= 0:
                                if t['type'] == 'raw':
                                    space = s['raw_wh'] - (s['metal_qty'] + s['plastic_qty']); inc = t['metal'] + t['plastic']
                                    if inc > space: ratio = space/inc if inc > 0 else 0; s['wasted_materials'] += (inc - space)
                                    else: ratio = 1
                                    s['metal_qty'] += int(t['metal'] * ratio); s['plastic_qty'] += int(t['plastic'] * ratio)
                                elif t['type'] == 'finished_east':
                                    space = s['hub_east_cap'] - (s['east_heavy_qty'] + s['east_light_qty']); inc = t['heavy'] + t['light']
                                    ratio = space/inc if inc > space and inc > 0 else 1
                                    s['east_heavy_qty'] += int(t['heavy'] * ratio); s['east_light_qty'] += int(t['light'] * ratio)
                                elif t['type'] == 'finished_west':
                                    space = s['hub_west_cap'] - (s['west_heavy_qty'] + s['west_light_qty']); inc = t['heavy'] + t['light']
                                    ratio = space/inc if inc > space and inc > 0 else 1
                                    s['west_heavy_qty'] += int(t['heavy'] * ratio); s['west_light_qty'] += int(t['light'] * ratio)
                            else: new_t.append(t)
                        
                        # Procurement
                        plead = get_lead_time(dec['proc_mode'])
                        pcost = calc_freight(dec['buy_metal'] + dec['buy_plastic'], dec['proc_mode'])
                        mcost = (dec['buy_metal'] * env_cost_met) + (dec['buy_plastic'] * env_cost_pla)
                        if plead == 0: s['metal_qty'] += dec['buy_metal']; s['plastic_qty'] += dec['buy_plastic']
                        elif dec['buy_metal'] > 0 or dec['buy_plastic'] > 0: new_t.append({'type': 'raw', 'metal': dec['buy_metal'], 'plastic': dec['buy_plastic'], 'weeks_left': plead})

                        # Manufacturing
                        hrs = s['fac_hours']
                        uh = min(dec['make_heavy'], s['metal_qty'] // 2, s['plastic_qty'] // 2, hrs // 2)
                        s['metal_qty'] -= uh * 2; s['plastic_qty'] -= uh * 2; s['heavy_qty'] += uh; hrs -= (uh * 2)
                        ul = min(dec['make_light'], s['plastic_qty'] // 3, hrs)
                        s['plastic_qty'] -= ul * 3; s['light_qty'] += ul
                        s['last_hours_used'] = s['fac_hours'] - hrs
                        
                        # Shipping
                        tcap = s['transit_limit']
                        t_e = dec['ship_east_heavy'] + dec['ship_east_light']; r_e = tcap / t_e if t_e > tcap else 1
                        seh = min(int(dec['ship_east_heavy'] * r_e), s['heavy_qty']); s['heavy_qty'] -= seh
                        sel = min(int(dec['ship_east_light'] * r_e), s['light_qty']); s['light_qty'] -= sel
                        
                        t_w = dec['ship_west_heavy'] + dec['ship_west_light']; r_w = tcap / t_w if t_w > tcap else 1
                        swh = min(int(dec['ship_west_heavy'] * r_w), s['heavy_qty']); s['heavy_qty'] -= swh
                        swl = min(int(dec['ship_west_light'] * r_w), s['light_qty']); s['light_qty'] -= swl

                        le, lw = get_lead_time(dec['e_mode']), get_lead_time(dec['w_mode'])
                        scost = pcost + calc_freight(seh + sel, dec['e_mode']) + calc_freight(swh + swl, dec['w_mode'])
                        
                        if le == 0: s['east_heavy_qty'] += seh; s['east_light_qty'] += sel
                        elif seh > 0 or sel > 0: new_t.append({'type': 'finished_east', 'heavy': seh, 'light': sel, 'weeks_left': le})
                        if lw == 0: s['west_heavy_qty'] += swh; s['west_light_qty'] += swl
                        elif swh > 0 or swl > 0: new_t.append({'type': 'finished_west', 'heavy': swh, 'light': swl, 'weeks_left': lw})

                        # Sales Engine
                        dh = int(env_mkt_h * (data['u_h'] / tot_u_h)) if tot_u_h > 0 else 0
                        dl = int(env_mkt_l * (data['u_l'] / tot_u_l)) if tot_u_l > 0 else 0
                        
                        seh_sold = min(int(dh/2), s['east_heavy_qty']); s['east_heavy_qty'] -= seh_sold
                        sel_sold = min(int(dl/2), s['east_light_qty']); s['east_light_qty'] -= sel_sold
                        swh_sold = min(int(dh/2), s['west_heavy_qty']); s['west_heavy_qty'] -= swh_sold
                        swl_sold = min(int(dl/2), s['west_light_qty']); s['west_light_qty'] -= swl_sold
                        
                        rev = (seh_sold + swh_sold) * dec['price_h'] + (sel_sold + swl_sold) * dec['price_l']
                        l_rev = max(0, dh - (seh_sold+swh_sold))*dec['price_h'] + max(0, dl - (sel_sold+swl_sold))*dec['price_l']
                        
                        interest = s['debt'] * INTEREST_RATE
                        holding = (s['east_heavy_qty'] + s['east_light_qty'] + s['west_heavy_qty'] + s['west_light_qty']) * 1.0 + (s['metal_qty'] + s['plastic_qty']) * 0.5
                        intel = COST_INTEL if dec['buy_intel'] else 0
                        
                        exp = COST_OVERHEAD + mcost + scost + holding + dec['mkt_e'] + dec['mkt_w'] + dec['rd_spend'] + interest + intel
                        s['cash'] += (rev - exp)
                        if s['cash'] < 0: s['debt'] += (abs(s['cash']) * (1 + EMERGENCY_PENALTY)); s['cash'] = 0

                        supabase.table('team_state').update({
                            'cash': s['cash'], 'debt': s['debt'], 'last_revenue': rev, 'quality_index': s['quality_index'], 
                            'metal_qty': s['metal_qty'], 'plastic_qty': s['plastic_qty'], 'heavy_qty': s['heavy_qty'], 'light_qty': s['light_qty'], 
                            'east_heavy_qty': s['east_heavy_qty'], 'east_light_qty': s['east_light_qty'], 'west_heavy_qty': s['west_heavy_qty'], 'west_light_qty': s['west_light_qty'], 
                            'transit_pipeline': new_t, 'last_hours_used': s['last_hours_used'], 'wasted_materials': s['wasted_materials'], 'has_intel': dec['buy_intel'], 
                            'fac_hours': s['fac_hours'], 'raw_wh': s['raw_wh'], 'hub_east_cap': s['hub_east_cap'], 'hub_west_cap': s['hub_west_cap'], 'transit_limit': s['transit_limit']
                        }).eq('team_id', tid).execute()
                        
                        supabase.table('ledger').insert({
                            'team_id': tid, 'week': gs['current_week'], 'revenue': rev, 'total_exp': exp + data['cx'], 
                            'cash': s['cash'], 'debt': s['debt'], 'lost_sales': l_rev, 'materials': mcost, 'shipping': scost, 
                            'holding': holding, 'marketing': dec['mkt_e']+dec['mkt_w']+intel, 'rd': dec['rd_spend'], 'overhead': COST_OVERHEAD, 'interest': interest, 'capex': data['cx']
                        }).execute()
                        
                    supabase.table('game_state').update({'current_week': gs['current_week'] + 1, 'status': 'active' if gs['current_week'] < 12 else 'game_over'}).eq('id', 1).execute()
                    st.rerun()

    with tab_data:
        df = pd.DataFrame(get_db('ledger'))
        if df.empty: st.info("Analytics will populate after Week 1.")
        else:
            df['Team'] = df['team_id'].map(GREEK_TEAMS)
            df = df[df['team_id'] <= t_teams]
            
            c_states = pd.DataFrame([get_db('team_state', '*', 'team_id', t)[0] for t in range(1, t_teams + 1)])
            c_states['Team'] = c_states['team_id'].map(GREEK_TEAMS)
            c_states['Net'] = c_states['cash'] - c_states['debt']
            
            st.subheader("Global Leaderboard (Net Position)")
            fig_bar = go.Figure(go.Bar(x=c_states['Team'], y=c_states['Net'], marker_color=['#10b981' if v>=0 else '#e11d48' for v in c_states['Net']]))
            fig_bar.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_bar, use_container_width=True, theme="streamlit")
            
            ch1, ch2 = st.columns(2)
            with ch1:
                st.subheader("Revenue Trajectory")
                fig_rev = go.Figure()
                for i, team in enumerate(df['Team'].unique()):
                    tdf = df[df['Team'] == team].sort_values('week')
                    fig_rev.add_trace(go.Scatter(x=tdf['week'], y=tdf['revenue'], mode='lines+markers', name=team, line=dict(color=CORP_COLORS[i % len(CORP_COLORS)], width=3)))
                fig_rev.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig_rev, use_container_width=True, theme="streamlit")
            with ch2:
                st.subheader("Market Share Dominance")
                lw = df[df['week'] == df['week'].max()]
                fig_pie = go.Figure(go.Pie(labels=lw['Team'], values=lw['revenue'], hole=0.4, marker=dict(colors=CORP_COLORS)))
                fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig_pie, use_container_width=True, theme="streamlit")

# --- STUDENT ---
if st.session_state.role == 'team':
    tid = st.session_state.team_id
    gs = get_db('game_state')[0]
    s = get_db('team_state', '*', 'team_id', tid)[0]
    
    with st.sidebar:
        st.title(f"Firm {GREEK_TEAMS[tid]}")
        if st.button("Logout Portal", use_container_width=True): st.session_state.clear(); st.rerun()

    if gs['status'] == 'lobby':
        st.warning("Awaiting Instructor Authorization to begin the simulation.")
        st.stop()

    if gs['status'] == 'game_over' or s['debt'] > MAX_DEBT:
        st.title("Final Executive Audit")
        if s['debt'] > MAX_DEBT: st.error("FIRM INSOLVENT: Debt limits exceeded.")
        else: st.success("Operations Terminated Successfully.")
        
        df = pd.DataFrame(get_db('ledger', '*', 'team_id', tid))
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Net Position", f"${(s['cash'] - s['debt']):,.0f}")
        k2.metric("Total Revenue", f"${df['revenue'].sum() if not df.empty else 0:,.0f}")
        k3.metric("Lost Sales (Stockouts)", f"${df['lost_sales'].sum() if not df.empty else 0:,.0f}")
        k4.metric("Quality Index", f"{s['quality_index']:.2f}")
        
        st.subheader("Complete Financial Ledger")
        st.dataframe(df.set_index('week'), use_container_width=True)
        st.stop()

    if has_submitted(tid, gs['current_week']):
        st.info(f"### Strategy Locked for Week {gs['current_week']}.")
        st.write("Awaiting competitor actions and global market resolution.")
        st.stop()

    with st.sidebar:
        env_h, env_l, c_met, c_pla, env_msg = get_env(gs['current_week'])
        st.caption(f"Fiscal Quarter: Wk {gs['current_week']}/12")
        with st.form("strategy_input"):
            with st.expander("1. Pricing Strategy", expanded=True):
                ph = st.slider("Heavy Price ($)", 100, 400, 150)
                pl = st.slider("Light Price ($)", 50, 200, 80)
            with st.expander("2. R&D & Marketing"):
                rds = st.number_input("R&D Invest", min_value=0, value=0, step=10000)
                mke = st.number_input("Mkt (East)", min_value=0, value=10000, step=5000)
                mkw = st.number_input("Mkt (West)", min_value=0, value=10000, step=5000)
                intel = st.checkbox("Market Intel ($25k)", value=True)
            with st.expander("3. Production Control"):
                pmode = st.selectbox("Inbound", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
                bm = st.number_input(f"Metal (${c_met})", min_value=0, value=0, step=500)
                bp = st.number_input(f"Plastic (${c_pla})", min_value=0, value=0, step=500)
                mh = st.number_input("Build Heavy", min_value=0, value=500, step=100)
                ml = st.number_input("Build Light", min_value=0, value=800, step=100)
            with st.expander("4. Network Logistics"):
                st.caption("East Bound")
                emode = st.selectbox("E-Freight", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
                c1, c2 = st.columns(2)
                seh = c1.number_input("Heavy(E)", min_value=0, value=250)
                sel = c2.number_input("Light(E)", min_value=0, value=400)
                st.caption("West Bound")
                wmode = st.selectbox("W-Freight", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
                c3, c4 = st.columns(2)
                swh = c3.number_input("Heavy(W)", min_value=0, value=250)
                swl = c4.number_input("Light(W)", min_value=0, value=400)
            with st.expander("5. Finance & CAPEX"):
                c5, c6 = st.columns(2)
                cap_p = c5.number_input("Add Hrs ($50)", min_value=0, value=0, step=100)
                cap_rw = c6.number_input("Add RawWH ($2)", min_value=0, value=0, step=1000)
                c7, c8 = st.columns(2)
                cap_eh = c7.number_input("Add EHub ($5)", min_value=0, value=0, step=500)
                cap_wh = c8.number_input("Add WHub ($5)", min_value=0, value=0, step=500)
                cap_tr = st.number_input("Add Transit ($10)", min_value=0, value=0, step=500)
                nf = st.number_input("Financing (+/-)", value=0, step=100000)
            
            if st.form_submit_button("EXECUTE STRATEGY", use_container_width=True, type="primary"):
                try:
                    # UPSERT combined with int() casting makes this payload completely bulletproof
                    supabase.table('pending_decisions').upsert({
                        'team_id': int(tid), 'week': int(gs['current_week']), 
                        'price_h': int(ph), 'price_l': int(pl),
                        'rd_spend': int(rds), 'mkt_e': int(mke), 'mkt_w': int(mkw), 
                        'buy_metal': int(bm), 'buy_plastic': int(bp),
                        'make_heavy': int(mh), 'make_light': int(ml), 
                        'ship_east_heavy': int(seh), 'ship_west_heavy': int(swh),
                        'ship_east_light': int(sel), 'ship_west_light': int(swl), 
                        'e_mode': str(emode), 'w_mode': str(wmode),
                        'cap_prod': int(cap_p), 'cap_wh': int(cap_rw), 
                        'cap_he': int(cap_eh), 'cap_hw': int(cap_wh), 
                        'cap_tr': int(cap_tr), 'net_fin': int(nf), 
                        'buy_intel': bool(intel), 'proc_mode': str(pmode)
                    }).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync error. Try again. ({e})")

    st.title("Operations Command Center")
    if "RECESSION" in env_msg or "SHOCK" in env_msg: st.error(env_msg)
    else: st.info(env_msg)
    
    t1, t2, t3, t4 = st.tabs(["Telemetry", "Logistics Map", "Industry Rules", "Case Briefing"])
    
    with t1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Treasury", f"${s['cash']:,.0f}")
        c2.metric("Total Debt", f"${s['debt']:,.0f}")
        c3.metric("Quality Score", f"{s['quality_index']:.2f}")
        c4.metric("Factory Utilization", f"{(s['last_hours_used']/s['fac_hours']*100 if s['fac_hours']>0 else 0):.1f}%")
        
        df = pd.DataFrame(get_db('ledger', '*', 'team_id', tid))
        if not df.empty:
            cg1, cg2 = st.columns([1.5, 1])
            with cg1:
                st.subheader("Revenue vs Stockout Erosion")
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df['week'], y=df['revenue'], name="Revenue", mode="lines+markers", line=dict(color="#0284c7", width=3)))
                fig1.add_trace(go.Scatter(x=df['week'], y=df['lost_sales'], name="Lost Sales", mode="lines+markers", line=dict(color="#e11d48", width=3)))
                fig1.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig1, use_container_width=True, theme="streamlit")
            with cg2:
                if s['has_intel'] and gs['current_week'] > 1:
                    st.subheader("Competitor Market Share")
                    lw_data = pd.DataFrame(get_db('ledger', 'team_id, revenue', 'week', gs['current_week']-1))
                    lw_data = lw_data[lw_data['team_id'] <= gs.get('total_teams', 10)]
                    fig2 = go.Figure(go.Pie(labels=lw_data['team_id'].map(GREEK_TEAMS), values=lw_data['revenue'], hole=0.4, marker=dict(colors=CORP_COLORS)))
                    fig2.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
                    st.plotly_chart(fig2, use_container_width=True, theme="streamlit")
                else: st.warning("Market Visibility Classified. Intel required.")
            
            st.subheader("Expense Burn")
            fig3 = go.Figure()
            for col, name, clr in [('overhead', 'Fixed Overhead', '#475569'), ('materials', 'COGS', '#059669'), ('shipping', 'Freight', '#4f46e5'), ('marketing', 'S&M', '#ca8a04'), ('holding', 'Holding', '#d97706')]:
                fig3.add_trace(go.Bar(x=df['week'], y=df[col], name=name, marker_color=clr))
            fig3.update_layout(barmode='stack', height=300, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig3, use_container_width=True, theme="streamlit")
            
            st.markdown("---")
            st.subheader("Complete Historical Ledger")
            st.dataframe(df.set_index('week'), use_container_width=True)

    with t2:
        i1, i2, i3, i4 = st.columns(4)
        i1.metric("Raw Metal", f"{s['metal_qty']:,} / {s['raw_wh']:,}")
        i2.metric("Raw Plastic", f"{s['plastic_qty']:,} / {s['raw_wh']:,}")
        i3.metric("FG Heavy (Plant)", f"{s['heavy_qty']:,}")
        i4.metric("FG Light (Plant)", f"{s['light_qty']:,}")
        
        st.markdown("---")
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("East Hub (Heavy)", f"{s['east_heavy_qty']:,} / {s['hub_east_cap']:,}")
        h2.metric("East Hub (Light)", f"{s['east_light_qty']:,} / {s['hub_east_cap']:,}")
        h3.metric("West Hub (Heavy)", f"{s['west_heavy_qty']:,} / {s['hub_west_cap']:,}")
        h4.metric("West Hub (Light)", f"{s['west_light_qty']:,} / {s['hub_west_cap']:,}")
        
        st.markdown("---")
        st.subheader("Active Transit Manifest")
        with st.container(border=True):
            transit = json.loads(s['transit_pipeline']) if isinstance(s['transit_pipeline'], str) else s['transit_pipeline']
            if not transit: st.write("All clear. No assets in transit.")
            else:
                for t in transit:
                    if t['type'] == 'raw': st.info(f"**To Plant ({t['weeks_left']} Wks):** {t['metal']} Metal | {t['plastic']} Plastic")
                    elif t['type'] == 'finished_east': st.info(f"**To East Hub ({t['weeks_left']} Wks):** {t['heavy']} Heavy | {t['light']} Light")
                    elif t['type'] == 'finished_west': st.info(f"**To West Hub ({t['weeks_left']} Wks):** {t['heavy']} Heavy | {t['light']} Light")

    with t3:
        with st.container(border=True):
            st.markdown("""
            ### Core Physics & Rules
            
            **Production Matrix**
            | Product | Input Requirement | Time Required |
            | :--- | :--- | :--- |
            | **Titan Heavy** | 2 Metal, 2 Plastic | 2 Factory Hours |
            | **Titan Light** | 3 Plastic | 1 Factory Hour |

            **Freight Logistics Engine**
            | Carrier Mode | FTL Flat Rate | LTL Unit Rate | Base Lead Time | Delay Probability |
            | :--- | :--- | :--- | :--- | :--- |
            | **Economy** | $1,000 | $1.50 | 2 Weeks | 20% |
            | **Standard** | $2,000 | $3.00 | 1 Week | 10% |
            | **Express** | $4,000 | $6.00 | Instant | 1% |
            
            *(Note: 1 Full Truck Load [FTL] = 1,000 Units)*

            **Demand Generation (MNL)**
            Your market share is calculated as a zero-sum equation against all active firms.
            * **Price:** Direct negative impact. Lowering prices captures volume but destroys margins.
            * **Marketing:** Logarithmic positive impact. Has severe diminishing returns.
            * **R&D:** Linear positive impact. Crucial for B2B Titan Heavy sales.
            
            **Corporate Finance Constraints**
            * Bank interest is charged at **2% weekly** on total debt.
            * If cash drops below zero, a mandatory emergency loan is triggered with a **5% penalty fee**.
            * **Bankruptcy:** Total debt exceeding $15,000,000 triggers immediate corporate seizure.
            """)

    with t4:
        with st.container(border=True):
            st.markdown(f"""
            # Titan Operations: Navigating the Perfect Storm
            
            **Your Mandate**
            You have been installed as the VP of Supply Chain for **Team {GREEK_TEAMS[tid]}**. Your board of directors demands that you stabilize operations, capture maximum market share, and generate elite free cash flow over the next 12-week fiscal quarter.
            
            **The Network Architecture**
            You run a primary manufacturing facility that feeds two regional distribution centers (East Hub and West Hub). Your entire network is governed by hard physical constraints. 
            * If you over-order raw materials, excess inventory is discarded as waste.
            * If you over-produce, finished goods will choke your transit lines and hub capacities. 
            * You must strategically execute **CAPEX** (Capital Expenditure) to upgrade these bottlenecks before you scale.

            **The Looming Market Threats**
            The macroeconomic outlook is grim. Our analysts have flagged two major anomalies:
            
            1.  **Q4/Q5 Demand Contraction (Weeks 4 & 5):** Global recessionary fears are mounting. Expect a massive 15% drop in total available market demand. If you maintain aggressive production targets during this window, your network will bloat with unsold holding costs.
            2.  **Commodity Shock (Weeks 7 & 8):** Geopolitical instability in our primary sourcing regions will cause a violent spike in procurement costs. Metal will jump from \$10 to \$15, and Plastic will jump from \$5 to \$8. Firms that fail to stockpile raw materials prior to Week 7 will see their profit margins instantly erased.
            
            **Victory Condition**
            You are competing directly against the other firms in this lobby. The firm that concludes Week 12 with the highest **Net Position (Cash minus Debt)** wins the market. Do not go bankrupt.
            """)