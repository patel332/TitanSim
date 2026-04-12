import streamlit as st
import pandas as pd
import random
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

# --- CONFIGURATION & CSS ---
st.set_page_config(page_title="Titan Operations", layout="wide")

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
BASE_MARKET_HEAVY = 1500 
BASE_MARKET_LIGHT = 2500 
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

# --- FREIGHT LOGIC ---
TRUCK_CAPACITY = 1000
FREIGHT_RATES = {
    'Economy (2 Wks)': {'FTL': 1000, 'LTL': 1.50, 'base_lead': 2, 'reliability': 0.80},
    'Standard (1 Wk)': {'FTL': 2000, 'LTL': 3.00, 'base_lead': 1, 'reliability': 0.90},
    'Express (Instant)': {'FTL': 4000, 'LTL': 6.00, 'base_lead': 0, 'reliability': 0.99}
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
        msg = "📰 NEWS: Economists predict a 15% market contraction starting next week. Prepare your cash reserves."
        m_type = "warning"
    elif week in [4, 5]:
        msg = "🚨 RECESSION ACTIVE: Total market demand is down 15%. Avoid overproducing."
        m_type = "error"
        mkt_h = int(BASE_MARKET_HEAVY * 0.85)
        mkt_l = int(BASE_MARKET_LIGHT * 0.85)
    elif week == 6:
        msg = "📰 NEWS: Global supply chain disruptions detected. Raw material prices expected to surge next week."
        m_type = "warning"
    elif week in [7, 8]:
        msg = "🚨 SUPPLY SHOCK: Metal and Plastic procurement costs have skyrocketed."
        m_type = "error"
        c_met, c_pla = 15, 8

    return mkt_h, mkt_l, c_met, c_pla, msg, m_type

# --- INITIALIZATION & STATE ---
if 'week' not in st.session_state:
    st.session_state.week = 1
    st.session_state.game_over = False
    st.session_state.bankrupt = False
    
    st.session_state.state = {
        'financials': {
            'cash': 5_000_000,
            'debt': 0, 
            'revenue_last_week': 0,
            'expenses_last_week': 0,
            'lost_sales_revenue': 0,
            'capex_last_week': 0,
            'interest_paid': 0,
            'has_intel': True 
        },
        'capacities': {
            'factory_hours': 5000,
            'raw_warehouse': 40000,
            'hub_east': 5000,
            'hub_west': 5000,
            'transit_limit': 5000 
        },
        'plant': {
            'metal_qty': 5000,
            'plastic_qty': 10000,
            'heavy_qty': 500,
            'light_qty': 500,
            'last_prod_heavy': 0,
            'last_prod_light': 0,
            'last_hours_used': 0,
            'wasted_materials': 0,
            'quality_index': 1.0 
        },
        'hub_east': {
            'heavy_qty': 1000,
            'light_qty': 1000,
            'heavy_share': 0.50,
            'light_share': 0.50
        },
        'hub_west': {
            'heavy_qty': 1000,
            'light_qty': 1000,
            'heavy_share': 0.50,
            'light_share': 0.50
        },
        'competitor': {
            'price_heavy': 150,
            'price_light': 80,
            'quality_index': 1.0,
            'mkt_east': 10000,
            'mkt_west': 10000
        },
        'sales_report': {
            'east_h_dem': 0, 'east_h_sold': 0, 'east_h_lost': 0,
            'east_l_dem': 0, 'east_l_sold': 0, 'east_l_lost': 0,
            'west_h_dem': 0, 'west_h_sold': 0, 'west_h_lost': 0,
            'west_l_dem': 0, 'west_l_sold': 0, 'west_l_lost': 0,
        },
        'transit': [],
        'ledger': []
    }

env_mkt_h, env_mkt_l, env_cost_met, env_cost_pla, alert_msg, alert_type = get_environment(st.session_state.week)

# --- LOGIC ENGINE ---
def process_turn(p_h, p_l, mkt_e, mkt_w, rd_spend, buy_intel, b_m, b_p, proc_mode, m_h, m_l, s_e_h, s_e_l, e_mode, s_w_h, s_w_l, w_mode, cap_prod, cap_wh, cap_he, cap_hw, cap_tr, net_fin):
    s = st.session_state.state
    
    if net_fin < 0:
        actual_repayment = min(abs(net_fin), s['financials']['debt'])
        s['financials']['debt'] -= actual_repayment
        s['financials']['cash'] -= actual_repayment
    elif net_fin > 0:
        s['financials']['debt'] += net_fin
        s['financials']['cash'] += net_fin

    capex_cost = (cap_prod * CAPEX_COST_PROD) + (cap_wh * CAPEX_COST_WAREHOUSE) + \
                 (cap_he * CAPEX_COST_HUB) + (cap_hw * CAPEX_COST_HUB) + (cap_tr * CAPEX_COST_TRANSIT)
    s['capacities']['factory_hours'] += cap_prod
    s['capacities']['raw_warehouse'] += cap_wh
    s['capacities']['hub_east'] += cap_he
    s['capacities']['hub_west'] += cap_hw
    s['capacities']['transit_limit'] += cap_tr
    s['financials']['cash'] -= capex_cost
    s['financials']['capex_last_week'] = capex_cost

    s['plant']['quality_index'] += (rd_spend / 250_000) 
    s['competitor']['quality_index'] += 0.05 
    s['financials']['has_intel'] = buy_intel

    intel_cost = COST_INTEL if buy_intel else 0

    still_in_transit = []
    for t in s['transit']:
        t['weeks_left'] -= 1
        if t['weeks_left'] <= 0:
            if t['type'] == 'raw':
                current_raw = s['plant']['metal_qty'] + s['plant']['plastic_qty']
                space_left = s['capacities']['raw_warehouse'] - current_raw
                incoming = t['metal'] + t['plastic']
                if incoming > space_left:
                    ratio = space_left / incoming if incoming > 0 else 0
                    s['plant']['metal_qty'] += int(t['metal'] * ratio)
                    s['plant']['plastic_qty'] += int(t['plastic'] * ratio)
                    s['plant']['wasted_materials'] += (incoming - space_left)
                else:
                    s['plant']['metal_qty'] += t['metal']
                    s['plant']['plastic_qty'] += t['plastic']
            elif t['type'] == 'finished_east':
                current_e = s['hub_east']['heavy_qty'] + s['hub_east']['light_qty']
                space_left = s['capacities']['hub_east'] - current_e
                incoming = t['heavy'] + t['light']
                if incoming > space_left:
                    ratio = space_left / incoming if incoming > 0 else 0
                    s['hub_east']['heavy_qty'] += int(t['heavy'] * ratio)
                    s['hub_east']['light_qty'] += int(t['light'] * ratio)
                else:
                    s['hub_east']['heavy_qty'] += t['heavy']
                    s['hub_east']['light_qty'] += t['light']
            elif t['type'] == 'finished_west':
                current_w = s['hub_west']['heavy_qty'] + s['hub_west']['light_qty']
                space_left = s['capacities']['hub_west'] - current_w
                incoming = t['heavy'] + t['light']
                if incoming > space_left:
                    ratio = space_left / incoming if incoming > 0 else 0
                    s['hub_west']['heavy_qty'] += int(t['heavy'] * ratio)
                    s['hub_west']['light_qty'] += int(t['light'] * ratio)
                else:
                    s['hub_west']['heavy_qty'] += t['heavy']
                    s['hub_west']['light_qty'] += t['light']
        else:
            still_in_transit.append(t)
    s['transit'] = still_in_transit

    proc_lead = get_actual_lead_time(proc_mode)
    proc_freight_cost = calc_freight(b_m + b_p, proc_mode)
    mat_costs = (b_m * env_cost_met) + (b_p * env_cost_pla)
    
    if proc_lead == 0 and (b_m > 0 or b_p > 0): 
        s['plant']['metal_qty'] += b_m
        s['plant']['plastic_qty'] += b_p
    elif b_m > 0 or b_p > 0:
        s['transit'].append({'type': 'raw', 'metal': b_m, 'plastic': b_p, 'weeks_left': proc_lead})

    hours_available = s['capacities']['factory_hours']
    
    mat_limit_heavy = min(s['plant']['metal_qty'] // 2, s['plant']['plastic_qty'] // 2)
    req_heavy = min(m_h, mat_limit_heavy)
    
    if req_heavy * 2 <= hours_available:
        actual_p_h = req_heavy
        hours_available -= (actual_p_h * 2)
    else:
        actual_p_h = hours_available // 2
        hours_available -= (actual_p_h * 2)
        
    s['plant']['metal_qty'] -= (actual_p_h * 2)
    s['plant']['plastic_qty'] -= (actual_p_h * 2)
    s['plant']['heavy_qty'] += actual_p_h
    
    mat_limit_light = s['plant']['plastic_qty'] // 3
    req_light = min(m_l, mat_limit_light)
    
    if req_light * 1 <= hours_available:
        actual_p_l = req_light
        hours_available -= actual_p_l
    else:
        actual_p_l = hours_available
        hours_available -= actual_p_l
        
    s['plant']['plastic_qty'] -= (actual_p_l * 3)
    s['plant']['light_qty'] += actual_p_l

    s['plant']['last_prod_heavy'] = actual_p_h
    s['plant']['last_prod_light'] = actual_p_l
    s['plant']['last_hours_used'] = s['capacities']['factory_hours'] - hours_available

    transit_cap = s['capacities']['transit_limit']
    
    total_east_req = s_e_h + s_e_l
    if total_east_req > transit_cap:
        ratio_e = transit_cap / total_east_req
        actual_s_e_h = int(s_e_h * ratio_e)
        actual_s_e_l = int(s_e_l * ratio_e)
    else:
        actual_s_e_h, actual_s_e_l = s_e_h, s_e_l

    total_west_req = s_w_h + s_w_l
    if total_west_req > transit_cap:
        ratio_w = transit_cap / total_west_req
        actual_s_w_h = int(s_w_h * ratio_w)
        actual_s_w_l = int(s_w_l * ratio_w)
    else:
        actual_s_w_h, actual_s_w_l = s_w_h, s_w_l

    actual_s_e_h = min(actual_s_e_h, s['plant']['heavy_qty'])
    s['plant']['heavy_qty'] -= actual_s_e_h
    actual_s_w_h = min(actual_s_w_h, s['plant']['heavy_qty'])
    s['plant']['heavy_qty'] -= actual_s_w_h
    
    actual_s_e_l = min(actual_s_e_l, s['plant']['light_qty'])
    s['plant']['light_qty'] -= actual_s_e_l
    actual_s_w_l = min(actual_s_w_l, s['plant']['light_qty'])
    s['plant']['light_qty'] -= actual_s_w_l

    lead_e = get_actual_lead_time(e_mode)
    cost_e = calc_freight(actual_s_e_h + actual_s_e_l, e_mode)
    if lead_e == 0 and (actual_s_e_h > 0 or actual_s_e_l > 0):
        s['hub_east']['heavy_qty'] += actual_s_e_h
        s['hub_east']['light_qty'] += actual_s_e_l
    elif actual_s_e_h > 0 or actual_s_e_l > 0:
        s['transit'].append({'type': 'finished_east', 'heavy': actual_s_e_h, 'light': actual_s_e_l, 'weeks_left': lead_e})

    lead_w = get_actual_lead_time(w_mode)
    cost_w = calc_freight(actual_s_w_h + actual_s_w_l, w_mode)
    if lead_w == 0 and (actual_s_w_h > 0 or actual_s_w_l > 0):
        s['hub_west']['heavy_qty'] += actual_s_w_h
        s['hub_west']['light_qty'] += actual_s_w_l
    elif actual_s_w_h > 0 or actual_s_w_l > 0:
        s['transit'].append({'type': 'finished_west', 'heavy': actual_s_w_h, 'light': actual_s_w_l, 'weeks_left': lead_w})

    total_ship_costs = proc_freight_cost + cost_e + cost_w

    prev_comp_h = s['competitor']['price_heavy']
    prev_comp_l = s['competitor']['price_light']
    s['competitor']['price_heavy'] = int(max(110, min(250, prev_comp_h * random.uniform(0.90, 1.10))))
    s['competitor']['price_light'] = int(max(60, min(150, prev_comp_l * random.uniform(0.90, 1.10))))
    s['competitor']['mkt_east'] = max(5000, int(mkt_e * random.uniform(0.8, 1.2)))
    s['competitor']['mkt_west'] = max(5000, int(mkt_w * random.uniform(0.8, 1.2)))

    comp_heavy = s['competitor']['price_heavy']
    comp_light = s['competitor']['price_light']
    comp_qual = s['competitor']['quality_index']

    def calc_utility(price, mkt, qual, is_heavy):
        if is_heavy:
            return math.exp(-1.5 * (price/100) + 0.3 * math.log(max(mkt, 1)) + 1.2 * qual)
        else:
            return math.exp(-2.5 * (price/100) + 0.2 * math.log(max(mkt, 1)) + 0.8 * qual)

    u_p_e_h = calc_utility(p_h, mkt_e, s['plant']['quality_index'], True)
    u_c_e_h = calc_utility(comp_heavy, s['competitor']['mkt_east'], comp_qual, True)
    s['hub_east']['heavy_share'] = u_p_e_h / (u_p_e_h + u_c_e_h)

    u_p_e_l = calc_utility(p_l, mkt_e, s['plant']['quality_index'], False)
    u_c_e_l = calc_utility(comp_light, s['competitor']['mkt_east'], comp_qual, False)
    s['hub_east']['light_share'] = u_p_e_l / (u_p_e_l + u_c_e_l)

    u_p_w_h = calc_utility(p_h, mkt_w, s['plant']['quality_index'], True)
    u_c_w_h = calc_utility(comp_heavy, s['competitor']['mkt_west'], comp_qual, True)
    s['hub_west']['heavy_share'] = u_p_w_h / (u_p_w_h + u_c_w_h)

    u_p_w_l = calc_utility(p_l, mkt_w, s['plant']['quality_index'], False)
    u_c_w_l = calc_utility(comp_light, s['competitor']['mkt_west'], comp_qual, False)
    s['hub_west']['light_share'] = u_p_w_l / (u_p_w_l + u_c_w_l)

    demand_e_h = int(env_mkt_h * s['hub_east']['heavy_share'])
    demand_e_l = int(env_mkt_l * s['hub_east']['light_share'])
    demand_w_h = int(env_mkt_h * s['hub_west']['heavy_share'])
    demand_w_l = int(env_mkt_l * s['hub_west']['light_share'])

    sold_e_h = min(demand_e_h, s['hub_east']['heavy_qty'])
    sold_e_l = min(demand_e_l, s['hub_east']['light_qty'])
    sold_w_h = min(demand_w_h, s['hub_west']['heavy_qty'])
    sold_w_l = min(demand_w_l, s['hub_west']['light_qty'])
    
    s['sales_report'] = {
        'east_h_dem': demand_e_h, 'east_h_sold': sold_e_h, 'east_h_lost': demand_e_h - sold_e_h,
        'east_l_dem': demand_e_l, 'east_l_sold': sold_e_l, 'east_l_lost': demand_e_l - sold_e_l,
        'west_h_dem': demand_w_h, 'west_h_sold': sold_w_h, 'west_h_lost': demand_w_h - sold_w_h,
        'west_l_dem': demand_w_l, 'west_l_sold': sold_w_l, 'west_l_lost': demand_w_l - sold_w_l,
    }

    s['hub_east']['heavy_qty'] -= sold_e_h
    s['hub_east']['light_qty'] -= sold_e_l
    s['hub_west']['heavy_qty'] -= sold_w_h
    s['hub_west']['light_qty'] -= sold_w_l
    
    revenue = (sold_e_h + sold_w_h) * p_h + (sold_e_l + sold_w_l) * p_l
    lost_revenue = (s['sales_report']['east_h_lost'] + s['sales_report']['west_h_lost']) * p_h + \
                   (s['sales_report']['east_l_lost'] + s['sales_report']['west_l_lost']) * p_l
    
    s['financials']['cash'] += revenue
    s['financials']['revenue_last_week'] = revenue
    s['financials']['lost_sales_revenue'] = lost_revenue

    holding_costs = ((s['hub_east']['heavy_qty'] + s['hub_east']['light_qty'] + 
                      s['hub_west']['heavy_qty'] + s['hub_west']['light_qty']) * COST_HOLDING_FG) + \
                    ((s['plant']['metal_qty'] + s['plant']['plastic_qty']) * COST_HOLDING_RAW)

    interest = s['financials']['debt'] * INTEREST_RATE
    s['financials']['interest_paid'] = interest
    
    expenses = COST_OVERHEAD + mat_costs + total_ship_costs + holding_costs + mkt_e + mkt_w + rd_spend + interest + intel_cost
    s['financials']['cash'] -= expenses
    s['financials']['expenses_last_week'] = expenses

    if s['financials']['cash'] < 0:
        emergency_amt = abs(s['financials']['cash'])
        penalty = emergency_amt * EMERGENCY_PENALTY
        s['financials']['debt'] += (emergency_amt + penalty)
        s['financials']['cash'] = 0

    s['ledger'].append({
        'Week': st.session_state.week,
        'Revenue': revenue,
        'Materials': mat_costs,
        'Shipping': total_ship_costs,
        'Holding': holding_costs,
        'Marketing': mkt_e + mkt_w + intel_cost,
        'R&D': rd_spend,
        'Overhead': COST_OVERHEAD,
        'Interest': interest,
        'CAPEX': capex_cost,
        'Total Exp': expenses + capex_cost,
        'Lost Sales': lost_revenue,
        'Cash': s['financials']['cash'],
        'Debt': s['financials']['debt']
    })

    if s['financials']['debt'] > MAX_DEBT:
        st.session_state.bankrupt = True
        st.session_state.game_over = True
    elif st.session_state.week >= MAX_WEEKS:
        st.session_state.game_over = True
    else:
        st.session_state.week += 1

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# --- UI RENDERING ---
apply_css()

if st.session_state.game_over:
    # --- EXECUTIVE SUMMARY REPORT ---
    st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>End of Term: Executive Summary Report</h1>", unsafe_allow_html=True)
    
    if st.session_state.bankrupt:
        st.markdown("<h3 style='text-align: center; color: #ef4444;'>STATUS: INSOLVENT (MAXIMUM DEBT EXCEEDED)</h3>", unsafe_allow_html=True)
    else:
        st.markdown("<h3 style='text-align: center; color: #22c55e;'>STATUS: OPERATIONS COMPLETED</h3>", unsafe_allow_html=True)
        
    st.markdown("<hr style='border-color: #3f3f46; margin-top: 20px; margin-bottom: 30px;'>", unsafe_allow_html=True)
    
    s = st.session_state.state
    df = pd.DataFrame(s['ledger'])
    
    # Calc Aggregates
    final_cash = s['financials']['cash']
    final_debt = s['financials']['debt']
    net_position = final_cash - final_debt
    total_rev = df['Revenue'].sum() if len(df) > 0 else 0
    total_exp = df['Total Exp'].sum() if len(df) > 0 else 0
    total_lost = df['Lost Sales'].sum() if len(df) > 0 else 0

    # Macro Financials
    st.markdown("### I. Macro Financials")
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f"<div class='stat-card'><div class='stat-title'>Net Position</div><div class='stat-value'>${net_position:,.0f}</div></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='stat-card'><div class='stat-title'>Total Revenue</div><div class='stat-value' style='color:#22c55e;'>${total_rev:,.0f}</div></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='stat-card'><div class='stat-title'>Final Cash</div><div class='stat-value'>${final_cash:,.0f}</div></div>", unsafe_allow_html=True)
    k4.markdown(f"<div class='stat-card'><div class='stat-title'>Final Debt</div><div class='stat-value' style='color:#ef4444;'>${final_debt:,.0f}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Secondary Data Blocks
    c_cost, c_ops = st.columns(2)

    with c_cost:
        st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>II. Total Cost Breakdown</h3>", unsafe_allow_html=True)
        st.markdown(f"""
        <table class="dash-table">
            <thead>
                <tr><th>Expense Category</th><th style='text-align: right;'>12-Week Total</th></tr>
            </thead>
            <tbody>
                <tr><td>Materials (COGS)</td><td style='text-align: right;'>${df['Materials'].sum():,.0f}</td></tr>
                <tr><td>Shipping & Freight</td><td style='text-align: right;'>${df['Shipping'].sum():,.0f}</td></tr>
                <tr><td>Inventory Holding</td><td style='text-align: right;'>${df['Holding'].sum():,.0f}</td></tr>
                <tr><td>Marketing & Intel</td><td style='text-align: right;'>${df['Marketing'].sum():,.0f}</td></tr>
                <tr><td>R&D (Quality)</td><td style='text-align: right;'>${df['R&D'].sum():,.0f}</td></tr>
                <tr><td>Fixed Overhead</td><td style='text-align: right;'>${df['Overhead'].sum():,.0f}</td></tr>
                <tr><td>Debt Interest</td><td style='text-align: right;'>${df['Interest'].sum():,.0f}</td></tr>
                <tr><td>CAPEX (Upgrades)</td><td style='text-align: right;'>${df['CAPEX'].sum():,.0f}</td></tr>
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
            <thead>
                <tr><th>Metric</th><th style='text-align: right;'>Value</th></tr>
            </thead>
            <tbody>
                <tr><td>Total Lost Sales (Stock-Out Penalty)</td><td style='text-align: right; color: #ef4444;'>${total_lost:,.0f}</td></tr>
                <tr><td>Wasted Materials (Capacity Overflow)</td><td style='text-align: right; color: #ef4444;'>{s['plant']['wasted_materials']:,} units</td></tr>
                <tr><td>Final R&D Quality Index</td><td style='text-align: right; color: #3b82f6;'>{s['plant']['quality_index']:.2f}</td></tr>
            </tbody>
        </table>
        """, unsafe_allow_html=True)
        st.markdown("<br><h3 style='margin-top:0;'>IV. Ending Asset Positions</h3>", unsafe_allow_html=True)
        st.markdown(f"""
        <table class="dash-table">
            <thead>
                <tr><th>Asset Location</th><th style='text-align: right;'>Units Remaining</th></tr>
            </thead>
            <tbody>
                <tr><td>Factory (Raw Materials)</td><td style='text-align: right;'>{(s['plant']['metal_qty'] + s['plant']['plastic_qty']):,}</td></tr>
                <tr><td>Factory (Finished Goods)</td><td style='text-align: right;'>{(s['plant']['heavy_qty'] + s['plant']['light_qty']):,}</td></tr>
                <tr><td>East Hub (Finished Goods)</td><td style='text-align: right;'>{(s['hub_east']['heavy_qty'] + s['hub_east']['light_qty']):,}</td></tr>
                <tr><td>West Hub (Finished Goods)</td><td style='text-align: right;'>{(s['hub_west']['heavy_qty'] + s['hub_west']['light_qty']):,}</td></tr>
            </tbody>
        </table>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Ledger Download
    st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
    st.markdown("### V. Complete Ledger Export")
    col_dl, _ = st.columns([1, 4])
    with col_dl:
        csv_data = convert_df_to_csv(df)
        st.download_button(label="Download CSV Audit", data=csv_data, file_name='titan_ledger.csv', mime='text/csv', use_container_width=True)
    st.dataframe(df.set_index('Week'), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Restart Simulation", use_container_width=True):
        st.session_state.clear()
        st.rerun()

else:
    # NORMAL GAME UI
    with st.sidebar:
        st.markdown("<h2>Decision Center</h2>", unsafe_allow_html=True)
        st.markdown(f"<div style='color: #a1a1aa; margin-bottom:15px;'>Week {st.session_state.week} / {MAX_WEEKS}</div>", unsafe_allow_html=True)
        
        with st.expander("1. Market Pricing", expanded=True):
            price_heavy = st.slider("Heavy Price ($)", 100, 300, 150, step=5)
            price_light = st.slider("Light Price ($)", 50, 150, 80, step=5)
            buy_intel = st.checkbox("Buy Market Intel ($25,000)", value=True)

        with st.expander("2. Demand Generation"):
            rd_spend = st.number_input("R&D Investment ($)", min_value=0, step=10000, value=0)
            st.caption("Marketing Hub Budgets")
            mkt_e = st.number_input("Mkt Spend (East Hub)", min_value=0, step=5000, value=10000)
            mkt_w = st.number_input("Mkt Spend (West Hub)", min_value=0, step=5000, value=10000)

        with st.expander("3. Procurement"):
            st.caption(f"Current Costs: Metal ${env_cost_met} | Plastic ${env_cost_pla}")
            proc_mode = st.selectbox("Freight Mode (Inbound)", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
            buy_metal = st.number_input(f"Order Metal", min_value=0, step=500, value=0)
            buy_plastic = st.number_input(f"Order Plastic", min_value=0, step=500, value=0)
        
        with st.expander("4. Production"):
            make_heavy = st.number_input("Produce Heavy", min_value=0, step=100, value=500)
            make_light = st.number_input("Produce Light", min_value=0, step=100, value=800)
        
        with st.expander("5. Shipping"):
            st.caption("To East Hub")
            e_mode = st.selectbox("East Freight Mode", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
            col1, col2 = st.columns(2)
            ship_east_heavy = col1.number_input("Heavy (E)", min_value=0, step=100, value=250)
            ship_east_light = col2.number_input("Light (E)", min_value=0, step=100, value=400)
            st.caption("To West Hub")
            w_mode = st.selectbox("West Freight Mode", ["Standard (1 Wk)", "Economy (2 Wks)", "Express (Instant)"])
            col3, col4 = st.columns(2)
            ship_west_heavy = col3.number_input("Heavy (W)", min_value=0, step=100, value=250)
            ship_west_light = col4.number_input("Light (W)", min_value=0, step=100, value=400)

        with st.expander("6. Capacity Upgrades (CAPEX)"):
            cap_prod = st.number_input("Add Factory Hours ($50/hr)", min_value=0, step=100)
            cap_wh = st.number_input("Add Raw Warehouse ($2/unit)", min_value=0, step=1000)
            cap_he = st.number_input("Add East Hub Cap ($5/unit)", min_value=0, step=500)
            cap_hw = st.number_input("Add West Hub Cap ($5/unit)", min_value=0, step=500)
            cap_tr = st.number_input("Add Transit Limit ($10/unit)", min_value=0, step=500)

        with st.expander("7. Corporate Finance"):
            st.caption(f"Current Debt: ${st.session_state.state['financials']['debt']:,} (2% Weekly Interest)")
            st.caption("Enter negative number to repay debt.")
            net_financing = st.number_input("Net Financing", value=0, step=100000)

        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("Submit Week", type="primary", use_container_width=True):
            process_turn(price_heavy, price_light, mkt_e, mkt_w, rd_spend, buy_intel, buy_metal, buy_plastic, proc_mode, make_heavy, make_light, 
                         ship_east_heavy, ship_east_light, e_mode, ship_west_heavy, ship_west_light, w_mode,
                         cap_prod, cap_wh, cap_he, cap_hw, cap_tr, net_financing)
            st.rerun()

        if st.button("Restart", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    s = st.session_state.state

    st.markdown("<h2 style='margin-bottom:10px;'>Supply Chain Management Dashboard</h2>", unsafe_allow_html=True)

    if alert_type == "warning":
        st.warning(alert_msg)
    elif alert_type == "error":
        st.error(alert_msg)
    else:
        st.info(alert_msg)

    tab_dash, tab_ops, tab_manual, tab_case = st.tabs(["Executive Dashboard", "Operations & Logistics", "Case Manual", "Business Case"])

    with tab_dash:
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.markdown(f"<div class='stat-card'><div class='stat-title'>Cash Balance</div><div class='stat-value'>${s['financials']['cash']:,}</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='stat-card'><div class='stat-title'>Total Debt</div><div class='stat-value' style='color:#ef4444;'>${s['financials']['debt']:,}</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='stat-card'><div class='stat-title'>Quality Index</div><div class='stat-value' style='color:#3b82f6;'>{s['plant']['quality_index']:.2f}</div></div>", unsafe_allow_html=True)
        k4.markdown(f"<div class='stat-card'><div class='stat-title'>Operational Expenses</div><div class='stat-value' style='color:#ef4444;'>-${s['financials']['expenses_last_week']:,}</div></div>", unsafe_allow_html=True)
        k5.markdown(f"<div class='stat-card'><div class='stat-title'>Lost Sales Penalty</div><div class='stat-value' style='color:#ef4444;'>-${s['financials']['lost_sales_revenue']:,}</div></div>", unsafe_allow_html=True)
        
        if s['financials'].get('has_intel', True):
            k6.markdown(f"<div class='stat-card'><div class='stat-title'>Last Wk Apex Price (H/L)</div><div class='stat-value'>${s['competitor']['price_heavy']} / ${s['competitor']['price_light']}</div></div>", unsafe_allow_html=True)
        else:
            k6.markdown(f"<div class='stat-card'><div class='stat-title'>Last Wk Apex Price (H/L)</div><div class='stat-value' style='color:#64748b;'>CLASSIFIED</div></div>", unsafe_allow_html=True)

        col_mid, col_right, col_pie = st.columns([1.5, 1.5, 1])

        with col_mid:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Expense Breakdown")
            if len(s['ledger']) > 0:
                df = pd.DataFrame(s['ledger'])
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df['Week'], y=df['Overhead'], name='Overhead', marker_color='#475569'))
                fig.add_trace(go.Bar(x=df['Week'], y=df['Interest'], name='Interest', marker_color='#dc2626'))
                fig.add_trace(go.Bar(x=df['Week'], y=df['Holding'], name='Holding', marker_color='#f59e0b'))
                fig.add_trace(go.Bar(x=df['Week'], y=df['Shipping'], name='Shipping', marker_color='#3b82f6'))
                fig.add_trace(go.Bar(x=df['Week'], y=df['Materials'], name='Materials', marker_color='#10b981'))
                fig.add_trace(go.Bar(x=df['Week'], y=df['Marketing'], name='Marketing', marker_color='#ec4899'))
                fig.add_trace(go.Bar(x=df['Week'], y=df['R&D'], name='R&D', marker_color='#06b6d4'))
                fig.add_trace(go.Bar(x=df['Week'], y=df['CAPEX'], name='CAPEX', marker_color='#8b5cf6'))
                fig.update_layout(barmode='stack', template="plotly_dark", height=250, margin=dict(l=0, r=0, t=30, b=0),
                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Submit first week to generate chart.")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Revenue vs Lost Sales")
            if len(s['ledger']) > 0:
                df = pd.DataFrame(s['ledger'])
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df['Week'], y=df['Revenue'], mode='lines+markers', name='Revenue', line=dict(color='#22c55e', width=3)))
                fig2.add_trace(go.Scatter(x=df['Week'], y=df['Lost Sales'], mode='lines+markers', name='Lost Sales', line=dict(color='#ef4444', width=3)))
                fig2.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=30, b=0),
                                   paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Submit first week to generate chart.")
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col_pie:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Market Share")
            if s['financials'].get('has_intel', True):
                east_player = (s['hub_east']['heavy_share'] * env_mkt_h + s['hub_east']['light_share'] * env_mkt_l) / (env_mkt_h + env_mkt_l)
                west_player = (s['hub_west']['heavy_share'] * env_mkt_h + s['hub_west']['light_share'] * env_mkt_l) / (env_mkt_h + env_mkt_l)
                
                fig3 = make_subplots(rows=2, cols=1, specs=[[{"type": "domain"}], [{"type": "domain"}]], subplot_titles=["East Hub", "West Hub"])
                fig3.add_trace(go.Pie(labels=['Player', 'Apex'], values=[east_player, 1-east_player], marker_colors=['#3b82f6', '#475569']), row=1, col=1)
                fig3.add_trace(go.Pie(labels=['Player', 'Apex'], values=[west_player, 1-west_player], marker_colors=['#3b82f6', '#475569']), row=2, col=1)
                fig3.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=30, b=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)')
                fig3.update_traces(textinfo='label+percent', textfont_size=10)
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Market Share Data Classified. Purchase Market Intel to view.")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
        st.markdown("### Product Sales Details & Ledger")
        if len(s['ledger']) > 0:
            st.dataframe(df.set_index('Week'), use_container_width=True)
        else:
            st.info("No data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_ops:
        col_cap, col_inv = st.columns([1, 2.5])
        
        with col_cap:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown("### Capacity Utilization")
            
            f_used = s['plant']['last_hours_used']
            f_cap = s['capacities']['factory_hours']
            st.write(f"**Factory Hours:** {f_used:,} / {f_cap:,}")
            st.progress(min(1.0, f_used / f_cap if f_cap > 0 else 0))

            r_used = s['plant']['metal_qty'] + s['plant']['plastic_qty']
            r_cap = s['capacities']['raw_warehouse']
            st.write(f"**Raw Warehouse:** {r_used:,} / {r_cap:,}")
            st.progress(min(1.0, r_used / r_cap if r_cap > 0 else 0))
            if s['plant']['wasted_materials'] > 0:
                st.markdown(f"<div class='stat-sub'>⚠️ {s['plant']['wasted_materials']:,} units wasted this run!</div>", unsafe_allow_html=True)

            e_used = s['hub_east']['heavy_qty'] + s['hub_east']['light_qty']
            e_cap = s['capacities']['hub_east']
            st.write(f"**East Hub:** {e_used:,} / {e_cap:,}")
            st.progress(min(1.0, e_used / e_cap if e_cap > 0 else 0))

            w_used = s['hub_west']['heavy_qty'] + s['hub_west']['light_qty']
            w_cap = s['capacities']['hub_west']
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
                    <thead>
                        <tr><th>Asset</th><th style='text-align: right;'>Quantity</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Metal (Raw)</td><td style='text-align: right;'>{s['plant']['metal_qty']:,} units</td></tr>
                        <tr><td>Plastic (Raw)</td><td style='text-align: right;'>{s['plant']['plastic_qty']:,} units</td></tr>
                        <tr><td>Titan Heavy (FG)</td><td style='text-align: right;'>{s['plant']['heavy_qty']:,} units</td></tr>
                        <tr><td>Titan Light (FG)</td><td style='text-align: right;'>{s['plant']['light_qty']:,} units</td></tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with inv_top2:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown(f"""
                <h3 style='margin-top:0;'>Regional Hubs (Current Stock)</h3>
                <table class="dash-table">
                    <thead>
                        <tr><th>Location</th><th style='text-align: right;'>Titan Heavy</th><th style='text-align: right;'>Titan Light</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>East Hub</td><td style='text-align: right;'>{s['hub_east']['heavy_qty']:,} units</td><td style='text-align: right;'>{s['hub_east']['light_qty']:,} units</td></tr>
                        <tr><td>West Hub</td><td style='text-align: right;'>{s['hub_west']['heavy_qty']:,} units</td><td style='text-align: right;'>{s['hub_west']['light_qty']:,} units</td></tr>
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
                    <thead>
                        <tr><th>Metric</th><th style='text-align: right;'>Value</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Heavy Built</td><td style='text-align: right;'>{s['plant']['last_prod_heavy']:,} units</td></tr>
                        <tr><td>Light Built</td><td style='text-align: right;'>{s['plant']['last_prod_light']:,} units</td></tr>
                        <tr><td>Hours Utilized</td><td style='text-align: right;'>{s['plant']['last_hours_used']:,} hrs</td></tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with inv_bot2:
                st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
                st.markdown("<h3 style='margin-top:0;'>In-Transit Pipeline</h3>", unsafe_allow_html=True)
                if len(s['transit']) == 0:
                    st.write("*Pipeline is empty.*")
                else:
                    transit_rows = ""
                    for t in s['transit']:
                        if t['type'] == 'raw':
                            transit_rows += f"<tr><td>📦 To Plant ({t['weeks_left']} wks)</td><td style='text-align: right;'>{t['metal']:,} Metal</td><td style='text-align: right;'>{t['plastic']:,} Plastic</td></tr>"
                        elif t['type'] == 'finished_east':
                            transit_rows += f"<tr><td>🚚 To East ({t['weeks_left']} wks)</td><td style='text-align: right;'>{t['heavy']:,} Heavy</td><td style='text-align: right;'>{t['light']:,} Light</td></tr>"
                        elif t['type'] == 'finished_west':
                            transit_rows += f"<tr><td>🚚 To West ({t['weeks_left']} wks)</td><td style='text-align: right;'>{t['heavy']:,} Heavy</td><td style='text-align: right;'>{t['light']:,} Light</td></tr>"
                    
                    st.markdown(f"""
                    <table class="dash-table">
                        <thead>
                            <tr><th>Destination</th><th style='text-align: right;'>Item 1</th><th style='text-align: right;'>Item 2</th></tr>
                        </thead>
                        <tbody>
                            {transit_rows}
                        </tbody>
                    </table>
                    """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    with tab_manual:
        m1, m2 = st.columns(2)
        
        with m1:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown(f"""
            <h3 style='margin-top:0;'>Bill of Materials & Production</h3>
            <table class="dash-table">
                <thead>
                    <tr><th>Product</th><th>Required Materials</th><th style='text-align: right;'>Factory Time</th></tr>
                </thead>
                <tbody>
                    <tr><td>Titan Heavy</td><td>2 Metal, 2 Plastic</td><td style='text-align: right;'>2 hours per unit</td></tr>
                    <tr><td>Titan Light</td><td>3 Plastic</td><td style='text-align: right;'>1 hour per unit</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown(f"""
            <h3 style='margin-top:0;'>Market Demand Engine (MNL)</h3>
            <p style="font-size: 13px; color: #a1a1aa;">Demand is calculated via a Multinomial Logit Model.</p>
            <table class="dash-table">
                <thead>
                    <tr><th>Input</th><th>Effect on Demand</th></tr>
                </thead>
                <tbody>
                    <tr><td><b>Price</b></td><td>Negative linear effect. Crucial for Titan Light sales.</td></tr>
                    <tr><td><b>Marketing</b></td><td>Positive logarithmic effect (Diminishing returns).</td></tr>
                    <tr><td><b>R&D (Quality)</b></td><td>Positive linear effect. Crucial for Titan Heavy sales.</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown(f"""
            <h3 style='margin-top:0;'>Corporate Finance</h3>
            <p style="font-size: 13px; color: #a1a1aa;">Manage your debt to survive market shocks.</p>
            <table class="dash-table">
                <thead>
                    <tr><th>Rule</th><th>Details</th></tr>
                </thead>
                <tbody>
                    <tr><td><b>Interest Rate</b></td><td>2% per week on total outstanding debt.</td></tr>
                    <tr><td><b>Emergency Loan</b></td><td>Triggered if cash drops below 0. Adds a 5% penalty fee to the borrowed principal.</td></tr>
                    <tr><td><b>Bankruptcy</b></td><td>If total debt exceeds $15,000,000, the bank seizes the company (Game Over).</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with m2:
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown(f"""
            <h3 style='margin-top:0;'>Macroeconomic Shocks</h3>
            <table class="dash-table">
                <thead>
                    <tr><th>Event</th><th>Timing</th><th>Impact</th></tr>
                </thead>
                <tbody>
                    <tr><td><b>Market Contraction</b></td><td>Weeks 4 & 5</td><td>Total available market drops 15% across all regions.</td></tr>
                    <tr><td><b>Supply Chain Crisis</b></td><td>Weeks 7 & 8</td><td>Metal cost increases to $15. Plastic cost increases to $8.</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown(f"""
            <h3 style='margin-top:0;'>Freight Operations (FTL/LTL)</h3>
            <p style="font-size: 13px; color: #a1a1aa;">A Full Truckload (FTL) holds exactly 1,000 units. Carrier delays can increase lead times randomly.</p>
            <table class="dash-table">
                <thead>
                    <tr><th>Freight Mode</th><th style='text-align: right;'>FTL Flat Rate</th><th style='text-align: right;'>LTL Rate (Per Unit)</th><th style='text-align: right;'>Base Lead</th><th style='text-align: right;'>Delay Risk</th></tr>
                </thead>
                <tbody>
                    <tr><td>Economy (Rail/Sea)</td><td style='text-align: right;'>$1,000</td><td style='text-align: right;'>$1.50</td><td style='text-align: right;'>2 Weeks</td><td style='text-align: right;'>20%</td></tr>
                    <tr><td>Standard (Road)</td><td style='text-align: right;'>$2,000</td><td style='text-align: right;'>$3.00</td><td style='text-align: right;'>1 Week</td><td style='text-align: right;'>10%</td></tr>
                    <tr><td>Express (Air)</td><td style='text-align: right;'>$4,000</td><td style='text-align: right;'>$6.00</td><td style='text-align: right;'>Instant</td><td style='text-align: right;'>1%</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
            st.markdown(f"""
            <h3 style='margin-top:0;'>Capacity Upgrades (CAPEX)</h3>
            <table class="dash-table">
                <thead>
                    <tr><th>Facility</th><th style='text-align: right;'>Expansion Cost</th></tr>
                </thead>
                <tbody>
                    <tr><td>Factory Hours</td><td style='text-align: right;'>$50 per additional hour</td></tr>
                    <tr><td>Raw Warehouse</td><td style='text-align: right;'>$2 per unit of space</td></tr>
                    <tr><td>Hub Capacity (East/West)</td><td style='text-align: right;'>$5 per unit of space</td></tr>
                    <tr><td>Transit Capacity</td><td style='text-align: right;'>$10 per unit shipped</td></tr>
                </tbody>
            </table>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_case:
        st.markdown("<div class='dash-panel'>", unsafe_allow_html=True)
        st.markdown("""
        <h1 class='case-header'>Titan Operations: Navigating the Perfect Storm</h1>
        
        <div class='case-text'>
        <p><b>Introduction</b><br>
        You have just been appointed as the Vice President of Supply Chain at Titan Operations, a mid-sized manufacturing firm specializing in heavy-duty machinery and light consumer electronics. Your predecessor was fired for failing to align the factory floor with market demand, leaving the company vulnerable to its primary competitor, Apex Corp.</p>
        
        <p>The board of directors expects you to stabilize the firm, capture market share, and generate maximum free cash flow over the next 12 weeks. Your performance will determine the future of the company.</p>
        
        <p><b>The Products</b><br>
        Your facility produces two items:</p>
        <ul>
            <li><b>Titan Heavy:</b> A premium B2B product. Producing one unit takes 2 units of Metal, 2 units of Plastic, and 2 hours of factory time. Business buyers are highly sensitive to product quality.</li>
            <li><b>Titan Light:</b> A budget B2C product. Producing one unit takes 3 units of Plastic and 1 hour of factory time. Consumer buyers are highly sensitive to price.</li>
        </ul>
        
        <p><b>The Network</b><br>
        You operate a single manufacturing plant that ships finished goods to two regional distribution centers: the East Hub and the West Hub. Every location in your network has strict capacity limits. If you order more raw materials than your warehouse can hold, the excess is discarded at your expense. If you try to push more volume through your transit pipelines or hubs than they can handle, the network will choke. You must actively invest capital (CAPEX) to upgrade these bottlenecks if you want to grow.</p>
        
        <p><b>Market Dynamics</b><br>
        Demand is not guaranteed. You are competing directly against Apex Corp for every sale. Your market share is calculated via a Multinomial Logit engine governed by three factors:</p>
        <ol>
            <li><b>Pricing:</b> Lower prices steal market share, but erode your margins.</li>
            <li><b>Marketing Spend:</b> Generates demand through regional hubs. Be careful: marketing has diminishing returns. Spending double the budget will not yield double the demand.</li>
            <li><b>R&D (Quality):</b> Every dollar spent on R&D permanently increases your Quality Index. This compounds over the entire 12-week period and is critical for selling the Titan Heavy product.</li>
        </ol>
        <p>If you fail to purchase weekly Market Intelligence reports, you will fly blind and lose visibility into Apex Corp's pricing and your own market share.</p>
        
        <p><b>Logistics and Freight</b><br>
        You manage all inbound and outbound freight. You must balance speed against cost.</p>
        <ul>
            <li><b>Economy Freight:</b> Takes 2 weeks. Cheap, but carries a high risk of unexpected carrier delays.</li>
            <li><b>Standard Freight:</b> Takes 1 week. Moderate cost and moderate risk.</li>
            <li><b>Express Freight:</b> Arrives instantly in the same week. Very expensive, but allows you to correct stock-outs immediately.</li>
        </ul>
        <p>Pay attention to your trucking utilization. A Full Truckload (FTL) holds 1,000 units and charges a flat rate. Less-Than-Truckload (LTL) shipments charge a steep per-unit premium.</p>
        
        <p><b>Corporate Finance</b><br>
        You begin with $5,000,000 in cash. Every asset you hold incurs holding costs, and your factory requires $150,000 per week in fixed overhead. You can borrow cash to fund rapid expansion, but the bank charges 2% weekly interest on all outstanding debt.</p> 
        <p>If your cash balance ever drops below zero, the bank will force an emergency bailout loan with a brutal 5% penalty fee. If your total debt exceeds $15,000,000, the bank will seize Titan Operations, and you will be terminated.</p>
        
        <p><b>The Looming Storm</b><br>
        Macroeconomic forecasts are not promising.</p>
        <ul>
            <li><b>Q4/Q5 Recession:</b> Consumer spending data indicates the total market size will contract by 15% during Weeks 4 and 5. If you do not throttle back production, your hubs will overflow with unsold inventory.</li>
            <li><b>Q7/Q8 Supply Shock:</b> Geopolitical instability is threatening the commodity markets. Expect raw material costs for Metal and Plastic to surge during Weeks 7 and 8. If you do not stockpile inventory beforehand, your margins will be erased.</li>
        </ul>
        
        <p>Your goal is to reach Week 12 with the highest Net Position (Cash minus Debt) possible. Do not run out of cash.</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)