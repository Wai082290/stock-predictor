"""
股票預測模型
結合新聞情緒和技術指標來預測股票升跌機率
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import joblib
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """預測結果"""
    sector: str             # 類別代碼
    sector_name: str        # 類別名稱
    up_probability: float   # 上升機率 (0-1)
    down_probability: float # 下跌機率 (0-1)
    direction: str          # "UP", "DOWN", "NEUTRAL"
    confidence: float       # 信心度 (0-1)
    key_factors: List[Dict] # 關鍵影響因素
    generated_at: datetime = field(default_factory=datetime.now)


class StockPredictor:
    """
    股票升跌預測器
    
    使用 Random Forest + Gradient Boosting 集成模型
    輸入: 新聞情緒 + 技術指標
    輸出: 升/跌/持平 的機率
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.model = None
        self.is_trained = False
        self.feature_names = []
        
        self._build_model()
    
    def _build_model(self):
        """建構模型"""
        # 使用 Random Forest（比較穩定，適合初始版本）
        self.model = RandomForestClassifier(
            n_estimators=200,      # 200 棵決策樹
            max_depth=8,           # 每棵樹最大深度
            min_samples_split=10,  # 分裂所需最少樣本
            min_samples_leaf=5,    # 葉節點最少樣本
            random_state=42,       # 固定隨機種子（可重複）
            n_jobs=-1,             # 使用所有 CPU 核心
        )
    
    def create_features(
        self,
        sentiment_data: Dict,
        stock_data: Dict[str, pd.DataFrame],
        sector_key: str,
    ) -> pd.DataFrame:
        """
        建立預測特徵
        
        Args:
            sentiment_data: 情緒分析結果
            stock_data: 股票歷史數據
            sector_key: 類別代碼
            
        Returns:
            特徵 DataFrame
        """
        features = {}
        
        # ===== 1. 新聞情緒特徵 =====
        sector_sent = sentiment_data.get(sector_key, {})
        features["sentiment_score"] = sector_sent.get("avg_score", 0)
        features["sentiment_confidence"] = sector_sent.get("avg_confidence", 0.5)
        features["news_count"] = sector_sent.get("count", 0)
        features["bullish_ratio"] = sector_sent.get("bullish_ratio", 0.5)
        
        # 最近7天 vs 更早的情緒變化
        features["sentiment_7d"] = sector_sent.get("recent_score", 0)
        features["sentiment_change"] = (
            features["sentiment_7d"] - features["sentiment_score"]
        )
        
        # ===== 2. 股票技術指標特徵 =====
        if stock_data:
            dfs = [df for df in stock_data.values() if len(df) > 20]
            
            if dfs:
                # 平均回報率
                features["return_5d"] = np.mean([
                    df["returns"].tail(5).mean() for df in dfs
                ])
                features["return_20d"] = np.mean([
                    df["returns"].tail(20).mean() for df in dfs
                ])
                
                # 動量（短期 vs 長期）
                features["momentum"] = features["return_5d"] - features["return_20d"]
                
                # 波動率
                features["volatility"] = np.mean([
                    df["returns"].std() for df in dfs
                ])
                
                # RSI 平均值
                rsi_values = []
                for df in dfs:
                    if "rsi" in df.columns:
                        last_rsi = df["rsi"].iloc[-1]
                        if not pd.isna(last_rsi):
                            rsi_values.append(last_rsi)
                
                features["avg_rsi"] = np.mean(rsi_values) if rsi_values else 50
                features["rsi_overbought"] = 1.0 if features["avg_rsi"] > 70 else 0.0
                features["rsi_oversold"] = 1.0 if features["avg_rsi"] < 30 else 0.0
                
                # 移動平均線信號
                ma_signals = []
                for df in dfs:
                    if "ma_5" in df and "ma_20" in df:
                        ma5 = df["ma_5"].iloc[-1]
                        ma20 = df["ma_20"].iloc[-1]
                        if not pd.isna(ma5) and not pd.isna(ma20):
                            ma_signals.append(1.0 if ma5 > ma20 else -1.0)
                
                features["ma_signal"] = np.mean(ma_signals) if ma_signals else 0
                
                # 成交量變化
                vol_ratios = []
                for df in dfs:
                    recent_vol = df["Volume"].tail(5).mean()
                    avg_vol = df["Volume"].tail(20).mean()
                    if avg_vol > 0:
                        vol_ratios.append(recent_vol / avg_vol)
                
                features["volume_ratio"] = np.mean(vol_ratios) if vol_ratios else 1.0
            else:
                # 沒有足夠數據時的預設值
                for key in ["return_5d", "return_20d", "momentum", "volatility",
                           "avg_rsi", "rsi_overbought", "rsi_oversold",
                           "ma_signal", "volume_ratio"]:
                    features[key] = 0.0
                features["avg_rsi"] = 50.0
                features["volume_ratio"] = 1.0
        
        # ===== 3. 時間特徵 =====
        now = datetime.now()
        features["day_of_week"] = now.weekday()
        features["month"] = now.month
        
        # 保存特徵名稱
        self.feature_names = list(features.keys())
        
        return pd.DataFrame([features])
    
    def generate_training_data(
        self,
        stock_data: Dict[str, pd.DataFrame],
        base_sentiment: float = 0,
        n_samples: int = 200,
    ) -> tuple:
        """
        生成訓練數據
        
        用歷史股價數據的滑動窗口來生成訓練樣本
        
        Returns:
            (X, y) - 特徵矩陣和標籤
        """
        X_list = []
        y_list = []
        
        dfs = [df for df in stock_data.values() if len(df) > 30]
        if not dfs:
            raise ValueError("沒有足夠的歷史數據來訓練模型")
        
        ref_df = dfs[0]
        max_i = min(len(ref_df) - 6, n_samples + 30)
        
        for i in range(25, max_i):
            features = {}
            
            # 模擬情緒（用價格趨勢作為代理）
            recent_returns = np.mean([
                df["returns"].iloc[max(0,i-5):i].mean()
                for df in dfs if len(df) > i
            ])
            
            features["sentiment_score"] = recent_returns * 10 + np.random.normal(0, 0.1)
            features["sentiment_confidence"] = 0.5 + np.random.uniform(0, 0.3)
            features["news_count"] = np.random.randint(5, 50)
            features["bullish_ratio"] = 0.5 + features["sentiment_score"] * 0.3
            features["sentiment_7d"] = features["sentiment_score"] + np.random.normal(0, 0.05)
            features["sentiment_change"] = np.random.normal(0, 0.1)
            
            # 真實技術指標
            features["return_5d"] = np.mean([
                df["returns"].iloc[max(0,i-5):i].mean()
                for df in dfs if len(df) > i
            ])
            features["return_20d"] = np.mean([
                df["returns"].iloc[max(0,i-20):i].mean()
                for df in dfs if len(df) > i
            ])
            features["momentum"] = features["return_5d"] - features["return_20d"]
            features["volatility"] = np.mean([
                df["returns"].iloc[max(0,i-20):i].std()
                for df in dfs if len(df) > i
            ])
            
            # RSI
            rsi_vals = []
            for df in dfs:
                if "rsi" in df.columns and len(df) > i:
                    r = df["rsi"].iloc[i]
                    if not pd.isna(r):
                        rsi_vals.append(r)
            features["avg_rsi"] = np.mean(rsi_vals) if rsi_vals else 50
            features["rsi_overbought"] = 1.0 if features["avg_rsi"] > 70 else 0.0
            features["rsi_oversold"] = 1.0 if features["avg_rsi"] < 30 else 0.0
            
            features["ma_signal"] = 1.0 if features["return_5d"] > features["return_20d"] else -1.0
            features["volume_ratio"] = 1.0 + np.random.normal(0, 0.2)
            
            features["day_of_week"] = ref_df.index[i].weekday() if i < len(ref_df) else 0
            features["month"] = ref_df.index[i].month if i < len(ref_df) else 1
            
            X_list.append(features)
            
            # 計算標籤：未來 5 天的回報
            future_returns = []
            for df in dfs:
                if len(df) > i + 5:
                    fr = (df["Close"].iloc[i+5] / df["Close"].iloc[i]) - 1
                    future_returns.append(fr)
            
            if future_returns:
                avg_future = np.mean(future_returns)
                if avg_future > 0.01:      # > 1% → UP
                    y_list.append(2)
                elif avg_future < -0.01:   # < -1% → DOWN
                    y_list.append(0)
                else:                       # 持平
                    y_list.append(1)
            else:
                y_list.append(1)
        
        X = pd.DataFrame(X_list)
        y = pd.Series(y_list)
        
        self.feature_names = list(X.columns)
        
        return X, y
    
    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """
        訓練模型
        
        使用時間序列交叉驗證來評估模型表現
        """
        logger.info(f"🏋️ 開始訓練模型... (樣本數: {len(X)})")
        
        # 時間序列交叉驗證
        tscv = TimeSeriesSplit(n_splits=3)
        scores = []
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train = X.iloc[train_idx]
            X_val = X.iloc[val_idx]
            y_train = y.iloc[train_idx]
            y_val = y.iloc[val_idx]
            
            # 標準化
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
            
            # 訓練
            self.model.fit(X_train_scaled, y_train)
            
            # 驗證
            y_pred = self.model.predict(X_val_scaled)
            score = accuracy_score(y_val, y_pred)
            scores.append(score)
            logger.info(f"  Fold {fold+1}: 準確率 = {score:.3f}")
        
        # 最終用全部數據訓練
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        
        avg_score = np.mean(scores)
        logger.info(f"✅ 訓練完成！平均準確率: {avg_score:.3f}")
        
        return {
            "fold_scores": [round(s, 4) for s in scores],
            "avg_accuracy": round(avg_score, 4),
        }
    
    def predict(
        self,
        features: pd.DataFrame,
        sector_key: str,
        sector_name: str,
    ) -> PredictionResult:
        """
        進行預測
        
        Returns:
            PredictionResult 物件
        """
        if not self.is_trained:
            raise RuntimeError("模型尚未訓練！請先呼叫 train()")
        
        # 標準化特徵
        X_scaled = self.scaler.transform(features)
        
        # 預測機率
        probs = self.model.predict_proba(X_scaled)[0]
        
        # probs 可能是 [DOWN, NEUTRAL, UP] 或 [DOWN, UP]
        if len(probs) == 3:
            down_prob = probs[0]
            neutral_prob = probs[1]
            up_prob = probs[2]
        elif len(probs) == 2:
            down_prob = probs[0]
            up_prob = probs[1]
            neutral_prob = 0
        else:
            down_prob = up_prob = neutral_prob = 1/3
        
        # 判斷方向
        max_prob = max(down_prob, neutral_prob, up_prob)
        if max_prob == up_prob:
            direction = "UP"
        elif max_prob == down_prob:
            direction = "DOWN"
        else:
            direction = "NEUTRAL"
        
        # 分析關鍵因素
        key_factors = self._get_key_factors(features)
        
        return PredictionResult(
            sector=sector_key,
            sector_name=sector_name,
            up_probability=round(float(up_prob), 4),
            down_probability=round(float(down_prob), 4),
            direction=direction,
            confidence=round(float(max_prob), 4),
            key_factors=key_factors,
        )
    
    def _get_key_factors(self, features: pd.DataFrame) -> List[Dict]:
        """分析影響預測的關鍵因素"""
        factors = []
        row = features.iloc[0]
        
        # 情緒
        sent = row.get("sentiment_score", 0)
        if abs(sent) > 0.05:
            factors.append({
                "factor": "📰 新聞情緒",
                "value": f"{'正面' if sent > 0 else '負面'} ({sent:.3f})",
                "impact": "positive" if sent > 0 else "negative",
            })
        
        # 動量
        mom = row.get("momentum", 0)
        if abs(mom) > 0.002:
            factors.append({
                "factor": "📈 價格動量",
                "value": f"{'上升趨勢' if mom > 0 else '下降趨勢'} ({mom*100:.2f}%)",
                "impact": "positive" if mom > 0 else "negative",
            })
        
        # RSI
        rsi = row.get("avg_rsi", 50)
        if rsi > 70:
            factors.append({
                "factor": "⚠️ RSI 超買",
                "value": f"RSI = {rsi:.1f} (可能回調)",
                "impact": "negative",
            })
        elif rsi < 30:
            factors.append({
                "factor": "💡 RSI 超賣",
                "value": f"RSI = {rsi:.1f} (可能反彈)",
                "impact": "positive",
            })
        
        # 成交量
        vol = row.get("volume_ratio", 1)
        if vol > 1.3:
            factors.append({
                "factor": "📊 成交量放大",
                "value": f"{vol:.2f}x 平均量",
                "impact": "neutral",
            })
        
        # 移動平均線
        ma = row.get("ma_signal", 0)
        if ma != 0:
            factors.append({
                "factor": "📉 移動平均線",
                "value": f"{'黃金交叉 (看漲)' if ma > 0 else '死亡交叉 (看跌)'}",
                "impact": "positive" if ma > 0 else "negative",
            })
        
        return factors
    
    def save(self, path: str):
        """保存模型"""
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
        }, path)
        logger.info(f"💾 模型已保存到 {path}")
    
    def load(self, path: str):
        """載入模型"""
        data = joblib.load(path)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.feature_names = data["feature_names"]
        self.is_trained = True
        logger.info(f"📂 模型已從 {path} 載入")


# ===== 測試 =====

def test_predictor():
    """測試預測模型"""
    print("=" * 60)
    print("🧪 測試預測模型")
    print("=" * 60)
    
    from scraper.stock_data import StockDataFetcher, SECTORS
    
    fetcher = StockDataFetcher()
    predictor = StockPredictor()
    
    # 測試科技股
    sector = "technology"
    print(f"\n--- 訓練 {SECTORS[sector]['name']} 預測模型 ---")
    
    # 1. 獲取數據
    stock_data = fetcher.get_sector_data(sector, days=90)
    
    if not stock_data:
        print("❌ 沒有股票數據，無法訓練")
        return
    
    # 2. 生成訓練數據
    print("\n📊 生成訓練數據...")
    X, y = predictor.generate_training_data(stock_data)
    print(f"   訓練樣本: {len(X)}")
    print(f"   標籤分佈: UP={sum(y==2)}, NEUTRAL={sum(y==1)}, DOWN={sum(y==0)}")
    
    # 3. 訓練
    results = predictor.train(X, y)
    print(f"   平均準確率: {results['avg_accuracy']:.1%}")
    
    # 4. 預測
    print(f"\n🔮 進行預測...")
    
    # 模擬情緒數據
    sentiment_data = {
        sector: {
            "avg_score": 0.3,
            "avg_confidence": 0.7,
            "count": 25,
            "bullish_ratio": 0.6,
            "recent_score": 0.4,
        }
    }
    
    features = predictor.create_features(sentiment_data, stock_data, sector)
    prediction = predictor.predict(features, sector, SECTORS[sector]["name"])
    
    # 5. 顯示結果
    print(f"\n{'='*40}")
    print(f"  {prediction.sector_name} 預測結果")
    print(f"{'='*40}")
    
    # 方向 emoji
    if prediction.direction == "UP":
        dir_emoji = "🟢 ↑"
    elif prediction.direction == "DOWN":
        dir_emoji = "🔴 ↓"
    else:
        dir_emoji = "🟡 →"
    
    print(f"  預測方向: {dir_emoji} {prediction.direction}")
    print(f"  上升機率: {prediction.up_probability:.1%}")
    print(f"  下跌機率: {prediction.down_probability:.1%}")
    print(f"  信心度:   {prediction.confidence:.1%}")
    
    if prediction.key_factors:
        print(f"\n  關鍵因素:")
        for factor in prediction.key_factors:
            print(f"    {factor['factor']}: {factor['value']}")


if __name__ == "__main__":
    test_predictor()