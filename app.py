#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""株式おすすめアプリ v4 - Firebase対応・自動更新版
  設計：
    - サーバーが10分ごとに自己pingしてRenderのスリープを防止
    - データが35分以上古ければバックグラウンドで自動更新
    - データはFirebase Firestoreに保存（Render再起動後も維持）
    - クライアントは /api/data を読むだけ（更新トリガーなし）
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

from flask import Flask, jsonify, render_template, make_response
import yfinance as yf
import numpy as np
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json
import os
import time
import urllib.request

JST = timezone(timedelta(hours=9))
app = Flask(__name__)

# ══════════════════════════════════════════════════════
#  東証セクター別銘柄（全て .T）
# ══════════════════════════════════════════════════════
SECTORS = {
    "AI・半導体": {
        "icon": "🤖",
        "keywords": ["AI","半導体","chip","semiconductor","nvidia","人工知能","生成AI","LLM"],
        "stocks": {
            "9984.T":"ソフトバンクG", "8035.T":"東京エレクトロン",
            "6857.T":"アドバンテスト", "6723.T":"ルネサスエレクトロニクス",
            "6920.T":"レーザーテック", "6963.T":"ローム",
            "6504.T":"富士電機", "6503.T":"三菱電機",
            "6954.T":"ファナック", "6506.T":"安川電機",
            "4062.T":"イビデン", "6525.T":"KOKUSAI ELECTRIC",
            "6981.T":"村田製作所", "6976.T":"太陽誘電",
        },
    },
    "テクノロジー・IT": {
        "icon": "💻",
        "keywords": ["IT","tech","software","cloud","テクノロジー","クラウド","DX"],
        "stocks": {
            "6758.T":"ソニーグループ", "6702.T":"富士通",
            "6701.T":"NEC", "6752.T":"パナソニックHD",
            "6971.T":"京セラ", "4307.T":"野村総合研究所",
            "4684.T":"オービック", "9613.T":"NTTデータグループ",
            "3659.T":"ネクソン", "4369.T":"トレンドマイクロ",
            "2432.T":"DeNA", "3765.T":"ガンホー",
            "4901.T":"富士フイルムHD", "6367.T":"ダイキン工業",
        },
    },
    "通信": {
        "icon": "📡",
        "keywords": ["通信","5G","telecom","NTT","KDDI","ソフトバンク"],
        "stocks": {
            "9432.T":"NTT", "9433.T":"KDDI",
            "9434.T":"ソフトバンク", "4689.T":"LINEヤフー",
            "4385.T":"メルカリ", "4755.T":"楽天グループ",
            "3092.T":"ZOZO", "3632.T":"グリー",
            "6028.T":"テクノプロHD",
        },
    },
    "自動車・輸送機器": {
        "icon": "🚗",
        "keywords": ["自動車","EV","トヨタ","ホンダ","日産","car","auto"],
        "stocks": {
            "7203.T":"トヨタ自動車", "7267.T":"ホンダ",
            "7201.T":"日産自動車", "7270.T":"SUBARU",
            "7269.T":"スズキ", "7261.T":"マツダ",
            "7259.T":"アイシン", "7211.T":"三菱自動車",
            "5108.T":"ブリヂストン", "7012.T":"川崎重工業",
            "7011.T":"三菱重工業", "7013.T":"IHI",
            "6326.T":"クボタ", "6301.T":"コマツ",
        },
    },
    "ヘルスケア・医薬": {
        "icon": "🏥",
        "keywords": ["医薬","製薬","health","biotech","ヘルスケア","薬"],
        "stocks": {
            "4502.T":"武田薬品工業", "4503.T":"アステラス製薬",
            "4523.T":"エーザイ", "4519.T":"中外製薬",
            "4568.T":"第一三共", "4578.T":"大塚HD",
            "4507.T":"塩野義製薬", "4151.T":"協和キリン",
            "4543.T":"テルモ", "7741.T":"HOYA",
            "4021.T":"日産化学", "4188.T":"三菱ケミカルグループ",
        },
    },
    "金融・銀行": {
        "icon": "🏦",
        "keywords": ["銀行","金融","bank","finance","金利","UFJ","三菱"],
        "stocks": {
            "8306.T":"三菱UFJフィナンシャルG", "8316.T":"三井住友FG",
            "8411.T":"みずほFG", "7182.T":"ゆうちょ銀行",
            "8604.T":"野村HD", "8601.T":"大和証券G本社",
            "8591.T":"オリックス", "8697.T":"日本取引所G",
            "8309.T":"三井住友トラスト", "8308.T":"りそなHD",
            "8002.T":"丸紅", "8031.T":"三井物産",
            "8053.T":"住友商事",
        },
    },
    "保険・証券": {
        "icon": "💰",
        "keywords": ["保険","証券","insurance","securities"],
        "stocks": {
            "8766.T":"東京海上HD", "8750.T":"第一生命HD",
            "8725.T":"MS&ADインシュアランスG", "8630.T":"SOMPOホールディングス",
            "8253.T":"クレディセゾン", "8795.T":"T&Dホールディングス",
            "8698.T":"マネックスG", "8473.T":"SBIホールディングス",
        },
    },
    "仮想通貨・暗号資産": {
        "icon": "₿",
        "keywords": ["仮想通貨","暗号資産","crypto","bitcoin","ビットコイン","NFT","web3","ブロックチェーン"],
        "stocks": {
            "8698.T":"マネックスグループ", "8473.T":"SBIホールディングス",
            "9449.T":"GMOインターネットG", "3350.T":"メタプラネット",
            "3807.T":"フィスコ", "3696.T":"セレス",
            "4751.T":"サイバーエージェント", "2121.T":"ミクシィ",
        },
    },
    "エネルギー・電力": {
        "icon": "⚡",
        "keywords": ["エネルギー","電力","石油","ガス","energy","原油"],
        "stocks": {
            "5020.T":"ENEOSホールディングス", "5019.T":"出光興産",
            "9531.T":"東京ガス", "9532.T":"大阪ガス",
            "9503.T":"関西電力", "9501.T":"東京電力HD",
            "9502.T":"中部電力", "1605.T":"INPEX",
            "5021.T":"コスモエネルギーHD",
        },
    },
    "素材・化学": {
        "icon": "🔬",
        "keywords": ["化学","素材","chemical","material","鉄鋼"],
        "stocks": {
            "4063.T":"信越化学工業", "3407.T":"旭化成",
            "4183.T":"三井化学", "4452.T":"花王",
            "5401.T":"日本製鉄", "5411.T":"JFEホールディングス",
            "5713.T":"住友金属鉱山", "5802.T":"住友電気工業",
            "4005.T":"住友化学", "4042.T":"東ソー",
            "4901.T":"富士フイルムHD",
        },
    },
    "消費・小売": {
        "icon": "🛍️",
        "keywords": ["小売","消費","retail","consumer","ユニクロ","イオン"],
        "stocks": {
            "9983.T":"ファーストリテイリング", "8267.T":"イオン",
            "3382.T":"セブン&iHD", "9843.T":"ニトリHD",
            "3086.T":"Jフロントリテイリング", "3099.T":"三越伊勢丹HD",
            "7453.T":"良品計画", "3092.T":"ZOZO",
        },
    },
    "食品・飲料": {
        "icon": "🍜",
        "keywords": ["食品","飲料","food","beverage","農業"],
        "stocks": {
            "2802.T":"味の素", "2914.T":"日本たばこ産業",
            "2503.T":"キリンHD", "2502.T":"アサヒグループHD",
            "2801.T":"キッコーマン", "2897.T":"日清食品HD",
            "2871.T":"ニチレイ", "2282.T":"日本ハム",
            "2267.T":"ヤクルト本社", "1332.T":"ニッスイ",
        },
    },
    "不動産・建設": {
        "icon": "🏢",
        "keywords": ["不動産","建設","REIT","インフラ","住宅"],
        "stocks": {
            "8801.T":"三井不動産", "8802.T":"三菱地所",
            "8830.T":"住友不動産", "1925.T":"大和ハウス工業",
            "1928.T":"積水ハウス", "1801.T":"大成建設",
            "1802.T":"大林組", "1803.T":"清水建設",
            "1878.T":"大東建託", "3003.T":"ヒューリック",
        },
    },
    "ゲーム・エンタメ": {
        "icon": "🎮",
        "keywords": ["ゲーム","エンタメ","game","任天堂","コナミ"],
        "stocks": {
            "7974.T":"任天堂", "9766.T":"コナミグループ",
            "9684.T":"スクウェア・エニックスHD", "9697.T":"カプコン",
            "7832.T":"バンダイナムコHD", "9601.T":"松竹",
            "9602.T":"東宝", "4751.T":"サイバーエージェント",
            "3668.T":"コロプラ", "2121.T":"ミクシィ",
        },
    },
    "輸送・物流": {
        "icon": "🚢",
        "keywords": ["輸送","物流","鉄道","航空","海運","transport"],
        "stocks": {
            "9020.T":"東日本旅客鉄道", "9022.T":"東海旅客鉄道",
            "9021.T":"西日本旅客鉄道", "9202.T":"ANAホールディングス",
            "9201.T":"日本航空", "9101.T":"日本郵船",
            "9104.T":"商船三井", "9107.T":"川崎汽船",
            "9062.T":"日本通運", "9064.T":"ヤマトHD",
        },
    },
}

THEMES = {
    "AI・生成AI": {
        "icon": "🤖", "desc": "生成AI・LLM・AIチップ・AI関連ソフトウェア",
        "stocks": {"9984.T":"ソフトバンクG","8035.T":"東京エレクトロン","6857.T":"アドバンテスト","6723.T":"ルネサス","6920.T":"レーザーテック","4307.T":"野村総研","4684.T":"オービック","6954.T":"ファナック","6506.T":"安川電機"},
    },
    "半導体製造装置": {
        "icon": "🔬", "desc": "半導体製造装置・検査装置・素材",
        "stocks": {"8035.T":"東京エレクトロン","6857.T":"アドバンテスト","6920.T":"レーザーテック","6963.T":"ローム","4062.T":"イビデン","6525.T":"KOKUSAI ELECTRIC","6981.T":"村田製作所","6976.T":"太陽誘電","4063.T":"信越化学"},
    },
    "EV・電動化": {
        "icon": "⚡🚗", "desc": "電気自動車・電動化・EV部品",
        "stocks": {"7203.T":"トヨタ","7267.T":"ホンダ","7201.T":"日産","7270.T":"SUBARU","7269.T":"スズキ","7259.T":"アイシン","6723.T":"ルネサス","5108.T":"ブリヂストン","6981.T":"村田製作所"},
    },
    "インバウンド・観光": {
        "icon": "✈️", "desc": "訪日外国人・観光・ホテル・小売恩恵銘柄",
        "stocks": {"9202.T":"ANA HD","9201.T":"JAL","3099.T":"三越伊勢丹","8267.T":"イオン","9983.T":"ファーストリテイリング","9843.T":"ニトリHD","2502.T":"アサヒG","3086.T":"Jフロント"},
    },
    "円安メリット": {
        "icon": "💴", "desc": "円安進行時に恩恵を受ける輸出・製造業",
        "stocks": {"7203.T":"トヨタ","6758.T":"ソニーG","6954.T":"ファナック","7267.T":"ホンダ","6301.T":"コマツ","6326.T":"クボタ","5401.T":"日本製鉄","9984.T":"ソフトバンクG","4502.T":"武田薬品"},
    },
    "高配当株": {
        "icon": "💰", "desc": "高い配当利回りが期待される銘柄",
        "stocks": {"8306.T":"三菱UFJ","5020.T":"ENEOS HD","9432.T":"NTT","9433.T":"KDDI","2914.T":"日本たばこ産業","8591.T":"オリックス","5401.T":"日本製鉄","9101.T":"日本郵船","8766.T":"東京海上HD"},
    },
    "防衛・宇宙": {
        "icon": "🚀", "desc": "防衛費増額・宇宙開発恩恵銘柄",
        "stocks": {"7011.T":"三菱重工","7013.T":"IHI","7012.T":"川崎重工","6701.T":"NEC","6702.T":"富士通","6367.T":"ダイキン","1801.T":"大成建設"},
    },
    "バイオ・創薬": {
        "icon": "🧬", "desc": "バイオテクノロジー・創薬・医療機器",
        "stocks": {"4502.T":"武田薬品","4503.T":"アステラス","4519.T":"中外製薬","4568.T":"第一三共","4523.T":"エーザイ","4507.T":"塩野義製薬","4151.T":"協和キリン","4543.T":"テルモ","7741.T":"HOYA"},
    },
    "海運・物流": {
        "icon": "🚢", "desc": "海運・陸運・物流インフラ銘柄",
        "stocks": {"9101.T":"日本郵船","9104.T":"商船三井","9107.T":"川崎汽船","9062.T":"日本通運","9064.T":"ヤマトHD","9020.T":"JR東日本","9022.T":"JR東海","9202.T":"ANA HD"},
    },
    "食料・農業": {
        "icon": "🌾", "desc": "食品・農業・飲料・水産業",
        "stocks": {"2802.T":"味の素","2801.T":"キッコーマン","2897.T":"日清食品HD","2503.T":"キリンHD","2502.T":"アサヒG HD","2282.T":"日本ハム","2871.T":"ニチレイ","1332.T":"ニッスイ","2267.T":"ヤクルト"},
    },
    "仮想通貨・Web3": {
        "icon": "₿", "desc": "暗号資産取引所運営・ビットコイン保有・NFT・Web3関連企業",
        "stocks": {"8698.T":"マネックスグループ","8473.T":"SBIホールディングス","9449.T":"GMOインターネットG","3350.T":"メタプラネット","3807.T":"フィスコ","3696.T":"セレス","4751.T":"サイバーエージェント"},
    },
}

# ══════════════════════════════════════════════════════
#  テクニカル分析
# ══════════════════════════════════════════════════════
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    vals = (100 - 100 / (1 + gain / loss.replace(0, np.nan))).dropna()
    return float(vals.iloc[-1]) if not vals.empty else 50.0

def generate_reason(d):
    lines = []
    r1, r3 = d["return_1m"], d["return_3m"]
    rsi, score = d["rsi"], d["score"]
    per, pbr, div = d.get("per"), d.get("pbr"), d.get("div_yield", 0)
    sigs = [s["text"] for s in d.get("signals", [])]

    if score >= 14:   lines.append("📊 複数の強力な買いシグナルが重なる最高評価銘柄です。")
    elif score >= 10: lines.append("📊 テクニカル・ファンダメンタル両面で良好な状態です。")
    elif score >= 6:  lines.append("📊 一部のシグナルが好転しており、中期的な上昇が期待されます。")
    elif score >= 2:  lines.append("📊 一部に好転の兆しはありますが、慎重な判断が必要です。")
    else:             lines.append("📊 現時点では積極的な買いシグナルは少ない状態です。")

    if r1 > 10:   lines.append(f"直近1ヶ月で {r1:.1f}% の急騰。強いモメンタムが継続中です。")
    elif r1 > 3:  lines.append(f"直近1ヶ月で {r1:.1f}% 上昇し、上昇トレンドが続いています。")
    elif r1 > 0:  lines.append(f"直近1ヶ月で {r1:.1f}% の小幅上昇。安定した値動きです。")
    elif r1 > -5: lines.append(f"直近1ヶ月で {r1:.1f}% の小幅下落。底値模索中です。")
    else:         lines.append(f"直近1ヶ月で {r1:.1f}% 下落。底値確認が重要です。")

    if r3 > 20:    lines.append(f"3ヶ月では {r3:.1f}% の大幅上昇。中期トレンドは強気です。")
    elif r3 > 5:   lines.append(f"3ヶ月では {r3:.1f}% 上昇し、中期トレンドは上向きです。")
    elif r3 < -15: lines.append(f"3ヶ月では {r3:.1f}% 下落。反転タイミングの見極めが重要です。")

    if any("ゴールデンクロス" in s for s in sigs):
        lines.append("25日線が75日線を上回るゴールデンクロス形成中。中期の強気サインです。")
    elif any("デッドクロス" in s for s in sigs):
        lines.append("デッドクロス警戒。下落トレンドが続く可能性があります。")

    if rsi < 30:      lines.append(f"RSI({rsi:.0f})は売られすぎゾーン。反発上昇が期待されます。")
    elif rsi <= 50:   lines.append(f"RSI({rsi:.0f})は売られすぎ回復中。押し目買いの好機です。")
    elif rsi <= 65:   lines.append(f"RSI({rsi:.0f})は健全な上昇水準です。")
    elif rsi <= 75:   lines.append(f"RSI({rsi:.0f})はやや過熱気味。短期的な調整に注意。")
    else:             lines.append(f"RSI({rsi:.0f})は買われすぎゾーン。利益確定売りに注意。")

    if per and 0 < per < 15:  lines.append(f"PER {per:.1f}倍と割安水準。バリュー投資の観点から魅力的です。")
    elif per and per > 40:    lines.append(f"PER {per:.1f}倍と高め。成長への期待が織り込まれています。")
    if pbr and pbr < 1:       lines.append(f"PBR {pbr:.2f}倍と解散価値以下。下値リスクが限定的です。")
    if div and div > 3:       lines.append(f"配当利回り {div:.1f}% と高配当。インカムゲイン狙いにも適しています。")

    if any("出来高急増" in s for s in sigs):  lines.append("出来高が急増しており、市場の強い注目を集めています。")
    elif any("出来高増加" in s for s in sigs): lines.append("出来高が増加傾向で、市場の関心が高まっています。")

    return " ".join(lines)


def analyze_stock(ticker, display_name):
    """yfinanceデッドロック対策: デーモンスレッドで25秒タイムアウト"""
    hist_result = [None]
    hist_error  = [None]
    def _fetch():
        try:
            hist_result[0] = yf.Ticker(ticker).history(period="6mo", timeout=20)
        except Exception as e:
            hist_error[0] = e
    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=25)
    if t.is_alive():
        print(f"[SKIP] {ticker}: タイムアウト", flush=True)
        return None
    if hist_error[0] is not None:
        print(f"[SKIP] {ticker}: {hist_error[0]}", flush=True)
        return None
    hist = hist_result[0]
    try:
        if hist is None or hist.empty or len(hist) < 20:
            return None

        close   = hist["Close"]
        volume  = hist["Volume"]
        current = float(close.iloc[-1])

        p1m = float(close.iloc[max(-21, -len(close))])
        p3m = float(close.iloc[max(-63, -len(close))])
        ret_1m = (current - p1m) / p1m * 100
        ret_3m = (current - p3m) / p3m * 100

        ma5  = float(close.rolling(5).mean().iloc[-1])  if len(close) >= 5  else current
        ma25 = float(close.rolling(25).mean().iloc[-1]) if len(close) >= 25 else current
        ma75 = float(close.rolling(75).mean().iloc[-1]) if len(close) >= 75 else ma25

        rsi = calc_rsi(close)

        bb_std   = float(close.rolling(25).std().iloc[-1]) if len(close) >= 25 else 0
        bb_upper = ma25 + 2 * bb_std
        bb_lower = ma25 - 2 * bb_std
        bb_pct   = (current - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

        vol_now = float(volume.iloc[-5:].mean())
        vol_old = float(volume.iloc[-25:-5].mean()) if len(hist) >= 25 else vol_now
        vol_r   = vol_now / vol_old if vol_old > 0 else 1.0

        week52h = float(close.rolling(252).max().iloc[-1]) if len(close) >= 20 else float(close.max())
        week52l = float(close.rolling(252).min().iloc[-1]) if len(close) >= 20 else float(close.min())
        pct_from_high = (current - week52h) / week52h * 100 if week52h else 0
        per, pbr, div_yield = None, None, 0

        score, signals = 0, []

        if ret_1m > 10:    score += 3; signals.append({"text": f"強い上昇 1ヶ月+{ret_1m:.1f}%", "type": "positive"})
        elif ret_1m > 5:   score += 2; signals.append({"text": f"上昇継続 1ヶ月+{ret_1m:.1f}%", "type": "positive"})
        elif ret_1m > 0:   score += 1; signals.append({"text": f"小幅上昇 1ヶ月+{ret_1m:.1f}%", "type": "positive"})
        elif ret_1m < -10: score -= 2; signals.append({"text": f"急落中 1ヶ月{ret_1m:.1f}%", "type": "negative"})
        elif ret_1m < -5:  score -= 1; signals.append({"text": f"下落中 1ヶ月{ret_1m:.1f}%", "type": "negative"})

        if ret_3m > 20:   score += 3; signals.append({"text": f"中期急騰 3ヶ月+{ret_3m:.1f}%", "type": "positive"})
        elif ret_3m > 10: score += 2; signals.append({"text": f"中期上昇 3ヶ月+{ret_3m:.1f}%", "type": "positive"})
        elif ret_3m > 0:  score += 1
        elif ret_3m < -15: score -= 2
        elif ret_3m < -5:  score -= 1

        if current > ma25: score += 2; signals.append({"text": "25日MA上方（上昇トレンド）", "type": "positive"})
        else:              score -= 1; signals.append({"text": "25日MA下方（下降トレンド）", "type": "negative"})
        if ma25 > ma75:    score += 2; signals.append({"text": "ゴールデンクロス形成中", "type": "positive"})
        else:              signals.append({"text": "デッドクロス警戒", "type": "negative"})
        if current > ma75: score += 1; signals.append({"text": "75日MA上方（長期上昇）", "type": "positive"})

        if 30 <= rsi <= 50:   score += 3; signals.append({"text": f"RSI {rsi:.0f}（売られすぎ回復・買い場）", "type": "positive"})
        elif 50 < rsi <= 65:  score += 2; signals.append({"text": f"RSI {rsi:.0f}（健全な上昇）", "type": "neutral"})
        elif 25 <= rsi < 30:  score += 2; signals.append({"text": f"RSI {rsi:.0f}（強い売られすぎ・反発期待）", "type": "positive"})
        elif 65 < rsi <= 75:  score += 1; signals.append({"text": f"RSI {rsi:.0f}（やや過熱）", "type": "neutral"})
        elif rsi > 75:        score -= 1; signals.append({"text": f"RSI {rsi:.0f}（買われすぎ注意）", "type": "negative"})
        else:                 score += 1; signals.append({"text": f"RSI {rsi:.0f}（極端な売られすぎ）", "type": "neutral"})

        if bb_pct < 0.2:   score += 2; signals.append({"text": "BB下限付近（反発期待）", "type": "positive"})
        elif bb_pct < 0.4: score += 1; signals.append({"text": "BB下半分（割安圏）", "type": "positive"})
        elif bb_pct > 0.9: score -= 1; signals.append({"text": "BBバンド上限突破（過熱警戒）", "type": "negative"})

        if vol_r > 2.0:   score += 2; signals.append({"text": f"出来高急増 ×{vol_r:.1f}（注目急上昇）", "type": "positive"})
        elif vol_r > 1.3: score += 1; signals.append({"text": f"出来高増加 ×{vol_r:.1f}", "type": "positive"})

        if div_yield > 3.5: score += 2; signals.append({"text": f"高配当 {div_yield:.1f}%", "type": "positive"})
        elif div_yield > 2: score += 1; signals.append({"text": f"配当利回り {div_yield:.1f}%", "type": "positive"})

        if pct_from_high < -30: score += 1; signals.append({"text": f"52週高値から{pct_from_high:.0f}%（反発期待）", "type": "neutral"})
        elif pct_from_high > -5: signals.append({"text": f"52週高値圏", "type": "positive"})

        data = {
            "ticker": ticker, "name": display_name,
            "current_price": round(current, 0),
            "return_1m": round(ret_1m, 2), "return_3m": round(ret_3m, 2),
            "rsi": round(rsi, 1),
            "ma25": round(ma25, 0), "ma75": round(ma75, 0),
            "bb_pct": round(bb_pct, 2),
            "per": None, "pbr": None, "div_yield": None,
            "vol_ratio": round(vol_r, 2),
            "score": score, "signals": signals,
            "market": "JP",
        }
        data["reason"] = generate_reason(data)
        return data
    except Exception as e:
        print(f"[SKIP] {ticker}: {e}", flush=True)
        return None


# ══════════════════════════════════════════════════════
#  Firebase / ファイルキャッシュ（二重化）
# ══════════════════════════════════════════════════════
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache.json")
_db = None  # Firestore client（起動時に初期化）

_cache = {
    "recommendations": None,
    "themes": None,
    "last_update": None,
    "loading": False,
    "loading_since": 0,
    "charts": {},
}

def init_firebase():
    """Firebase Admin SDK初期化"""
    global _db
    key_json = os.environ.get("FIREBASE_KEY", "")
    if not key_json:
        print("[FIREBASE] FIREBASE_KEY未設定 → ファイルキャッシュのみ使用")
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fstore
        cred = credentials.Certificate(json.loads(key_json))
        firebase_admin.initialize_app(cred)
        _db = fstore.client()
        print("[FIREBASE] 接続成功 ✓")
    except Exception as e:
        print(f"[FIREBASE] 初期化失敗: {e}")

def save_data(recs, themes, last_update):
    """Firebase（優先）またはファイルにデータ保存。Firebaseは30秒タイムアウト付き。"""
    if _db is not None:
        result = [False]
        def _fb_save():
            try:
                _db.collection("cache").document("stock_data").set({
                    "recommendations": json.dumps(recs, ensure_ascii=False),
                    "themes": json.dumps(themes, ensure_ascii=False) if themes else "",
                    "last_update": last_update,
                })
                result[0] = True
                print(f"[FIREBASE] 保存完了: {last_update} ✓")
            except Exception as e:
                print(f"[FIREBASE] 保存失敗: {e}")
        t = threading.Thread(target=_fb_save, daemon=True)
        t.start()
        t.join(timeout=30)
        if t.is_alive():
            print("[FIREBASE] 保存タイムアウト（30秒）→ ファイルにフォールバック")
        elif result[0]:
            return  # Firebase保存成功
    # ファイルフォールバック
    try:
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"recommendations": recs, "themes": themes, "last_update": last_update}, f, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
        print(f"[FILE] 保存完了: {last_update} ✓")
    except Exception as e:
        print(f"[FILE] 保存失敗: {e}")

def load_data():
    """Firebase（優先）またはファイルからデータ読み込み。Firebaseは20秒タイムアウト付き。"""
    if _db is not None:
        result = [None]
        def _fb_load():
            try:
                doc = _db.collection("cache").document("stock_data").get()
                if doc.exists:
                    result[0] = doc.to_dict()
            except Exception as e:
                print(f"[FIREBASE] 読み込みエラー: {e}")
        t = threading.Thread(target=_fb_load, daemon=True)
        t.start()
        t.join(timeout=20)
        if t.is_alive():
            print("[FIREBASE] 読み込みタイムアウト（20秒）→ ファイルにフォールバック")
        elif result[0] is not None:
            try:
                d = result[0]
                _cache["recommendations"] = json.loads(d["recommendations"])
                _cache["themes"] = json.loads(d["themes"]) if d.get("themes") else None
                _cache["last_update"] = d.get("last_update")
                print(f"[FIREBASE] 読み込み完了: {_cache['last_update']} ✓")
                return True
            except Exception as e:
                print(f"[FIREBASE] データ解析失敗: {e}")
        else:
            print("[FIREBASE] ドキュメントなし or タイムアウト → ファイルにフォールバック")
    # ファイルフォールバック
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _cache["recommendations"] = data.get("recommendations")
            _cache["themes"] = data.get("themes")
            _cache["last_update"] = data.get("last_update")
            print(f"[FILE] 読み込み完了: {_cache['last_update']} ✓")
            return True
    except Exception as e:
        print(f"[FILE] 読み込み失敗: {e}")
    return False

def get_cache_age_minutes():
    """キャッシュの経過時間（分）。不明な場合は999"""
    try:
        if _cache["last_update"]:
            s = _cache["last_update"].replace(" JST", "").strip()
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    last = datetime.strptime(s, fmt)
                    return (datetime.now(JST).replace(tzinfo=None) - last).total_seconds() / 60
                except ValueError:
                    continue
    except:
        pass
    return 999

def get_firebase_last_update():
    """Firebaseのlast_updateだけ軽量取得（クロスインスタンス同期チェック用）"""
    if _db is None:
        return None
    result = [None]
    def _fetch():
        try:
            doc = _db.collection("cache").document("stock_data").get()
            if doc.exists:
                result[0] = doc.to_dict().get("last_update")
        except Exception as e:
            print(f"[FIREBASE] タイムスタンプ確認エラー: {e}", flush=True)
    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=10)
    return result[0]


# ══════════════════════════════════════════════════════
#  データ取得（バックグラウンド）
# ══════════════════════════════════════════════════════
def refresh_data():
    """yfinanceでデータ取得 → Firebase/ファイルに保存"""
    if _cache["loading"]:
        return
    _cache["loading"] = True
    _cache["loading_since"] = time.time()
    start = datetime.now(JST)
    print(f"[REFRESH] 開始 {start.strftime('%H:%M:%S JST')}", flush=True)
    try:
        # 全銘柄収集（重複除去）
        all_tasks = {}
        for sec, info in SECTORS.items():
            for t, n in info["stocks"].items():
                if t not in all_tasks:
                    all_tasks[t] = (n, [])
                all_tasks[t][1].append(sec)

        # 並列取得（5スレッド・120秒上限）
        stock_results = {}
        done = 0
        ex = ThreadPoolExecutor(max_workers=5)
        try:
            futures = {ex.submit(analyze_stock, t, name): t for t, (name, _) in all_tasks.items()}
            try:
                for future in as_completed(futures, timeout=120):
                    ticker = futures[future]
                    try:
                        result = future.result()
                    except Exception:
                        result = None
                    done += 1
                    if result:
                        stock_results[ticker] = result
                    if done % 10 == 0:
                        print(f"[REFRESH] {done}/{len(all_tasks)} 完了 / 有効:{len(stock_results)}", flush=True)
            except Exception:
                print(f"[REFRESH] タイムアウト: {done}/{len(all_tasks)} / 有効:{len(stock_results)}", flush=True)
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

        elapsed = (datetime.now(JST) - start).total_seconds()
        print(f"[REFRESH] 取得完了: {len(stock_results)}/{len(all_tasks)} 銘柄 ({elapsed:.0f}秒)", flush=True)

        if len(stock_results) < 15:
            print(f"[REFRESH] 銘柄数不足({len(stock_results)})。保存スキップ", flush=True)
            return

        # セクター振り分け
        recs = {}
        for sec, info in SECTORS.items():
            results = [stock_results[t] for t in info["stocks"] if t in stock_results]
            recs[sec] = {"icon": info["icon"],
                         "stocks": sorted(results, key=lambda x: x["score"], reverse=True)}
        _cache["recommendations"] = recs
        _cache["last_update"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
        print(f"[REFRESH] ✓ 完了: {_cache['last_update']}", flush=True)

        # テーマ処理
        themes = None
        try:
            all_theme_tickers = {}
            for theme, info in THEMES.items():
                for t, n in info["stocks"].items():
                    if t not in all_theme_tickers:
                        all_theme_tickers[t] = n
            extra = {t: n for t, n in all_theme_tickers.items() if t not in stock_results}
            if extra:
                ex2 = ThreadPoolExecutor(max_workers=5)
                try:
                    futures2 = {ex2.submit(analyze_stock, t, n): t for t, n in extra.items()}
                    try:
                        for future in as_completed(futures2, timeout=60):
                            try:
                                r = future.result()
                            except Exception:
                                r = None
                            if r:
                                stock_results[futures2[future]] = r
                    except Exception:
                        pass
                finally:
                    ex2.shutdown(wait=False, cancel_futures=True)
            themes = {}
            for theme, info in THEMES.items():
                results = [stock_results[t] for t in info["stocks"] if t in stock_results]
                themes[theme] = {"icon": info["icon"], "desc": info["desc"],
                                 "stocks": sorted(results, key=lambda x: x["score"], reverse=True)}
            _cache["themes"] = themes
        except Exception as te:
            print(f"[REFRESH] テーマ処理エラー（無視）: {te}")

        # 保存（Firebase or ファイル）
        save_data(_cache["recommendations"], _cache["themes"], _cache["last_update"])

    except Exception as e:
        print(f"[REFRESH] ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        _cache["loading"] = False


# ══════════════════════════════════════════════════════
#  API エンドポイント
# ══════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    """データ読み取り専用。ただしデータが全くない場合は自己修復でリフレッシュ起動。"""
    # loadingが5分以上続いている場合はスタックと判断してリセット
    if _cache["loading"] and (time.time() - _cache["loading_since"]) > 300:
        print("[WARN] loading が5分以上継続 → 強制リセット", flush=True)
        _cache["loading"] = False

    # データなし・ロードもしていない → バックグラウンドで取得開始（自己修復）
    if not _cache["recommendations"] and not _cache["loading"]:
        print("[INFO] データなし → バックグラウンドリフレッシュ開始", flush=True)
        threading.Thread(target=refresh_data, daemon=True).start()

    if _cache["recommendations"]:
        resp = make_response(jsonify({
            "recommendations": _cache["recommendations"],
            "themes": _cache["themes"],
            "last_update": _cache["last_update"],
            "loading": _cache["loading"],
        }))
    elif _cache["loading"]:
        resp = make_response(jsonify({"loading": True}))
    else:
        resp = make_response(jsonify({"loading": False, "error": True}))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.route("/api/status")
def api_status():
    has_recs = _cache["recommendations"] is not None
    stock_count = sum(len(v["stocks"]) for v in _cache["recommendations"].values()) if has_recs else 0
    return jsonify({
        "has_data": has_recs,
        "stock_count": stock_count,
        "last_update": _cache["last_update"],
        "is_loading": _cache["loading"],
        "cache_age_min": round(get_cache_age_minutes(), 1),
        "firebase": _db is not None,
    })

@app.route("/api/force-refresh")
def api_force_refresh():
    """強制リフレッシュ（管理用）"""
    _cache["loading"] = False
    threading.Thread(target=refresh_data, daemon=True).start()
    return jsonify({"status": "started", "message": "強制リフレッシュ開始しました"})

@app.route("/api/chart/<ticker>")
def api_chart(ticker):
    cached = _cache["charts"].get(ticker)
    if cached and time.time() - cached["ts"] < 3600:
        return jsonify({"ticker": ticker, "data": cached["data"]})

    result = [None]
    fetch_error = [None]
    def fetch():
        try:
            result[0] = yf.Ticker(ticker).history(period="3mo", interval="1d", timeout=15)
        except Exception as e:
            fetch_error[0] = e
    t = threading.Thread(target=fetch, daemon=True)
    t.start()
    t.join(timeout=20)
    if t.is_alive():
        print(f"[CHART] タイムアウト: {ticker}", flush=True)
        if cached:
            return jsonify({"ticker": ticker, "data": cached["data"]})
        return jsonify({"error": "タイムアウト"}), 504
    if fetch_error[0] is not None:
        if cached:
            return jsonify({"ticker": ticker, "data": cached["data"]})
        return jsonify({"error": str(fetch_error[0])}), 500
    hist = result[0]
    if hist is None or hist.empty:
        if cached:
            return jsonify({"ticker": ticker, "data": cached["data"]})
        return jsonify({"error": "No data"}), 404
    data = [{"date": idx.strftime("%m/%d"),
             "open": round(float(r["Open"]), 0), "high": round(float(r["High"]), 0),
             "low": round(float(r["Low"]), 0), "close": round(float(r["Close"]), 0),
             "volume": int(r["Volume"])} for idx, r in hist.iterrows()]
    _cache["charts"][ticker] = {"data": data, "ts": time.time()}
    return jsonify({"ticker": ticker, "data": data})


# ══════════════════════════════════════════════════════
#  バックグラウンドスレッド（自己ping + 自動更新）
# ══════════════════════════════════════════════════════
def scheduler_and_ping():
    """10分ごとに自己ping（Renderスリープ防止）+ データが古ければ自動更新"""
    url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if url:
        print(f"[PING] 自己ping設定: {url}/api/data")
    else:
        print("[PING] RENDER_EXTERNAL_URL未設定（ローカル環境）")

    while True:
        time.sleep(10 * 60)  # 10分待機

        # ── Firebase との同期チェック（別インスタンスの更新を拾う）──
        if not _cache["loading"]:
            fb_ts = get_firebase_last_update()
            if fb_ts and fb_ts != _cache.get("last_update"):
                print(f"[SYNC] Firebaseに新しいデータ検出 ({fb_ts}) → メモリ更新", flush=True)
                load_data()

        # データが35分以上古ければ更新
        age = get_cache_age_minutes()
        if age > 35 and not _cache["loading"]:
            print(f"[SCHEDULER] データが{age:.0f}分前 → バックグラウンド更新開始", flush=True)
            threading.Thread(target=refresh_data, daemon=True).start()
        else:
            status = "更新中" if _cache["loading"] else f"{age:.0f}分前"
            print(f"[SCHEDULER] データ状態: {status}", flush=True)

        # 自己ping（Renderスリープ防止）
        if url:
            try:
                urllib.request.urlopen(f"{url}/api/data", timeout=15)
                print(f"[PING] ✓ 成功", flush=True)
            except Exception as e:
                print(f"[PING] 失敗: {e}", flush=True)


# ══════════════════════════════════════════════════════
#  起動処理
# ══════════════════════════════════════════════════════
def startup():
    print("=" * 52)
    print("  📈 株式おすすめアプリ v4（Firebase対応）")
    print(f"  分析対象: {sum(len(v['stocks']) for v in SECTORS.values())} 銘柄")
    print("=" * 52)

    # Firebase初期化
    init_firebase()

    # データ読み込み（Firebase → ファイル）
    has_cache = load_data()
    if not has_cache:
        print("[STARTUP] データなし → 初回データ取得を開始")
        threading.Thread(target=refresh_data, daemon=True).start()
    else:
        age = get_cache_age_minutes()
        print(f"[STARTUP] キャッシュ年齢: {age:.0f}分")
        if age > 60:
            print("[STARTUP] 古いキャッシュ → バックグラウンドで更新開始")
            threading.Thread(target=refresh_data, daemon=True).start()
        else:
            print(f"[STARTUP] 有効なキャッシュ: {_cache['last_update']}")

    # 自己ping + 自動更新スレッド開始
    threading.Thread(target=scheduler_and_ping, daemon=True).start()
    print("[STARTUP] 完了 ✓")

startup()

if __name__ == "__main__":
    print("  http://localhost:5000  をブラウザで開いてください")
    app.run(host="0.0.0.0", port=5000, debug=False)
