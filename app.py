#!/usr/bin/env python3
"""
CryptoPulse 价格预测网站 - Flask后端
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
from hmac import compare_digest
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import time
import hashlib
import os

# 简单内存缓存
_cache = {}
_CACHE_TTL = 30  # 缓存30秒

def get_cache(key, ttl=_CACHE_TTL):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < ttl:
            return data
        else:
            del _cache[key]
    return None

def set_cache(key, data):
    _cache[key] = (data, time.time())
    if len(_cache) > 100:  # 最多缓存100条
        oldest = min(_cache.keys(), key=lambda k: _cache[k][1])
        del _cache[oldest]

def fetch_with_retry(url, params=None, retries=2, timeout=10):
    """带重试的HTTP请求"""
    for i in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(0.5)
    return None
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.secret_key = os.environ.get("SECRET_KEY", "cryptopulse_secret_key_2024")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "fuqian42")


# 支持的交易对
SYMBOLS = [
    # 主流币
    {"id": "BTC-USDT-SWAP", "name": "BTC 比特币"},
    {"id": "ETH-USDT-SWAP", "name": "ETH 以太坊"},
    {"id": "BNB-USDT-SWAP", "name": "BNB 币安币"},
    {"id": "SOL-USDT-SWAP", "name": "SOL 索拉纳"},
    {"id": "XRP-USDT-SWAP", "name": "XRP 瑞波"},
    {"id": "ADA-USDT-SWAP", "name": "ADA 艾达币"},
    {"id": "DOGE-USDT-SWAP", "name": "DOGE 狗狗币"},
    {"id": "AVAX-USDT-SWAP", "name": "AVAX 雪崩"},
    {"id": "DOT-USDT-SWAP", "name": "DOT 波卡"},
    {"id": "MATIC-USDT-SWAP", "name": "MATIC 马蹄"},
    {"id": "LINK-USDT-SWAP", "name": "LINK 预言机"},
    {"id": "LTC-USDT-SWAP", "name": "LTC 莱特币"},
    {"id": "TRX-USDT-SWAP", "name": "TRX 波场"},
    {"id": "ATOM-USDT-SWAP", "name": "ATOM 宇宙"},
    {"id": "UNI-USDT-SWAP", "name": "UNI  Uni"},
    # 热门Meme
    {"id": "SHIB-USDT-SWAP", "name": "SHIB 柴犬币"},
    {"id": "PEPE-USDT-SWAP", "name": "PEPE 青蛙"},
    {"id": "FLOKI-USDT-SWAP", "name": "FLOKI 弗洛基"},
    {"id": "WIF-USDT-SWAP", "name": "WIF 狗帽"},
    {"id": "BONK-USDT-SWAP", "name": "BONK Solana狗"},
    {"id": "ORDI-USDT-SWAP", "name": "ORDI 比特币NFT"},
    {"id": "SATS-USDT-SWAP", "name": "SATS 聪"},
    {"id": "MEME-USDT-SWAP", "name": "MEME Meme币"},
    {"id": "TURBO-USDT-SWAP", "name": "TURBO 涡轮"},
    {"id": "LADYS-USDT-SWAP", "name": "LADYS 女士币"},
    # 新公链/L2
    {"id": "ARB-USDT-SWAP", "name": "ARB Arbitrum"},
    {"id": "OP-USDT-SWAP", "name": "OP Optimism"},
    {"id": "APT-USDT-SWAP", "name": "APT Aptos"},
    {"id": "SUI-USDT-SWAP", "name": "SUI Sui"},
    {"id": "SEI-USDT-SWAP", "name": "SEI Sei"},
    {"id": "TIA-USDT-SWAP", "name": "TIA Celestia"},
    {"id": "INJ-USDT-SWAP", "name": "INJ Injective"},
    {"id": "JUP-USDT-SWAP", "name": "JUP Jupiter"},
    {"id": "NEAR-USDT-SWAP", "name": "NEAR 近协议"},
    {"id": "ALGO-USDT-SWAP", "name": "ALGO 阿尔戈"},
    {"id": "ICP-USDT-SWAP", "name": "ICP 互联网计算机"},
    {"id": "KAS-USDT-SWAP", "name": "KAS Kaspa"},
    {"id": "CFX-USDT-SWAP", "name": "CFX 树图"},
    {"id": "FTM-USDT-SWAP", "name": "FTM 幻影"},
    {"id": "HBAR-USDT-SWAP", "name": "HBAR 哈希图"},
    {"id": "VET-USDT-SWAP", "name": "VET 唯链"},
    {"id": "XTZ-USDT-SWAP", "name": "XTZ 泰佐斯"},
    {"id": "EOS-USDT-SWAP", "name": "EOS 柚子"},
    {"id": "ETC-USDT-SWAP", "name": "ETC 以太经典"},
    {"id": "BCH-USDT-SWAP", "name": "BCH 比特现金"},
    {"id": "XLM-USDT-SWAP", "name": "XLM 恒星币"},
    {"id": "NEO-USDT-SWAP", "name": "NEO 小蚁"},
    {"id": "QTUM-USDT-SWAP", "name": "QTUM 量子链"},
    # DeFi
    {"id": "AAVE-USDT-SWAP", "name": "AAVE Aave"},
    {"id": "CRV-USDT-SWAP", "name": "CRV Curve"},
    {"id": "COMP-USDT-SWAP", "name": "COMP Compound"},
    {"id": "MKR-USDT-SWAP", "name": "MKR Maker"},
    {"id": "SNX-USDT-SWAP", "name": "SNX 合成器"},
    {"id": "YFI-USDT-SWAP", "name": "YFI 大姨夫"},
    {"id": "LDO-USDT-SWAP", "name": "LDO Lido"},
    {"id": "RPL-USDT-SWAP", "name": "RPL 火箭池"},
    {"id": "FXS-USDT-SWAP", "name": "FXS Frax"},
    {"id": "DYDX-USDT-SWAP", "name": "DYDX dYdX"},
    {"id": "GMX-USDT-SWAP", "name": "GMX GMX"},
    {"id": "CAKE-USDT-SWAP", "name": "CAKE 薄饼"},
    {"id": "SUSHI-USDT-SWAP", "name": "SUSHI 寿司"},
    {"id": "1INCH-USDT-SWAP", "name": "1INCH 1inch"},
    {"id": "ZRX-USDT-SWAP", "name": "ZRX 0x"},
    {"id": "KNC-USDT-SWAP", "name": "KNC Kyber"},
    {"id": "BAL-USDT-SWAP", "name": "BAL Balancer"},
    {"id": "REN-USDT-SWAP", "name": "REN Republic"},
    # AI概念
    {"id": "FET-USDT-SWAP", "name": "FET Fetch.AI"},
    {"id": "AGIX-USDT-SWAP", "name": "AGIX Singularity"},
    {"id": "RNDR-USDT-SWAP", "name": "RNDR 渲染"},
    {"id": "GRT-USDT-SWAP", "name": "GRT 图谱"},
    {"id": "OCEAN-USDT-SWAP", "name": "OCEAN 海洋"},
    {"id": "CQT-USDT-SWAP", "name": "CQT Covalent"},
    {"id": "TAO-USDT-SWAP", "name": "TAO Bittensor"},
    {"id": "ARK-USDT-SWAP", "name": "ARK Ark"},
    # 游戏/元宇宙
    {"id": "AXS-USDT-SWAP", "name": "AXS 轴无限"},
    {"id": "SAND-USDT-SWAP", "name": "SAND 沙盒"},
    {"id": "MANA-USDT-SWAP", "name": "MANA Decentraland"},
    {"id": "GALA-USDT-SWAP", "name": "GALA 晚会"},
    {"id": "ENJ-USDT-SWAP", "name": "ENJ Enjin"},
    {"id": "ILV-USDT-SWAP", "name": "ILV 宝藏"},
    {"id": "APE-USDT-SWAP", "name": "APE 猿币"},
    {"id": "IMX-USDT-SWAP", "name": "IMX 不可变"},
    {"id": "GMT-USDT-SWAP", "name": "GMT StepN"},
    {"id": "GAL-USDT-SWAP", "name": "GAL Project Galaxy"},
    # 存储
    {"id": "FIL-USDT-SWAP", "name": "FIL 文件币"},
    {"id": "AR-USDT-SWAP", "name": "AR Arweave"},
    {"id": "STORJ-USDT-SWAP", "name": "STORJ Storj"},
    {"id": "BLUR-USDT-SWAP", "name": "BLUR Blur"},
    # 隐私
    {"id": "XMR-USDT-SWAP", "name": "XMR 门罗币"},
    {"id": "ZEC-USDT-SWAP", "name": "ZEC 大零币"},
    {"id": "DASH-USDT-SWAP", "name": "DASH 达世币"},
    # 其他热门
    {"id": "RUNE-USDT-SWAP", "name": "RUNE Thorchain"},
    {"id": "EGLD-USDT-SWAP", "name": "EGLD 金精灵"},
    {"id": "FLOW-USDT-SWAP", "name": "FLOW Flow"},
    {"id": "CHZ-USDT-SWAP", "name": "CHZ 粉丝币"},
    {"id": "BAT-USDT-SWAP", "name": "BAT 注意力币"},
    {"id": "ZIL-USDT-SWAP", "name": "ZIL Zilliqa"},
    {"id": "WAVES-USDT-SWAP", "name": "WAVES 波浪"},
    {"id": "KAVA-USDT-SWAP", "name": "KAVA Kava"},
    {"id": "ROSE-USDT-SWAP", "name": "ROSE 绿洲"},
    {"id": "CELO-USDT-SWAP", "name": "CELO Celo"},
    {"id": "ONE-USDT-SWAP", "name": "ONE 和谐"},
    {"id": "LRC-USDT-SWAP", "name": "LRC Loopring"},
    {"id": "CELR-USDT-SWAP", "name": "CELR Celer"},
    {"id": "ANKR-USDT-SWAP", "name": "ANKR Ankr"},
    {"id": "CKB-USDT-SWAP", "name": "CKB Nervos"},
    {"id": "MINA-USDT-SWAP", "name": "MINA Mina"},
    {"id": "IOTX-USDT-SWAP", "name": "IOTX IoTeX"},
    {"id": "ARPA-USDT-SWAP", "name": "ARPA ARPA"},
    {"id": "CTSI-USDT-SWAP", "name": "CTSI Cartesi"},
    {"id": "REQ-USDT-SWAP", "name": "REQ Request"},
    {"id": "LPT-USDT-SWAP", "name": "LPT Livepeer"},
    {"id": "BAND-USDT-SWAP", "name": "BAND 预言机"},
    {"id": "API3-USDT-SWAP", "name": "API3 API3"},
    {"id": "TRB-USDT-SWAP", "name": "TRB Tellor"},
    {"id": "UMA-USDT-SWAP", "name": "UMA UMA"},
    {"id": "BADGER-USDT-SWAP", "name": "BADGER Badger"},
    {"id": "DIGG-USDT-SWAP", "name": "DIGG Digg"},
    {"id": "PENDLE-USDT-SWAP", "name": "PENDLE Pendle"},
    {"id": "AERO-USDT-SWAP", "name": "AERO Aerodrome"},
    {"id": "W-USDT-SWAP", "name": "W  wormhole"},
    {"id": "JTO-USDT-SWAP", "name": "JTO Jito"},
    {"id": "STRK-USDT-SWAP", "name": "STRK Starknet"},
    {"id": "DYM-USDT-SWAP", "name": "DYM Dymension"},
    {"id": "PYTH-USDT-SWAP", "name": "PYTH Pyth"},
    {"id": "WLD-USDT-SWAP", "name": "WLD Worldcoin"},
    {"id": "PIXEL-USDT-SWAP", "name": "PIXEL Pixel"},
    {"id": "PORTAL-USDT-SWAP", "name": "PORTAL Portal"},
    {"id": "ETHFI-USDT-SWAP", "name": "ETHFI ether.fi"},
    {"id": "ENA-USDT-SWAP", "name": "ENA Ethena"},
    {"id": "OMNI-USDT-SWAP", "name": "OMNI Omni"},
    {"id": "TON-USDT-SWAP", "name": "TON Toncoin"},
    {"id": "NOT-USDT-SWAP", "name": "NOT Notcoin"},
    {"id": "HMSTR-USDT-SWAP", "name": "HMSTR Hamster"},
    {"id": "DOGS-USDT-SWAP", "name": "DOGS Dogs"},
    {"id": "CAT-USDT-SWAP", "name": "CAT Catizen"},
    {"id": "BOME-USDT-SWAP", "name": "BOME Book of Meme"},
    {"id": "SLERF-USDT-SWAP", "name": "SLERF Slerf"},
    {"id": "MEW-USDT-SWAP", "name": "MEW MEW"},
    {"id": "PNUT-USDT-SWAP", "name": "PNUT Peanut"},
    {"id": "GOAT-USDT-SWAP", "name": "GOAT Goat"},
    {"id": "BRETT-USDT-SWAP", "name": "BRETT Brett"},
    {"id": "MOG-USDT-SWAP", "name": "MOG Mog"},
    {"id": "NORMIE-USDT-SWAP", "name": "NORMIE Normie"},
    {"id": "FARTCOIN-USDT-SWAP", "name": "FARTCOIN Fartcoin"},
    # 美股/科技股永续
    {"id": "NVDA-USDT-SWAP", "name": "NVDA 英伟达"},
    {"id": "AMD-USDT-SWAP", "name": "AMD 超威半导体"},
    {"id": "AAPL-USDT-SWAP", "name": "AAPL 苹果"},
    {"id": "MSFT-USDT-SWAP", "name": "MSFT 微软"},
    {"id": "TSLA-USDT-SWAP", "name": "TSLA 特斯拉"},
    {"id": "META-USDT-SWAP", "name": "META Meta"},
    {"id": "GOOGL-USDT-SWAP", "name": "GOOGL 谷歌"},
    {"id": "AMZN-USDT-SWAP", "name": "AMZN 亚马逊"},
    {"id": "NFLX-USDT-SWAP", "name": "NFLX 奈飞"},
    {"id": "AVGO-USDT-SWAP", "name": "AVGO 博通"},
    {"id": "TSM-USDT-SWAP", "name": "TSM 台积电"},
    {"id": "INTC-USDT-SWAP", "name": "INTC 英特尔"},
    {"id": "QCOM-USDT-SWAP", "name": "QCOM 高通"},
    {"id": "MU-USDT-SWAP", "name": "MU 美光"},
    {"id": "SNDK-USDT-SWAP", "name": "SNDK 闪迪"},
    {"id": "ARM-USDT-SWAP", "name": "ARM Arm"},
    {"id": "SMCI-USDT-SWAP", "name": "SMCI 超微电脑"},
    {"id": "PLTR-USDT-SWAP", "name": "PLTR Palantir"},
    {"id": "COIN-USDT-SWAP", "name": "COIN Coinbase"},
    {"id": "MSTR-USDT-SWAP", "name": "MSTR MicroStrategy"},
    {"id": "HOOD-USDT-SWAP", "name": "HOOD Robinhood"},
    {"id": "UBER-USDT-SWAP", "name": "UBER 优步"},
    {"id": "SHOP-USDT-SWAP", "name": "SHOP Shopify"},
    {"id": "SQ-USDT-SWAP", "name": "SQ Block"},
    {"id": "PYPL-USDT-SWAP", "name": "PYPL PayPal"},
    {"id": "DIS-USDT-SWAP", "name": "DIS 迪士尼"},
    {"id": "NKE-USDT-SWAP", "name": "NKE 耐克"},
    {"id": "COST-USDT-SWAP", "name": "COST 开市客"},
    {"id": "WMT-USDT-SWAP", "name": "WMT 沃尔玛"},
    {"id": "JPM-USDT-SWAP", "name": "JPM 摩根大通"},
    {"id": "V-USDT-SWAP", "name": "V  Visa"},
    {"id": "MA-USDT-SWAP", "name": "MA 万事达"},
    {"id": "BA-USDT-SWAP", "name": "BA 波音"},
    {"id": "GE-USDT-SWAP", "name": "GE 通用电气"},
    {"id": "F-USDT-SWAP", "name": "F 福特"},
    {"id": "GM-USDT-SWAP", "name": "GM 通用汽车"},
    {"id": "RIVN-USDT-SWAP", "name": "RIVN Rivian"},
    {"id": "LCID-USDT-SWAP", "name": "LCID Lucid"},
    {"id": "RBLX-USDT-SWAP", "name": "RBLX Roblox"},
    {"id": "SNAP-USDT-SWAP", "name": "SNAP Snap"},
    {"id": "PINS-USDT-SWAP", "name": "PINS Pinterest"},
    {"id": "SPOT-USDT-SWAP", "name": "SPOT Spotify"},
    {"id": "U-USDT-SWAP", "name": "U Unity"},
    {"id": "AFRM-USDT-SWAP", "name": "AFRM Affirm"},
    {"id": "SOFI-USDT-SWAP", "name": "SOFI SoFi"},
    {"id": "UPST-USDT-SWAP", "name": "UPST Upstart"},
    # 中概股
    {"id": "BABA-USDT-SWAP", "name": "BABA 阿里巴巴"},
    {"id": "JD-USDT-SWAP", "name": "JD 京东"},
    {"id": "PDD-USDT-SWAP", "name": "PDD 拼多多"},
    {"id": "BIDU-USDT-SWAP", "name": "BIDU 百度"},
    {"id": "NIO-USDT-SWAP", "name": "NIO 蔚来"},
    {"id": "XPEV-USDT-SWAP", "name": "XPEV 小鹏"},
    {"id": "LI-USDT-SWAP", "name": "LI 理想"},
    {"id": "TME-USDT-SWAP", "name": "TME 腾讯音乐"},
    {"id": "VIPS-USDT-SWAP", "name": "VIPS 唯品会"},
    {"id": "BILI-USDT-SWAP", "name": "BILI 哔哩哔哩"},
    {"id": "IQ-USDT-SWAP", "name": "IQ 爱奇艺"},
    {"id": "HUYA-USDT-SWAP", "name": "HUYA 虎牙"},
    {"id": "DOYU-USDT-SWAP", "name": "DOYU 斗鱼"},
    {"id": "TAL-USDT-SWAP", "name": "TAL 好未来"},
    {"id": "EDU-USDT-SWAP", "name": "EDU 新东方"},
    {"id": "ZTO-USDT-SWAP", "name": "ZTO 中通快递"},
    {"id": "YMM-USDT-SWAP", "name": "YMM 满帮"},
    # 指数/ETF
    {"id": "SPX-USDT-SWAP", "name": "SPX 标普500"},
    {"id": "IXIC-USDT-SWAP", "name": "IXIC 纳斯达克"},
    {"id": "DJI-USDT-SWAP", "name": "DJI 道琼斯"},
    {"id": "SOX-USDT-SWAP", "name": "SOX 费城半导体"},
    {"id": "VIX-USDT-SWAP", "name": "VIX 恐慌指数"},
    {"id": "USOIL-USDT-SWAP", "name": "USOIL WTI原油"},
    {"id": "UKOIL-USDT-SWAP", "name": "UKOIL 布伦特原油"},
    {"id": "XAU-USDT-SWAP", "name": "XAU 黄金"},
    {"id": "XAG-USDT-SWAP", "name": "XAG 白银"},
    {"id": "SPEX-USDT-SWAP", "name": "SPEX 太空指数"},
]

TIMEFRAMES = [
    {"id": "1m", "name": "1分"},
    {"id": "3m", "name": "3分"},
    {"id": "5m", "name": "5分"},
    {"id": "15m", "name": "15分"},
    {"id": "30m", "name": "30分"},
    {"id": "1H", "name": "1时"},
    {"id": "2H", "name": "2时"},
    {"id": "4H", "name": "4时"},
    {"id": "6H", "name": "6时"},
    {"id": "8H", "name": "8时"},
    {"id": "12H", "name": "12时"},
    {"id": "1D", "name": "1天"},
    {"id": "3D", "name": "3天"},
    {"id": "1W", "name": "1周"},
    {"id": "1M", "name": "1月"},
]

SYMBOL_IDS = {item["id"] for item in SYMBOLS}
TIMEFRAME_IDS = {item["id"] for item in TIMEFRAMES}
TIMEFRAME_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1H": 3_600_000, "2H": 7_200_000,
    "4H": 14_400_000, "6H": 21_600_000, "8H": 28_800_000,
    "12H": 43_200_000, "1D": 86_400_000, "3D": 259_200_000,
    "1W": 604_800_000, "1M": 2_592_000_000,
}
STATIC_SYMBOL_NAMES = {item["id"]: item["name"] for item in SYMBOLS}


def get_live_symbols():
    """Return currently tradeable USDT linear swaps, falling back to the static catalog."""
    cached = get_cache("live_symbols", ttl=3600)
    if cached is not None:
        return cached
    fallback_cached = get_cache("live_symbols_fallback", ttl=300)
    if fallback_cached is not None:
        return fallback_cached
    try:
        resp = fetch_with_retry(
            "https://www.okx.com/api/v5/public/instruments",
            params={"instType": "SWAP"}, retries=2, timeout=10
        )
        payload = resp.json() if resp is not None else {}
        if payload.get("code") != "0":
            raise ValueError(payload.get("msg", "获取合约列表失败"))
        items = []
        for instrument in payload.get("data", []):
            inst_id = instrument.get("instId", "")
            if (instrument.get("state") != "live" or not inst_id.endswith("-USDT-SWAP")
                    or instrument.get("ctType") not in ("", "linear")):
                continue
            base = inst_id.removesuffix("-USDT-SWAP")
            items.append({
                "id": inst_id,
                "name": STATIC_SYMBOL_NAMES.get(inst_id, base),
                "category": instrument.get("instCategory", ""),
                "tick_size": instrument.get("tickSz", ""),
                "max_leverage": instrument.get("lever", ""),
            })
        if not items:
            raise ValueError("OKX未返回可交易USDT永续合约")
        preferred_order = {item["id"]: index for index, item in enumerate(SYMBOLS)}
        items.sort(key=lambda item: (preferred_order.get(item["id"], 9999), item["id"]))
        set_cache("live_symbols", items)
        return items
    except Exception:
        fallback = [dict(item, category="", tick_size="", max_leverage="") for item in SYMBOLS]
        set_cache("live_symbols_fallback", fallback)
        return fallback


def get_symbol_ids():
    return {item["id"] for item in get_live_symbols()}


def get_market_params():
    """Validate user supplied market parameters before calling OKX."""
    symbol = request.args.get("symbol", "BTC-USDT-SWAP")
    timeframe = request.args.get("timeframe", "1H")
    if symbol not in get_symbol_ids():
        return None, None, (jsonify({"error": "不支持的交易品种"}), 400)
    if timeframe not in TIMEFRAME_IDS:
        return None, None, (jsonify({"error": "不支持的时间周期"}), 400)
    return symbol, timeframe, None


def get_risk_settings():
    """Read bounded, user-configurable risk inputs from the request."""
    def number(name, default, minimum, maximum):
        try:
            value = float(request.args.get(name, default))
            if not np.isfinite(value):
                raise ValueError
            return max(minimum, min(value, maximum))
        except (TypeError, ValueError):
            return default

    return {
        "account_size": number("account_size", 1000, 10, 100_000_000),
        "risk_pct": number("risk_pct", 1, 0.1, 3),
        "max_margin_pct": number("max_margin_pct", 25, 1, 50),
        "max_leverage": int(number("max_leverage", 5, 1, 10)),
        "fee_pct": number("fee_pct", 0.05, 0, 1),
        "slippage_pct": number("slippage_pct", 0.02, 0, 1),
        "max_total_risk_pct": number("max_total_risk_pct", 3, 0.5, 10),
        "max_direction_exposure_pct": number("max_direction_exposure_pct", 100, 10, 500),
        "daily_loss_limit_pct": number("daily_loss_limit_pct", 3, 0.5, 20),
        "max_open_positions": int(number("max_open_positions", 3, 1, 20)),
    }

def fetch_klines(symbol, timeframe, limit=500):
    """从OKX获取K线数据"""
    url = "https://www.okx.com/api/v5/market/candles"
    # OKX candles endpoint returns at most 300 records per request.
    params = {"instId": symbol, "bar": timeframe, "limit": str(min(max(int(limit), 1), 300))}
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get("code") != "0":
            return None, data.get("msg", "API错误")
        
        return candles_to_dataframe(data["data"]), None
    except Exception as e:
        return None, str(e)


def get_market_quality(symbol):
    """Measure executable market quality from the current best bid/ask and 24h volume."""
    cache_key = f"market_quality_{symbol}"
    cached = get_cache(cache_key, ttl=10)
    if cached is not None:
        return cached
    unavailable = {"available": False, "tradeable": False, "reason": "盘口质量数据不可用"}
    try:
        resp = fetch_with_retry(
            "https://www.okx.com/api/v5/market/ticker",
            params={"instId": symbol}, retries=2, timeout=8
        )
        payload = resp.json() if resp is not None else {}
        if payload.get("code") != "0" or not payload.get("data"):
            return unavailable
        item = payload["data"][0]
        bid, ask, last = float(item["bidPx"]), float(item["askPx"]), float(item["last"])
        if bid <= 0 or ask <= 0 or ask < bid or last <= 0:
            return unavailable
        midpoint = (bid + ask) / 2
        spread_pct = (ask - bid) / midpoint * 100
        base_volume = float(item.get("volCcy24h") or 0)
        quote_volume = base_volume * last
        timestamp = int(item.get("ts") or 0)
        stale = timestamp <= 0 or int(time.time() * 1000) - timestamp > 60_000
        reasons = []
        if stale:
            reasons.append("盘口快照已过期")
        if spread_pct > 0.15:
            reasons.append(f"买卖点差{spread_pct:.3f}%过高")
        if quote_volume < 1_000_000:
            reasons.append(f"24小时成交额约${quote_volume:,.0f}，流动性不足")
        result = {
            "available": True,
            "tradeable": not reasons,
            "reason": "；".join(reasons) if reasons else "点差和成交额满足执行要求",
            "bid": bid, "ask": ask, "last": last,
            "spread_pct": round(spread_pct, 4),
            "quote_volume_24h": round(quote_volume, 2),
            "timestamp": timestamp,
        }
        set_cache(cache_key, result)
        return result
    except Exception:
        return unavailable


def get_data_freshness(candle_timestamp, timeframe, now_ms=None):
    """Reject signals built from candles older than three expected bar durations."""
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    duration = TIMEFRAME_MS.get(timeframe, 3_600_000)
    age_ms = max(0, now_ms - int(candle_timestamp))
    max_age_ms = duration * 3
    return {
        "stale": age_ms > max_age_ms,
        "age_minutes": round(age_ms / 60_000, 1),
        "max_age_minutes": round(max_age_ms / 60_000, 1),
    }


def candles_to_dataframe(candles):
    """Normalize OKX newest-first candle arrays into chronological rows."""
    candles = sorted(candles, key=lambda row: int(row[0]))
    df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume","volCcy","volCcyQuote","confirm"])
    if not df.empty:
        df["timestamp"] = df["timestamp"].astype(int)
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
    return df


def fetch_history_klines(symbol, timeframe, limit):
    """Fetch multiple OKX history pages, capped to keep a web request bounded."""
    target = min(max(int(limit), 1), 3000)
    url = "https://www.okx.com/api/v5/market/history-candles"
    rows = {}
    after = None
    try:
        while len(rows) < target:
            page_limit = min(300, target - len(rows))
            params = {"instId": symbol, "bar": timeframe, "limit": str(page_limit)}
            if after is not None:
                params["after"] = str(after)
            resp = fetch_with_retry(url, params=params, retries=2, timeout=15)
            if resp is None:
                return None, "OKX历史K线请求失败"
            payload = resp.json()
            if payload.get("code") != "0":
                return None, payload.get("msg", "API错误")
            page = payload.get("data") or []
            if not page:
                break
            for row in page:
                rows[int(row[0])] = row
            oldest = min(int(row[0]) for row in page)
            if after == oldest or len(page) < page_limit:
                break
            after = oldest
        return candles_to_dataframe(list(rows.values())[-target:]), None
    except Exception as e:
        return None, str(e)

def calc_indicators(df):
    """计算技术指标"""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    
    df["ma7"] = close.rolling(7).mean()
    df["ma20"] = close.rolling(20).mean()
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
    
    # KDJ指标
    low_9 = low.rolling(window=9).min()
    high_9 = high.rolling(window=9).max()
    rsv = (close - low_9) / (high_9 - low_9) * 100
    df["kdj_k"] = rsv.ewm(com=2).mean()
    df["kdj_d"] = df["kdj_k"].ewm(com=2).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]
    
    # 威廉指标
    df["willr"] = -100 * (high_9 - close) / (high_9 - low_9)
    
    # CCI指标
    tp = (high + low + close) / 3
    df["cci"] = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).std())
    
    # ADX趋势强度
    plus_dm = (high - high.shift()).where((high - high.shift()) > (low.shift() - low), 0)
    minus_dm = (low.shift() - low).where((low.shift() - low) > (high - high.shift()), 0)
    atr14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr14)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr14)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df["adx"] = dx.rolling(14).mean()
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di
    
    # K线实体和影线
    df["body"] = abs(close - df["open"])
    df["upper_wick"] = high - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - low
    df["is_bullish"] = close > df["open"]
    
    # 连涨连跌
    df["consecutive"] = (df["pct_change"] > 0).astype(int).groupby((df["pct_change"] <= 0).cumsum()).cumsum()
    df["consecutive_down"] = (df["pct_change"] < 0).astype(int).groupby((df["pct_change"] >= 0).cumsum()).cumsum()
    
    # 填充NaN
    df["kdj_k"] = df["kdj_k"].fillna(50)
    df["kdj_d"] = df["kdj_d"].fillna(50)
    df["kdj_j"] = df["kdj_j"].fillna(50)
    df["willr"] = df["willr"].fillna(-50)
    df["cci"] = df["cci"].fillna(0)
    df["adx"] = df["adx"].fillna(20)
    df["plus_di"] = df["plus_di"].fillna(20)
    df["minus_di"] = df["minus_di"].fillna(20)
    
    return df

def predict_price(df, periods=5):
    """Return a baseline path plus a volatility-aware uncertainty band."""
    df = df.dropna(subset=["close"])
    if len(df) < 30:
        price = float(df["close"].iloc[-1])
        return {"predicted": [price] * periods, "lower": [price] * periods,
                "upper": [price] * periods, "trend": "数据不足", "slope": 0,
                "momentum": 0, "volatility": 0, "mean_reversion": 0,
                "model_note": "数据不足，仅显示当前价格"}
    
    recent = df.tail(30)
    x = np.arange(len(recent))
    y = recent["close"].values
    
    # 加权线性回归（近期权重更大）
    weights = np.linspace(0.5, 2.0, len(recent))
    try:
        slope, intercept = np.polyfit(x, y, 1, w=weights)
    except:
        slope, intercept = np.polyfit(x, y, 1)
    
    future_x = np.arange(len(recent), len(recent) + periods)
    base_pred = slope * future_x + intercept
    
    # 动量调整
    momentum_1 = (recent["close"].iloc[-1] - recent["close"].iloc[-3]) / recent["close"].iloc[-3]
    momentum_3 = (recent["close"].iloc[-1] - recent["close"].iloc[-10]) / recent["close"].iloc[-10]
    avg_momentum = (momentum_1 * 0.6 + momentum_3 * 0.4)
    current_price = recent["close"].iloc[-1]
    
    # 均值回归
    ma20 = recent["close"].rolling(20).mean().iloc[-1]
    deviation = (current_price - ma20) / ma20 if ma20 else 0
    mean_reversion = -deviation * 0.1
    
    # 波动率
    volatility = float(df["pct_change"].tail(20).std())
    
    # 最终预测
    momentum_adj = np.linspace(0, avg_momentum * current_price * 0.3, periods)
    reversion_adj = np.linspace(0, mean_reversion * current_price * 0.5, periods)
    predicted = base_pred + momentum_adj + reversion_adj

    fitted = slope * x + intercept
    residual_std = float(np.std(y - fitted))
    one_bar_move = abs(volatility) / 100 * current_price
    base_uncertainty = max(residual_std, one_bar_move)
    bands = np.array([base_uncertainty * np.sqrt(step) for step in range(1, periods + 1)])
    lower = predicted - bands
    upper = predicted + bands
    
    trend_score = slope / current_price * 100 + avg_momentum * 50
    trend = "上涨" if trend_score > 0.3 else "下跌" if trend_score < -0.3 else "震荡"
    
    return {
        "predicted": [round(float(p), 2) for p in predicted],
        "lower": [round(float(p), 2) for p in lower],
        "upper": [round(float(p), 2) for p in upper],
        "slope": float(slope),
        "momentum": round(float(avg_momentum * 100), 2),
        "volatility": round(float(volatility), 2),
        "trend": trend,
        "mean_reversion": round(float(mean_reversion * 100), 2),
        "model_note": "线性基准路径与波动区间，不是目标价或概率保证",
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
        "1H": 60, "2H": 120, "4H": 240, "6H": 360, "8H": 480,
        "12H": 720, "1D": 1440, "3D": 4320, "1W": 10080, "1M": 43200
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
        "min_text": format_minutes(min_minutes),
        "max_text": format_minutes(max_minutes),
        "avg_text": format_minutes(avg_minutes),
        "min_minutes": round(min_minutes, 1),
        "max_minutes": round(max_minutes, 1),
        "avg_minutes": round(avg_minutes, 1),
        "volatility_factor": volatility_factor,
        "trend_factor": trend_factor
    }
    


def calc_trade_plan(score, current_price, atr, sr, symbol, leverage=3, account_size=1000,
                    risk_pct=1, max_margin_pct=25, max_leverage=5,
                    roundtrip_cost_pct=0.14):
    """Build a risk-budgeted plan with unambiguous margin and notional values."""
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
            "position_size": 0, "position_pct": 0, "margin_amount": 0,
            "margin_pct": 0, "notional_value": 0, "risk_reward": 0,
            "price_risk_amount": 0, "estimated_roundtrip_cost": 0,
            "risk_amount": 0, "risk_budget": round(account_size * risk_pct / 100, 2),
            "signal_strength": "none", "strength_text": "无交易信号",
            "pyramid": {"enabled": False}, "time_stop": {"enabled": False},
            "message": "信号不明确，建议观望"
        }
    
    # ATR止损倍数（盈亏比1:3到1:5）
    atr_sl_mult = 1.0
    atr_tp1_mult = 3.0  # 1:3
    atr_tp2_mult = 4.0  # 1:4
    atr_tp3_mult = 5.0  # 1:5
    
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
    gross_risk_reward = round(reward / risk, 2) if risk > 0 else 0
    
    # Size the position from the selected equity risk budget and exposure caps.
    leverage = max(1, min(int(leverage), int(max_leverage)))
    risk_budget = account_size * risk_pct / 100
    stop_pct = risk / entry if entry > 0 else 0
    cost_fraction = max(0, roundtrip_cost_pct) / 100
    effective_loss_fraction = stop_pct + cost_fraction
    net_reward_fraction = max(0, reward / entry - cost_fraction) if entry > 0 else 0
    risk_reward = round(net_reward_fraction / effective_loss_fraction, 2) if effective_loss_fraction else 0
    target_notional = risk_budget / effective_loss_fraction if effective_loss_fraction > 0 else 0
    max_margin_amount = account_size * max_margin_pct / 100
    notional_value = min(target_notional, max_margin_amount * leverage)
    margin_amount = notional_value / leverage if leverage else 0
    margin_pct = margin_amount / account_size * 100 if account_size else 0
    price_risk_amount = notional_value * stop_pct
    estimated_roundtrip_cost = notional_value * cost_fraction
    actual_risk_amount = price_risk_amount + estimated_roundtrip_cost
    
    # 每个止盈位的平仓比例
    tp1_close_pct = 30  # TP1平30%
    tp2_close_pct = 30  # TP2平30%
    tp3_close_pct = 40  # TP3平40%
    
    score_distance = abs(score - 50)
    if score_distance >= 20:
        signal_strength, strength_text = "strong", "强信号"
    elif score_distance >= 10:
        signal_strength, strength_text = "medium", "中等信号"
    else:
        signal_strength, strength_text = "weak", "弱信号"

    # Add only after price confirms the trade; never average down into the stop.
    entry2 = entry + atr * 0.5 if direction == "long" else entry - atr * 0.5
    entry3 = entry + atr if direction == "long" else entry - atr
    pyramid = {
        "enabled": True,
        "entry1": {"price": round(entry, 2), "pct": 50},
        "entry2": {"price": round(entry2, 2), "pct": 30},
        "entry3": {"price": round(entry3, 2), "pct": 20},
    }
    time_stop = {
        "enabled": True,
        "max_candles": 5,
        "rule": "持仓5根K线仍未到TP1，重新评估并考虑平仓",
    }
    
    return {
        "direction": direction,
        "direction_text": direction_text,
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        "tp1_close_pct": tp1_close_pct,
        "tp2_close_pct": tp2_close_pct,
        "tp3_close_pct": tp3_close_pct,
        "position_size": round(notional_value, 2),
        "position_pct": round(margin_pct, 1),
        "margin_amount": round(margin_amount, 2),
        "margin_pct": round(margin_pct, 1),
        "notional_value": round(notional_value, 2),
        "leverage": leverage,
        "risk_reward": risk_reward,
        "gross_risk_reward": gross_risk_reward,
        "price_risk_amount": round(price_risk_amount, 2),
        "estimated_roundtrip_cost": round(estimated_roundtrip_cost, 2),
        "risk_amount": round(actual_risk_amount, 2),
        "risk_budget": round(risk_budget, 2),
        "stop_pct": round(stop_pct * 100, 3),
        "atr_sl_mult": atr_sl_mult,
        "signal_strength": signal_strength,
        "strength_text": strength_text,
        "pyramid": pyramid,
        "time_stop": time_stop,
        "message": f"{direction_text}，盈亏比1:{risk_reward}"
    }


def apply_trade_risk_gate(plan, prediction, multi_tf_confirm, adx, fake_breakout,
                          time_filter, support_resistance, roundtrip_cost_pct=0.14,
                          market_quality=None, data_freshness=None, funding_rate=None):
    """Turn conflicting/uneconomic candidates into an explicit no-trade plan."""
    if plan["direction"] == "neutral":
        return plan, {"allowed": False, "reasons": [plan["message"]], "cost_pct": roundtrip_cost_pct}

    reasons = []
    direction = plan["direction"]
    entry = plan["entry"]
    risk = abs(entry - plan["stop_loss"])
    predicted = prediction.get("predicted") or []
    if direction == "long":
        expected_move = max([0] + [price - entry for price in predicted])
        barriers = [support_resistance.get(key) for key in ("pivot", "r1", "r2", "swing_high")]
        barriers = [value for value in barriers if value is not None and value > entry]
    else:
        expected_move = max([0] + [entry - price for price in predicted])
        barriers = [support_resistance.get(key) for key in ("pivot", "s1", "s2", "swing_low")]
        barriers = [value for value in barriers if value is not None and value < entry]

    expected_move_pct = expected_move / entry * 100 if entry else 0
    minimum_move_pct = max(roundtrip_cost_pct + 0.05, (risk / entry * 100) * 1.5) if entry else 0
    if not multi_tf_confirm.get("confirmed", False):
        reasons.append("1H与4H方向不一致")
    if adx < 20:
        reasons.append(f"ADX={adx:.0f}，趋势强度不足")
    if fake_breakout.get("is_fake"):
        reasons.append("检测到假突破")
    if time_filter.get("level") == "high":
        reasons.append(time_filter.get("reason", "当前时段流动性风险较高"))
    if data_freshness and data_freshness.get("stale"):
        reasons.append(f"已收盘K线距今{data_freshness['age_minutes']:.0f}分钟，行情数据过期")
    if market_quality:
        if not market_quality.get("available"):
            reasons.append("盘口质量数据不可用")
        elif not market_quality.get("tradeable"):
            reasons.append(market_quality.get("reason", "当前盘口不适合执行"))
    if funding_rate and funding_rate.get("warning"):
        rate = float(funding_rate.get("rate") or 0)
        if direction == "long" and rate > 0.05:
            reasons.append(f"多头资金费率{rate:+.4f}%过热，追多成本和拥挤风险过高")
        elif direction == "short" and rate < -0.05:
            reasons.append(f"空头资金费率{rate:+.4f}%过热，追空成本和拥挤风险过高")
    if expected_move_pct < minimum_move_pct:
        reasons.append(f"预测空间{expected_move_pct:.2f}%不足以覆盖成本与风险阈值{minimum_move_pct:.2f}%")

    barrier_rr = None
    if barriers and risk > 0:
        nearest = min(barriers) if direction == "long" else max(barriers)
        barrier_rr = abs(nearest - entry) / risk
        if barrier_rr < 1.5:
            reasons.append(f"最近支撑/阻力仅提供{barrier_rr:.1f}R空间")

    gate = {
        "allowed": not reasons,
        "reasons": reasons,
        "expected_move_pct": round(expected_move_pct, 3),
        "minimum_move_pct": round(minimum_move_pct, 3),
        "cost_pct": roundtrip_cost_pct,
        "barrier_risk_reward": round(barrier_rr, 2) if barrier_rr is not None else None,
        "market_quality_passed": market_quality.get("tradeable") if market_quality else None,
        "data_freshness_passed": not data_freshness.get("stale") if data_freshness else None,
    }
    if reasons:
        blocked = dict(plan)
        blocked.update({
            "direction": "neutral",
            "direction_text": "风控观望",
            "blocked": True,
            "candidate_direction": direction,
            "blocked_reasons": reasons,
            "position_size": 0,
            "position_pct": 0,
            "margin_amount": 0,
            "margin_pct": 0,
            "notional_value": 0,
            "price_risk_amount": 0,
            "estimated_roundtrip_cost": 0,
            "risk_amount": 0,
            "pyramid": {"enabled": False},
            "message": "风控拦截：" + "；".join(reasons),
        })
        return blocked, gate
    plan["blocked"] = False
    return plan, gate


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
            
            if "confirm" in df.columns:
                df = df[df["confirm"].astype(str) == "1"].copy()
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


def confirmation_from_multi_tf(multi_tf):
    """Derive confirmation from the exact same snapshot shown in the UI."""
    frames = multi_tf.get("timeframes", {})
    frame_4h, frame_1h = frames.get("4H", {}), frames.get("1H", {})
    if frame_4h.get("error") or frame_1h.get("error") or not frame_4h or not frame_1h:
        return {"confirmed": False, "reason": "多周期数据不足，禁止生成交易计划"}
    score_4h, score_1h = frame_4h.get("score", 50), frame_1h.get("score", 50)
    dir_4h = "bullish" if score_4h >= 55 else "bearish" if score_4h <= 45 else "neutral"
    dir_1h = "bullish" if score_1h >= 55 else "bearish" if score_1h <= 45 else "neutral"
    if dir_4h == dir_1h and dir_4h != "neutral":
        return {"confirmed": True, "reason": f"4H({score_4h}分)和1H({score_1h}分)同向{dir_4h}",
                "score_4h": score_4h, "score_1h": score_1h}
    return {"confirmed": False,
            "reason": f"4H({score_4h}分,{dir_4h})和1H({score_1h}分,{dir_1h})方向不一致，建议观望",
            "score_4h": score_4h, "score_1h": score_1h}


def get_funding_rate(symbol):
    """获取当前资金费率（带缓存）"""
    cache_key = f"funding_{symbol}"
    cached = get_cache(cache_key)
    if cached is not None:
        return cached
    
    try:
        url = "https://www.okx.com/api/v5/public/funding-rate"
        params = {"instId": symbol}
        resp = fetch_with_retry(url, params=params, retries=2, timeout=8)
        if resp is None:
            return {"rate": 0, "rate_text": "--", "next_time": 0, "next_time_text": "--", "warning": False}
        data = resp.json()
        if data.get("code") == "0" and data.get("data"):
            item = data["data"][0]
            rate = float(item.get("fundingRate", 0)) * 100  # 转成百分比
            next_time = int(item.get("nextFundingTime", 0))
            result = {
                "rate": round(rate, 4),
                "rate_text": f"{rate:+.4f}%",
                "next_time": next_time,
                "next_time_text": datetime.fromtimestamp(next_time/1000).strftime("%H:%M") if next_time else "--",
                "warning": rate > 0.05 or rate < -0.05
            }
            set_cache(cache_key, result)
            return result
    except Exception as e:
        pass
    return {"rate": 0, "rate_text": "--", "next_time": 0, "next_time_text": "--", "warning": False}


def get_mark_price(symbol):
    """Get the risk-management mark price used by OKX derivatives."""
    cache_key = f"mark_price_{symbol}"
    cached = get_cache(cache_key, ttl=5)
    if cached is not None:
        return cached
    try:
        resp = fetch_with_retry(
            "https://www.okx.com/api/v5/public/mark-price",
            params={"instType": "SWAP", "instId": symbol}, retries=2, timeout=8
        )
        payload = resp.json() if resp is not None else {}
        if payload.get("code") == "0" and payload.get("data"):
            item = payload["data"][0]
            result = {"price": float(item["markPx"]), "timestamp": int(item.get("ts", 0))}
            set_cache(cache_key, result)
            return result
    except Exception:
        pass
    return {"price": None, "timestamp": 0}



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

def detect_divergence(df):
    """检测RSI/MACD顶背离和底背离"""
    divergences = []
    if len(df) < 30:
        return {"has_divergence": False, "divergences": divergences, "bullish_count": 0, "bearish_count": 0}
    recent = df.tail(30)
    prices = recent["close"].values
    rsi = recent["rsi"].values
    macd = recent["macd"].values
    price_highs, rsi_highs = [], []
    for i in range(2, len(prices)-2):
        if prices[i] > prices[i-1] and prices[i] > prices[i+1] and prices[i] > prices[i-2] and prices[i] > prices[i+2]:
            price_highs.append((i, prices[i]))
            rsi_highs.append((i, rsi[i]))
    price_lows, rsi_lows = [], []
    for i in range(2, len(prices)-2):
        if prices[i] < prices[i-1] and prices[i] < prices[i+1] and prices[i] < prices[i-2] and prices[i] < prices[i+2]:
            price_lows.append((i, prices[i]))
            rsi_lows.append((i, rsi[i]))
    if len(price_highs) >= 2 and len(rsi_highs) >= 2:
        if price_highs[-1][1] > price_highs[-2][1] and rsi_highs[-1][1] < rsi_highs[-2][1]:
            divergences.append({"type": "bearish", "indicator": "RSI", "text": "⚠️ RSI顶背离：价格创新高但RSI走低，看跌信号"})
    if len(price_lows) >= 2 and len(rsi_lows) >= 2:
        if price_lows[-1][1] < price_lows[-2][1] and rsi_lows[-1][1] > rsi_lows[-2][1]:
            divergences.append({"type": "bullish", "indicator": "RSI", "text": "⚠️ RSI底背离：价格创新低但RSI走高，看涨信号"})
    macd_highs = []
    for i in range(2, len(macd)-2):
        if macd[i] > macd[i-1] and macd[i] > macd[i+1]:
            macd_highs.append((i, macd[i]))
    if len(price_highs) >= 2 and len(macd_highs) >= 2:
        if price_highs[-1][1] > price_highs[-2][1] and macd_highs[-1][1] < macd_highs[-2][1]:
            divergences.append({"type": "bearish", "indicator": "MACD", "text": "⚠️ MACD顶背离：看跌信号"})
    return {"has_divergence": len(divergences) > 0, "divergences": divergences,
            "bullish_count": sum(1 for d in divergences if d["type"] == "bullish"),
            "bearish_count": sum(1 for d in divergences if d["type"] == "bearish")}

def detect_fake_breakout(df):
    """检测假突破"""
    if len(df) < 20:
        return {"is_fake": False, "type": None, "text": "数据不足"}
    recent = df.tail(20)
    latest = df.iloc[-1]
    prev_high = recent["high"].iloc[:-1].max()
    prev_low = recent["low"].iloc[:-1].min()
    if latest["high"] > prev_high and latest["close"] < prev_high and latest["vol_ratio"] < 1.2:
        return {"is_fake": True, "type": "bull_trap", "text": "⚠️ 假突破（诱多）：刺破前高但收盘回落，量能不足"}
    if latest["low"] < prev_low and latest["close"] > prev_low and latest["vol_ratio"] < 1.2:
        return {"is_fake": True, "type": "bear_trap", "text": "⚠️ 假突破（诱空）：跌破前低但收盘回升，量能不足"}
    return {"is_fake": False, "type": None, "text": "无假突破信号"}

def detect_candlestick_patterns(df):
    """识别K线形态"""
    patterns = []
    if len(df) < 3:
        return {"patterns": patterns, "count": 0}
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    body = latest["body"]
    avg_body = df["body"].tail(10).mean()
    upper_wick = latest["upper_wick"]
    lower_wick = latest["lower_wick"]
    if not prev["is_bullish"] and latest["is_bullish"] and latest["close"] >= prev["open"] and latest["open"] <= prev["close"] and body > avg_body:
        patterns.append({"type": "bullish", "name": "看涨吞没", "text": "看涨吞没形态，反转信号"})
    if prev["is_bullish"] and not latest["is_bullish"] and latest["open"] >= prev["close"] and latest["close"] <= prev["open"] and body > avg_body:
        patterns.append({"type": "bearish", "name": "看跌吞没", "text": "看跌吞没形态，反转信号"})
    if body < avg_body * 0.3 and upper_wick > body * 2 and lower_wick > body * 2:
        patterns.append({"type": "neutral", "name": "十字星", "text": "十字星，犹豫信号，可能反转"})
    if lower_wick > body * 2 and upper_wick < body * 0.5 and latest["is_bullish"]:
        patterns.append({"type": "bullish", "name": "锤子线", "text": "锤子线，底部反转信号"})
    if upper_wick > body * 2 and lower_wick < body * 0.5 and not latest["is_bullish"]:
        patterns.append({"type": "bearish", "name": "射击之星", "text": "射击之星，顶部反转信号"})
    return {"patterns": patterns, "count": len(patterns)}

def get_consecutive_streak(df):
    """连涨连跌统计"""
    latest = df.iloc[-1]
    up_streak = int(latest["consecutive"])
    down_streak = int(latest["consecutive_down"])
    warning = None
    if up_streak >= 5:
        warning = f"⚠️ 连涨{up_streak}根，警惕回调"
    elif down_streak >= 5:
        warning = f"⚠️ 连跌{down_streak}根，关注反弹"
    return {"up_streak": up_streak, "down_streak": down_streak, "warning": warning, "has_warning": warning is not None}

def check_time_filter():
    """时间过滤"""
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    hour = now.hour
    is_weekend = weekday >= 5
    is_low_vol = (hour >= 21 or hour < 6)
    if is_weekend:
        return {"is_bad_time": True, "reason": "周末机构参与度可能下降，以实时点差和成交额为准", "level": "medium"}
    elif is_low_vol:
        return {"is_bad_time": True, "reason": "UTC 21:00-06:00低活跃时段，建议降低仓位", "level": "medium"}
    return {"is_bad_time": False, "reason": "交易时段正常", "level": "low"}

def calc_dynamic_leverage(atr, current_price, adx, max_leverage=5):
    """Conservative leverage suggestion; volatility can expand without warning."""
    atr_pct = atr / current_price * 100
    if atr_pct > 4:
        base_leverage = 1
    elif atr_pct > 2.5:
        base_leverage = 2
    elif atr_pct > 1.5:
        base_leverage = 3
    else:
        base_leverage = 4
    if adx > 30:
        base_leverage = min(base_leverage + 1, 5)
    elif adx < 20:
        base_leverage = max(base_leverage - 1, 1)
    base_leverage = min(base_leverage, max(1, int(max_leverage)))
    return {"recommended_leverage": round(base_leverage), "atr_pct": round(atr_pct, 2),
            "adx": round(float(adx), 1), "max_leverage": int(max_leverage),
            "note": f"ATR{atr_pct:.1f}% + ADX{adx:.0f}，保守上限{round(base_leverage)}倍"}

def calc_trailing_stop(plan, current_price):
    """移动止损规则"""
    if plan["direction"] == "neutral":
        return {"stage": "none", "stop_loss": None, "note": "观望中，不启用移动止损"}
    entry = plan["entry"]
    sl = plan["stop_loss"]
    tp1 = plan["tp1"]
    tp2 = plan["tp2"]
    if plan["direction"] == "long":
        if current_price >= tp2:
            return {"stage": "tp2", "stop_loss": tp1, "note": "已到TP2，止损上移到TP1，锁定利润"}
        elif current_price >= tp1:
            return {"stage": "tp1", "stop_loss": entry, "note": "已到TP1，止损移到入场价，保本交易"}
        return {"stage": "entry", "stop_loss": sl, "note": "未到TP1，保持初始止损"}
    else:
        if current_price <= tp2:
            return {"stage": "tp2", "stop_loss": tp1, "note": "已到TP2，止损下移到TP1，锁定利润"}
        elif current_price <= tp1:
            return {"stage": "tp1", "stop_loss": entry, "note": "已到TP1，止损移到入场价，保本交易"}
        return {"stage": "entry", "stop_loss": sl, "note": "未到TP1，保持初始止损"}

def estimate_win_rate(score, adx, has_divergence, fake_breakout, streak):
    """估算胜率"""
    base_rate = 50
    conviction = abs(score - 50)
    if conviction >= 30: base_rate += 15
    elif conviction >= 20: base_rate += 10
    elif conviction >= 5: base_rate += 5
    if adx > 30: base_rate += 8
    elif adx < 20: base_rate -= 5
    if has_divergence: base_rate -= 10
    if fake_breakout: base_rate -= 8
    if streak >= 5: base_rate -= 5
    return round(max(20, min(80, base_rate)))

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "登录已过期，请重新登录"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if compare_digest(str(password), ACCESS_PASSWORD):
        session["logged_in"] = True
        session.permanent = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "密码错误"})

@app.route("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/")
@login_required
def index():
    return render_template("index.html", symbols=get_live_symbols(), timeframes=TIMEFRAMES)


@app.route("/api/symbols")
@login_required
def api_symbols():
    symbols = get_live_symbols()
    return jsonify({"count": len(symbols), "data": symbols, "timestamp": int(time.time())})

@app.route("/api/price")
@login_required
def api_price():
    """轻量级：只返回当前价格，不计算指标"""
    try:
        symbol, _, validation_error = get_market_params()
        if validation_error:
            return validation_error
        df, error = fetch_klines(symbol, "1m", 2)
        if error or df is None or len(df) == 0:
            return jsonify({"error": "获取价格失败"})
        current_price = float(df.iloc[-1]["close"])
        mark_price = get_mark_price(symbol)
        return jsonify({
            "symbol": symbol,
            "current_price": current_price,
            "mark_price": mark_price["price"],
            "mark_timestamp": mark_price["timestamp"],
            "timestamp": int(time.time())
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/predict")
@login_required
def api_predict():
    try:
        symbol, timeframe, validation_error = get_market_params()
        if validation_error:
            return validation_error
        risk_settings = get_risk_settings()
        
        raw_df, error = fetch_klines(symbol, timeframe, 300)
        if error:
            return jsonify({"error": f"获取数据失败: {error}"}), 500
        if raw_df is None or len(raw_df) < 100:
            return jsonify({"error": "数据不足"}), 500
        market_price = float(raw_df.iloc[-1]["close"])
        if "confirm" in raw_df.columns:
            confirmed_df = raw_df[raw_df["confirm"].astype(str) == "1"].copy()
        else:
            confirmed_df = raw_df.copy()
        if len(confirmed_df) < 100:
            return jsonify({"error": "已收盘K线不足100根"}), 500

        # Indicators and signals only use closed candles; the latest tick is entry/display only.
        df = confirmed_df
        df = calc_indicators(df)
        latest = df.iloc[-1]
        pred = predict_price(df, periods=5)
        score, reasons = calc_signal_score(df)
        sr = calc_support_resistance(df)
        market_quality = get_market_quality(symbol)
        data_freshness = get_data_freshness(latest["timestamp"], timeframe)
        funding_rate = get_funding_rate(symbol)
        roundtrip_cost_pct = (risk_settings["fee_pct"] + risk_settings["slippage_pct"]) * 2
        
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
        
        ht = calc_holding_time(timeframe, pred, float(latest["atr"]), market_price)

        # 新增交易员级分析
        divergence = detect_divergence(df)
        fake_breakout = detect_fake_breakout(df)
        patterns = detect_candlestick_patterns(df)
        streak = get_consecutive_streak(df)
        time_filter = check_time_filter()
        adx_val = float(latest["adx"])
        leverage = calc_dynamic_leverage(float(latest["atr"]), market_price, adx_val,
                                         max_leverage=risk_settings["max_leverage"])
        multi_tf_data = analyze_multi_timeframe(symbol, timeframe)
        multi_tf_confirmation = confirmation_from_multi_tf(multi_tf_data)
        tp = calc_trade_plan(score, market_price, float(latest["atr"]), sr, symbol,
                             leverage=leverage["recommended_leverage"],
                             account_size=risk_settings["account_size"],
                             risk_pct=risk_settings["risk_pct"],
                             max_margin_pct=risk_settings["max_margin_pct"],
                             max_leverage=risk_settings["max_leverage"],
                             roundtrip_cost_pct=roundtrip_cost_pct)
        if tp["direction"] != "neutral":
            tp["time_stop"]["max_holding_minutes"] = {
                "1m": 5, "3m": 15, "5m": 25, "15m": 75, "30m": 150,
                "1H": 300, "2H": 600, "4H": 1200, "6H": 1800, "8H": 2400,
                "12H": 3600, "1D": 7200, "3D": 21600, "1W": 50400, "1M": 216000,
            }.get(timeframe, 300)
        tp, risk_gate = apply_trade_risk_gate(
            tp, pred, multi_tf_confirmation, adx_val, fake_breakout,
            time_filter, sr,
            roundtrip_cost_pct=roundtrip_cost_pct,
            market_quality=market_quality,
            data_freshness=data_freshness,
            funding_rate=funding_rate,
        )
        if not risk_gate["allowed"] and score not in range(46, 55):
            signal, signal_class = "风控观望", "neutral"
        trailing_stop = calc_trailing_stop(tp, market_price)
        win_rate = estimate_win_rate(score, adx_val, divergence["has_divergence"], fake_breakout["is_fake"], streak["up_streak"] if score >= 50 else streak["down_streak"])
        # 趋势判断
        trend = pred.get("trend", "震荡")
        trend_note = ""
        if trend == "震荡" and score >= 55:
            trend_note = "（趋势震荡，轻仓试多）"
        elif trend == "震荡" and score <= 45:
            trend_note = "（趋势震荡，轻仓试空）"
        
        # ADX趋势强度提示
        adx_note = ""
        if adx_val < 20:
            adx_note = f"ADX={adx_val:.0f}震荡市，"
        elif adx_val > 30:
            adx_note = f"ADX={adx_val:.0f}强趋势，"
        
        if tp["direction"] == "long":
            advice = f"{adx_note}可考虑做多{trend_note}，入场 ${tp['entry']:,.2f}，止损 ${tp['stop_loss']:,.2f}，TP1 ${tp['tp1']:,.2f}（3×ATR，平30%），TP2 ${tp['tp2']:,.2f}（4×ATR，平30%），TP3 ${tp['tp3']:,.2f}（5×ATR，平40%），建议持仓 {ht['min_text']}~{ht['max_text']}，信号质量{win_rate}分"
        elif tp["direction"] == "short":
            advice = f"{adx_note}可考虑做空{trend_note}，入场 ${tp['entry']:,.2f}，止损 ${tp['stop_loss']:,.2f}，TP1 ${tp['tp1']:,.2f}（3×ATR，平30%），TP2 ${tp['tp2']:,.2f}（4×ATR，平30%），TP3 ${tp['tp3']:,.2f}（5×ATR，平40%），建议持仓 {ht['min_text']}~{ht['max_text']}，信号质量{win_rate}分"
        else:
            advice = tp.get("message") or f"信号不明确，趋势{trend}，ADX={adx_val:.0f}，建议观望"
        
        # 信号置信度计算
        direction = "long" if score >= 55 else ("short" if score <= 45 else "neutral")
        current_price_val = float(latest["close"])
        rsi_val = float(latest["rsi"])
        macd_hist = float(latest.get("macd_hist", 0))
        ma20_val = float(latest.get("ma20", current_price_val))
        adx_val_local = adx_val if isinstance(adx_val, (int, float)) else 20
        vol_ratio_val = float(latest["vol_ratio"])
        kdj_k = float(latest["kdj_k"])
        kdj_d = float(latest["kdj_d"])
        
        confidence_factors = []
        if direction == "long" and rsi_val < 70:
            confidence_factors.append(("RSI", True))
        elif direction == "short" and rsi_val > 30:
            confidence_factors.append(("RSI", True))
        else:
            confidence_factors.append(("RSI", False))
        
        if direction == "long" and macd_hist > 0:
            confidence_factors.append(("MACD", True))
        elif direction == "short" and macd_hist < 0:
            confidence_factors.append(("MACD", True))
        else:
            confidence_factors.append(("MACD", False))
        
        if direction == "long" and current_price_val > ma20_val:
            confidence_factors.append(("均线", True))
        elif direction == "short" and current_price_val < ma20_val:
            confidence_factors.append(("均线", True))
        else:
            confidence_factors.append(("均线", False))
        
        if adx_val_local > 25:
            confidence_factors.append(("ADX趋势", True))
        else:
            confidence_factors.append(("ADX趋势", False))
        
        if vol_ratio_val > 1.2:
            confidence_factors.append(("成交量", True))
        else:
            confidence_factors.append(("成交量", False))
        
        if direction == "long" and kdj_k > kdj_d:
            confidence_factors.append(("KDJ", True))
        elif direction == "short" and kdj_k < kdj_d:
            confidence_factors.append(("KDJ", True))
        else:
            confidence_factors.append(("KDJ", False))
        
        confirmed = sum(1 for _, c in confidence_factors if c)
        confidence_pct = round(confirmed / len(confidence_factors) * 100)
        
        if confidence_pct >= 80:
            confidence_level = "极高"
            confidence_note = "指标高度一致，但仍须通过风险门禁"
        elif confidence_pct >= 65:
            confidence_level = "高"
            confidence_note = "大部分指标一致，按风险预算控制仓位"
        elif confidence_pct >= 50:
            confidence_level = "中"
            confidence_note = "指标有分歧，建议轻仓"
        else:
            confidence_level = "低"
            confidence_note = "指标严重分歧，不建议交易"
        
        confidence_data = {
            "score": confidence_pct,
            "level": confidence_level,
            "note": confidence_note,
            "factors": confidence_factors,
            "confirmed_count": confirmed,
            "total_count": len(confidence_factors)
        }
        
        return jsonify({
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": market_price,
            "mark_price": get_mark_price(symbol),
            "risk_settings": risk_settings,
            "market_quality": market_quality,
            "data_freshness": data_freshness,
            "signal_candle_closed": True,
            "signal_candle_timestamp": int(latest["timestamp"]),
            "confidence": confidence_data,
            "pct_change": float(latest["pct_change"]),
            "vol_ratio": float(latest["vol_ratio"]),
            "rsi": float(latest["rsi"]),
            "atr": float(latest["atr"]),
            "kdj": {"k": round(float(latest["kdj_k"]), 1), "d": round(float(latest["kdj_d"]), 1), "j": round(float(latest["kdj_j"]), 1)},
            "cci": round(float(latest["cci"]), 1),
            "willr": round(float(latest["willr"]), 1),
            "prediction": pred,
            "score": score,
            "signal": signal,
            "signal_class": signal_class,
            "reasons": reasons,
            "support_resistance": sr,
            "holding_time": ht,
            "trade_plan": tp,
            "risk_gate": risk_gate,
            "multi_tf": multi_tf_data,
            "funding_rate": funding_rate,
            "fib_levels": calc_fibonacci_and_levels(df),
            "volume_anomaly": detect_volume_anomaly(df),
            "divergence": divergence,
            "multi_tf_confirm": multi_tf_confirmation,
            "fake_breakout": fake_breakout,
            "candlestick": patterns,
            "streak": streak,
            "time_filter": time_filter,
            "adx": adx_val,
            "leverage": leverage,
            "trailing_stop": trailing_stop,
            "win_rate": win_rate,
            "signal_quality": win_rate,
            "advice": advice,
            "timestamp": datetime.now().isoformat(),
            "candles_count": len(df)
        })
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@app.route("/api/scan")
@login_required
def api_scan():
    """批量扫描前N个币种"""
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 50))
        _, timeframe, validation_error = get_market_params()
        if validation_error and timeframe is None:
            return validation_error
        symbols = get_live_symbols()[:limit]
        
        results = []
        for s in symbols:
            try:
                df, error = fetch_klines(s["id"], timeframe, 200)
                if error or df is None or len(df) < 100:
                    continue
                if "confirm" in df.columns:
                    df = df[df["confirm"].astype(str) == "1"].copy()
                if len(df) < 100:
                    continue
                df = calc_indicators(df)
                latest = df.iloc[-1]
                score, _ = calc_signal_score(df)
                results.append({
                    "symbol": s["id"],
                    "name": s["name"],
                    "score": score,
                    "price": round(float(latest["close"]), 2),
                    "pct_change": round(float(latest["pct_change"]), 2),
                    "rsi": round(float(latest["rsi"]), 1),
                    "vol_ratio": round(float(latest["vol_ratio"]), 2)
                })
            except:
                continue
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return jsonify({"count": len(results), "data": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def check_multi_tf_confirmation(symbol, timeframe):
    """多周期确认：4H和1H必须同向"""
    try:
        # 获取4H和1H数据
        df_4h, err1 = fetch_klines(symbol, "4H", 100)
        df_1h, err2 = fetch_klines(symbol, "1H", 100)
        
        if err1 or err2 or df_4h is None or df_1h is None:
            return {"confirmed": False, "reason": "多周期数据不足，禁止生成交易计划"}

        if "confirm" in df_4h.columns:
            df_4h = df_4h[df_4h["confirm"].astype(str) == "1"].copy()
        if "confirm" in df_1h.columns:
            df_1h = df_1h[df_1h["confirm"].astype(str) == "1"].copy()
        
        df_4h = calc_indicators(df_4h)
        df_1h = calc_indicators(df_1h)
        
        score_4h, _ = calc_signal_score(df_4h)
        score_1h, _ = calc_signal_score(df_1h)
        
        # 判断方向
        dir_4h = "bullish" if score_4h >= 55 else "bearish" if score_4h <= 45 else "neutral"
        dir_1h = "bullish" if score_1h >= 55 else "bearish" if score_1h <= 45 else "neutral"
        
        if dir_4h == dir_1h and dir_4h != "neutral":
            return {"confirmed": True, "reason": f"4H({score_4h}分)和1H({score_1h}分)同向{dir_4h}", "score_4h": score_4h, "score_1h": score_1h}
        else:
            return {"confirmed": False, "reason": f"4H({score_4h}分,{dir_4h})和1H({score_1h}分,{dir_1h})方向不一致，建议观望", "score_4h": score_4h, "score_1h": score_1h}
    except Exception as e:
        return {"confirmed": False, "reason": f"多周期确认失败，禁止交易: {str(e)}"}


@app.route("/api/backtest")
@login_required
def api_backtest():
    """历史回测"""
    try:
        symbol, timeframe, validation_error = get_market_params()
        if validation_error:
            return validation_error
        days = max(1, min(int(request.args.get("days", 30)), 90))
        initial_balance = float(request.args.get("capital", 1000))
        risk_settings = get_risk_settings()
        risk_settings["account_size"] = initial_balance
        if not np.isfinite(initial_balance) or initial_balance <= 0:
            return jsonify({"error": "初始资金必须大于0"}), 400
        
        bars_per_day = {
            "1m": 1440, "3m": 480, "5m": 288, "15m": 96, "30m": 48,
            "1H": 24, "2H": 12, "4H": 6, "6H": 4, "8H": 3, "12H": 2,
            "1D": 1, "3D": 1 / 3, "1W": 1 / 7, "1M": 1 / 30,
        }
        requested_bars = max(60, int(np.ceil(days * bars_per_day[timeframe])) + 55)
        df, error = fetch_history_klines(symbol, timeframe, requested_bars)
        if error or df is None or len(df) < 60:
            return jsonify({"error": f"数据不足: {error or '至少需要60根K线'}"})
        
        df = calc_indicators(df)
        
        # 回测参数
        balance = initial_balance
        trades = []
        position = None
        max_balance = initial_balance
        max_drawdown = 0
        
        fee_rate = risk_settings["fee_pct"] / 100
        slippage_rate = risk_settings["slippage_pct"] / 100

        def realize_leg(pos, exit_price, fraction):
            signed_return = ((exit_price - pos["entry"]) / pos["entry"])
            if pos["side"] == "short":
                signed_return *= -1
            leg_notional = pos["notional"] * fraction
            pos["realized"] += leg_notional * signed_return - leg_notional * fee_rate
            pos["remaining"] = max(0, pos["remaining"] - fraction)

        def finish_trade(pos, exit_price, reason):
            nonlocal balance, max_balance, max_drawdown
            balance += pos["realized"]
            margin = pos["notional"] / pos["leverage"] if pos["leverage"] else pos["notional"]
            pnl_pct = pos["realized"] / margin * 100 if margin else 0
            trades.append({
                "side": pos["side"], "entry": round(pos["entry"], 6),
                "exit": round(exit_price, 6), "reason": reason,
                "pnl_pct": round(pnl_pct, 2), "pnl": round(pos["realized"], 2),
                "balance": round(balance, 2), "leverage": pos["leverage"],
                "notional": round(pos["notional"], 2),
            })
            max_balance = max(max_balance, balance)
            max_drawdown = max(max_drawdown, (max_balance - balance) / max_balance * 100 if max_balance else 0)

        for i in range(50, len(df) - 1):
            row = df.iloc[i]
            if position is None:
                score, _ = calc_signal_score(df.iloc[:i + 1])
                direction = "long" if score >= 60 else "short" if score <= 40 else None
                if direction is None or float(row["adx"]) < 20:
                    continue
                next_row = df.iloc[i + 1]
                raw_entry = float(next_row["open"])
                entry = raw_entry * (1 + slippage_rate if direction == "long" else 1 - slippage_rate)
                leverage_data = calc_dynamic_leverage(float(row["atr"]), entry, float(row["adx"]),
                                                       max_leverage=risk_settings["max_leverage"])
                plan = calc_trade_plan(score, entry, float(row["atr"]), calc_support_resistance(df.iloc[:i + 1]),
                                       symbol, leverage=leverage_data["recommended_leverage"], account_size=balance,
                                       risk_pct=risk_settings["risk_pct"],
                                       max_margin_pct=risk_settings["max_margin_pct"],
                                       max_leverage=risk_settings["max_leverage"],
                                       roundtrip_cost_pct=(risk_settings["fee_pct"] + risk_settings["slippage_pct"]) * 2)
                prediction = predict_price(df.iloc[:i + 1], periods=5)
                expected = max([0] + ([p - entry for p in prediction["predicted"]] if direction == "long"
                                      else [entry - p for p in prediction["predicted"]]))
                minimum_cost_move = (risk_settings["fee_pct"] + risk_settings["slippage_pct"]) * 2 + 0.05
                if expected / entry * 100 < max(minimum_cost_move, plan["stop_pct"] * 1.5):
                    continue
                position = {
                    "side": direction, "entry": entry, "stop_loss": plan["stop_loss"],
                    "targets": [plan["tp1"], plan["tp2"], plan["tp3"]],
                    "fractions": [0.3, 0.3, 0.4], "next_target": 0,
                    "remaining": 1.0, "notional": plan["notional_value"],
                    "leverage": plan["leverage"], "opened_index": i + 1,
                    "realized": -plan["notional_value"] * fee_rate,
                }
                continue

            high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
            is_long = position["side"] == "long"
            stop_hit = low <= position["stop_loss"] if is_long else high >= position["stop_loss"]
            if stop_hit:
                exit_price = position["stop_loss"] * (1 - slippage_rate if is_long else 1 + slippage_rate)
                realize_leg(position, exit_price, position["remaining"])
                finish_trade(position, exit_price, "止损")
                position = None
                continue

            while position and position["next_target"] < 3:
                target = position["targets"][position["next_target"]]
                target_hit = high >= target if is_long else low <= target
                if not target_hit:
                    break
                fraction = min(position["fractions"][position["next_target"]], position["remaining"])
                exit_price = target * (1 - slippage_rate if is_long else 1 + slippage_rate)
                realize_leg(position, exit_price, fraction)
                position["next_target"] += 1
                if position["next_target"] == 1:
                    position["stop_loss"] = position["entry"]
                if position["remaining"] <= 0.0001:
                    finish_trade(position, exit_price, "TP3")
                    position = None
                    break

            if position and i - position["opened_index"] >= 5 and position["next_target"] == 0:
                exit_price = close * (1 - slippage_rate if is_long else 1 + slippage_rate)
                realize_leg(position, exit_price, position["remaining"])
                finish_trade(position, exit_price, "时间止损")
                position = None

        if position is not None:
            close = float(df.iloc[-1]["close"])
            is_long = position["side"] == "long"
            exit_price = close * (1 - slippage_rate if is_long else 1 + slippage_rate)
            realize_leg(position, exit_price, position["remaining"])
            finish_trade(position, exit_price, "期末平仓")
            position = None
        
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        total_pnl = balance - initial_balance
        total_pnl_pct = total_pnl / initial_balance * 100
        actual_days = max(0, (int(df["timestamp"].iloc[-1]) - int(df["timestamp"].iloc[50])) / 86400000)
        
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
        profit_factor = abs(sum(t["pnl"] for t in wins) / sum(t["pnl"] for t in losses)) if losses and sum(t["pnl"] for t in losses) != 0 else 0
        
        return jsonify({
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "actual_days": round(actual_days, 1),
            "bars_count": len(df),
            "history_truncated": requested_bars > 3000,
            "fee_rate_pct": fee_rate * 100,
            "slippage_rate_pct": slippage_rate * 100,
            "strategy_note": "收盘信号、下一根开盘成交、ADX过滤、风险仓位、分批止盈、保本止损、5根K线时间止损；不含历史多周期过滤和资金费率",
            "initial_balance": initial_balance,
            "final_balance": round(balance, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "max_drawdown": round(max_drawdown, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "recent_trades": trades[-10:]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/wechat-push", methods=["POST"])
@login_required
def api_wechat_push():
    """微信推送（Server酱）"""
    try:
        data = request.get_json(silent=True) or {}
        sendkey = data.get("sendkey", "")
        title = data.get("title", "CryptoPulse提醒")
        desp = data.get("desp", "")
        
        if not sendkey:
            return jsonify({"success": False, "error": "缺少SendKey"})
        
        # Server酱推送API
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        payload = {"title": title, "desp": desp}
        resp = requests.post(url, data=payload, timeout=10)
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 0:
                return jsonify({"success": True, "message": "推送成功"})
            else:
                return jsonify({"success": False, "error": result.get("message", "推送失败")})
        else:
            return jsonify({"success": False, "error": f"HTTP {resp.status_code}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/fear-greed")
@login_required
def api_fear_greed():
    """获取恐慌贪婪指数"""
    try:
        cache_key = "fear_greed"
        cached = get_cache(cache_key)
        if cached:
            return jsonify(cached)
        
        resp = fetch_with_retry("https://api.alternative.me/fng/?limit=1", retries=2, timeout=8)
        if resp and resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                item = data["data"][0]
                value = int(item["value"])
                classification = item["value_classification"]
                result = {
                    "value": value,
                    "classification": classification,
                    "timestamp": item.get("timestamp", ""),
                    "note": f"恐慌贪婪指数：{value} ({classification})"
                }
                set_cache(cache_key, result)
                return jsonify(result)
        return jsonify({"value": 50, "classification": "Neutral", "note": "获取失败，默认中性"})
    except Exception as e:
        return jsonify({"value": 50, "classification": "Neutral", "note": f"获取失败: {str(e)}"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
