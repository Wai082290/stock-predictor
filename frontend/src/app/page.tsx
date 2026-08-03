'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw,
  BarChart3, Newspaper, Activity, AlertTriangle,
  ArrowUpRight, ArrowDownRight, Clock
} from 'lucide-react';
import {
  ResponsiveContainer, Tooltip, XAxis, YAxis,
  Area, AreaChart, ComposedChart, Line, ReferenceLine
} from 'recharts';

interface KeyFactor {
  factor: string;
  value: string;
  impact: 'positive' | 'negative' | 'neutral';
}

interface Prediction {
  sector: string;
  sector_name: string;
  up_probability: number;
  down_probability: number;
  neutral_probability: number;
  direction: string;
  confidence: number;
  key_factors: KeyFactor[];
  news_count: number;
  sentiment_score: number;
  model_accuracy: number;
  generated_at: string;
}

interface ChartDataPoint {
  date: string;
  value?: number | null;
  forecast?: number | null;
  upper?: number | null;
  lower?: number | null;
  type?: string;
  volume?: number;
}

interface ChartData {
  sector: string;
  sector_name: string;
  data: ChartDataPoint[];
  total_return_pct: number;
  historical_count: number;
  forecast_count: number;
}

interface NewsItem {
  title: string;
  source: string;
  url: string;
  published_at: string;
  sentiment_score: number;
  sentiment_label: string;
  sectors: string[];
}

interface DashboardData {
  status: string;
  predictions: Prediction[];
  market_overview: {
    avg_up_probability: number;
    market_sentiment: string;
    sectors_analyzed: number;
    most_bullish: string;
    most_bearish: string;
    total_news: number;
  };
  last_updated: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ===== 時間範圍選項 =====
const TIME_RANGES = [
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '1年', value: 365 },
];

// ===== 走勢圖組件(含預測區間 + 時間切換) =====
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
      .catch(err => {
        console.error(`Chart fetch error for ${sector}:`, err);
        setLoading(false);
      });
  }, [sector, days, showForecast]);

  if (loading) {
    return (
      <div className="h-32 flex items-center justify-center">
        <div className="text-slate-500 text-xs">載入圖表中...</div>
      </div>
    );
  }

  if (!chartData || !chartData.data || chartData.data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center">
        <div className="text-slate-500 text-xs">暫無走勢數據</div>
      </div>
    );
  }

  const isPositive = chartData.total_return_pct >= 0;
  const lineColor = isPositive ? '#22c55e' : '#ef4444';
  const forecastColor = '#3b82f6';
  const gradientId = `gradient-${sector}`;
  const forecastGradientId = `forecast-gradient-${sector}`;

  // 找出歷史和預測的分界日期
  const historicalData = chartData.data.filter(d => d.type === 'historical');
  const separatorDate = historicalData.length > 0 
    ? historicalData[historicalData.length - 1].date 
    : null;

  return (
    <div className="mt-3">
      {/* 頂部:標題和回報率 */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-slate-500">
          {days} 天走勢 {showForecast && chartData.forecast_count > 0 && '+ 預測'}
        </span>
        <span className={`text-xs font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {isPositive ? '+' : ''}{chartData.total_return_pct.toFixed(2)}%
        </span>
      </div>

      {/* 圖表 */}
      <ResponsiveContainer width="100%" height={120}>
        <ComposedChart 
          data={chartData.data} 
          margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
          onClick={() => {}}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.4} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
            <linearGradient id={forecastGradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={forecastColor} stopOpacity={0.3} />
              <stop offset="100%" stopColor={forecastColor} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" hide />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '12px',
              padding: '8px',
            }}
            labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
            formatter={(value: any, name: string) => {
              if (value === null || value === undefined) return null;
              const labels: { [key: string]: string } = {
                value: '歷史指數',
                forecast: '預測值',
                upper: '預測上限',
                lower: '預測下限',
              };
              return [Number(value).toFixed(2), labels[name] || name];
            }}
            labelFormatter={(label) => new Date(label).toLocaleDateString('zh-HK')}
          />
          
          {/* 預測區間陰影 */}
          {showForecast && (
            <>
              <Area
                type="monotone"
                dataKey="upper"
                stroke="none"
                fill={`url(#${forecastGradientId})`}
                connectNulls
              />
              <Area
                type="monotone"
                dataKey="lower"
                stroke="none"
                fill="#0f172a"
                connectNulls
              />
            </>
          )}
          
          {/* 歷史走勢(填充區域) */}
          <Area
            type="monotone"
            dataKey="value"
            stroke={lineColor}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            connectNulls={false}
          />
          
          {/* 預測線(虛線) */}
          {showForecast && (
            <Line
              type="monotone"
              dataKey="forecast"
              stroke={forecastColor}
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
              connectNulls
            />
          )}
          
          {/* 歷史/預測分界線 */}
          {showForecast && separatorDate && (
            <ReferenceLine 
              x={separatorDate} 
              stroke="#64748b" 
              strokeDasharray="2 2"
              label={{ value: '今日', position: 'top', fill: '#94a3b8', fontSize: 10 }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* 時間切換按鈕 */}
      <div className="flex items-center justify-between mt-2 gap-1">
        <div className="flex gap-1">
          {TIME_RANGES.map(range => (
            <button
              key={range.value}
              onClick={(e) => {
                e.stopPropagation();
                setDays(range.value);
              }}
              className={`px-2 py-0.5 text-xs rounded transition ${
                days === range.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowForecast(!showForecast);
          }}
          className={`px-2 py-0.5 text-xs rounded transition ${
            showForecast
              ? 'bg-blue-600/30 text-blue-300 border border-blue-500/50'
              : 'bg-slate-800 text-slate-500'
          }`}
        >
          🔮 預測
        </button>
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
  const [activeTab, setActiveTab] = useState<'predictions' | 'news'>('predictions');
  const [selectedSector, setSelectedSector] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard`);
      const data = await res.json();
      setDashboard(data);
      setError(null);
    } catch (err) {
      setError('無法連接到伺服器。請確保後端正在運行。');
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/news?limit=100`);
      const data = await res.json();
      setNews(data.news || []);
    } catch (err) {
      console.error('News fetch error:', err);
    }
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${API_URL}/refresh`, { method: 'POST' });
      setTimeout(() => {
        fetchDashboard();
        fetchNews();
        setRefreshing(false);
      }, 30000);
    } catch (err) {
      console.error('Refresh error:', err);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    fetchNews();
    const interval = setInterval(() => {
      fetchDashboard();
      fetchNews();
    }, 120000);
    return () => clearInterval(interval);
  }, [fetchDashboard, fetchNews]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-16 h-16 text-blue-500 animate-pulse mx-auto mb-4" />
          <h2 className="text-white text-2xl font-bold mb-2">AI 股票預測系統</h2>
          <p className="text-slate-400">正在載入數據...</p>
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
          <button
            onClick={() => { setLoading(true); fetchDashboard(); }}
            className="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
          >
            重試
          </button>
        </div>
      </div>
    );
  }

  const predictions = dashboard?.predictions || [];
  const overview = dashboard?.market_overview;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-xl font-bold">📈 AI 股票預測系統</h1>
              <p className="text-slate-500 text-xs flex items-center gap-1">
                <Clock className="w-3 h-3" />
                更新: {dashboard?.last_updated 
                  ? new Date(dashboard.last_updated).toLocaleString('zh-HK')
                  : '等待中'}
              </p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 px-4 py-2 rounded-lg text-sm transition"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? '刷新中...' : '刷新數據'}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {overview && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            <div className="bg-slate-900 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-500 text-xs mb-1">市場情緒</p>
              <p className={`text-lg font-bold ${
                overview.market_sentiment === 'bullish' ? 'text-green-400' :
                overview.market_sentiment === 'bearish' ? 'text-red-400' : 'text-yellow-400'
              }`}>
                {overview.market_sentiment === 'bullish' ? '🟢 看漲' :
                 overview.market_sentiment === 'bearish' ? '🔴 看跌' : '🟡 中性'}
              </p>
            </div>
            <div className="bg-slate-900 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-500 text-xs mb-1">平均上升機率</p>
              <p className="text-lg font-bold text-blue-400">
                {(overview.avg_up_probability * 100).toFixed(1)}%
              </p>
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

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('predictions')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition ${
              activeTab === 'predictions' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <BarChart3 className="w-4 h-4" /> 預測結果
          </button>
          <button
            onClick={() => setActiveTab('news')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition ${
              activeTab === 'news' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Newspaper className="w-4 h-4" /> 新聞動態 ({news.length})
          </button>
        </div>

        {activeTab === 'predictions' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {predictions.map((pred) => (
              <div
                key={pred.sector}
                onClick={() => setSelectedSector(selectedSector === pred.sector ? null : pred.sector)}
                className={`rounded-xl p-5 border-l-4 cursor-pointer transition-all bg-slate-900 hover:scale-[1.01] ${
                  pred.direction === 'UP' ? 'border-green-500' :
                  pred.direction === 'DOWN' ? 'border-red-500' : 'border-yellow-500'
                } ${selectedSector === pred.sector ? 'ring-2 ring-blue-500' : ''}`}
              >
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

                {/* ⭐ 走勢圖 + 預測區間 + 時間切換 */}
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

                {pred.key_factors && pred.key_factors.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-800">
                    {pred.key_factors.slice(0, 2).map((f, i) => (
                      <div key={i} className="flex items-center gap-1 text-xs text-slate-400 mt-1">
                        {f.impact === 'positive' ? <ArrowUpRight className="w-3 h-3 text-green-400" /> :
                         f.impact === 'negative' ? <ArrowDownRight className="w-3 h-3 text-red-400" /> :
                         <Minus className="w-3 h-3 text-slate-500" />}
                        <span>{f.factor}: {f.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {activeTab === 'news' && (
          <div className="space-y-2">
            {news.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <Newspaper className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>暫無新聞數據</p>
              </div>
            ) : (
              news.map((item, idx) => (
                <div key={idx} className="bg-slate-900 rounded-lg p-4 border border-slate-800 hover:border-slate-700 transition">
                  <div className="flex justify-between items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <a href={item.url} target="_blank" rel="noopener noreferrer"
                         className="text-blue-400 hover:text-blue-300 text-sm font-medium block">
                        {item.title}
                      </a>
                      <div className="flex items-center gap-2 mt-1.5 text-xs text-slate-500 flex-wrap">
                        <span>{item.source}</span>
                        <span>•</span>
                        <span>{new Date(item.published_at).toLocaleDateString('zh-HK')}</span>
                        {item.sectors?.length > 0 && (
                          <>
                            <span>•</span>
                            {item.sectors.slice(0, 2).map(s => (
                              <span key={s} className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">{s}</span>
                            ))}
                          </>
                        )}
                      </div>
                    </div>
                    <span className={`px-2 py-1 rounded-full text-xs whitespace-nowrap ${
                      item.sentiment_label === 'bullish' ? 'bg-green-500/20 text-green-400' :
                      item.sentiment_label === 'bearish' ? 'bg-red-500/20 text-red-400' :
                      'bg-slate-700 text-slate-400'
                    }`}>
                      {item.sentiment_label === 'bullish' ? '↑看漲' :
                       item.sentiment_label === 'bearish' ? '↓看跌' : '→中性'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>

      <footer className="bg-slate-900 border-t border-slate-800 mt-12 px-4 py-4">
        <div className="max-w-7xl mx-auto flex items-start gap-2 text-yellow-600 text-xs">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <p>
            <strong>免責聲明:</strong>本系統的預測結果僅供參考,不構成任何投資建議。
            預測區間基於歷史波動率計算(87% 信心區間),不保證未來實際表現。
          </p>
        </div>
      </footer>
    </div>
  );
}