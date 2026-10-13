"""Fetch MGC/GC Dec-2026 gold bars from Yahoo for the AI Playbook gold dashboard.
Writes gold.json in the same shape as IBKR's price history, one entry per timeframe."""
import json, datetime as dt
import pandas as pd, yfinance as yf
SYM, FB = "GCZ26.CMX", "GC=F"
TF = [("ONE_MIN","1m","7d",60,None),("FIVE_MINS","5m","30d",300,None),("FIFTEEN_MINS","15m","60d",900,None),
      ("THIRTY_MINS","30m","60d",1800,None),("ONE_HOUR","60m","60d",3600,None),("FOUR_HOURS","60m","730d",14400,"4h"),
      ("ONE_DAY","60m","730d",86400,"session"),("ONE_WEEK","1wk","10y",604800,None),("ONE_MONTH","1mo","max",2678400,None)]
def get(iv, per):
    for s in (SYM, FB):
        df = yf.download(s, interval=iv, period=per, progress=False, auto_adjust=False)
        if df is not None and len(df) >= 30:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df[["Open","High","Low","Close"]].dropna()
            df.index = df.index.tz_convert("UTC") if df.index.tz is not None else df.index.tz_localize("UTC")
            return df, s
    return None, None
now = dt.datetime.now(dt.timezone.utc)
out = {"symbol": SYM, "generated_utc": now.isoformat(timespec="seconds").replace("+00:00","Z"), "timeframes": {}}
cache = {}
for step, iv, per, secs, rs in TF:
    key = (iv, per)
    if key not in cache: cache[key] = get(iv, per)
    df, used = cache[key]
    if df is None: out["timeframes"][step] = {"error": "no data from Yahoo"}; continue
    if rs == "session":
        df = df.resample("24h", offset="22h").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
    elif rs:
        df = df.resample(rs).agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
    df = df.iloc[-261:]
    out["timeframes"][step] = {"symbol_used": used, "chart_step": secs, "chart_end": out["generated_utc"],
        "time": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in df.index],
        "open": [round(float(x), 2) for x in df["Open"]], "high": [round(float(x), 2) for x in df["High"]],
        "low": [round(float(x), 2) for x in df["Low"]], "close": [round(float(x), 2) for x in df["Close"]]}
    print(step, used, len(df), df.index[-1])
json.dump(out, open("gold.json", "w"))
