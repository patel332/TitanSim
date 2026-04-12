# Titan Operations: Supply Chain Management Simulation

Titan Operations is an advanced, interactive MBA-level business simulation built in Python. Players step into the role of Vice President of Supply Chain, tasked with rescuing a struggling manufacturing firm, competing for market share, and navigating a volatile global economy over a simulated 12-week fiscal quarter.

## 🚀 Key Features

* **Dynamic Demand Engine (MNL):** Market share is not guaranteed. Demand is calculated using a Multinomial Logit Model factoring in Price elasticity, R&D (Quality) compounding, and Marketing spend (diminishing returns).
* **Freight & Logistics Physics:** Balance speed vs. cost with Economy (2-week), Standard (1-week), and Express (Instant) freight. The engine automatically calculates Full Truckload (FTL) flat rates vs. Less-Than-Truckload (LTL) unit premiums, while injecting realistic carrier delay probabilities.
* **Corporate Finance:** Manage a $5M starting cash balance against a $150K weekly overhead. Take on debt to fund massive CAPEX network expansions, but manage the 2% weekly interest rate to avoid emergency bailout penalties and bankruptcy.
* **Macroeconomic Shocks:** Survive dynamic events including a Q4 15% global market contraction and a Q7 raw materials price surge. 
* **Executive Audit Report:** At the end of the 12 weeks, the dashboard collapses into a printable Executive Summary detailing Net Position, Cost Breakdowns, Asset Positions, and a downloadable CSV ledger for academic grading.

## 🛠 Tech Stack

* **Frontend & Framework:** [Streamlit](https://streamlit.io/)
* **Data Manipulation:** [Pandas](https://pandas.pydata.org/)
* **Data Visualization:** [Plotly](https://plotly.com/)
* **Database (Multiplayer):** [Supabase](https://supabase.com/)

## 💻 How to Run Locally

If you want to run the single-player simulation on your local machine:

1. Clone this repository:
   ```bash
   git clone [https://github.com/your-username/titan-operations-sim.git](https://github.com/your-username/titan-operations-sim.git)