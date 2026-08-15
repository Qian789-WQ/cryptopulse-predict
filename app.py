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
    symbol = request.args.get("symbol", "BTC-USDT-SWAP")
    timeframe = request.args.get("timeframe", "1H")
    
    # 获取数据
    df, error = fetch_klines(symbol, timeframe, 500)
    if error:
        return jsonify({"error": f"获取数据失败: {error}"}), 500
    if df is None or len(df) < 100:
        return jsonify({"error": "数据不足"}), 500
    
    # 计算指标
    df = calc_indicators(df)
    latest = df.iloc[-1]
    
    # 预测
    pred = predict_price(df, periods=5)
    
    # 评分
    score, reasons = calc_signal_score(df)
    
    # 支撑阻力
    sr = calc_support_resistance(df)
    
    # 信号
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
    
    # 操作建议
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
        "holding_time": calc_holding_time(timeframe, pred, float(latest["atr"]), float(latest["close"])),
        "advice": advice,
        "timestamp": datetime.now().isoformat(),
        "candles_count": len(df)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
