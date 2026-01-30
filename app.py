from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd
import requests
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")


def build_pl_timeseries(orders: pd.DataFrame, pair: str):
    od = orders[(orders["pair"] == pair)].copy()
    od = od.sort_values("date")

    base = str(od.iloc[0]["base"])
    quote = str(od.iloc[0]["quote"])

    lots = []
    realized = 0.0
    series = []

    for _, r in od.iterrows():
        typ = r["type"]
        qty = float(r["filled"] or 0.0)
        total = float(r["total"] or 0.0)
        fee_asset = r.get("fee_asset")
        fee_qty = float(r.get("fee_qty") or 0.0)

        if typ == "BUY":
            net_qty = qty
            cost = total

            if fee_asset == base:
                net_qty = qty - fee_qty
            elif fee_asset == quote:
                cost = total + fee_qty

            lots.append([net_qty, cost])

        elif typ == "SELL":
            sold_qty = qty
            proceeds = total

            if fee_asset == quote:
                proceeds = total - fee_qty
            elif fee_asset == base:
                sold_qty = qty + fee_qty

            remaining = sold_qty
            cost_basis = 0.0

            while remaining > 1e-12 and lots:
                lot_qty, lot_cost = lots[0]
                if lot_qty <= remaining:
                    cost_basis += lot_cost
                    remaining -= lot_qty
                    lots.pop(0)
                else:
                    frac = remaining / lot_qty
                    cost_basis += lot_cost * frac
                    lots[0][0] = lot_qty - remaining
                    lots[0][1] = lot_cost * (1 - frac)
                    remaining = 0.0

            realized += (proceeds - cost_basis)

            series.append({
                "date": r["date"].strftime("%Y-%m-%d %H:%M:%S"),
                "pl": round(realized, 2)
            })

    return series



# ---------- Parsing helpers ----------

FEE_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([A-Za-z0-9]+)\s*$")


def parse_fee(fee_str: Any) -> Tuple[Optional[str], float]:
    """
    Binance export sometimes puts Fee like "0.00000229BTC" or "0.103371BRL".
    Returns (asset, qty). If cannot parse, returns (None, 0.0).
    """
    if not isinstance(fee_str, str):
        return (None, 0.0)
    s = fee_str.replace(" ", "")
    m = FEE_RE.match(s)
    if not m:
        # try without whitespace anchors
        m = re.match(r"([0-9]*\.?[0-9]+)([A-Za-z0-9]+)", s)
    if not m:
        return (None, 0.0)
    return (m.group(2), float(m.group(1)))


def extract_orders(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans the Binance "Spot Order History" export that contains repeated header rows.
    Keeps only real order rows (BUY/SELL) and tries to attach the fee that appears
    in a following "detail" row.
    """
    orders: List[Dict[str, Any]] = []
    n = len(raw_df)

    for i, row in raw_df.iterrows():
        typ = row.get("Type")
        pair = row.get("Pair")

        if isinstance(typ, str) and typ in ("BUY", "SELL") and isinstance(pair, str) and "/" in pair:
            base = row.get("Base Asset")
            quote = row.get("Quote Asset")
            status = row.get("Status")

            # These columns usually already contain the right filled/total:
            filled = row.get("Filled")
            total = row.get("Total")
            avg_price = row.get("AvgTrading Price") if pd.notna(row.get("AvgTrading Price")) else row.get("Order Price")

            date = pd.to_datetime(row.get("Date(UTC)"), errors="coerce")

            # Fee often appears in a following "detail" row where "Quote Asset" is like "0.00000229BTC".
            fee_asset: Optional[str] = None
            fee_qty: float = 0.0
            for j in range(i + 1, min(i + 4, n)):
                r2 = raw_df.iloc[j]
                fee_candidate = r2.get("Quote Asset")
                fa, fq = parse_fee(fee_candidate)
                if fa:
                    fee_asset, fee_qty = fa, fq
                    break

            orders.append(
                {
                    "date": date,
                    "pair": pair,
                    "type": typ,
                    "base": base,
                    "quote": quote,
                    "filled": float(filled) if pd.notna(filled) else None,
                    "total": float(total) if pd.notna(total) else None,
                    "avg_price": float(avg_price) if pd.notna(avg_price) else None,
                    "fee_asset": fee_asset,
                    "fee_qty": float(fee_qty or 0.0),
                    "status": status,
                }
            )

    out = pd.DataFrame(orders)
    if len(out) == 0:
        return out
    out = out.dropna(subset=["date", "pair", "type"])
    out = out.sort_values("date")
    return out


# ---------- P/L computation (FIFO) ----------

@dataclass
class PLResult:
    pair: str
    base: str
    quote: str
    realized_pl: float
    proceeds_total: float
    cost_sold_total: float
    position_qty: float
    position_cost: float
    avg_cost: float
    unrealized_pl: Optional[float]
    current_price: Optional[float]


def compute_pl_fifo(orders: pd.DataFrame, pair: str, current_price: Optional[float]) -> PLResult:
    od = orders[(orders["pair"] == pair)].copy()
    od = od.sort_values("date")

    if len(od) == 0:
        raise ValueError("Nenhuma ordem encontrada para o par selecionado.")

    base = str(od.iloc[0]["base"])
    quote = str(od.iloc[0]["quote"])

    # Each lot = [qty_base, cost_quote_total]
    lots: List[List[float]] = []

    realized = 0.0
    proceeds_total = 0.0
    cost_sold_total = 0.0

    for _, r in od.iterrows():
        typ = r["type"]
        qty = float(r["filled"] or 0.0)
        total = float(r["total"] or 0.0)

        fee_asset = r.get("fee_asset")
        fee_qty = float(r.get("fee_qty") or 0.0)

        if typ == "BUY":
            net_qty = qty
            cost = total

            # Heuristic:
            # - if fee charged in base asset, we receive less base.
            # - if fee charged in quote asset, we pay a little more quote.
            if fee_asset == base:
                net_qty = qty - fee_qty
            elif fee_asset == quote:
                cost = total + fee_qty

            lots.append([net_qty, cost])

        elif typ == "SELL":
            sold_qty = qty
            proceeds = total

            # Heuristic:
            # - if fee charged in quote asset, proceeds reduce.
            # - if fee charged in base asset, more base was deducted to sell.
            if fee_asset == quote:
                proceeds = total - fee_qty
            elif fee_asset == base:
                sold_qty = qty + fee_qty

            remaining = sold_qty
            cost_basis = 0.0

            while remaining > 1e-12 and lots:
                lot_qty, lot_cost = lots[0]
                if lot_qty <= remaining + 1e-12:
                    cost_basis += lot_cost
                    remaining -= lot_qty
                    lots.pop(0)
                else:
                    frac = remaining / lot_qty
                    cost_basis += lot_cost * frac
                    lots[0][0] = lot_qty - remaining
                    lots[0][1] = lot_cost * (1 - frac)
                    remaining = 0.0

            realized += (proceeds - cost_basis)
            proceeds_total += proceeds
            cost_sold_total += cost_basis

    position_qty = sum(q for q, _ in lots)
    position_cost = sum(c for _, c in lots)
    avg_cost = (position_cost / position_qty) if position_qty > 1e-12 else 0.0

    unrealized_pl = None
    if current_price is not None and position_qty > 1e-12:
        unrealized_pl = position_qty * current_price - position_cost

    return PLResult(
        pair=pair,
        base=base,
        quote=quote,
        realized_pl=realized,
        proceeds_total=proceeds_total,
        cost_sold_total=cost_sold_total,
        position_qty=position_qty,
        position_cost=position_cost,
        avg_cost=avg_cost,
        unrealized_pl=unrealized_pl,
        current_price=current_price,
    )


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip().replace(".", "").replace(",", ".")  # tolerate pt-BR
        return float(s)
    except Exception:
        return None


def fetch_price_binance(symbol: str) -> Optional[float]:
    """
    Fetch last price from Binance public API (no key).
    Example symbols: BTCBRL, BTCUSDT, ETHBRL...
    """
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        return float(data["price"])
    except Exception:
        return None


# ---------- Routes ----------

@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():    
    """
    Accepts an uploaded .xlsx export and returns summary + rows.
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Envie um arquivo .xlsx."}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".xlsx"):
        return jsonify({"ok": False, "error": "Formato inválido. Envie um .xlsx."}), 400

    desired_pair = request.form.get("pair", "").strip()
    current_price = safe_float(request.form.get("current_price"))

    try:
        content = f.read()
        raw_df = pd.read_excel(io.BytesIO(content))
        orders = extract_orders(raw_df)
        if len(orders) == 0:
            return jsonify({"ok": False, "error": "Não encontrei ordens BUY/SELL no arquivo."}), 400

        pairs = sorted(orders["pair"].dropna().unique().tolist())

        if not desired_pair:
            if "BTC/BRL" in pairs:
                desired_pair = "BTC/BRL"
            else:
                desired_pair = pairs[0]

        # If no current price provided, try to auto-fetch from Binance (only for symbols like BTC/BRL -> BTCBRL).
        auto_price = None
        if current_price is None:
            symbol = desired_pair.replace("/", "")
            auto_price = fetch_price_binance(symbol)
            current_price = auto_price

        res = compute_pl_fifo(orders, desired_pair, current_price)

        # Return also a small table for transparency.
        view = orders[orders["pair"] == desired_pair].copy()
        view["date"] = view["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
        rows = view.tail(200).to_dict(orient="records")

        pl_series = build_pl_timeseries(orders, desired_pair)

        return jsonify(
            {
                "ok": True,
                "pairs": pairs,
                "selected_pair": desired_pair,
                "result": {
                    "pair": res.pair,
                    "base": res.base,
                    "quote": res.quote,
                    "realized_pl": res.realized_pl,
                    "unrealized_pl": res.unrealized_pl,
                    "current_price": res.current_price,
                    "position_qty": res.position_qty,
                    "position_cost": res.position_cost,
                    "avg_cost": res.avg_cost,
                    "proceeds_total": res.proceeds_total,
                    "cost_sold_total": res.cost_sold_total,
                },
                "rows": rows,
                "price_source": "auto" if auto_price is not None and request.form.get("current_price") in (None, "",) else "manual",
                "notes": [
                    "Cálculo de custo: FIFO (primeiro que entra, primeiro que sai).",
                    "Heurística de fee: se a taxa estiver na moeda base, reduz a quantidade recebida (BUY) / aumenta a quantidade vendida (SELL). Se estiver na moeda cotada, ajusta custo/proventos.",
                    "Para taxas em outra moeda (ex: BNB), o app não converte automaticamente (ficaria dependendo de cotação da taxa).",
                ],
                "pl_series": pl_series,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Falha ao processar: {e}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)