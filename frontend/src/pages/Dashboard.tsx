import { useParams, Link } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { mockModelResults } from '@/data/mockData';
import { RefreshCw, Download, Settings, Database, TrendingUp, TrendingDown, Users, AlertTriangle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';

const CHART_COLORS = ['#004AAC', '#FF7E51', '#FFAE41', '#4995FF', '#FFC982', '#A1E6FF'];

export default function Dashboard() {
  const { id } = useParams<{ id: string }>();
  const { projects, userPreferences, pinnedInsights } = useAppStore();
  const project = projects.find((p) => p.id === id);
  const { density, chartStyle } = userPreferences;

  const kpis = [
    { label: 'AUC Score', value: mockModelResults.auc.toFixed(3), trend: '+2.1%', up: true, icon: TrendingUp, color: '#004AAC' },
    { label: 'Accuracy', value: `${(mockModelResults.accuracy * 100).toFixed(1)}%`, trend: '+1.3%', up: true, icon: TrendingUp, color: '#4995FF' },
    { label: 'F1 Score', value: mockModelResults.f1Score.toFixed(3), trend: '-0.5%', up: false, icon: TrendingDown, color: '#FF7E51' },
    { label: 'Clients à risque', value: '2,847', trend: '+12%', up: true, icon: AlertTriangle, color: '#FFAE41' },
    { label: 'Prédictions totales', value: '42,312', trend: '', up: true, icon: Users, color: '#004AAC' },
    { label: 'Risque moyen', value: '23.4%', trend: '-3.2%', up: false, icon: TrendingDown, color: '#FF7E51' },
  ];

  const visibleKpis = density === 'simplified' ? kpis.slice(0, 4) : density === 'standard' ? kpis.slice(0, 6) : kpis;

  const featureData = mockModelResults.featureImportance.map((f) => ({ name: f.feature, value: +(f.importance * 100).toFixed(1) }));
  const trendData = Array.from({ length: 12 }, (_, i) => ({ month: ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'][i], churn: +(Math.random() * 15 + 5).toFixed(1), retention: +(Math.random() * 20 + 75).toFixed(1) }));
  const riskDistribution = [{ name: 'Faible (<30%)', value: 31200 }, { name: 'Moyen (30-70%)', value: 8265 }, { name: 'Élevé (>70%)', value: 2847 }];

  const renderChart = (data: Record<string, unknown>[], type: string) => {
    switch (type) {
      case 'line': return <LineChart data={data}><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip /><Line type="monotone" dataKey="value" stroke="#004AAC" strokeWidth={2} dot={false} /></LineChart>;
      case 'area': return <AreaChart data={data}><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip /><Area type="monotone" dataKey="value" fill="#004AAC" fillOpacity={0.15} stroke="#004AAC" strokeWidth={2} /></AreaChart>;
      default: return <BarChart data={data}><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="value" radius={[6, 6, 0, 0]}>{data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}</Bar></BarChart>;
    }
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">{project?.title || 'Dashboard'}</h1>
          <div className="flex gap-2 mt-1">
            <span className="text-[10px] bg-dxc-royal/15 text-dxc-royal px-2 py-0.5 rounded-full font-medium">{project?.sector}</span>
            <span className="text-[10px] bg-dxc-melon/15 text-dxc-melon px-2 py-0.5 rounded-full font-medium">{project?.algorithm}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Link to={`/app/projects/${id}/data`} className="border border-border text-muted-foreground hover:text-foreground px-3 py-2 rounded-lg text-xs inline-flex items-center gap-1"><Database className="h-3.5 w-3.5" /> Données</Link>
          <Link to={`/app/projects/${id}/settings`} className="border border-border text-muted-foreground hover:text-foreground px-3 py-2 rounded-lg text-xs inline-flex items-center gap-1"><Settings className="h-3.5 w-3.5" /> Paramètres</Link>
          <button className="border border-border text-muted-foreground hover:text-foreground px-3 py-2 rounded-lg text-xs inline-flex items-center gap-1"><RefreshCw className="h-3.5 w-3.5" /> Rafraîchir</button>
          <button className="bg-dxc-royal text-dxc-white px-3 py-2 rounded-lg text-xs inline-flex items-center gap-1 font-medium"><Download className="h-3.5 w-3.5" /> Exporter</button>
        </div>
      </div>

      {/* KPIs */}
      <div className={`grid gap-4 mb-6 ${density === 'simplified' ? 'grid-cols-2 md:grid-cols-4' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-6'}`}>
        {visibleKpis.map((kpi, i) => (
          <div key={i} className="bg-card rounded-xl border border-border p-4" style={{ borderLeftWidth: 4, borderLeftColor: kpi.color }}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">{kpi.label}</span>
              <kpi.icon className="h-3.5 w-3.5" style={{ color: kpi.color }} />
            </div>
            <div className="text-2xl font-bold text-card-foreground">{kpi.value}</div>
            {kpi.trend && <span className={`text-[10px] font-medium ${kpi.up ? 'text-dxc-royal' : 'text-dxc-melon'}`}>{kpi.trend}</span>}
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className={`grid gap-4 mb-6 ${density === 'simplified' ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-2'}`}>
        <div className="bg-card rounded-xl border border-border p-4">
          <h3 className="font-bold text-card-foreground text-sm mb-4">Importance des features</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              {renderChart(featureData as any, chartStyle)}
            </ResponsiveContainer>
          </div>
        </div>

        {density !== 'simplified' && (
          <div className="bg-card rounded-xl border border-border p-4">
            <h3 className="font-bold text-card-foreground text-sm mb-4">Distribution du risque</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={riskDistribution} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {riskDistribution.map((_, i) => <Cell key={i} fill={CHART_COLORS[i]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {density === 'expert' && (
          <div className="bg-card rounded-xl border border-border p-4 lg:col-span-2">
            <h3 className="font-bold text-card-foreground text-sm mb-4">Tendance du churn (12 mois)</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="churn" fill="#FF7E51" fillOpacity={0.15} stroke="#FF7E51" strokeWidth={2} />
                  <Area type="monotone" dataKey="retention" fill="#004AAC" fillOpacity={0.1} stroke="#004AAC" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Top risky entities */}
      {density !== 'simplified' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <div className="p-4 border-b border-border">
            <h3 className="font-bold text-card-foreground text-sm">Top 5 clients à risque</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-dxc-midnight text-dxc-peach text-xs">
                <th className="px-4 py-2 text-left">ID</th>
                <th className="px-4 py-2 text-left">Client</th>
                <th className="px-4 py-2 text-left">Risque</th>
                <th className="px-4 py-2 text-left">Facteurs</th>
              </tr>
            </thead>
            <tbody>
              {mockModelResults.topRiskyEntities.map((entity, i) => (
                <tr key={entity.id} className={i % 2 === 0 ? 'bg-card' : 'bg-dxc-canvas'}>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{entity.id}</td>
                  <td className="px-4 py-2.5 text-card-foreground font-medium">{entity.name}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${entity.risk * 100}%`, background: entity.risk > 0.8 ? '#D14600' : entity.risk > 0.5 ? '#FF7E51' : '#004AAC' }} />
                      </div>
                      <span className="text-xs font-bold" style={{ color: entity.risk > 0.8 ? '#D14600' : '#FF7E51' }}>{(entity.risk * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {entity.factors.map((f) => <span key={f} className="text-[10px] bg-dxc-gold/15 text-dxc-gold px-2 py-0.5 rounded-full">{f}</span>)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pinned insights */}
      {pinnedInsights.length > 0 && (
        <div className="mt-6">
          <h3 className="font-bold text-foreground text-sm mb-3">📌 Insights épinglés</h3>
          <div className="space-y-2">
            {pinnedInsights.map((msg) => (
              <div key={msg.id} className="bg-card rounded-xl border-l-4 border-l-dxc-melon border border-border p-4 text-sm text-card-foreground line-clamp-3">
                {msg.content.slice(0, 200)}...
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
