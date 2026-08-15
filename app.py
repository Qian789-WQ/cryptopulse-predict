#!/usr/bin/env python3
"""
CryptoPulse 价格预测网站 - Flask后端
"""
from flask import Flask, render_template, jsonify, request
import requests
import numpy as np
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

# 支持的交易对
SYMBOLS = [
    {"id": "BTC-USDT-SWAP", "name": "BTC 比特币"},
    {"id": "ETH-USDT-SWAP", "name": "ETH 以太坊"},
    {"id": "SOL-USDT-SWAP", "name": "SOL 索拉纳"},
    {"id": "BNB-USDT-SWAP", "name": "BNB 币安币"},
    {"id": "XRP-USDT-SWAP", "name": "XRP 瑞波币"},
    {"id": "DOGE-USDT-SWAP", "name": "DOGE 狗狗币"},
    {"id": "ADA-USDT-SWAP", "name": "ADA 艾达币"},
    {"id": "AVAX-USDT-SWAP", "name": "AVAX 雪崩"},
    {"id": "DOT-USDT-SWAP", "name": "DOT 波卡"},
    {"id": "MATIC-USDT-SWAP", "name": "MATIC 马蹄"},
    {"id": "LINK-USDT-SWAP", "name": "LINK 预言机"},
    {"id": "LTC-USDT-SWAP", "name": "LTC 莱特币"},
    {"id": "TRX-USDT-SWAP", "name": "TRX 波场"},
    {"id": "ATOM-USDT-SWAP", "name": "ATOM 宇宙"},
    {"id": "UNI-USDT-SWAP", "name": "UNI  uni"},
]

TIMEFRAMES = [
    {"id": "1m", "name": "1分钟"},
    {"id": "5m", "name": "5分钟"},
    {"id": "15m", "name": "15分钟"},
    {"id": "1H", "name": "1小时"},
    {"id": "4H", "name": "4小时"},
    {"id": "1D", "name": "日线"},
]

def fetch_klines(symbol, timeframe, limit=500):
    """从OKX获取K线数据"""
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": symbol, "bar": timeframe, "limit": str(limit)}
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get("code") != "0":
            return None, data.get("msg", "API错误")
        
        candles = data["data"][::-1]
        df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume","volCcy","volCcyQuote","confirm"])
        df["timestamp"] = df["timestamp"].astype(int)
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df, None
    except Exception as e:
        return None, str(e)

def calc_indicators(df):
    """计算技术指标"""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    
    df["ma7"] = close.rolling(7).mean()
    df["ma21"] = close.rolling(21).mean()
    df["ma50"] = close.rolling(50).mean()
    
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    
    df["bb_mid"] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    
    df["vol_ma20"] = volume.rolling(20).mean()
    df["vol_ratio"] = volume / df["vol_ma20"]
    df["pct_change"] = close.pct_change() * 100
    
    return df

def predict_price(df, periods=5):
    """简单预测未来价格"""
    recent = df.tail(30).copy()
    recent["x"] = np.arange(len(recent))
    
    x = recent["x"].values
    y = recent["close"].values
    coeffs = np.polyfit(x, y, 1)
    slope = coeffs[0]
    intercept = coeffs[1]
    
    future_x = np.arange(len(recent), len(recent) + periods)
    predicted = slope * future_x + intercept
    
    momentum = (df["close"].iloc[-1] - df["close"].iloc[-5]) / df["close"].iloc[-5] * 100
    volatility = df["pct_change"].tail(20).std()
    
    return {
        "predicted": [float(p) for p in predicted],
        "slope": float(slope),
        "momentum": float(momentum),
        "volatility": float(volatility),
        "trend": "上涨" if slope > 0 else "下跌"
    }

def calc_signal_score(df):
    """综合多因子计算信号评分"""
    score = 50
    reasons = []
    latest = df.iloc[-1]
    
    # MA排列
    if latest["ma7"] > latest["ma21"] > latest["ma50"]:
        score += 20; reasons.append("均线多头排列")
    elif latest["ma7"] < latest["ma21"] < latest["ma50"]:
        score -= 20; reasons.append("均线空头排列")
    elif latest["ma7"] > latest["ma21"]:
        score += 10; reasons.append("短期均线向上")
    else:
        score -= 10; reasons.append("短期均线向下")
    
    # RSI
    rsi = latest["rsi"]
    if rsi < 30:
        score += 15; reasons.append(f"RSI超卖({rsi:.1f})")
    elif rsi > 70:
        score -= 15; reasons.append(f"RSI超买({rsi:.1f})")
    elif rsi < 50:
        score += 5; reasons.append(f"RSI偏弱({rsi:.1f})")
    else:
        score -= 5; reasons.append(f"RSI偏强({rsi:.1f})")
    
    # MACD
    if latest["macd"] > latest["macd_signal"] and latest["macd_hist"] > 0:
        score += 15; reasons.append("MACD金叉向上")
    elif latest["macd"] < latest["macd_signal"] and latest["macd_hist"] < 0:
        score -= 15; reasons.append("MACD死叉向下")
    elif latest["macd_hist"] > 0:
        score += 5; reasons.append("MACD动能向上")
    else:
        score -= 5; reasons.append("MACD动能向下")
    
    # 布林带
    bb_pos = (latest["close"] - latest["bb_lower"]) / (latest["bb_upper"] - latest["bb_lower"])
    if bb_pos < 0.2:
        score += 10; reasons.append(f"接近下轨({bb_pos:.0%})")
    elif bb_pos > 0.8:
        score -= 10; reasons.append(f"接近上轨({bb_pos:.0%})")
    
    # 成交量
    if latest["vol_ratio"] > 1.5 and latest["pct_change"] > 0:
        score += 10; reasons.append(f"放量上涨(量比{latest['vol_ratio']:.1f})")
    elif latest["vol_ratio"] > 1.5 and latest["pct_change"] < 0:
        score -= 10; reasons.append(f"放量下跌(量比{latest['vol_ratio']:.1f})")
    
    # 价格vs MA50
    if latest["close"] > latest["ma50"]:
        score += 10; reasons.append("价格在MA50上方")
    else:
        score -= 10; reasons.append("价格在MA50下方")
    
    # 动量
    momentum = (latest["close"] - df["close"].iloc[-5]) / df["close"].iloc[-5] * 100
    if momentum > 2:
        score += 10; reasons.append(f"5日动量+{momentum:.1f}%")
    elif momentum < -2:
        score -= 10; reasons.append(f"5日动量{momentum:.1f}%")
    
    score = max(0, min(100, score))
    return int(score), reasons

def calc_support_resistance(df):
    """计算支撑阻力位"""
    recent = df.tail(50)
    high = recent["high"].max()
    low = recent["low"].min()
    close = df["close"].iloc[-1]
    
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    
    return {
        "pivot": round(float(pivot), 2),
        "r1": round(float(r1), 2),
        "r2": round(float(r2), 2),
        "s1": round(float(s1), 2),
        "s2": round(float(s2), 2),
        "swing_high": round(float(high), 2),
        "swing_low": round(float(low), 2)
    }


def calc_holding_time(timeframe, prediction, atr, current_price):
    """计算建议持仓时间"""
    # 周期对应的分钟数
    tf_minutes = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1H": 60, "2H": 120, "4H": 240, "6H": 360, "12H": 720, "1D": 1440
    }
    tf_min = tf_minutes.get(timeframe, 60)
    
    # 基础持仓时间：预测5根K线的时间
    base_minutes = tf_min * 5
    
    # 根据波动率调整（ATR占比）
    atr_pct = atr / current_price * 100
    if atr_pct > 3:  # 高波动，缩短持仓
        volatility_factor = 0.6
    elif atr_pct > 1.5:  # 中等波动
        volatility_factor = 0.8
    else:  # 低波动，可以持有更久
        volatility_factor = 1.2
    
    # 根据趋势强度调整
    slope = abs(prediction["slope"])
    slope_pct = slope / current_price * 100
    if slope_pct > 0.5:  # 强趋势
        trend_factor = 1.3
    elif slope_pct > 0.2:  # 中等趋势
        trend_factor = 1.0
    else:  # 弱趋势
        trend_factor = 0.7
    
    # 计算持仓时间范围
    avg_minutes = base_minutes * volatility_factor * trend_factor
    min_minutes = avg_minutes * 0.6
    max_minutes = avg_minutes * 1.4
    
    # 格式化时间
    def format_minutes(mins):
        if mins < 60:
            return f"{int(mins)}分钟"
        elif mins < 1440:
            hours = mins / 60
            return f"{hours:.1f}小时"
        else:
            days = mins / 1440
            return f"{days:.1f}天"
    


def calc_trade_plan(score, current_price, atr, sr, symbol):
    """计算精确交易计划：入场、止损、TP1/2/3、仓位、盈亏比"""
    # 基于评分决定方向
    if score >= 55:
        direction = "long"
        direction_text = "做多"
    elif score <= 45:
        direction = "short"
        direction_text = "做空"
    else:
        return {
            "direction": "neutral",
            "direction_text": "观望",
            "entry": None, "stop_loss": None,
            "tp1": None, "tp2": None, "tp3": None,
            "position_size": 0, "risk_reward": 0,
            "message": "信号不明确，建议观望"
        }
    
    # ATR止损倍数
    atr_sl_mult = 1.5
    atr_tp1_mult = 2.0  # 1:1.33
    atr_tp2_mult = 3.0  # 1:2
    atr_tp3_mult = 4.5  # 1:3
    
    if direction == "long":
        entry = current_price
        stop_loss = entry - atr * atr_sl_mult
        tp1 = entry + atr * atr_tp1_mult
        tp2 = entry + atr * atr_tp2_mult
        tp3 = entry + atr * atr_tp3_mult
    else:
        entry = current_price
        stop_loss = entry + atr * atr_sl_mult
        tp1 = entry - atr * atr_tp1_mult
        tp2 = entry - atr * atr_tp2_mult
        tp3 = entry - atr * atr_tp3_mult
    
    # 盈亏比（用TP1算）
    risk = abs(entry - stop_loss)
    reward = abs(tp1 - entry)
    risk_reward = round(reward / risk, 2) if risk > 0 else 0
    
    # 建议仓位（基于1%风险法则，假设账户1000USDT）
    account_size = 1000  # 默认账户大小
    risk_per_trade = 0.01  # 1%风险
    risk_amount = account_size * risk_per_trade
    if risk > 0:
        position_size = round(risk_amount / risk * entry, 2)
    else:
        position_size = 0
    
    # 仓位百分比
    position_pct = round(position_size / account_size * 100, 1)
    
    return {
        "direction": direction,
        "direction_text": direction_text,
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        "position_size": position_size,
        "position_pct": position_pct,
        "risk_reward": risk_reward,
        "risk_amount": round(risk_amount, 2),
        "atr_sl_mult": atr_sl_mult,
        "message": f"{direction_text}，盈亏比1:{risk_reward}"
    }


def analyze_multi_timeframe(symbol, current_timeframe):
    """多周期共振分析：同时分析多个周期的趋势"""
    try:
        timeframes = ["15m", "1H", "4H", "1D"]
        results = {}
        
        for tf in timeframes:
            df, error = fetch_klines(symbol, tf, 200)
            if error or df is None or len(df) < 50:
                results[tf] = {"trend": "未知", "score": 50, "error": error or "数据不足"}
                continue
            
            df = calc_indicators(df)
            latest = df.iloc[-1]
            
            trend_score = 50
            if latest["ma7"] > latest["ma21"] > latest["ma50"]:
                trend = "上涨"
                trend_score = 75
            elif latest["ma7"] < latest["ma21"] < latest["ma50"]:
                trend = "下跌"
                trend_score = 25
            elif latest["ma7"] > latest["ma21"]:
                trend = "偏多"
                trend_score = 60
            elif latest["ma7"] < latest["ma21"]:
                trend = "偏空"
                trend_score = 40
            else:
                trend = "震荡"
                trend_score = 50
            
            rsi = latest["rsi"]
            if rsi > 70:
                trend_score -= 10
            elif rsi < 30:
                trend_score += 10
            
            trend_score = max(0, min(100, trend_score))
            results[tf] = {
                "trend": trend,
                "score": trend_score,
                "rsi": round(float(rsi), 1),
                "price": round(float(latest["close"]), 2)
            }
        
        scores = [results[tf]["score"] for tf in timeframes if "score" in results[tf]]
        avg_score = sum(scores) / len(scores) if scores else 50
        
        bullish_count = sum(1 for s in scores if s >= 55)
        bearish_count = sum(1 for s in scores if s <= 45)
        
        if bullish_count >= 3:
            resonance = "强烈多头共振"
            resonance_level = 3
        elif bullish_count >= 2:
            resonance = "多头共振"
            resonance_level = 2
        elif bearish_count >= 3:
            resonance = "强烈空头共振"
            resonance_level = -3
        elif bearish_count >= 2:
            resonance = "空头共振"
            resonance_level = -2
        else:
            resonance = "无明显共振"
            resonance_level = 0
        
        return {
            "timeframes": results,
            "avg_score": round(avg_score, 1),
            "resonance": resonance,
            "resonance_level": resonance_level,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "current_timeframe": current_timeframe
        }
    except Exception as e:
        return {
            "timeframes": {},
            "avg_score": 50,
            "resonance": "分析失败",
            "resonance_level": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "current_timeframe": current_timeframe,
            "error": str(e)
        }


def get_funding_rate(symbol):
    """获取当前资金费率"""
    try:
        url = "https://www.okx.com/api/v5/public/funding-rate"
        params = {"instId": symbol}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("code") == "0" and data.get("data"):
            item = data["data"][0]
            rate = float(item.get("fundingRate", 0)) * 100  # 转成百分比
            next_time = int(item.get("nextFundingTime", 0))
            return {
                "rate": round(rate, 4),
                "rate_text": f"{rate:+.4f}%",
                "next_time": next_time,
                "next_time_text": datetime.fromtimestamp(next_time/1000).strftime("%H:%M") if next_time else "--",
                "warning": rate > 0.05 or rate < -0.05  # 费率过高提醒
            }
    except Exception as e:
        pass
    return {"rate": 0, "rate_text": "--", "next_time": 0, "next_time_text": "--", "warning": False}



def calc_fibonacci_and_levels(df):
    """计算斐波那契回撤位和前高前低"""
    recent = df.tail(50)
    high = recent["high"].max()
    low = recent["low"].min()
    diff = high - low
    
    # 斐波那契回撤位
    fib_levels = {
        "0.236": round(high - diff * 0.236, 2),
        "0.382": round(high - diff * 0.382, 2),
        "0.5": round(high - diff * 0.5, 2),
        "0.618": round(high - diff * 0.618, 2),
        "0.786": round(high - diff * 0.786, 2),
    }
    
    # 前高前低（最近20根）
    recent20 = df.tail(20)
    prev_high = round(recent20["high"].iloc[:-1].max(), 2)
    prev_low = round(recent20["low"].iloc[:-1].min(), 2)
    
    # 整数关口
    current = df["close"].iloc[-1]
    round_level = round(current / 1000) * 1000 if current > 1000 else round(current / 100) * 100
    
    return {
        "fibonacci": fib_levels,
        "prev_high": prev_high,
        "prev_low": prev_low,
        "round_level": round_level,
        "swing_high": round(high, 2),
        "swing_low": round(low, 2)
    }



def detect_volume_anomaly(df):
    """检测成交量异常"""
    latest = df.iloc[-1]
    vol_ratio = latest["vol_ratio"]
    pct_change = latest["pct_change"]
    
    anomalies = []
    
    # 放量突破
    if vol_ratio > 2.0 and abs(pct_change) > 1:
        if pct_change > 0:
            anomalies.append({"type": "volume_breakout", "text": f"放量上涨突破 (量比{vol_ratio:.1f})", "bullish": True})
        else:
            anomalies.append({"type": "volume_breakdown", "text": f"放量下跌破位 (量比{vol_ratio:.1f})", "bullish": False})
    
    # 缩量回调
    if vol_ratio < 0.5 and abs(pct_change) < 0.5:
        anomalies.append({"type": "low_volume", "text": f"缩量整理 (量比{vol_ratio:.1f})", "bullish": None})
    
    # 天量
    if vol_ratio > 3:
        anomalies.append({"type": "extreme_volume", "text": f"⚠️ 异常天量 (量比{vol_ratio:.1f})，注意变盘", "bullish": None})
    
    return {
        "vol_ratio": round(float(vol_ratio), 2),
        "anomalies": anomalies,
        "has_anomaly": len(anomalies) > 0
    }



    return {
        "min_minutes": int(min_minutes),
        "max_minutes": int(max_minutes),
        "avg_minutes": int(avg_minutes),
        "min_text": format_minutes(min_minutes),
        "max_text": format_minutes(max_minutes),
        "avg_text": format_minutes(avg_minutes),
        "volatility_factor": volatility_factor,
        "trend_factor": trend_factor,
        "atr_pct": round(atr_pct, 2),
        "slope_pct": round(slope_pct, 4)
    }

    return {
        "pivot": float(pivot),
        "r1": float(r1), "r2": float(r2),
        "s1": float(s1), "s2": float(s2),
        "recent_high": float(high),
        "recent_low": float(low)
    }

@app.route("/")
def index():
    return render_template("index.html", symbols=SYMBOLS, timeframes=TIMEFRAMES)

@app.route("/api/predict")
def api_predict():
    try:
        symbol = request.args.get("symbol", "BTC-USDT-SWAP")
        timeframe = request.args.get("timeframe", "1H")
        
        df, error = fetch_klines(symbol, timeframe, 500)
        if error:
            return jsonify({"error": f"获取数据失败: {error}"}), 500
        if df is None or len(df) < 100:
            return jsonify({"error": "数据不足"}), 500
        
        df = calc_indicators(df)
        latest = df.iloc[-1]
        pred = predict_price(df, periods=5)
        score, reasons = calc_signal_score(df)
        sr = calc_support_resistance(df)
        
        if score >= 70:
            signal = "强烈看涨"
            signal_class = "strong-bullish"
        elif score >= 55:
            signal = "偏多"
            signal_class = "bullish"
        elif score >= 45:
            signal = "中性观望"
            signal_class = "neutral"
        elif score >= 30:
            signal = "偏空"
            signal_class = "bearish"
        else:
            signal = "强烈看空"
            signal_class = "strong-bearish"
        
        ht = calc_holding_time(timeframe, pred, float(latest["atr"]), float(latest["close"]))
        if score >= 60:
            advice = f"可考虑做多，止损设在 ${sr['s1']:,.2f}，第一目标 ${sr['r1']:,.2f}，建议持仓 {ht['min_text']}~{ht['max_text']}"
        elif score <= 40:
            advice = f"可考虑做空，止损设在 ${sr['r1']:,.2f}，第一目标 ${sr['s1']:,.2f}，建议持仓 {ht['min_text']}~{ht['max_text']}"
        else:
            advice = f"信号不明确，建议观望等待，如入场建议持仓不超过 {ht['avg_text']}"
        
        return jsonify({
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": float(latest["close"]),
            "pct_change": float(latest["pct_change"]),
            "vol_ratio": float(latest["vol_ratio"]),
            "rsi": float(latest["rsi"]),
            "atr": float(latest["atr"]),
            "prediction": pred,
            "score": score,
            "signal": signal,
            "signal_class": signal_class,
            "reasons": reasons,
            "support_resistance": sr,
            "holding_time": ht,
            "trade_plan": calc_trade_plan(score, float(latest["close"]), float(latest["atr"]), sr, symbol),
            "multi_tf": analyze_multi_timeframe(symbol, timeframe),
            "funding_rate": get_funding_rate(symbol),
            "fib_levels": calc_fibonacci_and_levels(df),
            "volume_anomaly": detect_volume_anomaly(df),
            "advice": advice,
            "timestamp": datetime.now().isoformat(),
            "candles_count": len(df)
        })
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
