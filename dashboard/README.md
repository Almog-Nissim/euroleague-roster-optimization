# Dashboard

React + Vite front end for the EuroLeague roster engine, in Hebrew (RTL).
Live: <https://dashboard-mu-eight-81.vercel.app/>

Three tabs: the headline with a pick-your-club comparison, engine vs reality per club,
and an interactive roster builder across budgets.

The data comes from two JSON files in `public/`, written by the Python side:
`export_dashboard.py` (checks every frozen value first) and `roster_sweep.py`.
Nothing is computed here that the Python side does not already produce.

```bash
npm install
npm run dev      # local
npm run build    # what Vercel runs (Root Directory: dashboard)
```
