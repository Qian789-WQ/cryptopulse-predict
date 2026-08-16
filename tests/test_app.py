import unittest
from unittest.mock import Mock, patch
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
        self.assertAlmostEqual(
            plan["risk_amount"],
            plan["price_risk_amount"] + plan["estimated_roundtrip_cost"],
            places=2,
        )
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

    def test_risk_gate_blocks_crowded_same_direction_funding(self):
        plan = cryptopulse.calc_trade_plan(75, 100, 2, {}, "BTC-USDT-SWAP")
        blocked, gate = cryptopulse.apply_trade_risk_gate(
            plan,
            {"predicted": [101, 103, 105, 106, 107]},
            {"confirmed": True}, 30, {"is_fake": False}, {"level": "low"}, {},
            funding_rate={"rate": 0.08, "warning": True},
        )
        self.assertFalse(gate["allowed"])
        self.assertEqual(blocked["direction"], "neutral")
        self.assertTrue(any("资金费率" in reason for reason in gate["reasons"]))

    def test_short_signal_win_rate_uses_conviction(self):
        self.assertEqual(
            cryptopulse.estimate_win_rate(20, 25, False, False, 0),
            cryptopulse.estimate_win_rate(80, 25, False, False, 0),
        )

    def test_confirmation_uses_rendered_multi_timeframe_snapshot(self):
        snapshot = {"timeframes": {"4H": {"score": 72}, "1H": {"score": 61}}}
        confirmation = cryptopulse.confirmation_from_multi_tf(snapshot)
        self.assertTrue(confirmation["confirmed"])
        self.assertEqual(confirmation["score_4h"], 72)

    def test_4h_signal_treats_opposite_1h_as_cautious_entry(self):
        snapshot = {
            "current_timeframe": "4H",
            "timeframes": {"4H": {"score": 25}, "1H": {"score": 75}},
        }
        confirmation = cryptopulse.confirmation_from_multi_tf(snapshot, "short")
        self.assertFalse(confirmation["confirmed"])
        self.assertTrue(confirmation["compatible"])

        plan = cryptopulse.calc_trade_plan(25, 100, 2, {}, "BTC-USDT-SWAP")
        allowed, gate = cryptopulse.apply_trade_risk_gate(
            plan, {"predicted": [99, 97, 95, 94, 93]}, confirmation, 30,
            {"is_fake": False}, {"level": "low"}, {},
        )
        self.assertTrue(gate["allowed"])
        self.assertEqual(gate["mode"], "cautious")
        self.assertEqual(gate["risk_multiplier"], 0.5)
        self.assertEqual(allowed["direction"], "short")

    def test_prediction_exposes_expanding_uncertainty_band(self):
        prediction = cryptopulse.predict_price(cryptopulse.calc_indicators(sample_market_data()))
        self.assertEqual(len(prediction["lower"]), 5)
        self.assertTrue(all(lo <= mid <= hi for lo, mid, hi in zip(
            prediction["lower"], prediction["predicted"], prediction["upper"]
        )))
        self.assertGreaterEqual(
            prediction["upper"][-1] - prediction["lower"][-1],
            prediction["upper"][0] - prediction["lower"][0],
        )

    def test_data_freshness_uses_timeframe_duration(self):
        result = cryptopulse.get_data_freshness(1_000_000, "1H", now_ms=8_200_000)
        self.assertFalse(result["stale"])
        stale = cryptopulse.get_data_freshness(1_000_000, "1H", now_ms=12_000_001)
        self.assertTrue(stale["stale"])


class RouteTests(unittest.TestCase):
    def setUp(self):
        cryptopulse.app.config.update(TESTING=True, SECRET_KEY="test")
        cryptopulse._cache["live_symbols"] = (
            [dict(item, category="", tick_size="", max_leverage="") for item in cryptopulse.SYMBOLS],
            __import__("time").time(),
        )
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
        self.assertIn("win_rate_ci", payload)
        self.assertIn("sample_quality", payload)
        self.assertIn("expectancy", payload)

    @patch.object(cryptopulse, "get_open_interest_context")
    @patch.object(cryptopulse, "get_data_freshness")
    @patch.object(cryptopulse, "get_market_quality")
    @patch.object(cryptopulse, "get_mark_price")
    @patch.object(cryptopulse, "get_funding_rate")
    @patch.object(cryptopulse, "fetch_klines")
    def test_predict_contract_contains_frontend_fields(
        self, fetch_klines, funding_rate, mark_price, market_quality, freshness, open_interest
    ):
        self.login()
        fetch_klines.return_value = (sample_market_data(), None)
        funding_rate.return_value = {
            "rate": 0,
            "rate_text": "0.0000%",
            "next_time": 0,
            "next_time_text": "--",
            "warning": False,
        }
        mark_price.return_value = {"price": 129.5, "timestamp": 123456789}
        market_quality.return_value = {
            "available": True, "tradeable": True, "spread_pct": 0.01,
            "quote_volume_24h": 10_000_000, "reason": "执行质量正常",
        }
        freshness.return_value = {"stale": False, "age_minutes": 60, "max_age_minutes": 180}
        open_interest.return_value = {
            "available": True, "oi_usd": 50_000_000, "change_pct": None,
            "regime": "collecting", "note": "正在采样",
        }
        response = self.client.get(
            "/api/predict?symbol=BTC-USDT-SWAP&timeframe=1H"
        )
        self.assertEqual(response.status_code, 200)
        plan = response.get_json()["trade_plan"]
        self.assertIn("pyramid", plan)
        self.assertEqual(plan["time_stop"]["max_holding_minutes"], 300)
        self.assertEqual(response.get_json()["mark_price"]["price"], 129.5)
        self.assertTrue(response.get_json()["market_quality"]["tradeable"])
        self.assertTrue(response.get_json()["open_interest"]["available"])
        self.assertIn("lower", response.get_json()["prediction"])
        self.assertEqual(fetch_klines.call_count, 5)

    @patch.object(cryptopulse, "fetch_with_retry")
    def test_market_quality_calculates_spread_and_quote_volume(self, fetch):
        cryptopulse._cache.pop("market_quality_BTC-USDT-SWAP", None)
        response = Mock()
        response.json.return_value = {"code": "0", "data": [{
            "bidPx": "99.9", "askPx": "100.1", "last": "100",
            "volCcy24h": "20000", "ts": str(int(__import__("time").time() * 1000)),
        }]}
        fetch.return_value = response
        quality = cryptopulse.get_market_quality("BTC-USDT-SWAP")
        self.assertAlmostEqual(quality["spread_pct"], 0.2, places=3)
        self.assertEqual(quality["quote_volume_24h"], 2_000_000)
        self.assertFalse(quality["tradeable"])

    @patch.object(cryptopulse, "fetch_with_retry")
    def test_open_interest_context_reports_current_usd_value(self, fetch):
        symbol = "ETH-USDT-SWAP"
        cryptopulse._cache.pop(f"open_interest_{symbol}", None)
        cryptopulse._oi_samples.pop(symbol, None)
        response = Mock()
        response.json.return_value = {"code": "0", "data": [{
            "oiCcy": "10000", "oiUsd": "20000000", "ts": "123456789",
        }]}
        fetch.return_value = response
        context = cryptopulse.get_open_interest_context(symbol, 2000, 100_000_000)
        self.assertTrue(context["available"])
        self.assertEqual(context["oi_usd"], 20_000_000)
        self.assertEqual(context["regime"], "collecting")
        self.assertEqual(context["oi_to_volume_ratio"], 0.2)

    def test_risk_settings_are_bounded(self):
        self.login()
        with cryptopulse.app.test_request_context(
            "/api/predict?risk_pct=99&max_leverage=50&max_margin_pct=99"
        ):
            settings = cryptopulse.get_risk_settings()
        self.assertEqual(settings["risk_pct"], 3)
        self.assertEqual(settings["max_leverage"], 10)
        self.assertEqual(settings["max_margin_pct"], 50)

    def test_symbols_route_returns_current_cached_catalog(self):
        self.login()
        response = self.client.get("/api/symbols")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], len(cryptopulse.SYMBOLS))
        self.assertEqual(payload["data"][0]["id"], cryptopulse.SYMBOLS[0]["id"])

    def test_frontend_guards_websocket_symbol_switch(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        self.assertIn("instId===selectedSymbol", html)
        self.assertIn("subscribedSymbol", html)
        self.assertIn("requestId!==predictionRequestId", html)
        self.assertIn("normalizeRiskSettings", html)
        self.assertIn("markPrices[o.symbol]||livePrices[o.symbol]", html)
        self.assertIn("if(wsConnected)subscribeSymbol(id);\n            predict();", html)
        self.assertNotIn("calcLiquidation", html)
        self.assertNotIn("kellyPos", html)
        self.assertNotIn("economicEvents", html)
        self.assertIn("orderRoundtripCost", html)
        self.assertIn("marketQualityVal", html)
        self.assertIn("openInterestVal", html)
        self.assertIn('id="decisionCockpit"', html)
        self.assertIn('id="professionalDetails" style="display:none"', html)
        self.assertIn("function renderDecisionCockpit", html)
        self.assertIn("function confirmPyramidAdd", html)
        self.assertIn("function confirmTakeProfit", html)
        self.assertIn("filled_notional:plannedNotional*0.5", html)
        self.assertIn("亏损仓禁止补仓", html)
        self.assertIn("function buildTradeSizing", html)
        self.assertIn("function previewPyramidAdd", html)
        self.assertIn("function recommendedLeverageForData", html)
        self.assertIn("max_loss_amount:sizing.maxLoss", html)
        self.assertIn("系统推荐并采用杠杆", html)
        self.assertIn("本次加仓保证金", html)
        self.assertIn("const WATCH_TIMEFRAMES=['15m','1H','4H']", html)
        self.assertIn('id="favoriteToggle"', html)
        self.assertIn("function scanWatchlist", html)
        self.assertIn("function showWatchSignal", html)
        self.assertIn("function signalRiskCap", html)
        self.assertIn("轻仓模式", html)
        self.assertIn('id=\'orderSetupModal\'', html)
        self.assertIn("function submitOrderSetup", html)
        self.assertIn("function actualTradePlanHtml", html)
        self.assertIn("不再显示模型默认仓位", html)
        self.assertIn("Notification.permission==='granted'", html)
        self.assertIn("pushWechat(`⭐ ${title}`", html)


if __name__ == "__main__":
    unittest.main()
