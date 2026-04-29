#\!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""株式おすすめアプリ v3 - 東証専用 / 全銘柄並列取得"""

from flask import Flask, jsonify, render_template
import yfinance as yf
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json
import os
import time
import requests
import functools

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
            "6756.T":"日立国際電気", "6981.T":"村田製作所",
            "6976.T":"太陽誘電",
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
            "4812.T":"NTTデータ", "4901.T":"富士フイルムHD",
            "6367.T":"ダイキン工業",
        },
    },
    "通信": {
        "icon": "📡",
        "keywords": ["通信","5G","telecom","NTT","KDDI","ソフトバンク"],
        "stocks": {
            "9432.T":"NTT", "9433.T":"KDDI",
            "9434.T":"ソフトバンク", "9414.T":"日本BS放送",
            "9437.T":"NTTドコモ(参考)", "9603.T":"エイチ・アイ・エス",
            "4689.T":"LINEヤフー", "2440.T":"ぐるなび",
            "3632.T":"グリー", "4385.T":"メルカリ",
            "4911.T":"資生堂", "3092.T":"ZOZO",
            "4755.T":"楽天グループ", "6028.T":"テクノプロHD",
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
            "5105.T":"TOYO TIRE", "5108.T":"ブリヂストン",
            "7012.T":"川崎重工業", "7011.T":"三菱重工業",
            "7013.T":"IHI", "6326.T":"クボタ",
            "6301.T":"コマツ",
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
            "4021.T":"日産化学", "4185.T":"JSR",
            "4188.T":"三菱ケミカルグループ", "4004.T":"レゾナック",
            "4911.T":"資生堂",
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
            "8354.T":"ふくおかFG", "8355.T":"静岡銀行",
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
            "8096.T":"兼松エレクトロニクス", "7148.T":"FPG",
        },
    },
    "仮想通貨・暗号資産": {
        "icon": "₿",
        "keywords": ["仮想通貨","暗号資産","crypto","bitcoin","ビットコイン","NFT","web3","ブロックチェーン","coincheck"],
        "stocks": {
            "8698.T":"マネックスグループ",  "8473.T":"SBIホールディングス",
            "9449.T":"GMOインターネットG",  "3350.T":"メタプラネット",
            "3807.T":"フィスコ",            "3696.T":"セレス",
            "2315.T":"カイカ",              "4751.T":"サイバーエージェント",
            "3632.T":"グリー",              "9984.T":"ソフトバンクG",
            "3659.T":"ネクソン",            "2121.T":"ミクシィ",
        },
    },
    "エネルギー・電力": {
        "icon": "⚡",
        "keywords": ["エネルギー","電力","石油","ガス","energy","原油"],
        "stocks": {
            "5020.T":"ENEOSホールディングス", "5019.T":"出光興産",
            "9531.T":"東京ガス", "9532.T":"大阪ガス",
            "9503.T":"関西電力", "9501.T":"東京電力HD",
            "9502.T":"中部電力", "9504.T":"中国電力",
            "9505.T":"北陸電力", "9506.T":"東北電力",
            "1605.T":"INPEX", "5021.T":"コスモエネルギーHD",
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
            "5101.T":"横浜ゴム", "4005.T":"住友化学",
            "4042.T":"東ソー", "4201.T":"日本合成化学工業",
            "5202.T":"日本板硝子", "5301.T":"東海カーボン",
            "4901.T":"富士フイルムHD",
        },
    },
    "消費・小売": {
        "icon": "🛍️",
        "keywords": ["小売","消費","retail","consumer","ユニクロ","イオン"],
        "stocks": {
            "9983.T":"ファーストリテイリング", "8267.T":"イオン",
            "3382.T":"セブン&iHD", "9843.T":"ニトリHD",
            "2651.T":"ローソン", "8028.T":"ファミリーマート",
            "3086.T":"Jフロントリテイリング", "3099.T":"三越伊勢丹HD",
            "2670.T":"ABCマート", "7716.T":"ナカニシ",
            "9948.T":"アークス", "3337.T":"丸文",
            "2758.T":"テーオーシー", "7453.T":"良品計画",
            "3092.T":"ZOZO",
        },
    },
    "食品・飲料": {
        "icon": "🍜",
        "keywords": ["食品","飲料","food","beverage","農業"],
        "stocks": {
            "2802.T":"味の素", "2914.T":"日本たばこ産業",
            "2503.T":"キリンHD", "2502.T":"アサヒグループHD",
            "2587.T":"サントリー飲料食品", "2801.T":"キッコーマン",
            "2897.T":"日清食品HD", "2871.T":"ニチレイ",
            "2282.T":"日本ハム", "2267.T":"ヤクルト本社",
            "2288.T":"丸大食品", "2270.T":"雪印メグミルク",
            "2810.T":"ハウス食品G本社", "1332.T":"ニッスイ",
            "2531.T":"宝ホールディングス",
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
            "8984.T":"大和ハウスリート投資法人", "3269.T":"アドバンス・レジデンス投資法人",
            "3281.T":"GLP投資法人", "3234.T":"森ヒルズリート投資法人",
            "1808.T":"長谷工コーポレーション", "1878.T":"大東建託",
            "3003.T":"ヒューリック",
        },
    },
    "ゲーム・エンタメ": {
        "icon": "🎮",
        "keywords": ["ゲーム","エンタメ","game","任天堂","コナミ"],
        "stocks": {
            "7974.T":"任天堂", "9766.T":"コナミグループ",
            "9684.T":"スクウェア・エニックスHD", "3765.T":"ガンホー・オンライン",
            "9697.T":"カプコン", "7832.T":"バンダイナムコHD",
            "9601.T":"松竹", "9602.T":"東宝",
            "4324.T":"電通グループ", "2471.T":"エスプール",
            "3668.T":"コロプラ", "3632.T":"グリー",
            "4751.T":"サイバーエージェント", "2121.T":"ミクシィ",
            "4348.T":"インフォコム",
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
            "9147.T":"NIPPON EXPRESSホールディングス", "9006.T":"京浜急行電鉄",
            "9007.T":"小田急電鉄", "9008.T":"京王電鉄",
            "9009.T":"京成電鉄",
        },
    },
}

# ══════════════════════════════════════════════════════
#  テーマ別銘柄（東証のみ）
# ══════════════════════════════════════════════════════
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
        "stocks": {"9202.T":"ANA HD","9201.T":"JAL","3099.T":"三越伊勢丹","8267.T":"イオン","9983.T":"ファーストリテイリング","9843.T":"ニトリHD","2587.T":"サントリー飲料","2502.T":"アサヒG","3086.T":"Jフロント"},
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
        "stocks": {"7011.T":"三菱重工","7013.T":"IHI","7012.T":"川崎重工","6502.T":"東芝","6701.T":"NEC","6702.T":"富士通","7752.T":"リコー","6367.T":"ダイキン","1801.T":"大成建設"},
    },
    "バイオ・創薬": {
        "icon": "🧬", "desc": "バイオテクノロジー・創薬・医療機器",
        "stocks": {"4502.T":"武田薬品","4503.T":"アステラス","4519.T":"中外製薬","4568.T":"第一三共","4523.T":"エーザイ","4507.T":"塩野義製薬","4151.T":"協和キリン","4543.T":"テルモ","7741.T":"HOYA"},
    },
    "海運・物流": {
        "icon": "🚢", "desc": "海運・陸運・物流インフラ銘柄",
        "stocks": {"9101.T":"日本郵船","9104.T":"商船三井","9107.T":"川崎汽船","9062.T":"日本通運","9064.T":"ヤマトHD","9147.T":"NIPPON EXPRESS","9020.T":"JR東日本","9022.T":"JR東海","9202.T":"ANA HD"},
    },
    "食料・農業": {
        "icon": "🌾", "desc": "食品・農業・飲料・水産業",
        "stocks": {"2802.T":"味の素","2801.T":"キッコーマン","2897.T":"日清食品HD","2503.T":"キリンHD","2502.T":"アサヒG HD","2282.T":"日本ハム","2871.T":"ニチレイ","1332.T":"ニッスイ","2267.T":"ヤクルト"},
    },
    "仮想通貨・Web3": {
        "icon": "₿", "desc": "暗号資産取引所運営・ビットコイン保有・NFT・Web3関連企業",
        "stocks": {"8698.T":"マネックスグループ","8473.T":"SBIホールディングス","9449.T":"GMOインターネットG","3350.T":"メタプラネット","3807.T":"フィスコ","3696.T":"セレス","2315.T":"カイカ","4751.T":"サイバーエージェント","3632.T":"グリー"},
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

    # 総評
    if score >= 14:   lines.append("📊 複数の強力な買いシグナルが重なる最高評価銘柄です。")
    elif score >= 10: lines.append("📊 テクニカル・ファンダメンタル両面で良好な状態です。")
    elif score >= 6:  lines.append("📊 一部のシグナルが好転しており、中期的な上昇が期待されます。")
    elif score >= 2:  lines.append("📊 一部に好転の兆しはありますが、慎重な判断が必要です。")
    else:             lines.append("📊 現時点では積極的な買いシグナルは少ない状態です。")

    # モメンタム
    if r1 > 10:   lines.append(f"直近1ヶ月で {r1:.1f}% の急騰。強いモメンタムが継続中です。")
    elif r1 > 3:  lines.append(f"直近1ヶ月で {r1:.1f}% 上昇し、上昇トレンドが続いています。")
    elif r1 > 0:  lines.append(f"直近1ヶ月で {r1:.1f}% の小幅上昇。安定した値動きです。")
    elif r1 > -5: lines.append(f"直近1ヶ月で {r1:.1f}% の小幅下落。底値模索中です。")
    else:         lines.append(f"直近1ヶ月で {r1:.1f}% 下落。底値確認が重要です。")

    if r3 > 20:   lines.append(f"3ヶ月では {r3:.1f}% の大幅上昇。中期トレンドは強気です。")
    elif r3 > 5:  lines.append(f"3ヶ月では {r3:.1f}% 上昇し、中期トレンドは上向きです。")
    elif r3 < -15: lines.append(f"3ヶ月では {r3:.1f}% 下落。反転タイミングの見極めが重要です。")

    # トレンド
    if any("ゴールデンクロス" in s for s in sigs):
        lines.append("25日線が75日線を上回るゴールデンクロス形成中。中期の強気サインです。")
    elif any("デッドクロス" in s for s in sigs):
        lines.append("デッドクロス警戒。下落トレンドが続く可能性があります。")

    # RSI
    if rsi < 30:      lines.append(f"RSI({rsi:.0f})は売られすぎゾーン。反発上昇が期待されます。")
    elif rsi <= 50:   lines.append(f"RSI({rsi:.0f})は売られすぎ回復中。押し目買いの好機です。")
    elif rsi <= 65:   lines.append(f"RSI({rsi:.0f})は健全な上昇水準です。")
    elif rsi <= 75:   lines.append(f"RSI({rsi:.0f})はやや過熱気味。短期的な調整に注意。")
    else:             lines.append(f"RSI({rsi:.0f})は買われすぎゾーン。利益確定売りに注意。")

    # ファンダメンタル
    if per and 0 < per < 15:  lines.append(f"PER {per:.1f}倍と割安水準。バリュー投資の観点から魅力的です。")
    elif per and per > 40:    lines.append(f"PER {per:.1f}倍と高め。成長への期待が織り込まれています。")
    if pbr and pbr < 1:       lines.append(f"PBR {pbr:.2f}倍と解散価値以下。下値リスクが限定的です。")
    if div and div > 3:       lines.append(f"配当利回り {div:.1f}% と高配当。インカムゲイン狙いにも適しています。")

    # 出来高
    if any("出来高急増" in s for s in sigs): lines.append("出来高が急増しており、市場の強い注目を集めています。")
    elif any("出来高増加" in s for s in sigs): lines.append("出来高が増加傾向で、市場の関心が高まっています。")

    return " ".join(lines)


def analyze_stock(ticker, display_name):
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="6mo", timeout=20)
        if hist.empty or len(hist) < 20:
            return None

        close   = hist["Close"]
        volume  = hist["Volume"]
        current = float(close.iloc[-1])

        # ── リターン計算 ──
        p1w = float(close.iloc[max(-5,  -len(close))])
        p1m = float(close.iloc[max(-21, -len(close))])
        p3m = float(close.iloc[max(-63, -len(close))])
        ret_1w = (current - p1w) / p1w * 100
        ret_1m = (current - p1m) / p1m * 100
        ret_3m = (current - p3m) / p3m * 100

        # ── 移動平均（日本標準: 5・25・75日） ──
        ma5  = float(close.rolling(5).mean().iloc[-1])  if len(close) >= 5  else current
        ma25 = float(close.rolling(25).mean().iloc[-1]) if len(close) >= 25 else current
        ma75 = float(close.rolling(75).mean().iloc[-1]) if len(close) >= 75 else ma25

        # ── RSI(14) ──
        rsi = calc_rsi(close)

        # ── ボリンジャーバンド（25日・2σ） ──
        bb_std   = float(close.rolling(25).std().iloc[-1]) if len(close) >= 25 else 0
        bb_upper = ma25 + 2 * bb_std
        bb_lower = ma25 - 2 * bb_std
        bb_pct   = (current - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

        # ── 出来高 ──
        vol_now = float(volume.iloc[-5:].mean())
        vol_old = float(volume.iloc[-25:-5].mean()) if len(hist) >= 25 else vol_now
        vol_r   = vol_now / vol_old if vol_old > 0 else 1.0

        # ── 52週高値・安値（historyから計算） ──
        week52h = float(close.rolling(252).max().iloc[-1]) if len(close) >= 20 else float(close.max())
        week52l = float(close.rolling(252).min().iloc[-1]) if len(close) >= 20 else float(close.min())
        pct_from_high = (current - week52h) / week52h * 100 if week52h else 0
        per, pbr, div_yield = None, None, 0

        # ══ スコアリング（最大約20点） ══
        score, signals = 0, []

        # 1. モメンタム（最大6点）
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

        # 2. トレンド分析（最大5点）
        if current > ma25: score += 2; signals.append({"text": "25日MA上方（上昇トレンド）", "type": "positive"})
        else:              score -= 1; signals.append({"text": "25日MA下方（下降トレンド）", "type": "negative"})
        if ma25 > ma75:    score += 2; signals.append({"text": "ゴールデンクロス形成中", "type": "positive"})
        else:              signals.append({"text": "デッドクロス警戒", "type": "negative"})
        if current > ma75: score += 1; signals.append({"text": "75日MA上方（長期上昇）", "type": "positive"})

        # 3. RSI（最大3点）
        if 30 <= rsi <= 50:   score += 3; signals.append({"text": f"RSI {rsi:.0f}（売られすぎ回復・買い場）", "type": "positive"})
        elif 50 < rsi <= 65:  score += 2; signals.append({"text": f"RSI {rsi:.0f}（健全な上昇）", "type": "neutral"})
        elif 25 <= rsi < 30:  score += 2; signals.append({"text": f"RSI {rsi:.0f}（強い売られすぎ・反発期待）", "type": "positive"})
        elif 65 < rsi <= 75:  score += 1; signals.append({"text": f"RSI {rsi:.0f}（やや過熱）", "type": "neutral"})
        elif rsi > 75:        score -= 1; signals.append({"text": f"RSI {rsi:.0f}（買われすぎ注意）", "type": "negative"})
        else:                 score += 1; signals.append({"text": f"RSI {rsi:.0f}（極端な売られすぎ）", "type": "neutral"})

        # 4. ボリンジャーバンド（最大2点）
        if bb_pct < 0.2:   score += 2; signals.append({"text": "BB下限付近（反発期待）", "type": "positive"})
        elif bb_pct < 0.4: score += 1; signals.append({"text": "BB下半分（割安圏）", "type": "positive"})
        elif bb_pct > 0.9: score -= 1; signals.append({"text": "BBバンド上限突破（過熱警戒）", "type": "negative"})

        # 5. 出来高（最大2点）
        if vol_r > 2.0:   score += 2; signals.append({"text": f"出来高急増 ×{vol_r:.1f}（注目急上昇）", "type": "positive"})
        elif vol_r > 1.3: score += 1; signals.append({"text": f"出来高増加 ×{vol_r:.1f}", "type": "positive"})

        # 6. ファンダメンタル（最大4点）
        if per is not None and per > 0:
            if per < 15:   score += 2; signals.append({"text": f"PER {per:.1f}倍（割安）", "type": "positive"})
            elif per < 25: score += 1; signals.append({"text": f"PER {per:.1f}倍（適正）", "type": "neutral"})
            elif per > 50: score -= 1; signals.append({"text": f"PER {per:.1f}倍（割高注意）", "type": "negative"})

        if pbr is not None and pbr > 0:
            if pbr < 1:   score += 2; signals.append({"text": f"PBR {pbr:.2f}倍（解散価値以下）", "type": "positive"})
            elif pbr < 2: score += 1; signals.append({"text": f"PBR {pbr:.2f}倍（割安圏）", "type": "positive"})

        if div_yield > 3.5: score += 2; signals.append({"text": f"高配当 {div_yield:.1f}%", "type": "positive"})
        elif div_yield > 2: score += 1; signals.append({"text": f"配当利回り {div_yield:.1f}%", "type": "positive"})

        # 7. 52週高値からの乖離（最大1点）
        if pct_from_high < -30: score += 1; signals.append({"text": f"52週高値から{pct_from_high:.0f}%（反発期待）", "type": "neutral"})
        elif pct_from_high > -5: signals.append({"text": f"52週高値圏", "type": "positive"})

        data = {
            "ticker": ticker, "name": display_name,
            "current_price": round(current, 0),
            "return_1m": round(ret_1m, 2), "return_3m": round(ret_3m, 2),
            "rsi": round(rsi, 1),
            "ma25": round(ma25, 0), "ma75": round(ma75, 0),
            "bb_pct": round(bb_pct, 2),
            "per": round(per, 1) if per and per > 0 else None,
            "pbr": round(pbr, 2) if pbr and pbr > 0 else None,
            "div_yield": round(div_yield, 1) if div_yield > 0 else None,
            "vol_ratio": round(vol_r, 2),
            "score": score, "signals": signals,
            "market": "JP",
        }
        data["reason"] = generate_reason(data)
        return data
    except Exception as e:
        print(f"[SKIP] {ticker}: {e}")
        return None

# ══════════════════════════════════════════════════════
#  並列データ取得
# ══════════════════════════════════════════════════════
CACHE_FILE = "data_cache.json"
_cache = {"recommendations": None, "themes": None, "last_update": None, "loading": False, "charts": {}}

# ══════════════════════════════════════════════════════
#  ファイルキャッシュ（サーバー再起動対応）
# ══════════════════════════════════════════════════════
def save_cache_to_file():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "recommendations": _cache["recommendations"],
                "themes": _cache["themes"],
                "last_update": _cache["last_update"],
            }, f, ensure_ascii=False)
        print("[INFO] キャッシュをファイルに保存しました")
    except Exception as e:
        print(f"[WARN] キャッシュ保存失敗: {e}")

def load_cache_from_file():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _cache["recommendations"] = data.get("recommendations")
            _cache["themes"] = data.get("themes")
            _cache["last_update"] = data.get("last_update")
            print(f"[INFO] キャッシュ読み込み完了（{_cache['last_update']}）")
            return True
    except Exception as e:
        print(f"[WARN] キャッシュ読み込み失敗: {e}")
    return False

def refresh_data():
    if _cache["loading"]: return
    _cache["loading"] = True
    print("[INFO] データ取得開始（並列処理）...")
    try:
        # 全セクターの全銘柄リストを収集（重複除去）
        all_tasks = {}  # ticker -> (display_name, [sectors])
        for sec, info in SECTORS.items():
            for t, n in info["stocks"].items():
                if t not in all_tasks:
                    all_tasks[t] = (n, [])
                all_tasks[t][1].append(sec)

        # 並列取得（最大5スレッド・1銘柄30秒タイムアウト）
        stock_results = {}
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(analyze_stock, t, name): t
                       for t, (name, _) in all_tasks.items()}
            done = 0
            for future in as_completed(futures, timeout=600):
                ticker = futures[future]
                try:
                    result = future.result(timeout=30)
                except Exception:
                    result = None
                done += 1
                if result:
                    stock_results[ticker] = result
                if done % 20 == 0:
                    print(f"[INFO] {done}/{len(all_tasks)} 銘柄取得完了")

        print(f"[INFO] 取得成功: {len(stock_results)}/{len(all_tasks)} 銘柄")

        # セクター別に振り分け
        recs = {}
        for sec, info in SECTORS.items():
            results = [stock_results[t] for t in info["stocks"] if t in stock_results]
            recs[sec] = {"icon": info["icon"],
                         "stocks": sorted(results, key=lambda x: x["score"], reverse=True)}
        _cache["recommendations"] = recs

        # ★ここでタイムスタンプを確定・保存（テーマ処理が失敗しても必ず更新される）
        _cache["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[INFO] 完了: {_cache['last_update']}")
        save_cache_to_file()

        # テーマ別（同じく並列結果を使い回す）
        all_theme_tickers = {}
        for theme, info in THEMES.items():
            for t, n in info["stocks"].items():
                if t not in all_theme_tickers:
                    all_theme_tickers[t] = n

        # テーマにしかない銘柄を追加取得
        extra = {t: n for t, n in all_theme_tickers.items() if t not in stock_results}
        if extra:
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = {ex.submit(analyze_stock, t, n): t for t, n in extra.items()}
                for future in as_completed(futures, timeout=300):
                    try:
                        r = future.result(timeout=30)
                    except Exception:
                        r = None
                    if r:
                        stock_results[futures[future]] = r

        themes = {}
        for theme, info in THEMES.items():
            results = [stock_results[t] for t in info["stocks"] if t in stock_results]
            themes[theme] = {"icon": info["icon"], "desc": info["desc"],
                             "stocks": sorted(results, key=lambda x: x["score"], reverse=True)}
        _cache["themes"] = themes
    except Exception as e:
        print(f"[ERROR] refresh_data: {e}")
        import traceback; traceback.print_exc()
    finally:
        _cache["loading"] = False

# ══════════════════════════════════════════════════════
#  API
# ══════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    # キャッシュなし かつ 取得中でもない → バックグラウンドで取得開始
    if not _cache["recommendations"] and not _cache["loading"]:
        threading.Thread(target=refresh_data, daemon=True).start()
    if _cache["loading"] and not _cache["recommendations"]:
        return jsonify({"loading": True})
    # キャッシュあればすぐ返す（取得中でも古いデータを返す）
    return jsonify({"recommendations": _cache["recommendations"], "themes": _cache["themes"],
                    "last_update": _cache["last_update"], "loading": False})


@app.route("/api/chart/<ticker>")
def api_chart(ticker):
    # キャッシュチェック（1時間有効）
    cached = _cache["charts"].get(ticker)
    if cached and time.time() - cached["ts"] < 3600:
        return jsonify({"ticker": ticker, "data": cached["data"]})

    def _fetch():
        # カスタムセッションで全HTTPリクエストに10秒タイムアウトを設定
        sess = requests.Session()
        sess.request = functools.partial(sess.request, timeout=10)
        h = yf.Ticker(ticker, session=sess).history(period="3mo", interval="1d")
        return h

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_fetch)
            try:
                hist = fut.result(timeout=20)
            except Exception:
                # キャッシュが古くても返す（タイムアウト時のフォールバック）
                if cached:
                    return jsonify({"ticker": ticker, "data": cached["data"]})
                return jsonify({"error": "chart timeout"}), 504
        if hist.empty: return jsonify({"error": "No data"}), 404
        data = [{"date": idx.strftime("%m/%d"),
                 "open": round(float(r["Open"]), 0), "high": round(float(r["High"]), 0),
                 "low": round(float(r["Low"]), 0), "close": round(float(r["Close"]), 0),
                 "volume": int(r["Volume"])} for idx, r in hist.iterrows()]
        # キャッシュに保存
        _cache["charts"][ticker] = {"data": data, "ts": time.time()}
        return jsonify({"ticker": ticker, "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def background_scheduler():
    """10分ごとに自動データ更新（クライアントには通知しない）"""
    while True:
        time.sleep(10 * 60)
        print("[SCHEDULER] 定期更新開始...")
        refresh_data()

def self_ping():
    """10分ごとに自分自身にアクセスしてRenderのスリープを防止"""
    import urllib.request
    url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not url:
        print("[PING] RENDER_EXTERNAL_URL未設定。ローカル環境のためスキップ。")
        return
    print(f"[PING] 自己pingを開始します: {url}")
    while True:
        time.sleep(10 * 60)  # 10分待機
        try:
            urllib.request.urlopen(f"{url}/api/data", timeout=15)
            print(f"[PING] 自己ping成功 → スリープ防止")
        except Exception as e:
            print(f"[PING] 自己ping失敗: {e}")

def startup():
    print("=" * 52)
    print("  📈 株式おすすめアプリ v3 起動中（東証専用）")
    print(f"  分析対象: {sum(len(v['stocks']) for v in SECTORS.values())} 銘柄")
    print("=" * 52)
    # まずファイルキャッシュから読み込む（即座に提供できるように）
    if load_cache_from_file():
        print("[INFO] キャッシュから即座にデータを提供します")
        # バックグラウンドで最新データを取得
        threading.Thread(target=refresh_data, daemon=True).start()
    else:
        print("[INFO] キャッシュなし → 初回データ取得を開始します")
        threading.Thread(target=refresh_data, daemon=True).start()
    # 定期更新スケジューラー起動
    threading.Thread(target=background_scheduler, daemon=True).start()
    # 自己pingでスリープ防止
    threading.Thread(target=self_ping, daemon=True).start()

startup()

if __name__ == "__main__":
    print("  http://localhost:5000  をブラウザで開いてください")
    app.run(host="0.0.0.0", port=5000, debug=False)
