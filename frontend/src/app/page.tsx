'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw,
  BarChart3, Newspaper, Activity, AlertTriangle,
  ArrowUpRight, ArrowDownRight, Clock, Search, X
} from 'lucide-react';
import {
  ResponsiveContainer, Tooltip, XAxis, YAxis,
  Area, AreaChart, ComposedChart, Line, ReferenceLine
} from 'recharts';

interface KeyFactor { factor: string; value: string; impact: string; }
interface Prediction {
  sector: string; sector_name: string;
  up_probability: number; down_probability: number; neutral_probability: number;
  direction: string; confidence: number;
  key_factors: KeyFactor[]; news_count: number;
  sentiment_score: number; model_accuracy: number; generated_at: string;
}
interface ChartDataPoint {
  date: string; value?: number | null;
  forecast?: number | null; upper?: number | null; lower?: number | null;
  type?: string; volume?: number;
}
interface ChartData {
  sector: string; sector_name: string;
  data: ChartDataPoint[]; total_return_pct: number;
  historical_count: number; forecast_count: number;
}
interface NewsItem {
  title: string; source: string; url: string;
  published_at: string; sentiment_score: number;
  sentiment_label: string; sectors: string[];
}
interface DashboardData {
  status: string; predictions: Prediction[];
  market_overview: any; last_updated: string;
}
interface StockSearchResult { ticker: string; name: string; }
interface StockDetail {
  ticker: string; name: string;
  current_price: number; change: number; change_pct: number;
  open: number; high: number; low: number;
  volume: number; volume_formatted: string;
  prev_close: number; currency: string;
  market_cap_formatted: string; pe_ratio: number | null;
  dividend_yield: number | null;
  week_52_high: number; week_52_low: number;
  sector: string; industry: string; exchange: string;
  description: string;
  error?: string;
}
interface StockChart {
  ticker: string; data: any[]; total_return_pct: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TIME_RANGES = [
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '1年', value: 365 },
];

// ===== 股票搜尋組件 =====
function StockSearch() {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<StockSearchResult[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedStock, setSelectedStock] = useState<StockDetail | null>(null);
  const [stockChart, setStockChart] = useState<StockChart | null>(null);
  const [loading, setLoading] = useState(false);
  const [chartDays, setChartDays] = useState(30);

  // 搜尋建議
  useEffect(() => {
    if (query.length < 1) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => {
      fetch(`${API_URL}/stocks/search?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
          setSuggestions(data.results || []);
          setShowSuggestions(true);
        })
        .catch(err => console.error(err));
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  // 選擇股票
  const selectStock = async (ticker: string) => {
    setLoading(true);
    setShowSuggestions(false);
    setQuery(ticker);
    
    try {
      const [detailRes, chartRes] = await Promise.all([
        fetch(`${API_URL}/stocks/${ticker}`),
        fetch(`${API_URL}/stocks/${ticker}/chart?days=${chartDays}`),
      ]);
      
      const detail = await detailRes.json();
      const chart = await chartRes.json();
      
      setSelectedStock(detail);
      setStockChart(chart);
    } catch (err) {
      console.error('Failed to fetch stock:', err);
    } finally {
      setLoading(false);
    }
  };

  // 更換圖表時間範圍
  useEffect(() => {
    if (selectedStock && !selectedStock.error) {
      fetch(`${API_URL}/stocks/${selectedStock.ticker}/chart?days=${chartDays}`)
        .then(res => res.json())
        .then(data => setStockChart(data));
    }
  }, [chartDays]);

  const clearSearch = () => {
    setQuery('');
    setSelectedStock(null);
    setStockChart(null);
    setSuggestions([]);
  };

  const isPositive = (selectedStock?.change || 0) >= 0;

  return (
    <div className="mb-6">
      {/* 搜尋框 */}
      <div className="relative">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.length > 0 && setShowSuggestions(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && suggestions.length > 0) {
                selectStock(suggestions[0].ticker);
              }
            }}
            placeholder="🔍 搜尋股票代號或名稱 (例如: AAPL, Tesla, 騰訊)"
            className="w-full bg-slate-900 border border-slate-700 rounded-xl 
              pl-11 pr-10 py-3 text-white placeholder-slate-500
              focus:outline-none focus:border-blue-500 transition"
          />
          {query && (
            <button
              onClick={clearSearch}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 
                text-slate-500 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* 建議下拉列表 */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-50 w-full mt-2 bg-slate-800 border border-slate-700 
            rounded-xl shadow-2xl max-h-80 overflow-y-auto">
            {suggestions.map((s) => (
              <button
                key={s.ticker}
                onClick={() => selectStock(s.ticker)}
                className="w-full text-left px-4 py-3 hover:bg-slate-700 
                  flex justify-between items-center border-b border-slate-700 last:border-0"
              >
                <div>
                  <div className="text-white font-bold">{s.ticker}</div>
                  <div className="text-slate-400 text-sm">{s.name}</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 載入中 */}
      {loading && (
        <div className="mt-4 bg-slate-900 rounded-xl p-8 border border-slate-800 text-center">
          <Activity className="w-8 h-8 text-blue-500 animate-pulse mx-auto mb-2" />
          <p className="text-slate-400">載入股票資料...</p>
        </div>
      )}

      {/* 錯誤 */}
      {selectedStock?.error && (
        <div className="mt-4 bg-red-900/20 border border-red-500/50 rounded-xl p-4">
          <p className="text-red-400">❌ {selectedStock.error}</p>
        </div>
      )}

      {/* 股票詳情 */}
      {selectedStock && !selectedStock.error && !loading && (
        <div className="mt-4 bg-slate-900 rounded-xl p-6 border border-slate-800">
          {/* 標題和價格 */}
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-2xl font-bold">{selectedStock.ticker}</h2>
                <span className="text-xs px-2 py-0.5 bg-slate-800 rounded text-slate-400">
                  {selectedStock.exchange}
                </span>
              </div>
              <p className="text-slate-400 text-sm">{selectedStock.name}</p>
              <p className="text-slate-500 text-xs mt-1">
                {selectedStock.sector} • {selectedStock.industry}
              </p>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold">
                ${selectedStock.current_price}
                <span className="text-sm text-slate-500 ml-1">{selectedStock.currency}</span>
              </div>
              <div className={`flex items-center justify-end gap-1 mt-1 ${
                isPositive ? 'text-green-400' : 'text-red-400'
              }`}>
                {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                <span className="font-bold">
                  {isPositive ? '+' : ''}{selectedStock.change} 
                  ({isPositive ? '+' : ''}{selectedStock.change_pct}%)
                </span>
              </div>
            </div>
          </div>

          {/* 走勢圖 */}
          {stockChart && stockChart.data && stockChart.data.length > 0 && (
            <div className="mb-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-slate-400">{chartDays} 天走勢</span>
                <span className={`text-sm font-bold ${
                  stockChart.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {stockChart.total_return_pct >= 0 ? '+' : ''}{stockChart.total_return_pct.toFixed(2)}%
                </span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={stockChart.data}>
                  <defs>
                    <linearGradient id="stockGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={stockChart.total_return_pct >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0.4} />
                      <stop offset="100%" stopColor={stockChart.total_return_pct >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: '#94a3b8' }}
                    formatter={(value: any) => [`$${Number(value).toFixed(2)}`, '收盤價']}
                    labelFormatter={(label: any) => new Date(String(label)).toLocaleDateString('zh-HK')}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={stockChart.total_return_pct >= 0 ? '#22c55e' : '#ef4444'}
                    strokeWidth={2}
                    fill="url(#stockGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>

              {/* 時間切換 */}
              <div className="flex gap-1 mt-2 justify-center">
                {TIME_RANGES.map(range => (
                  <button
                    key={range.value}
                    onClick={() => setChartDays(range.value)}
                    className={`px-3 py-1 text-xs rounded transition ${
                      chartDays === range.value
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                    }`}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 詳細數據 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-4 border-t border-slate-800">
            <div>
              <p className="text-slate-500 text-xs">開盤</p>
              <p className="text-white font-bold">${selectedStock.open}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">最高</p>
              <p className="text-green-400 font-bold">${selectedStock.high}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">最低</p>
              <p className="text-red-400 font-bold">${selectedStock.low}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">昨收</p>
              <p className="text-white font-bold">${selectedStock.prev_close}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">成交量</p>
              <p className="text-white font-bold">{selectedStock.volume_formatted}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">市值</p>
              <p className="text-white font-bold">{selectedStock.market_cap_formatted}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">P/E</p>
              <p className="text-white font-bold">{selectedStock.pe_ratio || 'N/A'}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">股息率</p>
              <p className="text-white font-bold">
                {selectedStock.dividend_yield ? `${selectedStock.dividend_yield}%` : 'N/A'}
              </p>
            </div>
            {selectedStock.week_52_high && (
              <>
                <div>
                  <p className="text-slate-500 text-xs">52週高</p>
                  <p className="text-green-400 font-bold">${selectedStock.week_52_high.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-slate-500 text-xs">52週低</p>
                  <p className="text-red-400 font-bold">${selectedStock.week_52_low.toFixed(2)}</p>
                </div>
              </>
            )}
          </div>

          {/* 公司描述 */}
          {selectedStock.description && (
            <div className="mt-4 pt-4 border-t border-slate-800">
              <p className="text-slate-500 text-xs mb-1">公司簡介</p>
              <p className="text-slate-300 text-sm leading-relaxed">{selectedStock.description}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ===== 類別走勢圖組件(不變) =====
function SectorChart({ sector }: { sector: string }) {
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [showForecast, setShowForecast] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/sectors/${sector}/chart?days=${days}&include_forecast=${showForecast}`)
      .then(res => res.json())
      .then(data => {
        setChartData(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [sector, days, showForecast]);

  if (loading) return <div className="h-32 flex items-center justify-center text-slate-500 text-xs">載入中...</div>;
  if (!chartData?.data?.length) return <div className="h-32 flex items-center justify-center text-slate-500 text-xs">暫無數據</div>;

  const isPositive = chartData.total_return_pct >= 0;
  const lineColor = isPositive ? '#22c55e' : '#ef4444';
  const gradientId = `gradient-${sector}`;
  const forecastGradientId = `forecast-gradient-${sector}`;
  const historicalData = chartData.data.filter(d => d.type === 'historical');
  const separatorDate = historicalData.length > 0 ? historicalData[historicalData.length - 1].date : null;

  return (
    <div className="mt-3">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-slate-500">
          {days}天{showForecast && chartData.forecast_count > 0 && ' + 預測'}
        </span>
        <span className={`text-xs font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {isPositive ? '+' : ''}{chartData.total_return_pct.toFixed(2)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <ComposedChart data={chartData.data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.4} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
            <linearGradient id={forecastGradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" hide />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
            labelStyle={{ color: '#94a3b8' }}
            formatter={(value: any, name: any) => {
              if (value === null || value === undefined) return ['', ''];
              const labels: any = { value: '歷史', forecast: '預測', upper: '上限', lower: '下限' };
              return [Number(value).toFixed(2), labels[String(name)] || String(name)];
            }}
            labelFormatter={(label: any) => new Date(String(label)).toLocaleDateString('zh-HK')}
          />
          {showForecast && (
            <>
              <Area type="monotone" dataKey="upper" stroke="none" fill={`url(#${forecastGradientId})`} connectNulls />
              <Area type="monotone" dataKey="lower" stroke="none" fill="#0f172a" connectNulls />
            </>
          )}
          <Area type="monotone" dataKey="value" stroke={lineColor} strokeWidth={2} fill={`url(#${gradientId})`} connectNulls={false} />
          {showForecast && <Line type="monotone" dataKey="forecast" stroke="#3b82f6" strokeWidth={2} strokeDasharray="4 4" dot={false} connectNulls />}
          {showForecast && separatorDate && (
            <ReferenceLine x={separatorDate} stroke="#64748b" strokeDasharray="2 2" />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-between mt-2 gap-1">
        <div className="flex gap-1">
          {TIME_RANGES.map(range => (
            <button
              key={range.value}
              onClick={(e) => { e.stopPropagation(); setDays(range.value); }}
              className={`px-2 py-0.5 text-xs rounded transition ${
                days === range.value ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >{range.label}</button>
          ))}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); setShowForecast(!showForecast); }}
          className={`px-2 py-0.5 text-xs rounded transition ${
            showForecast ? 'bg-blue-600/30 text-blue-300 border border-blue-500/50' : 'bg-slate-800 text-slate-500'
          }`}
        >🔮 預測</button>
      </div>
    </div>
  );
}

// ===== 主頁面 =====
export default function HomePage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'search' | 'predictions' | 'news'>('predictions');
  const [selectedSector, setSelectedSector] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard`);
      const data = await res.json();
      setDashboard(data);
      setError(null);
    } catch (err) {
      setError('無法連接到伺服器');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/news?limit=100`);
      const data = await res.json();
      setNews(data.news || []);
    } catch (err) { console.error(err); }
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${API_URL}/refresh`, { method: 'POST' });
      setTimeout(() => { fetchDashboard(); fetchNews(); setRefreshing(false); }, 30000);
    } catch (err) { setRefreshing(false); }
  };

  useEffect(() => {
    fetchDashboard();
    fetchNews();
    const interval = setInterval(() => { fetchDashboard(); fetchNews(); }, 120000);
    return () => clearInterval(interval);
  }, [fetchDashboard, fetchNews]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-16 h-16 text-blue-500 animate-pulse mx-auto mb-4" />
          <h2 className="text-white text-2xl font-bold mb-2">AI 股票預測系統</h2>
          <p className="text-slate-400">載入中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
          <h2 className="text-white text-xl font-bold mb-2">連接錯誤</h2>
          <p className="text-slate-400 mb-4">{error}</p>
          <button onClick={() => { setLoading(true); fetchDashboard(); }} className="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg">重試</button>
        </div>
      </div>
    );
  }

  const predictions = dashboard?.predictions || [];
  const overview = dashboard?.market_overview;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-xl font-bold">📈 AI 股票預測系統</h1>
              <p className="text-slate-500 text-xs flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {dashboard?.last_updated ? new Date(dashboard.last_updated).toLocaleString('zh-HK') : '等待中'}
              </p>
            </div>
          </div>
          <button onClick={handleRefresh} disabled={refreshing}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 px-4 py-2 rounded-lg text-sm transition">
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? '刷新中...' : '刷新'}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {overview && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            <div className="bg-slate-900 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-500 text-xs mb-1">市場情緒</p>
              <p className={`text-lg font-bold ${overview.market_sentiment === 'bullish' ? 'text-green-400' : overview.market_sentiment === 'bearish' ? 'text-red-400' : 'text-yellow-400'}`}>
                {overview.market_sentiment === 'bullish' ? '🟢 看漲' : overview.market_sentiment === 'bearish' ? '🔴 看跌' : '🟡 中性'}
              </p>
            </div>
            <div className="bg-slate-900 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-500 text-xs mb-1">平均上升機率</p>
              <p className="text-lg font-bold text-blue-400">{(overview.avg_up_probability * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-slate-900 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-500 text-xs mb-1">已分析新聞</p>
              <p className="text-lg font-bold text-purple-400">{overview.total_news} 篇</p>
            </div>
            <div className="bg-slate-900 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-500 text-xs mb-1">最看漲</p>
              <p className="text-lg font-bold text-green-400">{overview.most_bullish}</p>
            </div>
            <div className="bg-slate-900 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-500 text-xs mb-1">最看跌</p>
              <p className="text-lg font-bold text-red-400">{overview.most_bearish}</p>
            </div>
          </div>
        )}

        <div className="flex gap-2 mb-6 flex-wrap">
          <button onClick={() => setActiveTab('search')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition ${
              activeTab === 'search' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}>
            <Search className="w-4 h-4" /> 股票搜尋
          </button>
          <button onClick={() => setActiveTab('predictions')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition ${
              activeTab === 'predictions' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}>
            <BarChart3 className="w-4 h-4" /> 類別預測
          </button>
          <button onClick={() => setActiveTab('news')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition ${
              activeTab === 'news' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}>
            <Newspaper className="w-4 h-4" /> 新聞 ({news.length})
          </button>
        </div>

        {/* 股票搜尋 */}
        {activeTab === 'search' && <StockSearch />}

        {/* 預測結果 */}
        {activeTab === 'predictions' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {predictions.map((pred) => (
              <div key={pred.sector}
                onClick={() => setSelectedSector(selectedSector === pred.sector ? null : pred.sector)}
                className={`rounded-xl p-5 border-l-4 cursor-pointer transition-all bg-slate-900 hover:scale-[1.01] ${
                  pred.direction === 'UP' ? 'border-green-500' : pred.direction === 'DOWN' ? 'border-red-500' : 'border-yellow-500'
                } ${selectedSector === pred.sector ? 'ring-2 ring-blue-500' : ''}`}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-bold">{pred.sector_name}</h3>
                  {pred.direction === 'UP' ? <TrendingUp className="w-5 h-5 text-green-400" /> :
                   pred.direction === 'DOWN' ? <TrendingDown className="w-5 h-5 text-red-400" /> :
                   <Minus className="w-5 h-5 text-yellow-400" />}
                </div>
                <div className="mb-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-green-400">↑ {(pred.up_probability * 100).toFixed(1)}%</span>
                    <span className="text-slate-400">{(pred.neutral_probability * 100).toFixed(1)}%</span>
                    <span className="text-red-400">↓ {(pred.down_probability * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-2.5 overflow-hidden flex">
                    <div className="bg-green-500 h-full" style={{ width: `${pred.up_probability * 100}%` }} />
                    <div className="bg-yellow-500/50 h-full" style={{ width: `${pred.neutral_probability * 100}%` }} />
                    <div className="bg-red-500 h-full" style={{ width: `${pred.down_probability * 100}%` }} />
                  </div>
                </div>
                <div onClick={(e) => e.stopPropagation()}>
                  <SectorChart sector={pred.sector} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 mt-3 pt-3 border-t border-slate-800">
                  <div>信心度: <span className="text-white">{(pred.confidence * 100).toFixed(0)}%</span></div>
                  <div>新聞: <span className="text-white">{pred.news_count} 篇</span></div>
                  <div>情緒: <span className={pred.sentiment_score > 0 ? 'text-green-400' : pred.sentiment_score < 0 ? 'text-red-400' : 'text-slate-300'}>
                    {pred.sentiment_score > 0 ? '+' : ''}{pred.sentiment_score.toFixed(3)}
                  </span></div>
                  <div>模型: <span className="text-white">{(pred.model_accuracy * 100).toFixed(0)}%</span></div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 新聞 */}
        {activeTab === 'news' && (
          <div className="space-y-2">
            {news.map((item, idx) => (
              <div key={idx} className="bg-slate-900 rounded-lg p-4 border border-slate-800 hover:border-slate-700 transition">
                <div className="flex justify-between items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 text-sm font-medium block">
                      {item.title}
                    </a>
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-slate-500 flex-wrap">
                      <span>{item.source}</span>
                      <span>•</span>
                      <span>{new Date(item.published_at).toLocaleDateString('zh-HK')}</span>
                    </div>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs whitespace-nowrap ${
                    item.sentiment_label === 'bullish' ? 'bg-green-500/20 text-green-400' :
                    item.sentiment_label === 'bearish' ? 'bg-red-500/20 text-red-400' :
                    'bg-slate-700 text-slate-400'
                  }`}>
                    {item.sentiment_label === 'bullish' ? '↑看漲' : item.sentiment_label === 'bearish' ? '↓看跌' : '→中性'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="bg-slate-900 border-t border-slate-800 mt-12 px-4 py-4">
        <div className="max-w-7xl mx-auto flex items-start gap-2 text-yellow-600 text-xs">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <p><strong>免責聲明:</strong>本系統僅供參考,不構成投資建議。</p>
        </div>
      </footer>
    </div>
  );
}