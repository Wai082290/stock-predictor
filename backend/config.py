import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

class Settings:
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    
    # 股票類別定義
    STOCK_SECTORS = {
        "technology": {
            "name": "科技股",
            "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
            "keywords": [
                "tech", "software", "AI", "artificial intelligence",
                "cloud", "Apple", "Microsoft", "Google", "Amazon",
                "Meta", "NVIDIA", "semiconductor", "chip"
            ]
        },
        "finance": {
            "name": "金融股",
            "tickers": ["JPM", "BAC", "GS", "V", "MA"],
            "keywords": [
                "bank", "banking", "interest rate", "Fed",
                "Federal Reserve", "loan", "credit", "JPMorgan",
                "Goldman", "Wall Street", "monetary"
            ]
        },
        "healthcare": {
            "name": "醫療股",
            "tickers": ["JNJ", "UNH", "PFE", "ABBV", "LLY"],
            "keywords": [
                "pharma", "drug", "FDA", "clinical trial",
                "biotech", "vaccine", "hospital", "medical",
                "healthcare", "Pfizer"
            ]
        },
        "energy": {
            "name": "能源股",
            "tickers": ["XOM", "CVX", "COP", "SLB"],
            "keywords": [
                "oil", "gas", "petroleum", "OPEC", "crude",
                "energy", "renewable", "solar", "Exxon"
            ]
        },
        "consumer": {
            "name": "消費股",
            "tickers": ["PG", "KO", "WMT", "COST", "NKE"],
            "keywords": [
                "retail", "consumer", "spending", "e-commerce",
                "Walmart", "Nike", "Coca-Cola", "brand"
            ]
        },
        "ev_clean_energy": {
            "name": "電動車/新能源",
            "tickers": ["TSLA", "NIO", "RIVN", "ENPH"],
            "keywords": [
                "electric vehicle", "EV", "Tesla", "battery",
                "lithium", "charging", "solar", "clean energy"
            ]
        },
    }

settings = Settings()