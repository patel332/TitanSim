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

# --- CSS ARCHITECTURE (GLASSMORPHISM & ADAPTIVE THEMING) ---
def apply_css():
    st.markdown("""
        <style>
        /* Base typography - Apple System Font Stack */
        .stApp { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"; }
        
        /* Sidebar layout adjustment */
        [data-testid="stSidebar"] { min-width: 320px !important; background: rgba(128, 128, 128, 0.05); backdrop-filter: blur(20px); border-right: 1px solid rgba(128, 128, 128, 0.2); }
        [data-testid="stHeader"] { background-color: transparent; }
        .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 1600px; }
        
        /* Glassmorphism Panels */
        .dash-panel { 
            background: rgba(128, 128, 128, 0.08); 
            backdrop-filter: blur(16px); 
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(128, 128, 128, 0.2); 
            border-radius: 16px; 
            padding: 24px; 
            margin-bottom: 16px; 
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        }
        
        /* Stat Cards */
        .stat-card { 
            background: rgba(128, 128, 128, 0.08); 
            backdrop-filter: blur(16px); 
            border: 1px solid rgba(128, 128, 128, 0.2); 
            border-radius: 12px; 
            padding: 16px; 
            text-align: center; 
            height: 100%; 
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
        }
        .stat-title { font-size: 13px; margin-bottom: 5px; font-weight: 500; opacity: 0.8;}
        .stat-value { font-size: 24px; font-weight: 700; }
        
        /* Tables */
        .dash-table { width: 100%; border-collapse: collapse; font-size: 14px; }
        .dash-table th { padding: 12px; border-bottom: 1px solid rgba(128, 128, 128, 0.2); text-align: left; text-transform: uppercase; font-size: 11px; opacity: 0.7;}
        .dash-table td { padding: 12px; border-bottom: 1px solid rgba(128, 128, 128, 0.1); }
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background: transparent; }
        .stTabs [data-baseweb="tab"] { background-color: rgba(128, 128, 128, 0.05); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px 8px 0 0; padding: 10px 20px; font-weight: 500;}
        .stTabs [aria-selected="true"] { background-color: rgba(128, 128, 128, 0.15) !important; border-bottom-color: transparent !important; }
        
        /* Login Card */
        .login-card { 
            background: rgba(128, 128, 128, 0.1); 
            backdrop-filter: blur(20px); 
            border: 1px solid rgba(128, 128, 128, 0.2); 
            border-radius: 20px; 
            padding: 40px; 
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1); 
        }
        hr { border-color: rgba(128, 128, 128, 0.2); margin-top: 10px; margin-bottom: 10px;}
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

# --- HELPERS ---
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

    if week in [4, 5]:
        msg = "RECESSION ACTIVE: Total market demand is down 15%. Avoid overproducing."
        m_type = "error"
        mkt_h = int(BASE_MARKET_HEAVY * 0.85)
        mkt_l = int(BASE_MARKET_LIGHT * 0.85)
    elif week in [7, 8]:
        msg = "SUPPLY SHOCK: Metal and Plastic procurement costs have skyrocketed."
        m_type = "error"
        c_met, c_pla = 15, 8

    return mkt_h, mkt_l, c_met, c_pla, msg, m_type

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

# --- LOGIN SCREEN ---
apply_css()

if 'role' not in st.session_state: st.session_state.role = None
if 'team_id' not in st.session_state: st.session_state.team_id = None

if st.session_state.role is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; margin-bottom: 5px; font-weight: 800;'>Titan Operations</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; opacity: 0.7; margin-bottom: 30px;'>Supply Chain Management Simulation</p>", unsafe_allow_html=True)
        
        login_type = st.radio("Access Level", ["Student Team", "Instructor Console"], horizontal=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if login_type == "Student Team":
            team_options = [f"{i} - Team {GREEK_TEAMS[i]}" for i in range(1, 11)]
            t_selection = st.selectbox("Assign Competitor Profile", team_options)
            t_id = int(t_selection.split(" ")[0])
            pwd = st.text_input("Access Key", type="password")
            if st.button("Initialize Dashboard", use_container_width=True, type="primary"):
                res = supabase.table('teams').select('password').eq('id', t_id).execute()
                if res.data and res.data[0]['password'] == pwd:
                    st.session_state.role = 'team'
                    st.session_state.team_id = t_id
                    st.rerun()
                else:
                    st.error("Authentication Failed")
        else:
            pwd = st.text_input("Master Password", type="password")
            if st.button("Enter Control Panel", use_container_width=True, type="primary"):
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
    game_state = fetch_game_state()
    current_week = game_state['current_week']
    status = game_state['status']
    total_teams = game_state.get('total_teams', 10)
    
    with st.sidebar:
        st.markdown("### Control Panel")
        if st.button("Log Out"):
            st.session_state.clear()
            st.rerun()
        
        st.markdown("---")
        st.error("🚨 Danger Zone")
        if st.button("HARD RESTART GAME"):
            with st.spinner("Wiping Database..."):
                supabase.table('game_state').update({'current_week': 1, 'status': 'lobby'}).eq('id', 1).execute()
                supabase.table('pending_decisions').delete().neq('team_id', 0).execute()
                supabase.table('ledger').delete().neq('team_id', 0).execute()
                for i in range(1, 11):
                    supabase.table('team_state').update({
                        'cash': 5000000, 'debt': 0, 'quality_index': 1.0, 'metal_qty': 5000, 'plastic_qty': 10000,
                        'heavy_qty': 500, 'light_qty': 500, 'east_heavy_qty': 1000, 'east_light_qty': 1000,
                        'west_heavy_qty': 1000, 'west_light_qty': 1000, 'transit_pipeline': '[]', 'last_revenue': 0,
                        'wasted_materials': 0, 'fac_hours': 5000, 'raw_wh': 40000, 'hub_east_cap': 5000, 'hub_west_cap': 5000, 'transit_limit': 5000
                    }).eq('team_id', i).execute()
            st.success("Simulation Reset to Week 1 Lobby.")
            st.rerun()
    
    tab_ctrl, tab_analytics = st.tabs(["⚙️ Game Control", "📈 Global Analytics"])
    
    with tab_ctrl:
        st.markdown(f"### Current Phase: Week {current_week} | Status: {status.upper()}")
        
        if status == 'lobby':
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.subheader("Simulation Lobby Initialization")
            st.write("The game is currently locked. Students cannot submit decisions until the instructor starts the simulation.")
            selected_teams = st.slider("Select Number of Participating Teams", min_value=2, max_value=10, value=total_teams)
            if st.button("Launch Simulation", type="primary"):
                supabase.table('game_state').update({'status': 'active', 'total_teams': selected_teams}).eq('id', 1).execute()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

        if status == 'game_over':
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.error("The simulation has concluded. View final metrics in Global Analytics.")
            st.markdown("</div>", unsafe_allow_html=True)
            
        subs = supabase.table('pending_decisions').select('team_id').eq('week', current_week).execute().data
        sub_ids = [s['team_id'] for s in subs]
        
        st.write(f"**Teams Ready: {len(sub_ids)} / {total_teams}**")
        cols = st.columns(total_teams)
        for i in range(1, total_teams + 1):
            color = "🟢 Ready" if i in sub_ids else "🔴 Waiting"
            cols[i-1].markdown(f"<div class='stat-card'><div style='font-size:12px; font-weight:bold;'>{GREEK_TEAMS[i]}</div><div style='font-size:11px; opacity:0.8;'>{color}</div></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_run, col_stop = st.columns(2)
        with col_run:
            if st.button("Process Turn for All Teams", type="primary", use_container_width=True, disabled=(status == 'game_over')):
                if len(sub_ids) < total_teams:
                    st.warning("Not all teams have submitted.")
                else:
                    with st.spinner("Processing Global Market Engine..."):
                        all_decs = supabase.table('pending_decisions').select('*').eq('week', current_week).execute().data
                        env_mkt_h, env_mkt_l, env_cost_met, env_cost_pla, _, _ = get_environment(current_week)
                        
                        team_states = {t: fetch_team_state(t) for t in range(1, total_teams + 1)}
                        utilities = {}
                        total_u_h, total_u_l = 0, 0
                        
                        # Phase 1
                        for dec in all_decs:
                            tid = dec['team_id']
                            if tid > total_teams: continue
                            state = team_states[tid]
                            
                            if dec['net_fin'] < 0:
                                repay = min(abs(dec['net_fin']), state['debt'])
                                state['debt'] -= repay; state['cash'] -= repay
                            else:
                                state['debt'] += dec['net_fin']; state['cash'] += dec['net_fin']
                                
                            capex = (dec['cap_prod']*CAPEX_COST_PROD) + (dec['cap_wh']*CAPEX_COST_WAREHOUSE) + (dec['cap_he']*CAPEX_COST_HUB) + (dec['cap_hw']*CAPEX_COST_HUB) + (dec['cap_tr']*CAPEX_COST_TRANSIT)
                            state['cash'] -= capex
                            state['fac_hours'] += dec['cap_prod']; state['raw_wh'] += dec['cap_wh']; state['hub_east_cap'] += dec['cap_he']; state['hub_west_cap'] += dec['cap_hw']; state['transit_limit'] += dec['cap_tr']
                            state['quality_index'] = float(state['quality_index']) + (dec['rd_spend'] / 250_000.0)
                            state['has_intel'] = dec['buy_intel']
                            
                            u_h = math.exp(-1.5 * (dec['price_h']/100) + 0.3 * math.log(max(dec['mkt_e']+dec['mkt_w'], 1)) + 1.2 * state['quality_index'])
                            u_l = math.exp(-2.5 * (dec['price_l']/100) + 0.2 * math.log(max(dec['mkt_e']+dec['mkt_w'], 1)) + 0.8 * state['quality_index'])
                            utilities[tid] = {'u_h': u_h, 'u_l': u_l, 'dec': dec, 'state': state, 'capex': capex}
                            total_u_h += u_h; total_u_l += u_l
                            
                        # Phase 2
                        for tid, data in utilities.items():
                            dec = data['dec']
                            state = data['state']
                            transit = state['transit_pipeline'] if isinstance(state['transit_pipeline'], list) else json.loads(state['transit_pipeline'])
                            still_in_transit = []
                            
                            for t in transit:
                                t['weeks_left'] -= 1
                                if t['weeks_left'] <= 0:
                                    if t['type'] == 'raw':
                                        space_left = state['raw_wh'] - (state['metal_qty'] + state['plastic_qty'])
                                        incoming = t['metal'] + t['plastic']
                                        if incoming > space_left:
                                            ratio = space_left / incoming if incoming > 0 else 0
                                            state['metal_qty'] += int(t['metal'] * ratio); state['plastic_qty'] += int(t['plastic'] * ratio)
                                            state['wasted_materials'] += (incoming - space_left)
                                        else:
                                            state['metal_qty'] += t['metal']; state['plastic_qty'] += t['plastic']
                                    elif t['type'] == 'finished_east':
                                        space_left = state['hub_east_cap'] - (state['east_heavy_qty'] + state['east_light_qty'])
                                        incoming = t['heavy'] + t['light']
                                        if incoming > space_left:
                                            ratio = space_left / incoming if incoming > 0 else 0
                                            state['east_heavy_qty'] += int(t['heavy'] * ratio); state['east_light_qty'] += int(t['light'] * ratio)
                                        else:
                                            state['east_heavy_qty'] += t['heavy']; state['east_light_qty'] += t['light']
                                    elif t['type'] == 'finished_west':
                                        space_left = state['hub_west_cap'] - (state['west_heavy_qty'] + state['west_light_qty'])
                                        incoming = t['heavy'] + t['light']
                                        if incoming > space_left:
                                            ratio = space_left / incoming if incoming > 0 else 0
                                            state['west_heavy_qty'] += int(t['heavy'] * ratio); state['west_light_qty'] += int(t['light'] * ratio)
                                        else:
                                            state['west_heavy_qty'] += t['heavy']; state['west_light_qty'] += t['light']
                                else: still_in_transit.append(t)
                            
                            proc_lead = get_actual_lead_time(dec['proc_mode'])
                            proc_freight_cost = calc_freight(dec['buy_metal'] + dec['buy_plastic'], dec['proc_mode'])
                            mat_costs = (dec['buy_metal'] * env_cost_met) + (dec['buy_plastic'] * env_cost_pla)
                            
                            if proc_lead == 0 and (dec['buy_metal'] > 0 or dec['buy_plastic'] > 0): 
                                state['metal_qty'] += dec['buy_metal']; state['plastic_qty'] += dec['buy_plastic']
                            elif dec['buy_metal'] > 0 or dec['buy_plastic'] > 0:
                                still_in_transit.append({'type': 'raw', 'metal': dec['buy_metal'], 'plastic': dec['buy_plastic'], 'weeks_left': proc_lead})

                            hours_available = state['fac_hours']
                            req_heavy = min(dec['make_heavy'], min(state['metal_qty'] // 2, state['plastic_qty'] // 2))
                            if req_heavy * 2 <= hours_available: actual_p_h = req_heavy
                            else: actual_p_h = hours_available // 2
                            hours_available -= (actual_p_h * 2)
                            state['metal_qty'] -= (actual_p_h * 2); state['plastic_qty'] -= (actual_p_h * 2); state['heavy_qty'] += actual_p_h
                            
                            req_light = min(dec['make_light'], state['plastic_qty'] // 3)
                            if req_light <= hours_available: actual_p_l = req_light
                            else: actual_p_l = hours_available
                            hours_available -= actual_p_l
                            state['plastic_qty'] -= (actual_p_l * 3); state['light_qty'] += actual_p_l
                            state['last_prod_heavy'] = actual_p_h; state['last_prod_light'] = actual_p_l; state['last_hours_used'] = state['fac_hours'] - hours_available

                            transit_cap = state['transit_limit']
                            total_east_req = dec['ship_east_heavy'] + dec['ship_east_light']
                            if total_east_req > transit_cap:
                                ratio_e = transit_cap / total_east_req
                                actual_s_e_h = int(dec['ship_east_heavy'] * ratio_e); actual_s_e_l = int(dec['ship_east_light'] * ratio_e)
                            else:
                                actual_s_e_h, actual_s_e_l = dec['ship_east_heavy'], dec['ship_east_light']

                            total_west_req = dec['ship_west_heavy'] + dec['ship_west_light']
                            if total_west_req > transit_cap:
                                ratio_w = transit_cap / total_west_req
                                actual_s_w_h = int(dec['ship_west_heavy'] * ratio_w); actual_s_w_l = int(dec['ship_west_light'] * ratio_w)
                            else:
                                actual_s_w_h, actual_s_w_l = dec['ship_west_heavy'], dec['ship_west_light']

                            actual_s_e_h = min(actual_s_e_h, state['heavy_qty']); state['heavy_qty'] -= actual_s_e_h
                            actual_s_w_h = min(actual_s_w_h, state['heavy_qty']); state['heavy_qty'] -= actual_s_w_h
                            actual_s_e_l = min(actual_s_e_l, state['light_qty']); state['light_qty'] -= actual_s_e_l
                            actual_s_w_l = min(actual_s_w_l, state['light_qty']); state['light_qty'] -= actual_s_w_l

                            lead_e = get_actual_lead_time(dec['e_mode'])
                            cost_e = calc_freight(actual_s_e_h + actual_s_e_l, dec['e_mode'])
                            if lead_e == 0 and (actual_s_e_h > 0 or actual_s_e_l > 0): state['east_heavy_qty'] += actual_s_e_h; state['east_light_qty'] += actual_s_e_l
                            elif actual_s_e_h > 0 or actual_s_e_l > 0: still_in_transit.append({'type': 'finished_east', 'heavy': actual_s_e_h, 'light': actual_s_e_l, 'weeks_left': lead_e})

                            lead_w = get_actual_lead_time(dec['w_mode'])
                            cost_w = calc_freight(actual_s_w_h + actual_s_w_l, dec['w_mode'])
                            if lead_w == 0 and (actual_s_w_h > 0 or actual_s_w_l > 0): state['west_heavy_qty'] += actual_s_w_h; state['west_light_qty'] += actual_s_w_l
                            elif actual_s_w_h > 0 or actual_s_w_l > 0: still_in_transit.append({'type': 'finished_west', 'heavy': actual_s_w_h, 'light': actual_s_w_l, 'weeks_left': lead_w})

                            state['transit_pipeline'] = still_in_transit

                            share_h = data['u_h'] / total_u_h if total_u_h > 0 else 0
                            share_l = data['u_l'] / total_u_l if total_u_l > 0 else 0
                            demand_h = int(env_mkt_h * share_h); demand_l = int(env_mkt_l * share_l)
                            
                            sold_e_h = min(int(demand_h/2), state['east_heavy_qty']); state['east_heavy_qty'] -= sold_e_h
                            sold_e_l = min(int(demand_l/2), state['east_light_qty']); state['east_light_qty'] -= sold_e_l
                            sold_w_h = min(int(demand_h/2), state['west_heavy_qty']); state['west_heavy_qty'] -= sold_w_h
                            sold_w_l = min(int(demand_l/2), state['west_light_qty']); state['west_light_qty'] -= sold_w_l
                            
                            revenue = (sold_e_h + sold_w_h) * dec['price_h'] + (sold_e_l + sold_w_l) * dec['price_l']
                            lost_sales_h = max(0, demand_h - (sold_e_h + sold_w_h))
                            lost_sales_l = max(0, demand_l - (sold_e_l + sold_w_l))
                            lost_revenue = (lost_sales_h * dec['price_h']) + (lost_sales_l * dec['price_l'])
                            
                            state['cash'] += revenue
                            holding_costs = ((state['east_heavy_qty'] + state['east_light_qty'] + state['west_heavy_qty'] + state['west_light_qty']) * COST_HOLDING_FG) + ((state['metal_qty'] + state['plastic_qty']) * COST_HOLDING_RAW)

                            intel_cost = COST_INTEL if dec['buy_intel'] else 0
                            interest = state['debt'] * INTEREST_RATE
                            expenses = COST_OVERHEAD + mat_costs + proc_freight_cost + cost_e + cost_w + holding_costs + dec['mkt_e'] + dec['mkt_w'] + dec['rd_spend'] + interest + intel_cost
                            
                            state['cash'] -= expenses
                            if state['cash'] < 0: state['debt'] += (abs(state['cash']) * (1 + EMERGENCY_PENALTY)); state['cash'] = 0

                            supabase.table('team_state').update({
                                'cash': state['cash'], 'debt': state['debt'], 'quality_index': state['quality_index'],
                                'wasted_materials': state['wasted_materials'], 'has_intel': state['has_intel'], 'last_revenue': revenue,
                                'fac_hours': state['fac_hours'], 'raw_wh': state['raw_wh'], 'hub_east_cap': state['hub_east_cap'], 'hub_west_cap': state['hub_west_cap'], 'transit_limit': state['transit_limit'],
                                'metal_qty': state['metal_qty'], 'plastic_qty': state['plastic_qty'], 'heavy_qty': state['heavy_qty'], 'light_qty': state['light_qty'],
                                'east_heavy_qty': state['east_heavy_qty'], 'east_light_qty': state['east_light_qty'], 'west_heavy_qty': state['west_heavy_qty'], 'west_light_qty': state['west_light_qty'],
                                'transit_pipeline': state['transit_pipeline'], 'last_prod_heavy': state['last_prod_heavy'], 'last_prod_light': state['last_prod_light'], 'last_hours_used': state['last_hours_used']
                            }).eq('team_id', tid).execute()
                            
                            supabase.table('ledger').insert({
                                'team_id': tid, 'week': current_week, 'revenue': revenue, 'materials': mat_costs, 'shipping': proc_freight_cost + cost_e + cost_w, 'holding': holding_costs,
                                'marketing': dec['mkt_e'] + dec['mkt_w'] + intel_cost, 'rd': dec['rd_spend'], 'overhead': COST_OVERHEAD, 'interest': interest, 'capex': data['capex'], 
                                'total_exp': expenses + data['capex'], 'lost_sales': lost_revenue, 'cash': state['cash'], 'debt': state['debt']
                            }).execute()
                            
                        new_week = current_week + 1
                        new_status = 'active' if new_week <= MAX_WEEKS else 'game_over'
                        supabase.table('game_state').update({'current_week': new_week, 'status': new_status}).eq('id', 1).execute()
                        st.rerun()
                        
        with col_stop:
            if st.button("End Game Early", use_container_width=True, disabled=(status == 'game_over')):
                supabase.table('game_state').update({'status': 'game_over'}).eq('id', 1).execute()
                st.rerun()

    with tab_analytics:
        st.markdown("### Global Performance Telemetry")
        
        all_ledgers = supabase.table('ledger').select('*').execute().data
        if not all_ledgers:
            st.info("No data available yet. Analytics will populate after Week 1 is processed.")
        else:
            df = pd.DataFrame(all_ledgers)
            df['Team Name'] = df['team_id'].map(GREEK_TEAMS)
            df = df[df['team_id'] <= total_teams] # Filter out inactive teams
            
            # Leaderboard (Current Status)
            current_states = pd.DataFrame([fetch_team_state(t) for t in range(1, total_teams + 1)])
            current_states['Team Name'] = current_states['team_id'].map(GREEK_TEAMS)
            current_states['Net Position'] = current_states['cash'] - current_states['debt']
            current_states = current_states.sort_values(by='Net Position', ascending=False)
            
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("#### Live Rankings (Net Position)")
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=current_states['Team Name'], 
                y=current_states['Net Position'],
                marker_color=['#22c55e' if v >= 0 else '#ef4444' for v in current_states['Net Position']]
            ))
            fig_bar.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True, theme="streamlit")
            st.markdown("</div>", unsafe_allow_html=True)

            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown("#### Revenue Trajectory")
                fig_rev = go.Figure()
                for team in df['Team Name'].unique():
                    team_data = df[df['Team Name'] == team].sort_values(by='week')
                    fig_rev.add_trace(go.Scatter(x=team_data['week'], y=team_data['revenue'], mode='lines+markers', name=team))
                fig_rev.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_rev, use_container_width=True, theme="streamlit")
                st.markdown("</div>", unsafe_allow_html=True)
                
            with col_ch2:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown("#### Quality Index Growth")
                fig_q = go.Figure()
                for tid in range(1, total_teams + 1):
                    # Reconstruct quality over time based on R&D spend to plot it
                    team_data = df[df['team_id'] == tid].sort_values(by='week')
                    q_vals = [1.0] # Starting quality
                    for rd in team_data['rd']:
                        q_vals.append(q_vals[-1] + (rd / 250_000.0))
                    # Plot aligned with weeks (Week 0 to current)
                    weeks = [0] + list(team_data['week'])
                    fig_q.add_trace(go.Scatter(x=weeks, y=q_vals, mode='lines', name=GREEK_TEAMS[tid]))
                fig_q.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_q, use_container_width=True, theme="streamlit")
                st.markdown("</div>", unsafe_allow_html=True)


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
        if st.button("Refresh Status"): st.rerun()
        st.stop()
        
    if status == 'game_over' or state['debt'] > MAX_DEBT:
        st.markdown("<div class='dash-panel'><h1 style='text-align: center; margin-bottom: 0;'>End of Term: Executive Summary Report</h1>", unsafe_allow_html=True)
        if state['debt'] > MAX_DEBT: st.markdown("<h3 style='text-align: center; color: #ef4444;'>STATUS: INSOLVENT (MAXIMUM DEBT EXCEEDED)</h3>", unsafe_allow_html=True)
        else: st.markdown("<h3 style='text-align: center; color: #22c55e;'>STATUS: OPERATIONS COMPLETED</h3>", unsafe_allow_html=True)
            
        st.markdown("<hr>", unsafe_allow_html=True)
        
        ledger_data = supabase.table('ledger').select('*').eq('team_id', tid).execute().data
        df = pd.DataFrame(ledger_data) if ledger_data else pd.DataFrame()
        
        final_cash = state['cash']; final_debt = state['debt']
        net_position = final_cash - final_debt
        total_rev = df['revenue'].sum() if not df.empty else 0
        total_exp = df['total_exp'].sum() if not df.empty else 0
        total_lost = df['lost_sales'].sum() if not df.empty else 0

        st.markdown("### I. Macro Financials")
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"<div class='stat-card'><div class='stat-title'>Net Position</div><div class='stat-value'>${net_position:,.0f}</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='stat-card'><div class='stat-title'>Total Revenue</div><div class='stat-value'>${total_rev:,.0f}</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='stat-card'><div class='stat-title'>Final Cash</div><div class='stat-value'>${final_cash:,.0f}</div></div>", unsafe_allow_html=True)
        k4.markdown(f"<div class='stat-card'><div class='stat-title'>Final Debt</div><div class='stat-value'>${final_debt:,.0f}</div></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### II. Complete Ledger Export")
        if not df.empty:
            st.dataframe(df.set_index('week'), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()
        
    if has_submitted(tid, current_week):
        st.info(f"### Decisions Submitted for Week {current_week}.")
        st.write(f"Waiting for the instructor to process the global turn. Your dashboard will update automatically when Week {current_week + 1} begins.")
        if st.button("Refresh Status"): st.rerun()
        st.stop()
        
    # --- ACTIVE GAME UI ---
    env_mkt_h, env_mkt_l, env_cost_met, env_cost_pla, alert_msg, alert_type = get_environment(current_week)
    
    with st.sidebar:
        st.markdown(f"<div style='color: inherit; opacity: 0.7; margin-bottom:15px;'>Week {current_week} / {MAX_WEEKS}</div>", unsafe_allow_html=True)
        
        with st.form("decision_form"):
            with st.expander("1. Pricing Strategy", expanded=True):
                price_heavy = st.slider("Heavy Price ($)", 100, 300, 150, step=5)
                price_light = st.slider("Light Price ($)", 50, 150, 80, step=5)
            
            with st.expander("2. R&D and Marketing"):
                rd_spend = st.number_input("R&D Investment ($)", min_value=0, step=10000, value=0)
                mkt_e = st.number_input("Mkt Spend (East Hub)", min_value=0, step=5000, value=10000)
                mkt_w = st.number_input("Mkt Spend (West Hub)", min_value=0, step=5000, value=10000)
                buy_intel = st.checkbox("Buy Market Intel ($25k)", value=True)
            
            with st.expander("3. Procurement & Production"):
                proc_mode = st.selectbox("Freight Mode (Inbound)", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
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
        k2.markdown(f"<div class='stat-card'><div class='stat-title'>Total Debt</div><div class='stat-value'>${state['debt']:,.0f}</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='stat-card'><div class='stat-title'>Quality Index</div><div class='stat-value'>{state['quality_index']:.2f}</div></div>", unsafe_allow_html=True)
        
        last_exp = df.iloc[-1]['total_exp'] if not df.empty else 0
        last_lost = df.iloc[-1]['lost_sales'] if not df.empty else 0
        
        k4.markdown(f"<div class='stat-card'><div class='stat-title'>Last Wk Expenses</div><div class='stat-value'>-${last_exp:,.0f}</div></div>", unsafe_allow_html=True)
        k5.markdown(f"<div class='stat-card'><div class='stat-title'>Last Wk Lost Sales</div><div class='stat-value'>-${last_lost:,.0f}</div></div>", unsafe_allow_html=True)
        
        if state['has_intel']: k6.markdown(f"<div class='stat-card'><div class='stat-title'>Market Visibility</div><div class='stat-value'>ACTIVE</div></div>", unsafe_allow_html=True)
        else: k6.markdown(f"<div class='stat-card'><div class='stat-title'>Market Visibility</div><div class='stat-value'>CLASSIFIED</div></div>", unsafe_allow_html=True)

        col_mid, col_right, col_pie = st.columns([1.5, 1.5, 1])
        with col_mid:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Expense Breakdown")
            if not df.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df['week'], y=df['overhead'], name='Overhead'))
                fig.add_trace(go.Bar(x=df['week'], y=df['materials'], name='Materials'))
                fig.add_trace(go.Bar(x=df['week'], y=df['shipping'], name='Shipping'))
                fig.update_layout(barmode='stack', height=250, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True, theme="streamlit")
            else: st.info("Submit first week to generate chart.")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Revenue vs Lost Sales")
            if not df.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df['week'], y=df['revenue'], mode='lines+markers', name='Revenue'))
                fig2.add_trace(go.Scatter(x=df['week'], y=df['lost_sales'], mode='lines+markers', name='Lost Sales'))
                fig2.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig2, use_container_width=True, theme="streamlit")
            else: st.info("Submit first week to generate chart.")
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col_pie:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Global Market Share")
            if current_week > 1 and state['has_intel']:
                global_ledger = supabase.table('ledger').select('team_id, revenue').eq('week', current_week - 1).execute().data
                if global_ledger:
                    tdf = pd.DataFrame(global_ledger)
                    tdf = tdf[tdf['team_id'] <= game_state.get('total_teams', 10)]
                    labels = [GREEK_TEAMS[d] for d in tdf['team_id']]
                    fig3 = go.Figure(data=[go.Pie(labels=labels, values=tdf['revenue'], hole=.3)])
                    fig3.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)')
                    fig3.update_traces(textinfo='label+percent', textfont_size=10)
                    st.plotly_chart(fig3, use_container_width=True, theme="streamlit")
            elif current_week == 1: st.info("Generates in Wk 2.")
            else: st.info("Visibility Classified.")
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
                st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Factory Stock</h3><table class='dash-table'><thead><tr><th>Asset</th><th>Qty</th></tr></thead><tbody><tr><td>Metal</td><td>{0:,}</td></tr><tr><td>Plastic</td><td>{1:,}</td></tr><tr><td>Heavy FG</td><td>{2:,}</td></tr><tr><td>Light FG</td><td>{3:,}</td></tr></tbody></table></div>".format(state['metal_qty'], state['plastic_qty'], state['heavy_qty'], state['light_qty']), unsafe_allow_html=True)
            with inv_top2:
                st.markdown("<div class='dash-panel'><h3 style='margin-top:0;'>Regional Hubs</h3><table class='dash-table'><thead><tr><th>Location</th><th>Heavy</th><th>Light</th></tr></thead><tbody><tr><td>East Hub</td><td>{0:,}</td><td>{1:,}</td></tr><tr><td>West Hub</td><td>{2:,}</td><td>{3:,}</td></tr></tbody></table></div>".format(state['east_heavy_qty'], state['east_light_qty'], state['west_heavy_qty'], state['west_light_qty']), unsafe_allow_html=True)

    with tab_manual:
        st.write("Manual content available in documentation.")

    with tab_case:
        st.write("Business Case available in documentation.")