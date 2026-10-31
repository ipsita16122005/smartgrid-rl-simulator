# GRIDBOUND: The Energy Chronicles

An interactive RPG-style smart-grid simulator built with Python and Streamlit.

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Create and activate a virtual environment (recommended):

   **Windows**
   ```bash
   py -m venv .venv
   .venv\Scripts\activate
   ```

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Start the website:
   ```bash
   streamlit run app.py
   ```

Streamlit will print a local URL, usually http://localhost:8501. Open it in your browser.

## What's included

- Hour-by-hour campus energy simulation
- Solar generation, demand, battery state and time-of-use prices
- Manual actions and a transparent rule-based Grid Advisor
- Battery charging/discharging limits and charging efficiency
- Adventure log and interactive charts
- Strategy Arena comparing Grid Only, Rule-Based and Balanced Dispatch
- Field Guide explaining RL state, action and reward

## Important project note

The current version is a working educational simulator, not a trained reinforcement-learning system. The Grid Advisor is rule-based. The Strategy Arena compares deterministic benchmark policies. A genuine RL extension should:

1. Implement the simulator as a Gymnasium environment.
2. Define observation space, action space and reward function.
3. Train DQN/PPO with Stable-Baselines3.
4. Evaluate on held-out days and compare with the same baselines.
5. Load the trained policy into the website.

All profiles, prices and emissions factors currently use illustrative demo values, not live data.
