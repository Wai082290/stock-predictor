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