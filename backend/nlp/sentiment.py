"""
新聞情緒分析模組
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Tuple
from dataclasses import dataclass
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    score: float
    label: str
    confidence: float
    sectors: List[str]


class SentimentAnalyzer:
    """金融新聞情緒分析器"""
    
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
            "arm", "processor",
        ],
    }
    
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
        """初始化 (Render 免費版用輕量模式)"""
        is_render = os.environ.get("RENDER") == "true"
        
        if is_render:
            logger.info("Render environment detected, using lightweight mode")
            self.model_loaded = False
            return
        
        logger.info("Loading FinBERT model...")
        model_name = "ProsusAI/finbert"
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.eval()
            logger.info("FinBERT loaded successfully")
            self.model_loaded = True
        except Exception as e:
            logger.error(f"Model loading failed: {e}")
            self.model_loaded = False
    
    def analyze(self, text: str) -> SentimentResult:
        """分析一段文本的情緒"""
        if self.model_loaded:
            model_score, model_confidence = self._model_analyze(text)
        else:
            model_score, model_confidence = 0, 0.5
        
        rule_score = self._rule_analyze(text)
        
        if self.model_loaded:
            final_score = model_score * 0.7 + rule_score * 0.3
            confidence = model_confidence
        else:
            final_score = rule_score
            confidence = 0.5
        
        if final_score > 0.15:
            label = "bullish"
        elif final_score < -0.15:
            label = "bearish"
        else:
            label = "neutral"
        
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
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.softmax(outputs.logits, dim=1)[0]
            
            positive = probs[0].item()
            negative = probs[1].item()
            neutral = probs[2].item()
            
            score = positive - negative
            confidence = max(positive, negative, neutral)
            
            return score, confidence
            
        except Exception as e:
            logger.error(f"Model analysis error: {e}")
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
        
        sorted_sectors = sorted(
            sector_matches.items(), key=lambda x: x[1], reverse=True
        )
        return [s[0] for s in sorted_sectors[:3]]
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """批量分析"""
        results = []
        for text in texts:
            results.append(self.analyze(text))
        return results