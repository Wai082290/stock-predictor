'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw,
  BarChart3, Newspaper, Activity, AlertTriangle,
  ArrowUpRight, ArrowDownRight, Clock, Search, X,
  Sparkles, Zap, Globe, Star, StarOff, Flame,
  DollarSign, TrendingUp as TrendUp, Bell, Layers
} from 'lucide-react';
import {
  ResponsiveContainer, Tooltip, XAxis, YAxis,
  Area, AreaChart, ComposedChart, Line, ReferenceLine,
  RadialBarChart, RadialBar, PolarAngleAxis, Legend
} from 'recharts';
import { LogoWithText, Logo } from '../components/Logo';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TIME_RANGES = [
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '1年', value: 365 },
];

// ===== 恐懼貪婪指數 =====
function FearGreedIndex() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_URL}/market/fear-greed`)
      .then(res => res.json())
      .then(setData);
  }, []);

  if (!data) return null;

  const chartData = [{ name: 'Index', value: data.index, fill: data.color }];

  return (
    <div className="glass-strong rounded-2xl p-5 card-hover">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-slate-500 text-xs font-medium">🌡️ 恐懼貪婪指數</p>
          <p className="text-2xl font-black" style={{ color: data.color }}>
            {data.emoji} {data.index}
          </p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <RadialBarChart innerRadius="60%" outerRadius="90%" data={chartData} startAngle={180} endAngle={0}>
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar background={{ fill: '#1e293b' }} dataKey="value" cornerRadius={10} />
        </RadialBarChart>
      </ResponsiveContainer>
      <p className="text-center text-sm font-bold mt-1" style={{ color: data.color }}>{data.label}</p>
    </div>
  );
}

// ===== 全球市場時鐘 =====
function MarketClock() {
  const [markets, setMarkets] = useState<any[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    fetch(`${API_URL}/market/hours`)
      .then(res => res.json())
      .then(data => setMarkets(data.markets || []));

    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="glass-strong rounded-2xl p-5 card-hover">
      <div className="flex items-center justify-between mb-3">
        <p className="text-slate-500 text-xs font-medium flex items-center gap-1">
          <Clock className="w-3 h-3" /> 全球市場
        </p>
        <p className="text-xs text-slate-400 font-mono">
          {currentTime.toLocaleTimeString('zh-HK')}
        </p>
      </div>
      <div className="space-y-2">
        {markets.map((m) => (
          <div key={m.code} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2">
              {m.flag}
              <span className={m.is_open ? 'text-green-400 font-bold' : 'text-slate-500'}>
                {m.code}
              </span>
            </span>
            <span className="text-xs text-slate-400 font-mono">{m.local_time}</span>
            <span className={`text-xs ${m.is_open ? 'text-green-400' : 'text-slate-500'}`}>
              {m.is_open ? '🟢 開市' : '🔴 休市'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ===== 匯率轉換器 =====
function CurrencyConverter() {
  const [amount, setAmount] = useState('100');
  const [from, setFrom] = useState('USD');
  const [to, setTo] = useState('HKD');
  const [rates, setRates] = useState<any>({});

  useEffect(() => {
    fetch(`${API_URL}/exchange/rate`)
      .then(res => res.json())
      .then(data => setRates(data.rates || {}));
  }, []);

  const convert = () => {
    const num = parseFloat(amount) || 0;
    if (from === 'USD') return (num * (rates[to] || 1)).toFixed(2);
    if (to === 'USD') return (num / (rates[from] || 1)).toFixed(2);
    // 通過 USD 轉換
    return ((num / (rates[from] || 1)) * (rates[to] || 1)).toFixed(2);
  };

  const currencies = ['USD', 'HKD', 'CNY', 'EUR', 'JPY', 'GBP', 'TWD'];

  return (
    <div className="glass-strong rounded-2xl p-5 card-hover">
      <p className="text-slate-500 text-xs font-medium mb-3 flex items-center gap-1">
        <DollarSign className="w-3 h-3" /> 匯率轉換
      </p>
      <input
        type="number"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="w-full glass rounded-lg px-3 py-2 text-white text-lg font-bold mb-2 focus:outline-none focus:border-blue-500"
      />
      <div className="flex gap-2 mb-2">
        <select value={from} onChange={(e) => setFrom(e.target.value)}
          className="flex-1 glass rounded-lg px-2 py-1 text-white text-sm focus:outline-none">
          {currencies.map(c => <option key={c} value={c} className="bg-slate-800">{c}</option>)}
        </select>
        <button onClick={() => { setFrom(to); setTo(from); }} className="text-slate-400 hover:text-white">⇄</button>
        <select value={to} onChange={(e) => setTo(e.target.value)}
          className="flex-1 glass rounded-lg px-2 py-1 text-white text-sm focus:outline-none">
          {currencies.map(c => <option key={c} value={c} className="bg-slate-800">{c}</option>)}
        </select>
      </div>
      <p className="text-2xl font-black text-gradient text-center">{convert()} {to}</p>
    </div>
  );
}

// ===== 熱門股票 =====
function TrendingStocks({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [data, setData] = useState<any>({ gainers: [], losers: [] });

  useEffect(() => {
    fetch(`${API_URL}/market/trending`)
      .then(res => res.json())
      .then(setData);
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <div className="glass-strong rounded-2xl p-5">
        <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
          <Flame className="w-5 h-5 text-orange-400" />
          <span className="text-gradient-green">今日領漲</span>
        </h3>
        <div className="space-y-2">
          {data.gainers?.slice(0, 5).map((stock: any) => (
            <button key={stock.ticker} onClick={() => onSelect(stock.ticker)}
              className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-green-500/10 transition group">
              <div className="text-left">
                <p className="font-bold group-hover:text-green-400 transition">{stock.ticker}</p>
                <p className="text-xs text-slate-500">{stock.sector}</p>
              </div>
              <div className="text-right">
                <p className="text-white font-bold">${stock.price}</p>
                <p className="text-green-400 text-sm font-bold">+{stock.change_pct}%</p>
              </div>
            </button>
          ))}
        </div>
      </div>
      <div className="glass-strong rounded-2xl p-5">
        <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
          <TrendingDown className="w-5 h-5 text-red-400" />
          <span className="text-gradient-red">今日領跌</span>
        </h3>
        <div className="space-y-2">
          {data.losers?.slice(0, 5).map((stock: any) => (
            <button key={stock.ticker} onClick={() => onSelect(stock.ticker)}
              className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-red-500/10 transition group">
              <div className="text-left">
                <p className="font-bold group-hover:text-red-400 transition">{stock.ticker}</p>
                <p className="text-xs text-slate-500">{stock.sector}</p>
              </div>
              <div className="text-right">
                <p className="text-white font-bold">${stock.price}</p>
                <p className="text-red-400 text-sm font-bold">{stock.change_pct}%</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ===== 收藏股票功能 =====
function useFavorites() {
  const [favorites, setFavorites] = useState<string[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem('favorites');
    if (saved) setFavorites(JSON.parse(saved));
  }, []);

  const toggle = (ticker: string) => {
    const newFavs = favorites.includes(ticker)
      ? favorites.filter(f => f !== ticker)
      : [...favorites, ticker];
    setFavorites(newFavs);
    localStorage.setItem('favorites', JSON.stringify(newFavs));
  };

  return { favorites, toggle, isFav: (t: string) => favorites.includes(t) };
}

// ===== 股票搜尋 (升級版) =====
function StockSearch({ initialTicker }: { initialTicker?: string }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedStock, setSelectedStock] = useState<any>(null);
  const [stockChart, setStockChart] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [chartDays, setChartDays] = useState(30);
  const [priceAlert, setPriceAlert] = useState('');
  const [alertSet, setAlertSet] = useState(false);
  const { favorites, toggle, isFav } = useFavorites();

  useEffect(() => {
    if (initialTicker) selectStock(initialTicker);
  }, [initialTicker]);

  useEffect(() => {
    if (query.length < 1) { setSuggestions([]); return; }
    const timer = setTimeout(() => {
      fetch(`${API_URL}/stocks/search?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => { setSuggestions(data.results || []); setShowSuggestions(true); });
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const selectStock = async (ticker: string) => {
    setLoading(true);
    setShowSuggestions(false);
    setQuery(ticker);
    try {
      const [detail, chart] = await Promise.all([
        fetch(`${API_URL}/stocks/${ticker}`).then(r => r.json()),
        fetch(`${API_URL}/stocks/${ticker}/chart?days=${chartDays}`).then(r => r.json()),
      ]);
      setSelectedStock(detail);
      setStockChart(chart);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (selectedStock && !selectedStock.error) {
      fetch(`${API_URL}/stocks/${selectedStock.ticker}/chart?days=${chartDays}`)
        .then(res => res.json()).then(setStockChart);
    }
  }, [chartDays]);

  const setAlert = () => {
    if (!priceAlert || !selectedStock) return;
    localStorage.setItem(`alert_${selectedStock.ticker}`, priceAlert);
    setAlertSet(true);
    setTimeout(() => setAlertSet(false), 2000);
  };

  const isPositive = (selectedStock?.change || 0) >= 0;

  return (
    <div className="fade-in-up">
      {/* 收藏股票快速訪問 */}
      {favorites.length > 0 && (
        <div className="mb-4 glass rounded-xl p-3">
          <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">
            <Star className="w-3 h-3 text-yellow-400" /> 我的收藏
          </p>
          <div className="flex gap-2 flex-wrap">
            {favorites.map(ticker => (
              <button key={ticker} onClick={() => selectStock(ticker)}
                className="glass rounded-lg px-3 py-1 text-sm font-bold hover:bg-yellow-500/10 hover:text-yellow-400 transition">
                ⭐ {ticker}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="relative">
        <div className="relative group">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl blur opacity-20 group-hover:opacity-40 transition"></div>
          <div className="relative">
            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-blue-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => query.length > 0 && setShowSuggestions(true)}
              onKeyDown={(e) => { if (e.key === 'Enter' && suggestions.length > 0) selectStock(suggestions[0].ticker); }}
              placeholder="🔍 搜尋股票 (AAPL, Tesla, 騰訊...)"
              className="w-full glass-strong rounded-2xl pl-12 pr-12 py-4 text-white text-lg placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            {query && (
              <button onClick={() => { setQuery(''); setSelectedStock(null); setStockChart(null); }}
                className="absolute right-4 top-1/2 transform -translate-y-1/2 text-slate-500 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-50 w-full mt-2 glass-strong rounded-2xl shadow-2xl max-h-80 overflow-y-auto">
            {suggestions.map((s) => (
              <button key={s.ticker} onClick={() => selectStock(s.ticker)}
                className="w-full text-left px-5 py-3 hover:bg-blue-500/10 flex justify-between items-center border-b border-slate-800 last:border-0 group">
                <div>
                  <div className="text-white font-bold text-lg group-hover:text-blue-400">{s.ticker}</div>
                  <div className="text-slate-400 text-sm">{s.name}</div>
                </div>
                <ArrowUpRight className="w-5 h-5 text-slate-600 group-hover:text-blue-400" />
              </button>
            ))}
          </div>
        )}
      </div>

      {loading && (
        <div className="mt-6 glass rounded-2xl p-12 text-center">
          <Activity className="w-12 h-12 text-blue-400 animate-pulse mx-auto mb-3" />
          <p className="text-slate-300">載入中...</p>
        </div>
      )}

      {selectedStock?.error && (
        <div className="mt-6 glass rounded-2xl p-6 border border-red-500/50">
          <p className="text-red-400 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5" /> {selectedStock.error}
          </p>
        </div>
      )}

      {selectedStock && !selectedStock.error && !loading && (
        <div className="mt-6 glass-strong rounded-3xl p-8 fade-in-up card-hover">
          <div className="flex justify-between items-start mb-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-4xl font-black text-gradient">{selectedStock.ticker}</h2>
                <button onClick={() => toggle(selectedStock.ticker)}
                  className="text-yellow-400 hover:scale-110 transition">
                  {isFav(selectedStock.ticker) ? <Star className="w-6 h-6 fill-yellow-400" /> : <StarOff className="w-6 h-6" />}
                </button>
                <span className="text-xs px-3 py-1 bg-blue-500/10 border border-blue-500/30 rounded-full text-blue-400 font-medium">
                  {selectedStock.exchange}
                </span>
              </div>
              <p className="text-slate-300 text-lg font-medium">{selectedStock.name}</p>
              <p className="text-slate-500 text-sm mt-1">{selectedStock.sector} • {selectedStock.industry}</p>
            </div>
            <div className="text-right">
              <div className="text-5xl font-black text-white mb-1">
                ${selectedStock.current_price}
                <span className="text-sm text-slate-500 ml-2 font-normal">{selectedStock.currency}</span>
              </div>
              <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full font-bold text-lg ${
                isPositive ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'
              }`}>
                {isPositive ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                {isPositive ? '+' : ''}{selectedStock.change} ({isPositive ? '+' : ''}{selectedStock.change_pct}%)
              </div>
            </div>
          </div>

          {/* 價格提醒 */}
          <div className="glass rounded-xl p-3 mb-4 flex items-center gap-2">
            <Bell className="w-4 h-4 text-yellow-400" />
            <input
              type="number"
              value={priceAlert}
              onChange={(e) => setPriceAlert(e.target.value)}
              placeholder="設定價格提醒..."
              className="flex-1 bg-transparent text-white text-sm focus:outline-none placeholder-slate-500"
            />
            <button onClick={setAlert}
              className="text-xs bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded-full hover:bg-yellow-500/30">
              {alertSet ? '✓ 已設定' : '設定'}
            </button>
          </div>

          {stockChart?.data?.length > 0 && (
            <div className="mb-6 glass rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <span className="text-sm text-slate-400 font-medium">📈 {chartDays} 天走勢</span>
                <span className={`text-lg font-bold ${stockChart.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {stockChart.total_return_pct >= 0 ? '▲' : '▼'} {stockChart.total_return_pct >= 0 ? '+' : ''}{stockChart.total_return_pct.toFixed(2)}%
                </span>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={stockChart.data}>
                  <defs>
                    <linearGradient id="stock3d" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={stockChart.total_return_pct >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0.8} />
                      <stop offset="50%" stopColor={stockChart.total_return_pct >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={stockChart.total_return_pct >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                    <filter id="glow-line">
                      <feGaussianBlur stdDeviation="2" result="blur"/>
                      <feMerge>
                        <feMergeNode in="blur"/>
                        <feMergeNode in="SourceGraphic"/>
                      </feMerge>
                    </filter>
                  </defs>
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#1e293b' }} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#1e293b' }} domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'rgba(15,23,42,0.95)', border: '1px solid #3b82f6', borderRadius: '12px', backdropFilter: 'blur(10px)' }}
                    labelStyle={{ color: '#94a3b8' }}
                    formatter={(value: any) => [`$${Number(value).toFixed(2)}`, '收盤價']}
                    labelFormatter={(label: any) => new Date(String(label)).toLocaleDateString('zh-HK')}
                  />
                  <Area type="monotone" dataKey="value"
                    stroke={stockChart.total_return_pct >= 0 ? '#22c55e' : '#ef4444'}
                    strokeWidth={3} fill="url(#stock3d)" filter="url(#glow-line)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="flex gap-2 mt-3 justify-center">
                {TIME_RANGES.map(range => (
                  <button key={range.value} onClick={() => setChartDays(range.value)}
                    className={`px-4 py-1.5 text-xs font-medium rounded-full transition-all ${
                      chartDays === range.value
                        ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg shadow-blue-500/30'
                        : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50 hover:text-white'
                    }`}>{range.label}</button>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: '開盤', value: `$${selectedStock.open}`, color: 'text-white' },
              { label: '最高', value: `$${selectedStock.high}`, color: 'text-green-400' },
              { label: '最低', value: `$${selectedStock.low}`, color: 'text-red-400' },
              { label: '昨收', value: `$${selectedStock.prev_close}`, color: 'text-white' },
              { label: '成交量', value: selectedStock.volume_formatted, color: 'text-blue-400' },
              { label: '市值', value: selectedStock.market_cap_formatted, color: 'text-purple-400' },
              { label: 'P/E', value: selectedStock.pe_ratio || 'N/A', color: 'text-white' },
              { label: '股息率', value: selectedStock.dividend_yield ? `${selectedStock.dividend_yield}%` : 'N/A', color: 'text-yellow-400' },
            ].map((item, idx) => (
              <div key={idx} className="glass rounded-xl p-3 hover:border-blue-500/30 transition">
                <p className="text-slate-500 text-xs mb-1">{item.label}</p>
                <p className={`${item.color} font-bold text-lg`}>{item.value}</p>
              </div>
            ))}
          </div>

          {selectedStock.description && (
            <div className="mt-6 glass rounded-2xl p-5">
              <p className="text-slate-500 text-xs mb-2 font-semibold uppercase tracking-wide">📖 公司簡介</p>
              <p className="text-slate-300 text-sm leading-relaxed">{selectedStock.description}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ===== 類別走勢圖 (3D 版) =====
function SectorChart({ sector }: { sector: string }) {
  const [chartData, setChartData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [showForecast, setShowForecast] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/sectors/${sector}/chart?days=${days}&include_forecast=${showForecast}`)
      .then(res => res.json())
      .then(data => { setChartData(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [sector, days, showForecast]);

  if (loading) return <div className="h-32 flex items-center justify-center text-slate-500 text-xs">⏳ 載入中...</div>;
  if (!chartData?.data?.length) return <div className="h-32 flex items-center justify-center text-slate-500 text-xs">暫無數據</div>;

  const isPositive = chartData.total_return_pct >= 0;
  const lineColor = isPositive ? '#22c55e' : '#ef4444';
  const gradientId = `gradient-${sector}`;
  const forecastGradientId = `forecast-gradient-${sector}`;
  const glowId = `glow-${sector}`;
  const historicalData = chartData.data.filter((d: any) => d.type === 'historical');
  const separatorDate = historicalData.length > 0 ? historicalData[historicalData.length - 1].date : null;

  return (
    <div className="mt-3">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-slate-500 font-medium">
          📊 {days}天{showForecast && chartData.forecast_count > 0 && ' + 🔮 預測'}
        </span>
        <span className={`text-sm font-black ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {isPositive ? '▲' : '▼'} {isPositive ? '+' : ''}{chartData.total_return_pct.toFixed(2)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <ComposedChart data={chartData.data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.7} />
              <stop offset="50%" stopColor={lineColor} stopOpacity={0.3} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
            <linearGradient id={forecastGradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.05} />
            </linearGradient>
            <filter id={glowId}>
              <feGaussianBlur stdDeviation="2" result="blur"/>
              <feMerge>
                <feMergeNode in="blur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          <XAxis dataKey="date" hide />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ backgroundColor: 'rgba(15,23,42,0.95)', border: '1px solid #3b82f6', borderRadius: '12px', fontSize: '12px', backdropFilter: 'blur(10px)' }}
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
              <Area type="monotone" dataKey="lower" stroke="none" fill="#030712" connectNulls />
            </>
          )}
          <Area type="monotone" dataKey="value" stroke={lineColor} strokeWidth={3} 
            fill={`url(#${gradientId})`} filter={`url(#${glowId})`} connectNulls={false} />
          {showForecast && <Line type="monotone" dataKey="forecast" stroke="#8b5cf6" strokeWidth={2.5} strokeDasharray="5 5" dot={false} connectNulls />}
          {showForecast && separatorDate && (
            <ReferenceLine x={separatorDate} stroke="#8b5cf6" strokeDasharray="2 2" strokeOpacity={0.5} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-between mt-2 gap-1">
        <div className="flex gap-1">
          {TIME_RANGES.map(range => (
            <button key={range.value} onClick={(e) => { e.stopPropagation(); setDays(range.value); }}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${
                days === range.value
                  ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-md shadow-blue-500/30'
                  : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50'
              }`}>{range.label}</button>
          ))}
        </div>
        <button onClick={(e) => { e.stopPropagation(); setShowForecast(!showForecast); }}
          className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
            showForecast
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
              : 'bg-slate-800/50 text-slate-500'
          }`}>🔮 預測</button>
      </div>
    </div>
  );
}

// ===== 主頁面 =====
export default function HomePage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [news, setNews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'search' | 'predictions' | 'news'>('predictions');
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [translations, setTranslations] = useState<{ [key: string]: string }>({});
  const [translateEnabled, setTranslateEnabled] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [searchTicker, setSearchTicker] = useState<string>('');

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard`);
      setDashboard(await res.json());
      setError(null);
    } catch (err) { setError('無法連接到伺服器'); }
    finally { setLoading(false); }
  }, []);

  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/news?limit=100`);
      const data = await res.json();
      setNews(data.news || []);
    } catch (err) { console.error(err); }
  }, []);

  const translateAllNews = useCallback(async () => {
    if (!translateEnabled || news.length === 0) return;
    const untranslated = news.filter(n => !translations[n.title]).map(n => n.title);
    if (untranslated.length === 0) return;
    setTranslating(true);
    try {
      const batchSize = 20;
      for (let i = 0; i < untranslated.length; i += batchSize) {
        const batch = untranslated.slice(i, i + batchSize);
        const res = await fetch(`${API_URL}/translate/batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ texts: batch, target_lang: 'zh-TW' }),
        });
        const data = await res.json();
        if (data.translations) {
          const newT: { [key: string]: string } = {};
          data.translations.forEach((t: any) => {
            if (t.original && t.translated) newT[t.original] = t.translated;
          });
          setTranslations(prev => ({ ...prev, ...newT }));
        }
      }
    } catch (err) { console.error(err); }
    finally { setTranslating(false); }
  }, [news, translateEnabled, translations]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${API_URL}/refresh`, { method: 'POST' });
      setTimeout(() => { fetchDashboard(); fetchNews(); setRefreshing(false); }, 30000);
    } catch (err) { setRefreshing(false); }
  };

  const handleStockSelect = (ticker: string) => {
    setSearchTicker(ticker);
    setActiveTab('search');
  };

  useEffect(() => {
    fetchDashboard();
    fetchNews();
    const interval = setInterval(() => { fetchDashboard(); fetchNews(); }, 120000);
    return () => clearInterval(interval);
  }, [fetchDashboard, fetchNews]);

  useEffect(() => {
    if (translateEnabled) translateAllNews();
  }, [translateEnabled, news.length]);

  if (loading) {
    return (
      <div className="min-h-screen animated-gradient-bg flex items-center justify-center">
        <div className="text-center">
          <div className="mb-6 float">
            <Logo size={80} />
          </div>
          <LogoWithText size="lg" />
          <p className="text-slate-400 text-lg mt-4">正在啟動 AI 預測引擎...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen animated-gradient-bg flex items-center justify-center p-4">
        <div className="text-center max-w-md glass-strong rounded-3xl p-10 fade-in-up">
          <AlertTriangle className="w-20 h-20 text-yellow-500 mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-white mb-3">連接錯誤</h2>
          <p className="text-slate-400 mb-6 text-lg">{error}</p>
          <button onClick={() => { setLoading(true); fetchDashboard(); }}
            className="btn-glow bg-gradient-to-r from-blue-500 to-purple-500 text-white px-8 py-3 rounded-full font-bold">
            🔄 重試
          </button>
        </div>
      </div>
    );
  }

  const predictions = dashboard?.predictions || [];
  const overview = dashboard?.market_overview;

    return (
    <div className="min-h-screen text-white">
      {/* ⭐ 影片背景 */}
      <div className="video-background-wrapper">
        <video
          className="video-background"
          autoPlay
          loop
          muted
          playsInline
        >
          <source src="/background.mp4" type="video/mp4" />
        </video>
      </div>
      <div className="video-overlay"></div>
      
      <div className="fixed top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 z-50"></div>
      
      <header className="glass-strong border-b border-white/5 sticky top-1 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <LogoWithText size="md" />
          <div className="flex items-center gap-3">
            <p className="text-slate-500 text-xs hidden md:block">
              <Clock className="w-3 h-3 inline mr-1" />
              {dashboard?.last_updated ? new Date(dashboard.last_updated).toLocaleString('zh-HK') : '等待中'}
            </p>
            <button onClick={handleRefresh} disabled={refreshing}
              className="btn-glow flex items-center gap-2 bg-gradient-to-r from-blue-500 to-purple-500 hover:shadow-lg hover:shadow-blue-500/40 disabled:opacity-50 px-5 py-2.5 rounded-full text-sm font-bold transition">
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? '刷新中' : '刷新'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* 小工具區 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 fade-in-up">
          <FearGreedIndex />
          <MarketClock />
          <CurrencyConverter />
        </div>

        {/* 市場概覽 */}
        {overview && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            {[
              { label: '市場情緒', value: overview.market_sentiment === 'bullish' ? '🟢 看漲' : overview.market_sentiment === 'bearish' ? '🔴 看跌' : '🟡 中性',
                color: overview.market_sentiment === 'bullish' ? 'text-green-400' : overview.market_sentiment === 'bearish' ? 'text-red-400' : 'text-yellow-400',
                icon: <Zap className="w-4 h-4" /> },
              { label: '上升機率', value: `${(overview.avg_up_probability * 100).toFixed(1)}%`, color: 'text-gradient', icon: <TrendUp className="w-4 h-4" /> },
              { label: '分析新聞', value: `${overview.total_news}`, sub: '篇', color: 'text-purple-400', icon: <Newspaper className="w-4 h-4" /> },
              { label: '最看漲', value: overview.most_bullish, color: 'text-green-400', icon: <TrendingUp className="w-4 h-4" /> },
              { label: '最看跌', value: overview.most_bearish, color: 'text-red-400', icon: <TrendingDown className="w-4 h-4" /> },
            ].map((card, idx) => (
              <div key={idx} className="glass rounded-2xl p-4 card-hover" style={{ animationDelay: `${idx * 80}ms` }}>
                <div className="flex items-center gap-2 text-slate-500 text-xs mb-2">{card.icon} {card.label}</div>
                <p className={`text-2xl font-black ${card.color}`}>
                  {card.value}
                  {card.sub && <span className="text-sm text-slate-500 ml-1 font-normal">{card.sub}</span>}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* 熱門股票 */}
        <TrendingStocks onSelect={handleStockSelect} />

        {/* Tab 切換 */}
        <div className="flex gap-3 mb-8 flex-wrap items-center">
          {[
            { key: 'search', icon: <Search className="w-4 h-4" />, label: '股票搜尋' },
            { key: 'predictions', icon: <BarChart3 className="w-4 h-4" />, label: '類別預測' },
            { key: 'news', icon: <Newspaper className="w-4 h-4" />, label: `新聞 (${news.length})` },
          ].map((tab) => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key as any)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold transition-all ${
                activeTab === tab.key ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg shadow-blue-500/40'
                  : 'glass text-slate-400 hover:text-white hover:border-blue-500/30'
              }`}>
              {tab.icon} {tab.label}
            </button>
          ))}
          {activeTab === 'news' && (
            <button onClick={() => setTranslateEnabled(!translateEnabled)} disabled={translating}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold ml-auto ${
                translateEnabled ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-lg shadow-green-500/40'
                  : 'glass text-slate-400 hover:text-white'
              } ${translating ? 'opacity-50' : ''}`}>
              {translating ? (<><Activity className="w-4 h-4 animate-spin" /> 翻譯中</>) :
                translateEnabled ? (<><Globe className="w-4 h-4" /> 中文 ✓</>) : (<><Globe className="w-4 h-4" /> 翻譯</>)}
            </button>
          )}
        </div>

        {activeTab === 'search' && <StockSearch initialTicker={searchTicker} />}

        {activeTab === 'predictions' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {predictions.map((pred: any, idx: number) => (
              <div key={pred.sector} onClick={() => setSelectedSector(selectedSector === pred.sector ? null : pred.sector)}
                className={`glass-strong rounded-2xl p-6 cursor-pointer card-hover fade-in-up ${
                  pred.direction === 'UP' ? 'neon-border-green' :
                  pred.direction === 'DOWN' ? 'neon-border-red' :
                  'border border-yellow-500/30'
                } ${selectedSector === pred.sector ? 'ring-2 ring-blue-500' : ''}`}
                style={{ animationDelay: `${idx * 60}ms` }}>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-black">{pred.sector_name}</h3>
                  <div className={`p-2 rounded-full ${
                    pred.direction === 'UP' ? 'bg-green-500/20' :
                    pred.direction === 'DOWN' ? 'bg-red-500/20' : 'bg-yellow-500/20'
                  }`}>
                    {pred.direction === 'UP' ? <TrendingUp className="w-5 h-5 text-green-400" /> :
                     pred.direction === 'DOWN' ? <TrendingDown className="w-5 h-5 text-red-400" /> :
                     <Minus className="w-5 h-5 text-yellow-400" />}
                  </div>
                </div>
                <div className="mb-4">
                  <div className="flex justify-between text-xs mb-2 font-medium">
                    <span className="text-green-400">▲ {(pred.up_probability * 100).toFixed(1)}%</span>
                    <span className="text-slate-400">{(pred.neutral_probability * 100).toFixed(1)}%</span>
                    <span className="text-red-400">▼ {(pred.down_probability * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-slate-800/50 rounded-full h-3 overflow-hidden flex shadow-inner">
                    <div className="bg-gradient-to-r from-green-500 to-emerald-500 h-full" style={{ width: `${pred.up_probability * 100}%` }} />
                    <div className="bg-yellow-500/40 h-full" style={{ width: `${pred.neutral_probability * 100}%` }} />
                    <div className="bg-gradient-to-r from-red-500 to-rose-500 h-full" style={{ width: `${pred.down_probability * 100}%` }} />
                  </div>
                </div>
                <div onClick={(e) => e.stopPropagation()}>
                  <SectorChart sector={pred.sector} />
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs mt-4 pt-4 border-t border-slate-800">
                  <div className="glass rounded-lg p-2">
                    <div className="text-slate-500 mb-1">信心度</div>
                    <div className="text-white font-bold">{(pred.confidence * 100).toFixed(0)}%</div>
                  </div>
                  <div className="glass rounded-lg p-2">
                    <div className="text-slate-500 mb-1">新聞</div>
                    <div className="text-white font-bold">{pred.news_count} 篇</div>
                  </div>
                  <div className="glass rounded-lg p-2">
                    <div className="text-slate-500 mb-1">情緒</div>
                    <div className={`font-bold ${pred.sentiment_score > 0 ? 'text-green-400' : pred.sentiment_score < 0 ? 'text-red-400' : 'text-slate-300'}`}>
                      {pred.sentiment_score > 0 ? '+' : ''}{pred.sentiment_score.toFixed(3)}
                    </div>
                  </div>
                  <div className="glass rounded-lg p-2">
                    <div className="text-slate-500 mb-1">準確度</div>
                    <div className="text-white font-bold">{(pred.model_accuracy * 100).toFixed(0)}%</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'news' && (
          <div className="space-y-3">
            {news.map((item, idx) => (
              <div key={idx} className="glass rounded-xl p-4 card-hover"
                style={{ animationDelay: `${Math.min(idx * 20, 500)}ms` }}>
                <div className="flex justify-between items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <a href={item.url} target="_blank" rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 text-sm font-semibold block leading-relaxed">
                      {item.title}
                    </a>
                    {translateEnabled && translations[item.title] && translations[item.title] !== item.title && (
                      <p className="text-slate-300 text-sm mt-2 leading-relaxed border-l-2 border-green-500/50 pl-3">
                        🌏 {translations[item.title]}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-2 text-xs text-slate-500 flex-wrap">
                      <span className="bg-slate-800/50 px-2 py-0.5 rounded-full">{item.source}</span>
                      <span>•</span>
                      <span>{new Date(item.published_at).toLocaleDateString('zh-HK')}</span>
                    </div>
                  </div>
                  <span className={`px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap ${
                    item.sentiment_label === 'bullish' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
                    item.sentiment_label === 'bearish' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                    'bg-slate-700/50 text-slate-400 border border-slate-600'
                  }`}>
                    {item.sentiment_label === 'bullish' ? '▲ 看漲' : item.sentiment_label === 'bearish' ? '▼ 看跌' : '● 中性'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="glass-strong border-t border-white/5 mt-16 px-4 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <LogoWithText size="sm" />
            <p className="text-slate-500 text-xs">© 2024 StockSight AI</p>
          </div>
          <div className="flex items-start gap-3 text-yellow-500/80 text-xs">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <p><strong className="text-yellow-500">免責聲明:</strong> 本系統的預測結果僅供參考,不構成任何投資建議。</p>
          </div>
        </div>
      </footer>
    </div>
  );
}