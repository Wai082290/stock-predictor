"""
新聞爬蟲模組
負責從多個來源抓取30天的新聞
"""

import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional
import logging
import os
import sys

# 把 backend 加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===== 數據結構 =====

@dataclass
class NewsArticle:
    """一篇新聞的數據結構"""
    title: str              # 標題
    content: str            # 內容
    source: str             # 來源
    url: str                # 連結
    published_at: datetime  # 發布時間
    category: str = ""      # 分類


# ===== RSS 新聞爬蟲 =====

class RSSNewsScraper:
    """
    RSS 新聞爬蟲
    從多個 RSS 源抓取新聞
    """
    
    # 定義要抓取的 RSS 源
    RSS_FEEDS = {
        # 財經新聞
        "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
        "cnbc_top": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "reuters_business": "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best",
        
        # 科技新聞
        "techcrunch": "https://techcrunch.com/feed/",
        
        # 更多來源（可以自行添加）
        "investing_com": "https://www.investing.com/rss/news.rss",
    }
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """進入 async context manager 時建立 HTTP session"""
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 (compatible; StockBot/1.0)"},
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, *args):
        """離開時關閉 session"""
        if self.session:
            await self.session.close()
    
    async def fetch_all_news(self, days: int = 30) -> List[NewsArticle]:
        """
        抓取所有 RSS 源的新聞
        
        Args:
            days: 抓取最近幾天的新聞
            
        Returns:
            新聞文章列表
        """
        all_articles = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        logger.info(f"📰 開始抓取新聞 (最近 {days} 天)...")
        
        # 同時抓取所有 RSS 源
        tasks = []
        for name, url in self.RSS_FEEDS.items():
            tasks.append(self._fetch_single_feed(name, url, cutoff_date))
        
        # 等待所有任務完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ 抓取失敗: {result}")
                continue
            all_articles.extend(result)
        
        logger.info(f"✅ 總共抓取了 {len(all_articles)} 篇新聞")
        return all_articles
    
    async def _fetch_single_feed(
        self, feed_name: str, feed_url: str, cutoff_date: datetime
    ) -> List[NewsArticle]:
        """抓取單個 RSS 源"""
        articles = []
        
        try:
            async with self.session.get(feed_url) as response:
                if response.status != 200:
                    logger.warning(f"⚠️ {feed_name} 返回狀態碼 {response.status}")
                    return []
                
                content = await response.text()
                feed = feedparser.parse(content)
                
                for entry in feed.entries:
                    # 解析日期
                    published = self._parse_date(entry)
                    
                    # 跳過太舊的新聞
                    if published and published < cutoff_date:
                        continue
                    
                    # 建立文章物件
                    article = NewsArticle(
                        title=entry.get("title", "").strip(),
                        content=entry.get("summary", entry.get("description", "")).strip(),
                        source=feed_name,
                        url=entry.get("link", ""),
                        published_at=published or datetime.now(),
                        category="finance",
                    )
                    
                    # 只保留有標題的文章
                    if article.title:
                        articles.append(article)
                
                logger.info(f"  ✓ {feed_name}: 抓取了 {len(articles)} 篇")
                
        except asyncio.TimeoutError:
            logger.warning(f"⏰ {feed_name} 超時")
        except Exception as e:
            logger.error(f"❌ {feed_name} 錯誤: {e}")
        
        return articles
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """解析 RSS entry 的日期"""
        from time import mktime
        
        for date_field in ["published_parsed", "updated_parsed"]:
            parsed = entry.get(date_field)
            if parsed:
                try:
                    return datetime.fromtimestamp(mktime(parsed))
                except Exception:
                    pass
        return None


# ===== News API 爬蟲 =====

class NewsAPIFetcher:
    """
    使用 News API 抓取新聞
    需要 API Key（免費版每日 100 次）
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch_news(self, days: int = 30) -> List[NewsArticle]:
        """抓取新聞"""
        articles = []
        
        # 搜索關鍵詞
        queries = [
            "stock market",
            "earnings report",
            "tech stocks",
            "Federal Reserve interest rate",
            "oil price energy",
        ]
        
        from_date = (datetime.now() - timedelta(days=min(days, 30))).strftime("%Y-%m-%d")
        
        for query in queries:
            try:
                params = {
                    "q": query,
                    "from": from_date,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 50,
                    "apiKey": self.api_key,
                }
                
                async with self.session.get(
                    f"{self.base_url}/everything", params=params
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        for item in data.get("articles", []):
                            try:
                                pub_date = datetime.fromisoformat(
                                    item["publishedAt"].replace("Z", "+00:00")
                                ).replace(tzinfo=None)
                            except:
                                pub_date = datetime.now()
                            
                            article = NewsArticle(
                                title=item.get("title", ""),
                                content=item.get("description", "") or item.get("content", "") or "",
                                source=item.get("source", {}).get("name", "NewsAPI"),
                                url=item.get("url", ""),
                                published_at=pub_date,
                            )
                            
                            if article.title and "[Removed]" not in article.title:
                                articles.append(article)
                        
                        logger.info(f"  ✓ NewsAPI '{query}': {len(data.get('articles', []))} 篇")
                    
                    elif resp.status == 429:
                        logger.warning("⚠️ NewsAPI 請求次數已達上限")
                        break
                    else:
                        logger.warning(f"⚠️ NewsAPI 返回 {resp.status}")
                
            except Exception as e:
                logger.error(f"❌ NewsAPI 錯誤 (query={query}): {e}")
        
        return articles


# ===== 測試爬蟲 =====

async def test_scraper():
    """測試爬蟲是否正常運作"""
    print("=" * 60)
    print("🧪 測試新聞爬蟲")
    print("=" * 60)
    
    # 測試 RSS 爬蟲
    print("\n--- 測試 RSS 爬蟲 ---")
    async with RSSNewsScraper() as scraper:
        articles = await scraper.fetch_all_news(days=7)  # 先試 7 天
    
    print(f"\n📊 RSS 結果: {len(articles)} 篇新聞")
    
    # 顯示前 5 篇
    for i, article in enumerate(articles[:5]):
        print(f"\n  [{i+1}] {article.title[:80]}...")
        print(f"      來源: {article.source}")
        print(f"      時間: {article.published_at}")
    
    return articles


# 如果直接執行此檔案就進行測試
if __name__ == "__main__":
    asyncio.run(test_scraper())