"""
新聞情緒分析模組
使用 FinBERT 模型分析金融新聞的正面/負面情緒
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Tuple
from dataclasses import dataclass
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """情緒分析結果"""
    score: float        # -1.0 (極度看跌) 到 1.0 (極度看漲)
    label: str          # "bullish", "bearish", "neutral"
    confidence: float   # 信心度 0-1
    sectors: List[str]  # 相關的股票類別


class SentimentAnalyzer:
    """
    金融新聞情緒分析器
    
    使用 FinBERT 模型 - 專門針對金融文本訓練
    """
    
    # 類別關鍵詞（用來判斷新聞和哪個類別相關）
    SECTOR_KEYWORDS = {
        "technology": [
            "tech", "software", "AI", "artificial intelligence",
            "cloud", "apple", "microsoft", "google", "amazon",
            "meta", "nvidia", "semiconductor", "chip", "gpu",
            "data center", "saas", "platform", "digital",
        ],
        "finance": [
            "bank", "banking", "interest rate", "fed",
            "federal reserve", "loan", "credit", "jpmorgan",
            "goldman", "wall street", "monetary", "inflation",
            "treasury", "bond", "yield",
        ],
        "healthcare": [
            "pharma", "drug", "fda", "clinical trial",
            "biotech", "vaccine", "hospital", "medical",
            "healthcare", "pfizer", "patient", "treatment",
        ],
        "energy": [
            "oil", "gas", "petroleum", "opec", "crude",
            "energy", "renewable", "solar", "exxon", "chevron",
            "drilling", "barrel", "pipeline",
        ],
        "consumer": [
            "retail", "consumer", "spending", "e-commerce",
            "walmart", "nike", "coca-cola", "brand", "store",
            "shopping", "grocery",
        ],
                "ev_clean_energy": [
            "electric vehicle", "ev", "tesla", "battery",
            "lithium", "charging", "autonomous", "solar panel",
            "clean energy", "nio", "rivian",
        ],
        "semiconductor": [
            "semiconductor", "chip", "chipmaker", "wafer", "foundry",
            "nvidia", "amd", "intel", "tsmc", "asml", "qualcomm",
            "micron", "gpu", "cpu", "silicon", "fab", "lithography",
            "arm", "processor", "moore's law",
        ],
    }
    
    # 額外的金融情緒詞彙（加強分析）
    BULLISH_WORDS = [
        "surge", "soar", "rally", "boom", "breakout", "upgrade",
        "beat", "record high", "strong growth", "outperform",
        "bullish", "upside", "recovery", "expansion", "profit",
        "revenue growth", "positive",
    ]
    
    BEARISH_WORDS = [
        "crash", "plunge", "decline", "downturn", "recession",
        "downgrade", "miss", "layoff", "bankruptcy", "bearish",
        "downside", "sell-off", "correction", "loss", "debt",
        "negative", "warning", "risk",
    ]
    
    def __init__(self):
        """初始化模型（第一次會自動下載，約 400MB）"""
        logger.info("🤖 載入 FinBERT 模型...")
        
        model_name = "ProsusAI/finbert"
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.eval()  # 設為評估模式
            logger.info("✅ FinBERT 模型載入成功！")
            self.model_loaded = True
        except Exception as e:
            logger.error(f"❌ 模型載入失敗: {e}")
            logger.info("將使用規則基礎的情緒分析作為替代")
            self.model_loaded = False
    
    def analyze(self, text: str) -> SentimentResult:
        """
        分析一段文本的情緒
        
        Args:
            text: 要分析的文本（通常是新聞標題 + 內容）
            
        Returns:
            SentimentResult 物件
        """
        # 1. 模型分析
        if self.model_loaded:
            model_score, model_confidence = self._model_analyze(text)
        else:
            model_score, model_confidence = 0, 0.5
        
        # 2. 規則分析
        rule_score = self._rule_analyze(text)
        
        # 3. 綜合評分（模型 70% + 規則 30%）
        if self.model_loaded:
            final_score = model_score * 0.7 + rule_score * 0.3
            confidence = model_confidence
        else:
            final_score = rule_score
            confidence = 0.5
        
        # 4. 判斷標籤
        if final_score > 0.15:
            label = "bullish"
        elif final_score < -0.15:
            label = "bearish"
        else:
            label = "neutral"
        
        # 5. 找出相關類別
        sectors = self._find_sectors(text)
        
        return SentimentResult(
            score=round(final_score, 4),
            label=label,
            confidence=round(confidence, 4),
            sectors=sectors,
        )
    
    def _model_analyze(self, text: str) -> Tuple[float, float]:
        """使用 FinBERT 模型分析"""
        try:
            # 將文字轉為模型可以處理的格式
            inputs = self.tokenizer(
                text,
                return_tensors="pt",     # 返回 PyTorch tensor
                truncation=True,         # 超過長度就截斷
                max_length=512,          # 最大 512 個 token
                padding=True,
            )
            
            # 預測
            with torch.no_grad():  # 不需要計算梯度
                outputs = self.model(**inputs)
                probs = torch.softmax(outputs.logits, dim=1)[0]
            
            # FinBERT 輸出: [positive, negative, neutral]
            positive = probs[0].item()
            negative = probs[1].item()
            neutral = probs[2].item()
            
            # 轉換為 -1 到 1 的分數
            score = positive - negative
            confidence = max(positive, negative, neutral)
            
            return score, confidence
            
        except Exception as e:
            logger.error(f"模型分析錯誤: {e}")
            return 0, 0.5
    
    def _rule_analyze(self, text: str) -> float:
        """基於規則的情緒分析"""
        text_lower = text.lower()
        
        bullish = sum(1 for word in self.BULLISH_WORDS if word in text_lower)
        bearish = sum(1 for word in self.BEARISH_WORDS if word in text_lower)
        
        total = bullish + bearish
        if total == 0:
            return 0.0
        
        return (bullish - bearish) / total
    
    def _find_sectors(self, text: str) -> List[str]:
        """找出新聞相關的股票類別"""
        text_lower = text.lower()
        sector_matches = {}
        
        for sector, keywords in self.SECTOR_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > 0:
                sector_matches[sector] = count
        
        # 返回匹配最多的前3個類別
        sorted_sectors = sorted(
            sector_matches.items(), key=lambda x: x[1], reverse=True
        )
        return [s[0] for s in sorted_sectors[:3]]
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """批量分析多段文本"""
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            if (i + 1) % 50 == 0:
                logger.info(f"  分析進度: {i+1}/{total}")
            results.append(self.analyze(text))
        
        return results


# ===== 測試 =====

def test_sentiment():
    """測試情緒分析"""
    print("=" * 60)
    print("🧪 測試情緒分析器")
    print("=" * 60)
    
    # 建立分析器
    analyzer = SentimentAnalyzer()
    
    # 測試文本
    test_texts = [
        "Apple stock surges 5% after reporting record iPhone sales and strong revenue growth",
        "Major bank stocks plunge as Federal Reserve warns of potential recession risks",
        "Tesla announces new battery technology, EV market expected to expand rapidly",
        "Oil prices crash below $60 as OPEC fails to reach production agreement",
        "Tech sector remains stable despite mixed earnings reports from major companies",
        "NVIDIA shares soar to all-time high on AI chip demand boom",
        "Healthcare stocks decline after FDA rejects key drug application from Pfizer",
    ]
    
    print("\n--- 分析結果 ---\n")
    
    for text in test_texts:
        result = analyzer.analyze(text)
        
        # 用 emoji 表示方向
        if result.label == "bullish":
            emoji = "🟢"
        elif result.label == "bearish":
            emoji = "🔴"
        else:
            emoji = "🟡"
        
        print(f"{emoji} [{result.label:>7}] (分數: {result.score:+.3f}, "
              f"信心: {result.confidence:.2f})")
        print(f"   文本: {text[:70]}...")
        if result.sectors:
            print(f"   相關類別: {', '.join(result.sectors)}")
        print()


if __name__ == "__main__":
    test_sentiment()