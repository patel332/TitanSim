import streamlit as st
import pandas as pd
import random
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

# --- CSS ---
def apply_css():
    st.markdown("""
        <style>
        .stApp { background-color: #09090b; color: #f4f4f5; font-family: 'Inter', sans-serif; }
        [data-testid="stSidebar"] { background-color: #09090b; border-right: 1px solid #27272a; }
        [data-testid="stHeader"] { background-color: transparent; }
        .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 1600px; }
        .stat-card { background-color: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 15px; text-align: center; height: 100%; }
        .stat-title { color: #a1a1aa; font-size: 13px; margin-bottom: 5px; font-weight: 500;}
        .stat-value { font-size: 24px; font-weight: 700; color: #f4f4f5; }
        .stat-sub { font-size: 12px; color: #ef4444; margin-top: 5px; }
        .dash-panel { background-color: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 15px; margin-bottom: 15px; height: 100%; }
        .dash-table { width: 100%; border-collapse: collapse; font-size: 14px; background-color: rgba(0,0,0,0.15); }
        .dash-table thead tr { background-color: rgba(255,255,255,0.05); }
        .dash-table th, .dash-table td { padding: 12px 15px; border-bottom: 1px solid #27272a; color: #e2e8f0; text-align: left; }
        .dash-table th { color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px; }
        .dash-table tbody tr:nth-child(even) { background-color: rgba(255,255,255,0.02); }
        .dash-table tbody tr:hover { background-color: rgba(255,255,255,0.05); transition: background-color 0.2s; }
        .dash-table tr:last-child td { border-bottom: none; }
        hr { border-color: #27272a; margin-top: 10px; margin-bottom: 10px;}
        .stSelectbox label { color: #a1a1aa !important; font-size: 13px !important; }
        .case-text { font-size: 15px; line-height: 1.6; color: #d4d4d8; }
        .case-header { color: #f4f4f5; margin-top: 20px; margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE CONSTANTS ---
BASE_MARKET_HEAVY = 15000 
BASE_MARKET_LIGHT = 25000 
MAX_WEEKS = 12

COST_HOLDING_FG = 1.0  
COST_HOLDING_RAW = 0.5 
COST_OVERHEAD = 150_000
COST_INTEL = 25_000

CAPEX_COST_PROD = 50 
CAPEX_COST_WAREHOUSE = 2 
CAPEX_COST_HUB = 5 
CAPEX_COST_TRANSIT = 10 

INTEREST_RATE = 0.02
EMERGENCY_PENALTY = 0.05
MAX_DEBT = 15_000_000

TRUCK_CAPACITY = 1000
FREIGHT_RATES = {
    'Economy (2 Wks)': {'FTL': 1000, 'LTL': 1.50, 'base_lead': 2, 'reliability': 0.80},
    'Standard (1 Wk)': {'FTL': 2000, 'LTL': 3.00, 'base_lead': 1, 'reliability': 0.90},
    'Express (Instant)': {'FTL': 4000, 'LTL': 6.00, 'base_lead': 0, 'reliability': 0.99}
}

GREEK_TEAMS = {
    1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta", 5: "Epsilon",
    6: "Zeta", 7: "Eta", 8: "Theta", 9: "Iota", 10: "Kappa"
}

def calc_freight(qty, mode):
    if qty <= 0: return 0
    ftls = qty // TRUCK_CAPACITY
    ltls = qty % TRUCK_CAPACITY
    exact_cost = (ftls * FREIGHT_RATES[mode]['FTL']) + (ltls * FREIGHT_RATES[mode]['LTL'])
    round_up_cost = (ftls + 1) * FREIGHT_RATES[mode]['FTL']
    return min(exact_cost, round_up_cost) 

def get_actual_lead_time(mode):
    base = FREIGHT_RATES[mode]['base_lead']
    rel = FREIGHT_RATES[mode]['reliability']
    if random.random() > rel:
        return base + 1 
    return base

def get_environment(week):
    msg = "Market conditions are stable."
    m_type = "info"
    mkt_h, mkt_l = BASE_MARKET_HEAVY, BASE_MARKET_LIGHT
    c_met, c_pla = 10, 5

    if week == 3:
        msg = "NEWS: Economists predict a 15% market contraction starting next week. Prepare your cash reserves."
        m_type = "warning"
    elif week in [4, 5]:
        msg = "RECESSION ACTIVE: Total market demand is down 15%. Avoid overproducing."
        m_type = "error"
        mkt_h = int(BASE_MARKET_HEAVY * 0.85)
        mkt_l = int(BASE_MARKET_LIGHT * 0.85)
    elif week == 6:
        msg = "NEWS: Global supply chain disruptions detected. Raw material prices expected to surge next week."
        m_type = "warning"
    elif week in [7, 8]:
        msg = "SUPPLY SHOCK: Metal and Plastic procurement costs have skyrocketed."
        m_type = "error"
        c_met, c_pla = 15, 8

    return mkt_h, mkt_l, c_met, c_pla, msg, m_type

# --- SESSION STATE INIT ---
if 'role' not in st.session_state:
    st.session_state.role = None
if 'team_id' not in st.session_state:
    st.session_state.team_id = None

# --- DB FETCHERS ---
def fetch_game_state():
    res = supabase.table('game_state').select('*').eq('id', 1).execute()
    return res.data[0]

def fetch_team_state(tid):
    res = supabase.table('team_state').select('*').eq('team_id', tid).execute()
    return res.data[0]

def has_submitted(tid, week):
    res = supabase.table('pending_decisions').select('team_id').eq('team_id', tid).eq('week', week).execute()
    return len(res.data) > 0

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# --- LOGIN SCREEN ---
apply_css()

if st.session_state.role is None:
    st.markdown("<h1 style='text-align: center; margin-top:100px;'>Titan Operations</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
        login_type = st.selectbox("Login As:", ["Student Team", "Instructor"])
        
        if login_type == "Student Team":
            team_options = [f"{i} - Team {GREEK_TEAMS[i]}" for i in range(1, 11)]
            t_selection = st.selectbox("Select Competitor Profile", team_options)
            t_id = int(t_selection.split(" ")[0])
            pwd = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True):
                res = supabase.table('teams').select('password').eq('id', t_id).execute()
                if res.data and res.data[0]['password'] == pwd:
                    st.session_state.role = 'team'
                    st.session_state.team_id = t_id
                    st.rerun()
                else:
                    st.error("Incorrect Password")
        else:
            pwd = st.text_input("Instructor Password", type="password")
            if st.button("Login", use_container_width=True):
                if pwd == "admin123":
                    st.session_state.role = 'instructor'
                    st.rerun()
                else:
                    st.error("Access Denied")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# --- INSTRUCTOR DASHBOARD & ENGINE ---
if st.session_state.role == 'instructor':
    st.title("Instructor Control Panel")
    if st.button("Log Out"):
        st.session_state.clear()
        st.rerun()
        
    game_state = fetch_game_state()
    current_week = game_state['current_week']
    status = game_state['status']
    total_teams = game_state.get('total_teams', 10)
    
    st.markdown(f"### Current Week: {current_week} | Status: {status.upper()}")
    
    if status == 'lobby':
        st.warning("The game is currently in the Lobby. Students cannot submit decisions yet.")
        st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
        st.markdown("### Simulation Initialization")
        selected_teams = st.number_input("Number of Participating Teams", min_value=2, max_value=10, value=total_teams)
        if st.button("Start Game", type="primary"):
            supabase.table('game_state').update({'status': 'active', 'total_teams': selected_teams}).eq('id', 1).execute()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    if status == 'game_over':
        st.error("The simulation has concluded.")
        st.stop()
        
    subs = supabase.table('pending_decisions').select('team_id').eq('week', current_week).execute().data
    sub_ids = [s['team_id'] for s in subs]
    
    st.write(f"**Teams Ready: {len(sub_ids)} / {total_teams}**")
    cols = st.columns(total_teams)
    for i in range(1, total_teams + 1):
        color = "🟢 Ready" if i in sub_ids else "🔴 Waiting"
        cols[i-1].markdown(f"<div style='font-size:12px; text-align:center;'>{GREEK_TEAMS[i]}<br>{color}</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    col_run, col_stop = st.columns(2)
    with col_run:
        if st.button("Process Turn for All Teams", type="primary", use_container_width=True):
            with st.spinner("Processing Global Market Engine..."):
                all_decs = supabase.table('pending_decisions').select('*').eq('week', current_week).execute().data
                if len(all_decs) == 0:
                    st.error("No teams have submitted data!")
                    st.stop()
                    
                env_mkt_h, env_mkt_l, env_cost_met, env_cost_pla, _, _ = get_environment(current_week)
                
                team_states = {}
                for t in range(1, total_teams + 1):
                    team_states[t] = fetch_team_state(t)
                
                utilities = {}
                total_u_h, total_u_l = 0, 0
                
                # PASS 1: Calculate Global Utility Denominators
                for dec in all_decs:
                    tid = dec['team_id']
                    if tid > total_teams: continue
                    state = team_states[tid]
                    
                    if dec['net_fin'] < 0:
                        repay = min(abs(dec['net_fin']), state['debt'])
                        state['debt'] -= repay
                        state['cash'] -= repay
                    else:
                        state['debt'] += dec['net_fin']
                        state['cash'] += dec['net_fin']
                        
                    capex = (dec['cap_prod']*CAPEX_COST_PROD) + (dec['cap_wh']*CAPEX_COST_WAREHOUSE) + (dec['cap_he']*CAPEX_COST_HUB) + (dec['cap_hw']*CAPEX_COST_HUB) + (dec['cap_tr']*CAPEX_COST_TRANSIT)
                    state['cash'] -= capex
                    state['fac_hours'] += dec['cap_prod']
                    state['raw_wh'] += dec['cap_wh']
                    state['hub_east_cap'] += dec['cap_he']
                    state['hub_west_cap'] += dec['cap_hw']
                    state['transit_limit'] += dec['cap_tr']
                    
                    state['quality_index'] = float(state['quality_index']) + (dec['rd_spend'] / 250_000.0)
                    state['has_intel'] = dec['buy_intel']
                    
                    u_h = math.exp(-1.5 * (dec['price_h']/100) + 0.3 * math.log(max(dec['mkt_e']+dec['mkt_w'], 1)) + 1.2 * state['quality_index'])
                    u_l = math.exp(-2.5 * (dec['price_l']/100) + 0.2 * math.log(max(dec['mkt_e']+dec['mkt_w'], 1)) + 0.8 * state['quality_index'])
                    
                    utilities[tid] = {'u_h': u_h, 'u_l': u_l, 'dec': dec, 'state': state, 'capex': capex}
                    total_u_h += u_h
                    total_u_l += u_l
                    
                # PASS 2: Execute Logistics, Manufacturing, and Sales
                for tid, data in utilities.items():
                    dec = data['dec']
                    state = data['state']
                    
                    transit = state['transit_pipeline'] if isinstance(state['transit_pipeline'], list) else json.loads(state['transit_pipeline'])
                    still_in_transit = []
                    
                    for t in transit:
                        t['weeks_left'] -= 1
                        if t['weeks_left'] <= 0:
                            if t['type'] == 'raw':
                                current_raw = state['metal_qty'] + state['plastic_qty']
                                space_left = state['raw_wh'] - current_raw
                                incoming = t['metal'] + t['plastic']
                                if incoming > space_left:
                                    ratio = space_left / incoming if incoming > 0 else 0
                                    state['metal_qty'] += int(t['metal'] * ratio)
                                    state['plastic_qty'] += int(t['plastic'] * ratio)
                                    state['wasted_materials'] += (incoming - space_left)
                                else:
                                    state['metal_qty'] += t['metal']
                                    state['plastic_qty'] += t['plastic']
                            elif t['type'] == 'finished_east':
                                current_e = state['east_heavy_qty'] + state['east_light_qty']
                                space_left = state['hub_east_cap'] - current_e
                                incoming = t['heavy'] + t['light']
                                if incoming > space_left:
                                    ratio = space_left / incoming if incoming > 0 else 0
                                    state['east_heavy_qty'] += int(t['heavy'] * ratio)
                                    state['east_light_qty'] += int(t['light'] * ratio)
                                else:
                                    state['east_heavy_qty'] += t['heavy']
                                    state['east_light_qty'] += t['light']
                            elif t['type'] == 'finished_west':
                                current_w = state['west_heavy_qty'] + state['west_light_qty']
                                space_left = state['hub_west_cap'] - current_w
                                incoming = t['heavy'] + t['light']
                                if incoming > space_left:
                                    ratio = space_left / incoming if incoming > 0 else 0
                                    state['west_heavy_qty'] += int(t['heavy'] * ratio)
                                    state['west_light_qty'] += int(t['light'] * ratio)
                                else:
                                    state['west_heavy_qty'] += t['heavy']
                                    state['west_light_qty'] += t['light']
                        else:
                            still_in_transit.append(t)
                    
                    proc_lead = get_actual_lead_time(dec['proc_mode'])
                    proc_freight_cost = calc_freight(dec['buy_metal'] + dec['buy_plastic'], dec['proc_mode'])
                    mat_costs = (dec['buy_metal'] * env_cost_met) + (dec['buy_plastic'] * env_cost_pla)
                    
                    if proc_lead == 0 and (dec['buy_metal'] > 0 or dec['buy_plastic'] > 0): 
                        state['metal_qty'] += dec['buy_metal']
                        state['plastic_qty'] += dec['buy_plastic']
                    elif dec['buy_metal'] > 0 or dec['buy_plastic'] > 0:
                        still_in_transit.append({'type': 'raw', 'metal': dec['buy_metal'], 'plastic': dec['buy_plastic'], 'weeks_left': proc_lead})

                    hours_available = state['fac_hours']
                    mat_limit_heavy = min(state['metal_qty'] // 2, state['plastic_qty'] // 2)
                    req_heavy = min(dec['make_heavy'], mat_limit_heavy)
                    
                    if req_heavy * 2 <= hours_available:
                        actual_p_h = req_heavy
                        hours_available -= (actual_p_h * 2)
                    else:
                        actual_p_h = hours_available // 2
                        hours_available -= (actual_p_h * 2)
                        
                    state['metal_qty'] -= (actual_p_h * 2)
                    state['plastic_qty'] -= (actual_p_h * 2)
                    state['heavy_qty'] += actual_p_h
                    
                    mat_limit_light = state['plastic_qty'] // 3
                    req_light = min(dec['make_light'], mat_limit_light)
                    
                    if req_light * 1 <= hours_available:
                        actual_p_l = req_light
                        hours_available -= actual_p_l
                    else:
                        actual_p_l = hours_available
                        hours_available -= actual_p_l
                        
                    state['plastic_qty'] -= (actual_p_l * 3)
                    state['light_qty'] += actual_p_l
                    state['last_prod_heavy'] = actual_p_h
                    state['last_prod_light'] = actual_p_l
                    state['last_hours_used'] = state['fac_hours'] - hours_available

                    transit_cap = state['transit_limit']
                    total_east_req = dec['ship_east_heavy'] + dec['ship_east_light']
                    if total_east_req > transit_cap:
                        ratio_e = transit_cap / total_east_req
                        actual_s_e_h = int(dec['ship_east_heavy'] * ratio_e)
                        actual_s_e_l = int(dec['ship_east_light'] * ratio_e)
                    else:
                        actual_s_e_h, actual_s_e_l = dec['ship_east_heavy'], dec['ship_east_light']

                    total_west_req = dec['ship_west_heavy'] + dec['ship_west_light']
                    if total_west_req > transit_cap:
                        ratio_w = transit_cap / total_west_req
                        actual_s_w_h = int(dec['ship_west_heavy'] * ratio_w)
                        actual_s_w_l = int(dec['ship_west_light'] * ratio_w)
                    else:
                        actual_s_w_h, actual_s_w_l = dec['ship_west_heavy'], dec['ship_west_light']

                    actual_s_e_h = min(actual_s_e_h, state['heavy_qty'])
                    state['heavy_qty'] -= actual_s_e_h
                    actual_s_w_h = min(actual_s_w_h, state['heavy_qty'])
                    state['heavy_qty'] -= actual_s_w_h
                    
                    actual_s_e_l = min(actual_s_e_l, state['light_qty'])
                    state['light_qty'] -= actual_s_e_l
                    actual_s_w_l = min(actual_s_w_l, state['light_qty'])
                    state['light_qty'] -= actual_s_w_l

                    lead_e = get_actual_lead_time(dec['e_mode'])
                    cost_e = calc_freight(actual_s_e_h + actual_s_e_l, dec['e_mode'])
                    if lead_e == 0 and (actual_s_e_h > 0 or actual_s_e_l > 0):
                        state['east_heavy_qty'] += actual_s_e_h
                        state['east_light_qty'] += actual_s_e_l
                    elif actual_s_e_h > 0 or actual_s_e_l > 0:
                        still_in_transit.append({'type': 'finished_east', 'heavy': actual_s_e_h, 'light': actual_s_e_l, 'weeks_left': lead_e})

                    lead_w = get_actual_lead_time(dec['w_mode'])
                    cost_w = calc_freight(actual_s_w_h + actual_s_w_l, dec['w_mode'])
                    if lead_w == 0 and (actual_s_w_h > 0 or actual_s_w_l > 0):
                        state['west_heavy_qty'] += actual_s_w_h
                        state['west_light_qty'] += actual_s_w_l
                    elif actual_s_w_h > 0 or actual_s_w_l > 0:
                        still_in_transit.append({'type': 'finished_west', 'heavy': actual_s_w_h, 'light': actual_s_w_l, 'weeks_left': lead_w})

                    total_ship_costs = proc_freight_cost + cost_e + cost_w
                    state['transit_pipeline'] = still_in_transit

                    # Sales
                    share_h = data['u_h'] / total_u_h if total_u_h > 0 else 0
                    share_l = data['u_l'] / total_u_l if total_u_l > 0 else 0
                    
                    demand_h = int(env_mkt_h * share_h)
                    demand_l = int(env_mkt_l * share_l)
                    
                    sold_e_h = min(int(demand_h/2), state['east_heavy_qty'])
                    sold_e_l = min(int(demand_l/2), state['east_light_qty'])
                    sold_w_h = min(int(demand_h/2), state['west_heavy_qty'])
                    sold_w_l = min(int(demand_l/2), state['west_light_qty'])
                    
                    state['east_heavy_qty'] -= sold_e_h
                    state['east_light_qty'] -= sold_e_l
                    state['west_heavy_qty'] -= sold_w_h
                    state['west_light_qty'] -= sold_w_l
                    
                    revenue = (sold_e_h + sold_w_h) * dec['price_h'] + (sold_e_l + sold_w_l) * dec['price_l']
                    lost_sales_h = max(0, demand_h - (sold_e_h + sold_w_h))
                    lost_sales_l = max(0, demand_l - (sold_e_l + sold_w_l))
                    lost_revenue = (lost_sales_h * dec['price_h']) + (lost_sales_l * dec['price_l'])
                    
                    state['cash'] += revenue
                    
                    holding_costs = ((state['east_heavy_qty'] + state['east_light_qty'] + state['west_heavy_qty'] + state['west_light_qty']) * COST_HOLDING_FG) + \
                                    ((state['metal_qty'] + state['plastic_qty']) * COST_HOLDING_RAW)

                    intel_cost = COST_INTEL if dec['buy_intel'] else 0
                    interest = state['debt'] * INTEREST_RATE
                    expenses = COST_OVERHEAD + mat_costs + total_ship_costs + holding_costs + dec['mkt_e'] + dec['mkt_w'] + dec['rd_spend'] + interest + intel_cost
                    
                    state['cash'] -= expenses
                    
                    if state['cash'] < 0:
                        emergency_amt = abs(state['cash'])
                        penalty = emergency_amt * EMERGENCY_PENALTY
                        state['debt'] += (emergency_amt + penalty)
                        state['cash'] = 0

                    supabase.table('team_state').update({
                        'cash': state['cash'], 'debt': state['debt'], 'quality_index': state['quality_index'],
                        'wasted_materials': state['wasted_materials'], 'has_intel': state['has_intel'],
                        'fac_hours': state['fac_hours'], 'raw_wh': state['raw_wh'], 
                        'hub_east_cap': state['hub_east_cap'], 'hub_west_cap': state['hub_west_cap'], 'transit_limit': state['transit_limit'],
                        'metal_qty': state['metal_qty'], 'plastic_qty': state['plastic_qty'], 
                        'heavy_qty': state['heavy_qty'], 'light_qty': state['light_qty'],
                        'east_heavy_qty': state['east_heavy_qty'], 'east_light_qty': state['east_light_qty'],
                        'west_heavy_qty': state['west_heavy_qty'], 'west_light_qty': state['west_light_qty'],
                        'transit_pipeline': state['transit_pipeline'],
                        'last_prod_heavy': state['last_prod_heavy'], 'last_prod_light': state['last_prod_light'],
                        'last_hours_used': state['last_hours_used']
                    }).eq('team_id', tid).execute()
                    
                    supabase.table('ledger').insert({
                        'team_id': tid, 'week': current_week,
                        'revenue': revenue, 'materials': mat_costs, 'shipping': total_ship_costs, 'holding': holding_costs,
                        'marketing': dec['mkt_e'] + dec['mkt_w'] + intel_cost, 'rd': dec['rd_spend'], 'overhead': COST_OVERHEAD,
                        'interest': interest, 'capex': data['capex'], 'total_exp': expenses + data['capex'],
                        'lost_sales': lost_revenue, 'cash': state['cash'], 'debt': state['debt']
                    }).execute()
                    
                new_week = current_week + 1
                new_status = 'active' if new_week <= MAX_WEEKS else 'game_over'
                supabase.table('game_state').update({'current_week': new_week, 'status': new_status}).eq('id', 1).execute()
                st.success("Turn Processed! Week Advanced.")
                st.rerun()
                
    with col_stop:
        if st.button("Stop/End Game Now", use_container_width=True):
            supabase.table('game_state').update({'status': 'game_over'}).eq('id', 1).execute()
            st.rerun()

# --- STUDENT TEAM DASHBOARD ---
if st.session_state.role == 'team':
    tid = st.session_state.team_id
    game_state = fetch_game_state()
    current_week = game_state['current_week']
    status = game_state['status']
    state = fetch_team_state(tid)
    
    st.sidebar.markdown(f"<h2>Team {GREEK_TEAMS[tid]}</h2>", unsafe_allow_html=True)
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()
        
    if status == 'lobby':
        st.warning("The Instructor has not started the simulation yet. Please wait in the lobby.")
        if st.button("Refresh"): st.rerun()
        st.stop()
        
    if status == 'game_over' or state['debt'] > MAX_DEBT:
        st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>End of Term: Executive Summary Report</h1>", unsafe_allow_html=True)
        if state['debt'] > MAX_DEBT:
            st.markdown("<h3 style='text-align: center; color: #ef4444;'>STATUS: INSOLVENT (MAXIMUM DEBT EXCEEDED)</h3>", unsafe_allow_html=True)
        else:
            st.markdown("<h3 style='text-align: center; color: #22c55e;'>STATUS: OPERATIONS COMPLETED</h3>", unsafe_allow_html=True)
            
        st.markdown("<hr style='border-color: #3f3f46; margin-top: 20px; margin-bottom: 30px;'>", unsafe_allow_html=True)
        
        ledger_data = supabase.table('ledger').select('*').eq('team_id', tid).execute().data
        df = pd.DataFrame(ledger_data) if ledger_data else pd.DataFrame()
        
        final_cash = state['cash']
        final_debt = state['debt']
        net_position = final_cash - final_debt
        total_rev = df['revenue'].sum() if not df.empty else 0
        total_exp = df['total_exp'].sum() if not df.empty else 0
        total_lost = df['lost_sales'].sum() if not df.empty else 0

        st.markdown("### I. Macro Financials")
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"<div class='stat-card'><div class='stat-title'>Net Position</div><div class='stat-value'>${net_position:,.0f}</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='stat-card'><div class='stat-title'>Total Revenue</div><div class='stat-value' style='color:#22c55e;'>${total_rev:,.0f}</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='stat-card'><div class='stat-title'>Final Cash</div><div class='stat-value'>${final_cash:,.0f}</div></div>", unsafe_allow_html=True)
        k4.markdown(f"<div class='stat-card'><div class='stat-title'>Final Debt</div><div class='stat-value' style='color:#ef4444;'>${final_debt:,.0f}</div></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c_cost, c_ops = st.columns(2)
        with c_cost:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("<h3 style='margin-top:0;'>II. Total Cost Breakdown</h3>", unsafe_allow_html=True)
            if not df.empty:
                st.markdown(f"""
                <table class="dash-table">
                    <thead><tr><th>Expense Category</th><th style='text-align: right;'>12-Week Total</th></tr></thead>
                    <tbody>
                        <tr><td>Materials (COGS)</td><td style='text-align: right;'>${df['materials'].sum():,.0f}</td></tr>
                        <tr><td>Shipping & Freight</td><td style='text-align: right;'>${df['shipping'].sum():,.0f}</td></tr>
                        <tr><td>Inventory Holding</td><td style='text-align: right;'>${df['holding'].sum():,.0f}</td></tr>
                        <tr><td>Marketing & Intel</td><td style='text-align: right;'>${df['marketing'].sum():,.0f}</td></tr>
                        <tr><td>R&D (Quality)</td><td style='text-align: right;'>${df['rd'].sum():,.0f}</td></tr>
                        <tr><td>Fixed Overhead</td><td style='text-align: right;'>${df['overhead'].sum():,.0f}</td></tr>
                        <tr><td>Debt Interest</td><td style='text-align: right;'>${df['interest'].sum():,.0f}</td></tr>
                        <tr><td>CAPEX (Upgrades)</td><td style='text-align: right;'>${df['capex'].sum():,.0f}</td></tr>
                        <tr style='background-color: rgba(255,255,255,0.05); font-weight: bold;'><td>Total Outflows</td><td style='text-align: right; color: #ef4444;'>${total_exp:,.0f}</td></tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_ops:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("<h3 style='margin-top:0;'>III. Decision Accuracy & Operations</h3>", unsafe_allow_html=True)
            st.markdown(f"""
            <table class="dash-table">
                <thead><tr><th>Metric</th><th style='text-align: right;'>Value</th></tr></thead>
                <tbody>
                    <tr><td>Total Lost Sales (Stock-Out)</td><td style='text-align: right; color: #ef4444;'>${total_lost:,.0f}</td></tr>
                    <tr><td>Wasted Materials (Overflow)</td><td style='text-align: right; color: #ef4444;'>{state['wasted_materials']:,} units</td></tr>
                    <tr><td>Final R&D Quality Index</td><td style='text-align: right; color: #3b82f6;'>{state['quality_index']:.2f}</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("<br><h3 style='margin-top:0;'>IV. Ending Asset Positions</h3>", unsafe_allow_html=True)
            st.markdown(f"""
            <table class="dash-table">
                <thead><tr><th>Asset Location</th><th style='text-align: right;'>Units Remaining</th></tr></thead>
                <tbody>
                    <tr><td>Factory (Raw Materials)</td><td style='text-align: right;'>{(state['metal_qty'] + state['plastic_qty']):,}</td></tr>
                    <tr><td>Factory (Finished Goods)</td><td style='text-align: right;'>{(state['heavy_qty'] + state['light_qty']):,}</td></tr>
                    <tr><td>East Hub (Finished Goods)</td><td style='text-align: right;'>{(state['east_heavy_qty'] + state['east_light_qty']):,}</td></tr>
                    <tr><td>West Hub (Finished Goods)</td><td style='text-align: right;'>{(state['west_heavy_qty'] + state['west_light_qty']):,}</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
        st.markdown("### V. Complete Ledger Export")
        if not df.empty:
            col_dl, _ = st.columns([1, 4])
            with col_dl:
                csv_data = convert_df_to_csv(df)
                st.download_button("Download CSV Audit", data=csv_data, file_name=f'team_{GREEK_TEAMS[tid]}_ledger.csv', mime='text/csv', use_container_width=True)
            st.dataframe(df.set_index('week'), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()
        
    if has_submitted(tid, current_week):
        st.info(f"### Decisions Submitted for Week {current_week}.")
        st.write(f"Waiting for the instructor to process the global turn. Your dashboard will update automatically when Week {current_week + 1} begins.")
        if st.button("Refresh Status"):
            st.rerun()
        st.stop()
        
    # --- ACTIVE GAME UI ---
    env_mkt_h, env_mkt_l, env_cost_met, env_cost_pla, alert_msg, alert_type = get_environment(current_week)
    
    with st.sidebar:
        st.markdown(f"<div style='color: #a1a1aa; margin-bottom:15px;'>Week {current_week} / {MAX_WEEKS}</div>", unsafe_allow_html=True)
        
        with st.form("decision_form"):
            with st.expander("1. Pricing", expanded=True):
                price_heavy = st.slider("Heavy Price ($)", 100, 300, 150, step=5)
                price_light = st.slider("Light Price ($)", 50, 150, 80, step=5)
            
            with st.expander("2. Investment"):
                rd_spend = st.number_input("R&D Investment ($)", min_value=0, step=10000, value=0)
                mkt_e = st.number_input("Mkt Spend (East Hub)", min_value=0, step=5000, value=10000)
                mkt_w = st.number_input("Mkt Spend (West Hub)", min_value=0, step=5000, value=10000)
                buy_intel = st.checkbox("Buy Market Intel ($25k)", value=True)
            
            with st.expander("3. Procurement & Production"):
                proc_mode = st.selectbox("Freight Mode", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
                buy_metal = st.number_input(f"Order Metal (${env_cost_met})", min_value=0, step=500, value=0)
                buy_plastic = st.number_input(f"Order Plastic (${env_cost_pla})", min_value=0, step=500, value=0)
                make_heavy = st.number_input("Produce Heavy", min_value=0, step=100, value=500)
                make_light = st.number_input("Produce Light", min_value=0, step=100, value=800)
            
            with st.expander("4. Outbound Shipping"):
                e_mode = st.selectbox("East Freight Mode", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
                col1, col2 = st.columns(2)
                ship_east_heavy = col1.number_input("Heavy (E)", min_value=0, step=100, value=250)
                ship_east_light = col2.number_input("Light (E)", min_value=0, step=100, value=400)
                w_mode = st.selectbox("West Freight Mode", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
                col3, col4 = st.columns(2)
                ship_west_heavy = col3.number_input("Heavy (W)", min_value=0, step=100, value=250)
                ship_west_light = col4.number_input("Light (W)", min_value=0, step=100, value=400)

            with st.expander("5. Finance & CAPEX"):
                cap_prod = st.number_input("Add Factory Hrs ($50/hr)", min_value=0, step=100)
                cap_wh = st.number_input("Add Raw WH ($2/u)", min_value=0, step=1000)
                cap_he = st.number_input("Add East Hub ($5/u)", min_value=0, step=500)
                cap_hw = st.number_input("Add West Hub ($5/u)", min_value=0, step=500)
                cap_tr = st.number_input("Add Transit ($10/u)", min_value=0, step=500)
                net_financing = st.number_input("Net Financing (+ Borrow / - Repay)", value=0, step=100000)
            
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Submit Week", type="primary", use_container_width=True)
            
            if submitted:
                supabase.table('pending_decisions').insert({
                    'team_id': tid, 'week': current_week,
                    'price_h': price_heavy, 'price_l': price_light,
                    'mkt_e': mkt_e, 'mkt_w': mkt_w, 'rd_spend': rd_spend, 'buy_intel': buy_intel,
                    'buy_metal': buy_metal, 'buy_plastic': buy_plastic, 'proc_mode': proc_mode,
                    'make_heavy': make_heavy, 'make_light': make_light,
                    'ship_east_heavy': ship_east_heavy, 'ship_east_light': ship_east_light, 'e_mode': e_mode,
                    'ship_west_heavy': ship_west_heavy, 'ship_west_light': ship_west_light, 'w_mode': w_mode,
                    'cap_prod': cap_prod, 'cap_wh': cap_wh, 'cap_he': cap_he, 'cap_hw': cap_hw, 'cap_tr': cap_tr,
                    'net_fin': net_financing
                }).execute()
                st.rerun()

    st.markdown("<h2 style='margin-bottom:10px;'>Supply Chain Management Dashboard</h2>", unsafe_allow_html=True)
    if alert_type == "warning": st.warning(alert_msg)
    elif alert_type == "error": st.error(alert_msg)
    else: st.info(alert_msg)

    tab_dash, tab_ops, tab_manual, tab_case = st.tabs(["Executive Dashboard", "Operations & Logistics", "Case Manual", "Business Case"])

    ledger_data = supabase.table('ledger').select('*').eq('team_id', tid).execute().data
    df = pd.DataFrame(ledger_data) if ledger_data else pd.DataFrame()

    with tab_dash:
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.markdown(f"<div class='stat-card'><div class='stat-title'>Cash Balance</div><div class='stat-value'>${state['cash']:,.0f}</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='stat-card'><div class='stat-title'>Total Debt</div><div class='stat-value' style='color:#ef4444;'>${state['debt']:,.0f}</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='stat-card'><div class='stat-title'>Quality Index</div><div class='stat-value' style='color:#3b82f6;'>{state['quality_index']:.2f}</div></div>", unsafe_allow_html=True)
        
        last_exp = df.iloc[-1]['total_exp'] if not df.empty else 0
        last_lost = df.iloc[-1]['lost_sales'] if not df.empty else 0
        
        k4.markdown(f"<div class='stat-card'><div class='stat-title'>Last Wk Expenses</div><div class='stat-value' style='color:#ef4444;'>-${last_exp:,.0f}</div></div>", unsafe_allow_html=True)
        k5.markdown(f"<div class='stat-card'><div class='stat-title'>Last Wk Lost Sales</div><div class='stat-value' style='color:#ef4444;'>-${last_lost:,.0f}</div></div>", unsafe_allow_html=True)
        
        if state['has_intel']:
            k6.markdown(f"<div class='stat-card'><div class='stat-title'>Market Visibility</div><div class='stat-value' style='color:#22c55e;'>ACTIVE</div></div>", unsafe_allow_html=True)
        else:
            k6.markdown(f"<div class='stat-card'><div class='stat-title'>Market Visibility</div><div class='stat-value' style='color:#64748b;'>CLASSIFIED</div></div>", unsafe_allow_html=True)

        col_mid, col_right, col_pie = st.columns([1.5, 1.5, 1])
        with col_mid:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Expense Breakdown")
            if not df.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df['week'], y=df['overhead'], name='Overhead', marker_color='#475569'))
                fig.add_trace(go.Bar(x=df['week'], y=df['interest'], name='Interest', marker_color='#dc2626'))
                fig.add_trace(go.Bar(x=df['week'], y=df['holding'], name='Holding', marker_color='#f59e0b'))
                fig.add_trace(go.Bar(x=df['week'], y=df['shipping'], name='Shipping', marker_color='#3b82f6'))
                fig.add_trace(go.Bar(x=df['week'], y=df['materials'], name='Materials', marker_color='#10b981'))
                fig.add_trace(go.Bar(x=df['week'], y=df['marketing'], name='Marketing', marker_color='#ec4899'))
                fig.add_trace(go.Bar(x=df['week'], y=df['rd'], name='R&D', marker_color='#06b6d4'))
                fig.add_trace(go.Bar(x=df['week'], y=df['capex'], name='CAPEX', marker_color='#8b5cf6'))
                fig.update_layout(barmode='stack', template="plotly_dark", height=250, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Submit first week to generate chart.")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Revenue vs Lost Sales")
            if not df.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df['week'], y=df['revenue'], mode='lines+markers', name='Revenue', line=dict(color='#22c55e', width=3)))
                fig2.add_trace(go.Scatter(x=df['week'], y=df['lost_sales'], mode='lines+markers', name='Lost Sales', line=dict(color='#ef4444', width=3)))
                fig2.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Submit first week to generate chart.")
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col_pie:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Global Market Share")
            if current_week > 1 and state['has_intel']:
                global_ledger = supabase.table('ledger').select('team_id, revenue').eq('week', current_week - 1).execute().data
                if global_ledger:
                    labels = [GREEK_TEAMS[d['team_id']] for d in global_ledger]
                    values = [d['revenue'] for d in global_ledger]
                    fig3 = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3)])
                    fig3.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=30, b=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)')
                    fig3.update_traces(textinfo='label+percent', textfont_size=10)
                    st.plotly_chart(fig3, use_container_width=True)
            elif current_week == 1:
                st.info("Market Share data will generate in Week 2.")
            else:
                st.info("Market Visibility Classified. Purchase Market Intel.")
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
        st.markdown("### Complete Ledger")
        if not df.empty:
            st.dataframe(df.set_index('week'), use_container_width=True)
        else:
            st.info("No data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_ops:
        col_cap, col_inv = st.columns([1, 2.5])
        with col_cap:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Capacity Utilization")
            f_used, f_cap = state['last_hours_used'], state['fac_hours']
            st.write(f"**Factory Hours:** {f_used:,} / {f_cap:,}")
            st.progress(min(1.0, f_used / f_cap if f_cap > 0 else 0))

            r_used, r_cap = state['metal_qty'] + state['plastic_qty'], state['raw_wh']
            st.write(f"**Raw Warehouse:** {r_used:,} / {r_cap:,}")
            st.progress(min(1.0, r_used / r_cap if r_cap > 0 else 0))
            if state['wasted_materials'] > 0:
                st.markdown(f"<div class='stat-sub'>⚠️ {state['wasted_materials']:,} units wasted this run!</div>", unsafe_allow_html=True)

            e_used, e_cap = state['east_heavy_qty'] + state['east_light_qty'], state['hub_east_cap']
            st.write(f"**East Hub:** {e_used:,} / {e_cap:,}")
            st.progress(min(1.0, e_used / e_cap if e_cap > 0 else 0))

            w_used, w_cap = state['west_heavy_qty'] + state['west_light_qty'], state['hub_west_cap']
            st.write(f"**West Hub:** {w_used:,} / {w_cap:,}")
            st.progress(min(1.0, w_used / w_cap if w_cap > 0 else 0))
            st.markdown("</div>", unsafe_allow_html=True)

        with col_inv:
            inv_top1, inv_top2 = st.columns(2)
            with inv_top1:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown(f"""
                <h3 style='margin-top:0;'>Factory (Current Stock)</h3>
                <table class="dash-table">
                    <thead><tr><th>Asset</th><th style='text-align: right;'>Quantity</th></tr></thead>
                    <tbody>
                        <tr><td>Metal (Raw)</td><td style='text-align: right;'>{state['metal_qty']:,} units</td></tr>
                        <tr><td>Plastic (Raw)</td><td style='text-align: right;'>{state['plastic_qty']:,} units</td></tr>
                        <tr><td>Titan Heavy (FG)</td><td style='text-align: right;'>{state['heavy_qty']:,} units</td></tr>
                        <tr><td>Titan Light (FG)</td><td style='text-align: right;'>{state['light_qty']:,} units</td></tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with inv_top2:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown(f"""
                <h3 style='margin-top:0;'>Regional Hubs (Current Stock)</h3>
                <table class="dash-table">
                    <thead><tr><th>Location</th><th style='text-align: right;'>Titan Heavy</th><th style='text-align: right;'>Titan Light</th></tr></thead>
                    <tbody>
                        <tr><td>East Hub</td><td style='text-align: right;'>{state['east_heavy_qty']:,} units</td><td style='text-align: right;'>{state['east_light_qty']:,} units</td></tr>
                        <tr><td>West Hub</td><td style='text-align: right;'>{state['west_heavy_qty']:,} units</td><td style='text-align: right;'>{state['west_light_qty']:,} units</td></tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            inv_bot1, inv_bot2 = st.columns(2)
            with inv_bot1:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown(f"""
                <h3 style='margin-top:0;'>Last Week Production</h3>
                <table class="dash-table">
                    <thead><tr><th>Metric</th><th style='text-align: right;'>Value</th></tr></thead>
                    <tbody>
                        <tr><td>Heavy Built</td><td style='text-align: right;'>{state['last_prod_heavy']:,} units</td></tr>
                        <tr><td>Light Built</td><td style='text-align: right;'>{state['last_prod_light']:,} units</td></tr>
                        <tr><td>Hours Utilized</td><td style='text-align: right;'>{state['last_hours_used']:,} hrs</td></tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with inv_bot2:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown("<h3 style='margin-top:0;'>In-Transit Pipeline</h3>", unsafe_allow_html=True)
                transit = state['transit_pipeline'] if isinstance(state['transit_pipeline'], list) else json.loads(state['transit_pipeline'])
                if len(transit) == 0:
                    st.write("*Pipeline is empty.*")
                else:
                    transit_rows = ""
                    for t in transit:
                        if t['type'] == 'raw':
                            transit_rows += f"<tr><td>📦 To Plant ({t['weeks_left']} wks)</td><td style='text-align: right;'>{t['metal']:,} Metal</td><td style='text-align: right;'>{t['plastic']:,} Plastic</td></tr>"
                        elif t['type'] == 'finished_east':
                            transit_rows += f"<tr><td>🚚 To East ({t['weeks_left']} wks)</td><td style='text-align: right;'>{t['heavy']:,} Heavy</td><td style='text-align: right;'>{t['light']:,} Light</td></tr>"
                        elif t['type'] == 'finished_west':
                            transit_rows += f"<tr><td>🚚 To West ({t['weeks_left']} wks)</td><td style='text-align: right;'>{t['heavy']:,} Heavy</td><td style='text-align: right;'>{t['light']:,} Light</td></tr>"
                    st.markdown(f"<table class='dash-table'><thead><tr><th>Destination</th><th style='text-align: right;'>Item 1</th><th style='text-align: right;'>Item 2</th></tr></thead><tbody>{transit_rows}</tbody></table>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    with tab_manual:
        m1, m2 = st.columns(2)
        with m1:
            st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Bill of Materials & Production</h3><table class='dash-table'><thead><tr><th>Product</th><th>Required Materials</th><th style='text-align: right;'>Factory Time</th></tr></thead><tbody><tr><td>Titan Heavy</td><td>2 Metal, 2 Plastic</td><td style='text-align: right;'>2 hours per unit</td></tr><tr><td>Titan Light</td><td>3 Plastic</td><td style='text-align: right;'>1 hour per unit</td></tr></tbody></table></div>", unsafe_allow_html=True)
            st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Market Demand Engine (MNL)</h3><p style='font-size: 13px; color: #a1a1aa;'>Demand is calculated via a zero-sum Multinomial Logit Model against the other active competitors.</p><table class='dash-table'><thead><tr><th>Input</th><th>Effect on Demand</th></tr></thead><tbody><tr><td><b>Price</b></td><td>Negative linear effect. Crucial for Titan Light sales.</td></tr><tr><td><b>Marketing</b></td><td>Positive logarithmic effect (Diminishing returns).</td></tr><tr><td><b>R&D (Quality)</b></td><td>Positive linear effect. Crucial for Titan Heavy sales.</td></tr></tbody></table></div>", unsafe_allow_html=True)
            st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Corporate Finance</h3><table class='dash-table'><thead><tr><th>Rule</th><th>Details</th></tr></thead><tbody><tr><td><b>Interest Rate</b></td><td>2% per week on total outstanding debt.</td></tr><tr><td><b>Emergency Loan</b></td><td>Triggered if cash drops below 0. Adds a 5% penalty fee to the borrowed principal.</td></tr><tr><td><b>Bankruptcy</b></td><td>If total debt exceeds $15,000,000, the bank seizes the company (Game Over).</td></tr></tbody></table></div>", unsafe_allow_html=True)
        with m2:
            st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Macroeconomic Shocks</h3><table class='dash-table'><thead><tr><th>Event</th><th>Timing</th><th>Impact</th></tr></thead><tbody><tr><td><b>Market Contraction</b></td><td>Weeks 4 & 5</td><td>Total available market drops 15% across all regions.</td></tr><tr><td><b>Supply Chain Crisis</b></td><td>Weeks 7 & 8</td><td>Metal cost increases to $15. Plastic cost increases to $8.</td></tr></tbody></table></div>", unsafe_allow_html=True)
            st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Freight Operations (FTL/LTL)</h3><table class='dash-table'><thead><tr><th>Freight Mode</th><th style='text-align: right;'>FTL Flat Rate</th><th style='text-align: right;'>LTL Rate (Per Unit)</th><th style='text-align: right;'>Base Lead</th><th style='text-align: right;'>Delay Risk</th></tr></thead><tbody><tr><td>Economy (Rail/Sea)</td><td style='text-align: right;'>$1,000</td><td style='text-align: right;'>$1.50</td><td style='text-align: right;'>2 Weeks</td><td style='text-align: right;'>20%</td></tr><tr><td>Standard (Road)</td><td style='text-align: right;'>$2,000</td><td style='text-align: right;'>$3.00</td><td style='text-align: right;'>1 Week</td><td style='text-align: right;'>10%</td></tr><tr><td>Express (Air)</td><td style='text-align: right;'>$4,000</td><td style='text-align: right;'>$6.00</td><td style='text-align: right;'>Instant</td><td style='text-align: right;'>1%</td></tr></tbody></table></div>", unsafe_allow_html=True)
            st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Capacity Upgrades (CAPEX)</h3><table class='dash-table'><thead><tr><th>Facility</th><th style='text-align: right;'>Expansion Cost</th></tr></thead><tbody><tr><td>Factory Hours</td><td style='text-align: right;'>$50 per additional hour</td></tr><tr><td>Raw Warehouse</td><td style='text-align: right;'>$2 per unit of space</td></tr><tr><td>Hub Capacity (East/West)</td><td style='text-align: right;'>$5 per unit of space</td></tr><tr><td>Transit Capacity</td><td style='text-align: right;'>$10 per unit shipped</td></tr></tbody></table></div>", unsafe_allow_html=True)

    with tab_case:
        st.markdown(f"<div class='dash-panel'><h1 class='case-header'>Titan Operations: Navigating the Perfect Storm</h1><div class='case-text'><p><b>Introduction</b><br>You have just been appointed as the Vice President of Supply Chain at Titan Operations ({GREEK_TEAMS[tid]}), a mid-sized manufacturing firm specializing in heavy-duty machinery and light consumer electronics.</p><p>The board of directors expects you to stabilize the firm, capture market share against the other competitive firms in the industry, and generate maximum free cash flow over the next 12 weeks. Your performance will determine the future of the company.</p><p><b>The Products</b><br>Your facility produces two items:</p><ul><li><b>Titan Heavy:</b> A premium B2B product. Producing one unit takes 2 units of Metal, 2 units of Plastic, and 2 hours of factory time. Business buyers are highly sensitive to product quality.</li><li><b>Titan Light:</b> A budget B2C product. Producing one unit takes 3 units of Plastic and 1 hour of factory time. Consumer buyers are highly sensitive to price.</li></ul><p><b>The Network</b><br>You operate a single manufacturing plant that ships finished goods to two regional distribution centers: the East Hub and the West Hub. Every location in your network has strict capacity limits. If you order more raw materials than your warehouse can hold, the excess is discarded at your expense. If you try to push more volume through your transit pipelines or hubs than they can handle, the network will choke. You must actively invest capital (CAPEX) to upgrade these bottlenecks if you want to grow.</p><p><b>Market Dynamics</b><br>Demand is not guaranteed. You are competing directly against the other student competitors for every sale. Your market share is calculated via a zero-sum Multinomial Logit engine governed by three factors:</p><ol><li><b>Pricing:</b> Lower prices steal market share, but erode your margins.</li><li><b>Marketing Spend:</b> Generates demand through regional hubs. Be careful: marketing has diminishing returns.</li><li><b>R&D (Quality):</b> Every dollar spent on R&D permanently increases your Quality Index. This compounds over the entire 12-week period and is critical for selling the Titan Heavy product.</li></ol><p>If you fail to purchase weekly Market Intelligence reports, you will fly blind and lose visibility into the macro market movements.</p><p><b>Logistics and Freight</b><br>You manage all inbound and outbound freight. You must balance speed against cost.</p><ul><li><b>Economy Freight:</b> Takes 2 weeks. Cheap, but carries a high risk of unexpected carrier delays.</li><li><b>Standard Freight:</b> Takes 1 week. Moderate cost and moderate risk.</li><li><b>Express Freight:</b> Arrives instantly in the same week. Very expensive, but allows you to correct stock-outs immediately.</li></ul><p>Pay attention to your trucking utilization. A Full Truckload (FTL) holds 1,000 units and charges a flat rate. Less-Than-Truckload (LTL) shipments charge a steep per-unit premium.</p><p><b>Corporate Finance</b><br>You begin with $5,000,000 in cash. Every asset you hold incurs holding costs, and your factory requires $150,000 per week in fixed overhead. You can borrow cash to fund rapid expansion, but the bank charges 2% weekly interest on all outstanding debt.</p><p>If your cash balance ever drops below zero, the bank will force an emergency bailout loan with a brutal 5% penalty fee. If your total debt exceeds $15,000,000, the bank will seize Titan Operations, and you will be terminated.</p><p><b>The Looming Storm</b><br>Macroeconomic forecasts are not promising.</p><ul><li><b>Q4/Q5 Recession:</b> Consumer spending data indicates the total market size will contract by 15% during Weeks 4 and 5. If you do not throttle back production, your hubs will overflow with unsold inventory.</li><li><b>Q7/Q8 Supply Shock:</b> Geopolitical instability is threatening the commodity markets. Expect raw material costs for Metal and Plastic to surge during Weeks 7 and 8. If you do not stockpile inventory beforehand, your margins will be erased.</li></ul><p>Your goal is to reach Week 12 with the highest Net Position (Cash minus Debt) possible. Do not run out of cash.</p></div></div>", unsafe_allow_html=True)