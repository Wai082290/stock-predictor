"""
股票數據抓取器
使用 yfinance 獲取歷史股價
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 股票類別定義
SECTORS = {
    "technology": {
        "name": "科技股",
        "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    },
    "finance": {
        "name": "金融股",
        "tickers": ["JPM", "BAC", "GS", "V", "MA"],
    },
    "healthcare": {
        "name": "醫療股",
        "tickers": ["JNJ", "UNH", "PFE", "ABBV", "LLY"],
    },
    "energy": {
        "name": "能源股",
        "tickers": ["XOM", "CVX", "COP", "SLB"],
    },
    "consumer": {
        "name": "消費股",
        "tickers": ["PG", "KO", "WMT", "COST", "NKE"],
    },
    "ev_clean_energy": {
        "name": "電動車/新能源",
        "tickers": ["TSLA", "NIO", "RIVN", "ENPH"],
    },
    "semiconductor": {
        "name": "半導體",
        "tickers": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM", "MU", "ASML"],
    },
}

class StockDataFetcher:
    """股票數據抓取器"""
    
    def get_sector_data(
        self, sector_key: str, days: int = 90
    ) -> Dict[str, pd.DataFrame]:
        """
        抓取某個類別所有股票的歷史數據
        
        Args:
            sector_key: 類別代碼 (如 "technology")
            days: 抓取多少天的數據
            
        Returns:
            {ticker: DataFrame} 的字典
        """
        sector = SECTORS.get(sector_key)
        if not sector:
            logger.error(f"未知的類別: {sector_key}")
            return {}
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        result = {}
        
        logger.info(f"📈 抓取 {sector['name']} 的股票數據...")
        
        for ticker in sector["tickers"]:
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(start=start_date, end=end_date)
                
                if df.empty:
                    logger.warning(f"  ⚠️ {ticker}: 沒有數據")
                    continue
                
                # 計算技術指標
                df["returns"] = df["Close"].pct_change()       # 每日回報率
                df["ma_5"] = df["Close"].rolling(5).mean()      # 5日移動平均
                df["ma_20"] = df["Close"].rolling(20).mean()    # 20日移動平均
                df["volatility"] = df["returns"].rolling(5).std()  # 波動率
                df["volume_ma"] = df["Volume"].rolling(5).mean()   # 成交量均線
                
                # 計算 RSI
                delta = df["Close"].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                df["rsi"] = 100 - (100 / (1 + rs))
                
                result[ticker] = df
                logger.info(f"  ✓ {ticker}: {len(df)} 天的數據")
                
            except Exception as e:
                logger.error(f"  ❌ {ticker}: {e}")
        
        return result
    
    def get_sector_performance(self, sector_key: str, days: int = 30) -> Dict:
        """
        計算類別整體表現
        
        Returns:
            包含類別表現摘要的字典
        """
        data = self.get_sector_data(sector_key, days + 10)  # 多抓幾天確保夠用
        sector = SECTORS.get(sector_key, {})
        
        if not data:
            return {"sector": sector_key, "error": "no data"}
        
        performances = []
        
        for ticker, df in data.items():
            if len(df) < 2:
                continue
            
            # 計算指標
            total_return = (df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1
            volatility = df["returns"].std() if "returns" in df else 0
            last_price = df["Close"].iloc[-1]
            last_rsi = df["rsi"].iloc[-1] if "rsi" in df and not pd.isna(df["rsi"].iloc[-1]) else 50
            
            performances.append({
                "ticker": ticker,
                "last_price": round(last_price, 2),
                "total_return": round(total_return * 100, 2),  # 百分比
                "volatility": round(volatility * 100, 2),
                "rsi": round(last_rsi, 1),
            })
        
        if not performances:
            return {"sector": sector_key, "error": "no valid data"}
        
        avg_return = sum(p["total_return"] for p in performances) / len(performances)
        
        return {
            "sector": sector_key,
            "sector_name": sector.get("name", sector_key),
            "avg_return_pct": round(avg_return, 2),
            "stocks": performances,
            "bullish_count": sum(1 for p in performances if p["total_return"] > 0),
            "bearish_count": sum(1 for p in performances if p["total_return"] <= 0),
        }


# ===== 測試 =====

def test_stock_data():
    """測試股票數據抓取"""
    print("=" * 60)
    print("🧪 測試股票數據抓取")
    print("=" * 60)
    
    fetcher = StockDataFetcher()
    
    # 測試科技股
    print("\n--- 科技股 30 天表現 ---")
    perf = fetcher.get_sector_performance("technology", days=30)
    
    print(f"\n📊 {perf.get('sector_name', 'N/A')} 摘要:")
    print(f"   平均回報: {perf.get('avg_return_pct', 0)}%")
    print(f"   上漲股票: {perf.get('bullish_count', 0)}")
    print(f"   下跌股票: {perf.get('bearish_count', 0)}")
    
    if "stocks" in perf:
        print(f"\n   個股表現:")
        for stock in perf["stocks"]:
            arrow = "↑" if stock["total_return"] > 0 else "↓"
            print(f"   {arrow} {stock['ticker']}: "
                  f"${stock['last_price']} "
                  f"({'+' if stock['total_return'] > 0 else ''}{stock['total_return']}%) "
                  f"RSI={stock['rsi']}")


if __name__ == "__main__":
    test_stock_data()