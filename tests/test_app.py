import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np
import pandas as pd

import app as cryptopulse


def sample_market_data(rows=120):
    close = np.linspace(100, 130, rows)
    return pd.DataFrame(
        {
            "timestamp": np.arange(rows) * 3_600_000,
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.linspace(1_000, 2_000, rows),
        }
    )


class CalculationTests(unittest.TestCase):
    def test_indicators_include_ma20(self):
        result = cryptopulse.calc_indicators(sample_market_data())
        self.assertIn("ma20", result.columns)
        self.assertTrue(np.isfinite(result.iloc[-1]["ma20"]))

    def test_trade_plan_contains_monitoring_fields(self):
        plan = cryptopulse.calc_trade_plan(75, 100, 2, {}, "BTC-USDT-SWAP")
        self.assertEqual(plan["direction"], "long")
        self.assertEqual(plan["pyramid"]["entry1"]["pct"], 50)
        self.assertEqual(plan["pyramid"]["entry2"]["pct"], 30)
        self.assertEqual(plan["pyramid"]["entry3"]["pct"], 20)
        self.assertEqual(plan["time_stop"]["max_candles"], 5)
        self.assertEqual(plan["signal_strength"], "strong")
        self.assertLessEqual(plan["margin_pct"], 25)
        self.assertLessEqual(plan["leverage"], 5)
        self.assertLessEqual(plan["risk_amount"], plan["risk_budget"])
        self.assertGreater(plan["pyramid"]["entry2"]["price"], plan["entry"])
        self.assertGreater(plan["pyramid"]["entry3"]["price"], plan["pyramid"]["entry2"]["price"])

    def test_risk_gate_blocks_conflicting_timeframes(self):
        plan = cryptopulse.calc_trade_plan(75, 100, 2, {}, "BTC-USDT-SWAP")
        blocked, gate = cryptopulse.apply_trade_risk_gate(
            plan,
            {"predicted": [101, 102, 103, 104, 105]},
            {"confirmed": False},
            30,
            {"is_fake": False},
            {"level": "low"},
            {},
        )
        self.assertFalse(gate["allowed"])
        self.assertEqual(blocked["direction"], "neutral")
        self.assertEqual(blocked["notional_value"], 0)

    def test_risk_gate_allows_aligned_economic_setup(self):
        plan = cryptopulse.calc_trade_plan(75, 100, 2, {}, "BTC-USDT-SWAP")
        allowed, gate = cryptopulse.apply_trade_risk_gate(
            plan,
            {"predicted": [101, 103, 105, 106, 107]},
            {"confirmed": True},
            30,
            {"is_fake": False},
            {"level": "low"},
            {},
        )
        self.assertTrue(gate["allowed"])
        self.assertEqual(allowed["direction"], "long")

    def test_short_signal_win_rate_uses_conviction(self):
        self.assertEqual(
            cryptopulse.estimate_win_rate(20, 25, False, False, 0),
            cryptopulse.estimate_win_rate(80, 25, False, False, 0),
        )


class RouteTests(unittest.TestCase):
    def setUp(self):
        cryptopulse.app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = cryptopulse.app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def test_market_api_requires_login(self):
        response = self.client.get("/api/price")
        self.assertEqual(response.status_code, 401)
        self.assertIn("登录已过期", response.get_json()["error"])

    def test_predict_rejects_unknown_symbol_before_fetch(self):
        self.login()
        response = self.client.get("/api/predict?symbol=INVALID&timeframe=1H")
        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持", response.get_json()["error"])

    @patch.object(cryptopulse, "fetch_history_klines")
    def test_backtest_reports_actual_coverage(self, fetch_history):
        self.login()
        fetch_history.return_value = (sample_market_data(120), None)
        response = self.client.get(
            "/api/backtest?symbol=BTC-USDT-SWAP&timeframe=1H&days=30&capital=1000"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["bars_count"], 120)
        self.assertIn("actual_days", payload)
        self.assertIn("下一根开盘成交", payload["strategy_note"])
        self.assertGreater(payload["fee_rate_pct"], 0)

    @patch.object(cryptopulse, "get_funding_rate")
    @patch.object(cryptopulse, "fetch_klines")
    def test_predict_contract_contains_frontend_fields(self, fetch_klines, funding_rate):
        self.login()
        fetch_klines.return_value = (sample_market_data(), None)
        funding_rate.return_value = {
            "rate": 0,
            "rate_text": "0.0000%",
            "next_time": 0,
            "next_time_text": "--",
            "warning": False,
        }
        response = self.client.get(
            "/api/predict?symbol=BTC-USDT-SWAP&timeframe=1H"
        )
        self.assertEqual(response.status_code, 200)
        plan = response.get_json()["trade_plan"]
        self.assertIn("pyramid", plan)
        self.assertEqual(plan["time_stop"]["max_holding_minutes"], 300)

    def test_frontend_guards_websocket_symbol_switch(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        self.assertIn("instId===selectedSymbol", html)
        self.assertIn("subscribedSymbol", html)
        self.assertIn("requestId!==predictionRequestId", html)


if __name__ == "__main__":
    unittest.main()
