"""
API 伺服器
提供預測結果的 REST API
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import logging
import numpy as np

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware

# 加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.news_scraper import RSSNewsScraper, NewsAPIFetcher
from scraper.stock_data import StockDataFetcher, SECTORS
from nlp.sentiment import SentimentAnalyzer
from ml.predictor import StockPredictor, PredictionResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== 建立 FastAPI 應用 =====

app = FastAPI(
    title="📈 AI 股票預測系統",
    description="基於 30 天新聞情緒分析，預測不同類別股票的升跌機率",
    version="1.0.0",
)

# 允許前端跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 允許所有來源（開發用）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 全局狀態 =====

class AppState:
    """應用程式狀態"""
    def __init__(self):
        self.stock_fetcher = StockDataFetcher()
        self.sentiment_analyzer: Optional[SentimentAnalyzer] = None
        self.predictors: Dict[str, StockPredictor] = {}
        
        # 緩存
        self.cached_predictions: Dict[str, dict] = {}
        self.cached_news: List[dict] = []
        self.last_update: Optional[datetime] = None
        self.is_processing = False

state = AppState()


# ===== API 端點 =====

@app.get("/")
async def root():
    """API 首頁"""
    return {
        "message": "📈 AI 股票預測系統 API",
        "status": "running",
        "last_update": state.last_update.isoformat() if state.last_update else "尚未更新",
        "endpoints": {
            "GET /sectors": "獲取所有股票類別",
            "GET /predictions": "獲取所有預測結果",
            "GET /predictions/{sector}": "獲取特定類別預測",
            "GET /news": "獲取新聞列表",
            "GET /dashboard": "獲取儀表板數據",
            "POST /refresh": "手動刷新數據",
        }
    }


# ===== 翻譯 API =====

# 翻譯快取(避免重複翻譯同樣的文字)
translation_cache: Dict[str, str] = {}


@app.post("/translate")
async def translate_text(request: dict):
    """
    翻譯文字 (使用免費的 MyMemory API)
    
    Body:
        text: 要翻譯的文字
        target_lang: 目標語言 (預設 zh-TW)
    """
    text = request.get("text", "").strip()
    target_lang = request.get("target_lang", "zh-TW")
    
    if not text:
        return {"translated": "", "original": text}
    
    # 檢查快取
    cache_key = f"{text}_{target_lang}"
    if cache_key in translation_cache:
        return {
            "translated": translation_cache[cache_key],
            "original": text,
            "cached": True,
        }
    
    try:
        import aiohttp
        
        # 使用免費的 MyMemory API
        # 語言代碼: zh-TW (繁中), zh-CN (簡中), ja (日文), ko (韓文)
        lang_pair = f"en|{target_lang}"
        
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text[:500],  # 限制字數避免超過 API 限制
            "langpair": lang_pair,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translated = data.get("responseData", {}).get("translatedText", text)
                    
                    # 存入快取
                    translation_cache[cache_key] = translated
                    
                    # 限制快取大小(避免無限增長)
                    if len(translation_cache) > 1000:
                        # 移除最舊的 200 個
                        keys_to_remove = list(translation_cache.keys())[:200]
                        for k in keys_to_remove:
                            del translation_cache[k]
                    
                    return {
                        "translated": translated,
                        "original": text,
                        "cached": False,
                    }
                else:
                    return {"translated": text, "original": text, "error": f"API returned {resp.status}"}
    
    except Exception as e:
        logger.error(f"翻譯失敗: {e}")
        return {"translated": text, "original": text, "error": str(e)}


@app.post("/translate/batch")
async def translate_batch(request: dict):
    """
    批量翻譯多個文字
    
    Body:
        texts: List of strings
        target_lang: 目標語言
    """
    texts = request.get("texts", [])
    target_lang = request.get("target_lang", "zh-TW")
    
    if not texts or not isinstance(texts, list):
        return {"translations": []}
    
    import aiohttp
    import asyncio
    
    async def translate_one(session, text):
        # 檢查快取
        cache_key = f"{text}_{target_lang}"
        if cache_key in translation_cache:
            return translation_cache[cache_key]
        
        try:
            lang_pair = f"en|{target_lang}"
            url = "https://api.mymemory.translated.net/get"
            params = {"q": text[:500], "langpair": lang_pair}
            
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translated = data.get("responseData", {}).get("translatedText", text)
                    translation_cache[cache_key] = translated
                    return translated
        except Exception as e:
            logger.error(f"翻譯錯誤: {e}")
        
        return text
    
    async with aiohttp.ClientSession() as session:
        # 並行翻譯(但限制並發數避免 rate limit)
        semaphore = asyncio.Semaphore(3)  # 最多同時 3 個請求
        
        async def bounded_translate(text):
            async with semaphore:
                result = await translate_one(session, text)
                await asyncio.sleep(0.3)  # 稍微延遲避免 rate limit
                return result
        
        results = await asyncio.gather(
            *[bounded_translate(text) for text in texts],
            return_exceptions=True
        )
    
    translations = []
    for original, result in zip(texts, results):
        if isinstance(result, Exception):
            translations.append({"original": original, "translated": original, "error": str(result)})
        else:
            translations.append({"original": original, "translated": result})
    
    return {"translations": translations}


# ===== 個股相關 API =====

@app.get("/stocks/search")
async def search_stocks(q: str = Query(..., min_length=1)):
    """搜尋股票(根據代號或名稱)"""
    try:
        import yfinance as yf
        
        # 常見股票列表(方便搜尋)
        common_stocks = {
            # 美股科技
            "AAPL": "Apple Inc.",
            "MSFT": "Microsoft Corporation",
            "GOOGL": "Alphabet Inc. (Google)",
            "AMZN": "Amazon.com Inc.",
            "META": "Meta Platforms Inc.",
            "NVDA": "NVIDIA Corporation",
            "TSLA": "Tesla Inc.",
            "AMD": "Advanced Micro Devices",
            "INTC": "Intel Corporation",
            "NFLX": "Netflix Inc.",
            "ORCL": "Oracle Corporation",
            "CRM": "Salesforce Inc.",
            "ADBE": "Adobe Inc.",
            "PYPL": "PayPal Holdings",
            "UBER": "Uber Technologies",
            # 美股金融
            "JPM": "JPMorgan Chase",
            "BAC": "Bank of America",
            "GS": "Goldman Sachs",
            "V": "Visa Inc.",
            "MA": "Mastercard Inc.",
            "WFC": "Wells Fargo",
            # 美股其他
            "JNJ": "Johnson & Johnson",
            "WMT": "Walmart Inc.",
            "PG": "Procter & Gamble",
            "KO": "Coca-Cola",
            "DIS": "Walt Disney",
            "NKE": "Nike Inc.",
            "MCD": "McDonald's",
            "PFE": "Pfizer Inc.",
            "XOM": "Exxon Mobil",
            "CVX": "Chevron",
            "BA": "Boeing Company",
            "GE": "General Electric",
            # 半導體
            "TSM": "Taiwan Semiconductor",
            "ASML": "ASML Holding",
            "QCOM": "Qualcomm",
            "MU": "Micron Technology",
            "AVGO": "Broadcom Inc.",
            # 電動車
            "NIO": "NIO Inc.",
            "RIVN": "Rivian Automotive",
            "LCID": "Lucid Group",
            "F": "Ford Motor",
            "GM": "General Motors",
            # 港股
            "0700.HK": "騰訊控股",
            "9988.HK": "阿里巴巴",
            "3690.HK": "美團",
            "1810.HK": "小米集團",
            "0005.HK": "匯豐控股",
            "0388.HK": "香港交易所",
            "0939.HK": "建設銀行",
            "1299.HK": "友邦保險",
            "2318.HK": "中國平安",
            "0883.HK": "中國海洋石油",
            # ETF
            "SPY": "SPDR S&P 500 ETF",
            "QQQ": "Invesco QQQ (Nasdaq 100)",
            "VOO": "Vanguard S&P 500",
            "ARKK": "ARK Innovation ETF",
        }
        
        q_upper = q.upper().strip()
        results = []
        
        # 搜尋匹配的股票
        for ticker, name in common_stocks.items():
            if (q_upper in ticker.upper() or 
                q.lower() in name.lower()):
                results.append({
                    "ticker": ticker,
                    "name": name,
                })
                if len(results) >= 10:  # 最多返回 10 個
                    break
        
        # 如果沒有匹配到常見股票,直接返回輸入的代號
        if not results:
            results.append({
                "ticker": q_upper,
                "name": q_upper,
            })
        
        return {"query": q, "results": results}
        
    except Exception as e:
        logger.error(f"搜尋股票失敗: {e}")
        return {"query": q, "results": [], "error": str(e)}


@app.get("/stocks/{ticker}")
async def get_stock_detail(ticker: str):
    """獲取單一股票的詳細資訊"""
    try:
        import yfinance as yf
        
        ticker_upper = ticker.upper().strip()
        stock = yf.Ticker(ticker_upper)
        
        # 獲取基本資訊
        info = stock.info
        
        # 獲取歷史數據(用於計算變化)
        hist = stock.history(period="5d")
        
        if hist.empty:
            return {
                "ticker": ticker_upper,
                "error": "找不到此股票代號",
            }
        
        # 計算當前價格和變化
        current_price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        
        # 今日數據
        today = hist.iloc[-1]
        
        return {
            "ticker": ticker_upper,
            "name": info.get("longName") or info.get("shortName") or ticker_upper,
            "current_price": round(current_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "open": round(float(today["Open"]), 2),
            "high": round(float(today["High"]), 2),
            "low": round(float(today["Low"]), 2),
            "volume": int(today["Volume"]),
            "volume_formatted": format_volume(int(today["Volume"])),
            "prev_close": round(prev_close, 2),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
            "market_cap_formatted": format_market_cap(info.get("marketCap")),
            "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else None,
            "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "exchange": info.get("exchange", "N/A"),
            "website": info.get("website", ""),
            "description": (info.get("longBusinessSummary", "")[:300] + "...") if info.get("longBusinessSummary") else "",
        }
        
    except Exception as e:
        logger.error(f"獲取股票 {ticker} 詳情失敗: {e}")
        return {"ticker": ticker, "error": str(e)}


# ===== 新功能 API =====

@app.get("/market/fear-greed")
async def get_fear_greed_index():
    """計算恐懼貪婪指數 (基於預測結果)"""
    if not state.cached_predictions:
        return {"index": 50, "label": "中性", "color": "#facc15"}
    
    # 計算平均上升機率
    up_probs = [p["up_probability"] for p in state.cached_predictions.values()]
    avg_up = sum(up_probs) / len(up_probs) if up_probs else 0.5
    
    # 轉換為 0-100 指數
    index = int(avg_up * 100)
    
    if index >= 75:
        label = "極度貪婪"
        color = "#22c55e"
        emoji = "🤑"
    elif index >= 55:
        label = "貪婪"
        color = "#84cc16"
        emoji = "😊"
    elif index >= 45:
        label = "中性"
        color = "#facc15"
        emoji = "😐"
    elif index >= 25:
        label = "恐懼"
        color = "#f97316"
        emoji = "😰"
    else:
        label = "極度恐懼"
        color = "#ef4444"
        emoji = "😱"
    
    return {
        "index": index,
        "label": label,
        "color": color,
        "emoji": emoji,
        "description": f"當前市場情緒: {label}",
    }


@app.get("/market/trending")
async def get_trending_stocks():
    """獲取熱門股票 (基於類別預測)"""
    if not state.cached_predictions:
        return {"stocks": []}
    
    trending = []
    
    # 從每個類別選出代表股票
    for sector_key, pred in state.cached_predictions.items():
        sector_info = SECTORS.get(sector_key, {})
        tickers = sector_info.get("tickers", [])[:2]  # 每個類別取 2 隻
        
        for ticker in tickers:
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                hist = stock.history(period="2d")
                
                if not hist.empty and len(hist) >= 2:
                    current = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2])
                    change_pct = ((current - prev) / prev * 100) if prev > 0 else 0
                    
                    trending.append({
                        "ticker": ticker,
                        "sector": sector_info.get("name", sector_key),
                        "price": round(current, 2),
                        "change_pct": round(change_pct, 2),
                        "prediction": pred["direction"],
                        "up_probability": pred["up_probability"],
                    })
            except Exception as e:
                logger.error(f"Failed to fetch trending {ticker}: {e}")
    
    # 按漲幅排序
    trending.sort(key=lambda x: x["change_pct"], reverse=True)
    
    return {
        "gainers": trending[:5],  # 前 5 名漲幅
        "losers": trending[-5:][::-1],  # 前 5 名跌幅
    }


@app.get("/market/hours")
async def get_market_hours():
    """獲取全球主要市場狀態"""
    from datetime import datetime, timezone, timedelta
    
    now_utc = datetime.now(timezone.utc)
    
    markets = [
        {
            "name": "🇺🇸 紐約",
            "code": "NYSE",
            "timezone": -5,  # EST
            "open_hour": 9.5,   # 9:30 AM
            "close_hour": 16,   # 4:00 PM
            "flag": "🇺🇸",
        },
        {
            "name": "🇭🇰 香港",
            "code": "HKEX",
            "timezone": 8,
            "open_hour": 9.5,   # 9:30 AM
            "close_hour": 16,   # 4:00 PM
            "flag": "🇭🇰",
        },
        {
            "name": "🇯🇵 東京",
            "code": "TSE",
            "timezone": 9,
            "open_hour": 9,
            "close_hour": 15,
            "flag": "🇯🇵",
        },
        {
            "name": "🇬🇧 倫敦",
            "code": "LSE",
            "timezone": 0,
            "open_hour": 8,
            "close_hour": 16.5,
            "flag": "🇬🇧",
        },
    ]
    
    result = []
    for market in markets:
        local_time = now_utc + timedelta(hours=market["timezone"])
        local_hour = local_time.hour + local_time.minute / 60
        weekday = local_time.weekday()
        
        # 週末休市
        is_weekend = weekday >= 5
        is_open = (not is_weekend) and (market["open_hour"] <= local_hour < market["close_hour"])
        
        # 計算距離開/關市時間
        if is_open:
            hours_until_close = market["close_hour"] - local_hour
            status = f"⏰ {int(hours_until_close)}小時 {int((hours_until_close % 1) * 60)}分鐘後收市"
        else:
            status = "🔴 休市中" if is_weekend else "⏱️ 未開市"
        
        result.append({
            "name": market["name"],
            "code": market["code"],
            "local_time": local_time.strftime("%H:%M"),
            "is_open": is_open,
            "status": status,
            "flag": market["flag"],
        })
    
    return {"markets": result}


@app.get("/exchange/rate")
async def get_exchange_rate():
    """獲取常用匯率"""
    try:
        import aiohttp
        
        # 使用免費 API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.exchangerate-api.com/v4/latest/USD",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates = data.get("rates", {})
                    return {
                        "base": "USD",
                        "rates": {
                            "HKD": rates.get("HKD", 7.8),
                            "CNY": rates.get("CNY", 7.2),
                            "EUR": rates.get("EUR", 0.92),
                            "JPY": rates.get("JPY", 150),
                            "GBP": rates.get("GBP", 0.79),
                            "TWD": rates.get("TWD", 32),
                        },
                        "updated": data.get("date"),
                    }
    except Exception as e:
        logger.error(f"Exchange rate error: {e}")
    
    # 預設值
    return {
        "base": "USD",
        "rates": {"HKD": 7.8, "CNY": 7.2, "EUR": 0.92, "JPY": 150, "GBP": 0.79, "TWD": 32},
    }


@app.get("/stocks/{ticker}/compare/{ticker2}")
async def compare_stocks(ticker: str, ticker2: str, days: int = 30):
    """比較兩隻股票"""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        results = []
        
        for t in [ticker.upper(), ticker2.upper()]:
            stock = yf.Ticker(t)
            hist = stock.history(period="3mo").tail(days)
            
            if hist.empty:
                continue
            
            # 標準化(第一天 = 100)
            first_price = float(hist["Close"].iloc[0])
            normalized = [(row.Index.strftime("%Y-%m-%d"), 
                          round((float(row.Close) / first_price) * 100, 2))
                         for row in hist.itertuples()]
            
            total_return = ((float(hist["Close"].iloc[-1]) / first_price) - 1) * 100
            
            results.append({
                "ticker": t,
                "data": [{"date": d, "value": v} for d, v in normalized],
                "total_return_pct": round(total_return, 2),
                "current_price": round(float(hist["Close"].iloc[-1]), 2),
            })
        
        return {"comparison": results}
        
    except Exception as e:
        logger.error(f"Compare stocks error: {e}")
        return {"comparison": [], "error": str(e)}



@app.get("/stocks/{ticker}/chart")
async def get_stock_chart(ticker: str, days: int = 30):
    """獲取單一股票的走勢圖數據"""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        ticker_upper = ticker.upper().strip()
        stock = yf.Ticker(ticker_upper)
        
        # 根據天數決定 period
        if days <= 7:
            period = "1mo"
        elif days <= 30:
            period = "3mo"
        elif days <= 90:
            period = "6mo"
        else:
            period = "1y"
        
        hist = stock.history(period=period)
        
        if hist.empty:
            return {"ticker": ticker_upper, "data": [], "error": "no data"}
        
        # 只取最近 N 天
        hist = hist.tail(days)
        
        chart_data = []
        for date, row in hist.iterrows():
            chart_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "value": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "open": round(float(row["Open"]), 2),
            })
        
        # 計算總回報
        if len(chart_data) >= 2:
            total_return = ((chart_data[-1]["value"] / chart_data[0]["value"]) - 1) * 100
        else:
            total_return = 0
        
        return {
            "ticker": ticker_upper,
            "data": chart_data,
            "days": len(chart_data),
            "total_return_pct": round(total_return, 2),
        }
        
    except Exception as e:
        logger.error(f"獲取 {ticker} 走勢失敗: {e}")
        return {"ticker": ticker, "data": [], "error": str(e)}


def format_volume(volume: int) -> str:
    """格式化成交量 (1234567 -> 1.23M)"""
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"{volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"{volume / 1_000:.2f}K"
    return str(volume)


def format_market_cap(cap) -> str:
    """格式化市值"""
    if not cap:
        return "N/A"
    if cap >= 1_000_000_000_000:
        return f"${cap / 1_000_000_000_000:.2f}T"
    elif cap >= 1_000_000_000:
        return f"${cap / 1_000_000_000:.2f}B"
    elif cap >= 1_000_000:
        return f"${cap / 1_000_000:.2f}M"
    return f"${cap:,}"

@app.get("/sectors")
async def get_sectors():
    """獲取所有股票類別"""
    sectors = []
    for key, info in SECTORS.items():
        sectors.append({
            "key": key,
            "name": info["name"],
            "tickers": info["tickers"],
            "stock_count": len(info["tickers"]),
        })
    return {"sectors": sectors, "total": len(sectors)}


@app.get("/sectors/{sector}/chart")
async def get_sector_chart(
    sector: str, 
    days: int = 30,
    include_forecast: bool = True
):
    """
    獲取類別的歷史走勢數據 + 未來預測區間
    
    參數:
        days: 天數 (7, 30, 90, 365)
        include_forecast: 是否包含未來預測區間
    """
    if sector not in SECTORS:
        raise HTTPException(status_code=404, detail=f"未知的類別: {sector}")
    
    try:
        from collections import defaultdict
        import numpy as np
        from datetime import timedelta
        
        # 抓取股票數據(多抓一點以計算指標)
        fetch_days = days + 30
        stock_data = state.stock_fetcher.get_sector_data(sector, days=fetch_days)
        
        if not stock_data:
            return {"sector": sector, "data": [], "error": "no data"}
        
        # 建立日期 → 標準化價格的字典
        price_by_date = defaultdict(list)
        volume_by_date = defaultdict(list)
        
        for ticker, df in stock_data.items():
            if df.empty or len(df) < 2:
                continue
            
            first_price = df["Close"].iloc[0]
            if first_price == 0:
                continue
            
            normalized = (df["Close"] / first_price) * 100
            
            for date, price in zip(df.index, normalized):
                date_str = date.strftime("%Y-%m-%d")
                price_by_date[date_str].append(float(price))
                volume_by_date[date_str].append(float(df.loc[date, "Volume"]))
        
        # 計算每天平均值
        chart_data = []
        for date_str in sorted(price_by_date.keys())[-days:]:
            prices = price_by_date[date_str]
            volumes = volume_by_date[date_str]
            
            if prices:
                chart_data.append({
                    "date": date_str,
                    "value": round(sum(prices) / len(prices), 2),
                    "volume": round(sum(volumes) / len(volumes) / 1_000_000, 2),
                    "type": "historical",  # 標記為歷史數據
                })
        
        # ===== 計算總回報 =====
        if len(chart_data) >= 2:
            total_return = ((chart_data[-1]["value"] / chart_data[0]["value"]) - 1) * 100
        else:
            total_return = 0
        
        # ===== 生成未來預測區間 =====
        forecast_data = []
        if include_forecast and len(chart_data) >= 10:
            # 計算歷史波動率(標準差)
            recent_values = [d["value"] for d in chart_data[-20:]]
            returns = np.diff(recent_values) / recent_values[:-1]
            volatility = np.std(returns)
            
            # 計算趨勢(最近 10 天的平均日回報)
            recent_returns = returns[-10:] if len(returns) >= 10 else returns
            avg_daily_return = np.mean(recent_returns) if len(recent_returns) > 0 else 0
            
            # 取得該類別的預測結果來調整方向
            prediction = state.cached_predictions.get(sector, {})
            up_prob = prediction.get("up_probability", 0.5)
            down_prob = prediction.get("down_probability", 0.3)
            
            # 根據預測機率調整未來趨勢
            direction_bias = (up_prob - down_prob) * 0.005  # 每日偏移
            
            # 生成未來 7 天的預測
            last_date = datetime.strptime(chart_data[-1]["date"], "%Y-%m-%d")
            last_value = chart_data[-1]["value"]
            forecast_days = 7
            
            current_value = last_value
            for i in range(1, forecast_days + 1):
                future_date = last_date + timedelta(days=i)
                # 跳過週末
                while future_date.weekday() >= 5:
                    future_date += timedelta(days=1)
                
                # 中間預測值(考慮趨勢和 AI 預測方向)
                expected_return = avg_daily_return + direction_bias
                current_value = current_value * (1 + expected_return)
                
                # 上下區間(1.5 個標準差,約 87% 信心區間)
                interval_width = volatility * np.sqrt(i) * 1.5 * current_value
                upper = current_value + interval_width
                lower = current_value - interval_width
                
                forecast_data.append({
                    "date": future_date.strftime("%Y-%m-%d"),
                    "value": None,  # 歷史線在這裡結束
                    "forecast": round(current_value, 2),
                    "upper": round(upper, 2),
                    "lower": round(lower, 2),
                    "type": "forecast",
                })
            
            # 讓歷史數據的最後一點也有 forecast 值,讓線連起來
            if chart_data:
                chart_data[-1]["forecast"] = chart_data[-1]["value"]
                chart_data[-1]["upper"] = chart_data[-1]["value"]
                chart_data[-1]["lower"] = chart_data[-1]["value"]
        
        # 合併歷史 + 預測
        all_data = chart_data + forecast_data
        
        return {
            "sector": sector,
            "sector_name": SECTORS[sector]["name"],
            "data": all_data,
            "historical_count": len(chart_data),
            "forecast_count": len(forecast_data),
            "total_return_pct": round(total_return, 2),
            "days": len(chart_data),
        }
        
    except Exception as e:
        logger.error(f"獲取走勢圖失敗 {sector}: {e}")
        import traceback
        traceback.print_exc()
        return {"sector": sector, "data": [], "error": str(e)}



@app.get("/predictions")
async def get_predictions():
    """獲取所有類別的預測結果"""
    if not state.cached_predictions:
        raise HTTPException(
            status_code=503,
            detail="預測數據尚未準備好。請先調用 POST /refresh 或等待系統初始化完成。"
        )
    
    # 按上升機率排序
    predictions = sorted(
        state.cached_predictions.values(),
        key=lambda x: x["up_probability"],
        reverse=True
    )
    
    return {
        "predictions": predictions,
        "total": len(predictions),
        "last_updated": state.last_update.isoformat() if state.last_update else None,
    }


@app.get("/predictions/{sector}")
async def get_sector_prediction(sector: str):
    """獲取特定類別的預測"""
    if sector not in SECTORS:
        raise HTTPException(status_code=404, detail=f"未知的類別: {sector}")
    
    pred = state.cached_predictions.get(sector)
    if not pred:
        raise HTTPException(status_code=503, detail=f"{sector} 的預測尚未準備好")
    
    # 也獲取類別表現
    try:
        performance = state.stock_fetcher.get_sector_performance(sector, 30)
    except:
        performance = {}
    
    return {
        "prediction": pred,
        "performance": performance,
        "tickers": SECTORS[sector]["tickers"],
    }


@app.get("/news")
async def get_news(
    sector: Optional[str] = Query(None, description="按類別篩選"),
    sentiment: Optional[str] = Query(None, description="按情緒篩選: bullish/bearish/neutral"),
    limit: int = Query(50, ge=1, le=200, description="返回數量"),
):
    """獲取新聞及情緒分析結果"""
    news = state.cached_news.copy()
    
    # 篩選
    if sector:
        news = [n for n in news if sector in n.get("sectors", [])]
    if sentiment:
        news = [n for n in news if n.get("sentiment_label") == sentiment]
    
    # 排序（最新的在前）
    news.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    
    return {
        "news": news[:limit],
        "total": len(news),
        "showing": min(limit, len(news)),
    }


@app.get("/dashboard")
async def get_dashboard():
    """獲取儀表板完整數據"""
    if not state.cached_predictions:
        return {
            "status": "initializing",
            "message": "系統正在初始化，請稍候...",
            "is_processing": state.is_processing,
        }
    
    predictions = sorted(
        state.cached_predictions.values(),
        key=lambda x: x["up_probability"],
        reverse=True
    )
    
    # 計算市場概覽
    avg_up = np.mean([p["up_probability"] for p in predictions])
    
    return {
        "status": "ready",
        "predictions": predictions,
        "market_overview": {
            "avg_up_probability": round(avg_up, 4),
            "market_sentiment": (
                "bullish" if avg_up > 0.55
                else "bearish" if avg_up < 0.45
                else "neutral"
            ),
            "sectors_analyzed": len(predictions),
            "most_bullish": predictions[0]["sector_name"] if predictions else "N/A",
            "most_bearish": predictions[-1]["sector_name"] if predictions else "N/A",
            "total_news": len(state.cached_news),
        },
        "last_updated": state.last_update.isoformat() if state.last_update else None,
    }


@app.post("/refresh")
async def refresh_data(background_tasks: BackgroundTasks):
    """手動觸發數據刷新"""
    if state.is_processing:
        return {"message": "已經在處理中，請稍候...", "status": "processing"}
    
    background_tasks.add_task(run_pipeline)
    return {"message": "🚀 數據刷新已啟動！預計需要 2-5 分鐘。", "status": "started"}


# ===== 核心管道 =====

async def run_pipeline():
    """
    完整的數據處理管道
    
    流程：
    1. 抓取新聞
    2. 情緒分析
    3. 抓取股票數據
    4. 訓練模型 & 預測
    """
    if state.is_processing:
        logger.warning("管道已在執行中")
        return
    
    state.is_processing = True
    
    try:
        logger.info("=" * 60)
        logger.info("🚀 開始完整數據處理管道")
        logger.info("=" * 60)
        
        # ===== Step 1: 抓取新聞 =====
        logger.info("\n📰 Step 1: 抓取新聞...")
        
        articles = []
        async with RSSNewsScraper() as scraper:
            rss_articles = await scraper.fetch_all_news(days=30)
            articles.extend(rss_articles)
        
        logger.info(f"   抓取了 {len(articles)} 篇新聞")
        
        if not articles:
            logger.warning("⚠️ 沒有抓取到新聞！使用測試數據...")
            # 如果沒抓到新聞，建立一些測試數據讓系統能運作
            from scraper.news_scraper import NewsArticle
            test_articles = [
                NewsArticle("Tech stocks rally on AI optimism", "Technology companies see gains...", "test", "", datetime.now()),
                NewsArticle("Federal Reserve holds interest rates steady", "The Fed decided to keep rates...", "test", "", datetime.now()),
                NewsArticle("Oil prices decline amid demand concerns", "Crude oil dropped below...", "test", "", datetime.now()),
                NewsArticle("Tesla reports strong Q4 deliveries", "EV maker Tesla delivered...", "test", "", datetime.now()),
                NewsArticle("Healthcare sector benefits from new drug approvals", "FDA approved several...", "test", "", datetime.now()),
            ]
            articles = test_articles
        
        # ===== Step 2: 情緒分析 =====
        logger.info("\n🧠 Step 2: 情緒分析...")
        
        if state.sentiment_analyzer is None:
            state.sentiment_analyzer = SentimentAnalyzer()
        
        analyzed_news = []
        
        for i, article in enumerate(articles):
            try:
                text = f"{article.title}. {article.content}"
                result = state.sentiment_analyzer.analyze(text)
                
                # 計算時間權重（越新的越重要）
                days_ago = (datetime.now() - article.published_at).days
                recency_weight = max(0.1, 1.0 - (days_ago / 30) * 0.5)
                
                analyzed_news.append({
                    "title": article.title,
                    "source": article.source,
                    "url": article.url,
                    "published_at": article.published_at.isoformat(),
                    "sentiment_score": result.score,
                    "sentiment_label": result.label,
                    "confidence": result.confidence,
                    "sectors": result.sectors,
                    "recency_weight": recency_weight,
                })
                
                if (i + 1) % 20 == 0:
                    logger.info(f"   已分析 {i+1}/{len(articles)} 篇")
                    
            except Exception as e:
                logger.error(f"   分析錯誤: {e}")
        
        state.cached_news = analyzed_news
        logger.info(f"   完成分析 {len(analyzed_news)} 篇新聞")
        
        # ===== Step 3: 聚合類別情緒 =====
        logger.info("\n📊 Step 3: 聚合類別情緒...")
        
        sector_sentiments = defaultdict(list)
        
        for news in analyzed_news:
            for sector in news["sectors"]:
                sector_sentiments[sector].append({
                    "score": news["sentiment_score"],
                    "confidence": news["confidence"],
                    "weight": news["recency_weight"],
                })
        
        aggregated = {}
        for sector_key in SECTORS:
            items = sector_sentiments.get(sector_key, [])
            
            if items:
                total_weight = sum(i["weight"] * i["confidence"] for i in items)
                if total_weight > 0:
                    avg_score = sum(
                        i["score"] * i["weight"] * i["confidence"] for i in items
                    ) / total_weight
                else:
                    avg_score = 0
                
                avg_conf = np.mean([i["confidence"] for i in items])
                bullish_count = sum(1 for i in items if i["score"] > 0.15)
                
                aggregated[sector_key] = {
                    "avg_score": round(avg_score, 4),
                    "avg_confidence": round(avg_conf, 4),
                    "count": len(items),
                    "bullish_ratio": round(bullish_count / len(items), 4) if items else 0.5,
                    "recent_score": round(avg_score, 4),  # 簡化
                }
            else:
                aggregated[sector_key] = {
                    "avg_score": 0,
                    "avg_confidence": 0.5,
                    "count": 0,
                    "bullish_ratio": 0.5,
                    "recent_score": 0,
                }
            
            logger.info(f"   {SECTORS[sector_key]['name']}: "
                       f"情緒={aggregated[sector_key]['avg_score']:.3f}, "
                       f"新聞={aggregated[sector_key]['count']}篇")
        
        # ===== Step 4: 預測 =====
        logger.info("\n🔮 Step 4: 訓練模型 & 預測...")
        
        for sector_key, sector_info in SECTORS.items():
            try:
                logger.info(f"\n   --- {sector_info['name']} ---")
                
                # 獲取股票數據
                stock_data = state.stock_fetcher.get_sector_data(sector_key, days=90)
                
                if not stock_data:
                    logger.warning(f"   ⚠️ 沒有股票數據，跳過")
                    continue
                
                # 建立預測器
                predictor = StockPredictor()
                
                # 生成訓練數據
                X, y = predictor.generate_training_data(stock_data)
                
                if len(X) < 15:
                    logger.warning(f"   ⚠️ 訓練數據不足 ({len(X)} 筆)，跳過")
                    continue
                
                # 訓練
                train_results = predictor.train(X, y)
                
                # 準備預測特徵
                features = predictor.create_features(
                    aggregated, stock_data, sector_key
                )
                
                # 預測
                prediction = predictor.predict(
                    features, sector_key, sector_info["name"]
                )
                
                # 保存結果
                state.cached_predictions[sector_key] = {
                    "sector": prediction.sector,
                    "sector_name": prediction.sector_name,
                    "up_probability": prediction.up_probability,
                    "down_probability": prediction.down_probability,
                    "neutral_probability": round(
                        1 - prediction.up_probability - prediction.down_probability, 4
                    ),
                    "direction": prediction.direction,
                    "confidence": prediction.confidence,
                    "key_factors": prediction.key_factors,
                    "news_count": aggregated[sector_key]["count"],
                    "sentiment_score": aggregated[sector_key]["avg_score"],
                    "model_accuracy": train_results["avg_accuracy"],
                    "generated_at": datetime.now().isoformat(),
                }
                
                state.predictors[sector_key] = predictor
                
                # 顯示結果
                dir_emoji = {"UP": "🟢↑", "DOWN": "🔴↓", "NEUTRAL": "🟡→"}
                logger.info(
                    f"   {dir_emoji.get(prediction.direction, '?')} "
                    f"UP={prediction.up_probability:.1%} "
                    f"DOWN={prediction.down_probability:.1%} "
                    f"(信心: {prediction.confidence:.1%})"
                )
                
            except Exception as e:
                logger.error(f"   ❌ {sector_info['name']} 預測失敗: {e}")
                import traceback
                traceback.print_exc()
        
        state.last_update = datetime.now()
        
        logger.info("\n" + "=" * 60)
        logger.info(f"✅ 管道完成！預測了 {len(state.cached_predictions)} 個類別")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 管道執行失敗: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        state.is_processing = False


# ===== 啟動事件 =====

@app.on_event("startup")
async def startup():
    """應用啟動時執行"""
    logger.info("🚀 應用程式啟動！")
    logger.info("正在初始化...")
    
    # 在背景執行管道
    asyncio.create_task(run_pipeline())


# ===== 執行 =====

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)