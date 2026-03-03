import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Eye, Tags, HeartPulse, Wrench, CheckCircle2, AlertTriangle, Info, ChevronRight } from 'lucide-react';
import { mockColumns, mockQualityIssues, mockSampleData } from '@/data/mockData';
import type { DataPrepStep, QualityIssue } from '@/types';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const CHART_COLORS = ['#004AAC', '#FF7E51', '#FFAE41', '#4995FF', '#FFC982', '#A1E6FF'];

const navSteps: { key: DataPrepStep; icon: typeof Upload; label: string }[] = [
  { key: 'upload', icon: Upload, label: 'Upload' },
  { key: 'preview', icon: Eye, label: 'Aperçu & Profil' },
  { key: 'metadata', icon: Tags, label: 'Métadonnées' },
  { key: 'quality', icon: HeartPulse, label: 'Qualité des données' },
  { key: 'corrections', icon: Wrench, label: 'Corrections' },
  { key: 'validation', icon: CheckCircle2, label: 'Validation finale' },
];

export default function DataPreparation() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { dataPreparationStep, setDataPrepStep, setDataset, dataset, projects, updateProject, applyCorrection } = useAppStore();
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(dataset.fileName !== '');
  const [selectedIssue, setSelectedIssue] = useState<string | null>(null);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [correctionsApplied, setCorrApplied] = useState(false);
  const [trainingStarted, setTrainingStarted] = useState(false);
  const [trainingStep, setTrainingStep] = useState(0);

  const project = projects.find((p) => p.id === id);
  const step = dataPreparationStep;

  const onDrop = useCallback((files: File[]) => {
    if (files.length === 0) return;
    setUploading(true);
    setTimeout(() => {
      setUploading(false);
      setUploaded(true);
      setDataset({
        fileName: 'customers.csv',
        rowCount: 42312,
        columnCount: 15,
        columns: mockColumns,
        qualityScore: 78,
        qualityIssues: mockQualityIssues,
        detectedSector: project?.sector || 'finance',
      });
      if (id) updateProject(id, { rowCount: 42312, columnCount: 15, fileName: 'customers.csv', pipelineProgress: 25 });
    }, 1500);
  }, [id]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/json': ['.json'] } });

  const severityIcon = (s: string) => s === 'critical' ? <AlertTriangle className="h-4 w-4 text-dxc-red" /> : s === 'warning' ? <AlertTriangle className="h-4 w-4 text-dxc-gold" /> : <Info className="h-4 w-4 text-dxc-blue" />;
  const severityBadge = (s: string) => s === 'critical' ? 'bg-dxc-red/15 text-dxc-red border-dxc-red/30' : s === 'warning' ? 'bg-dxc-gold/15 text-dxc-gold border-dxc-gold/30' : 'bg-dxc-blue/15 text-dxc-blue border-dxc-blue/30';
  const severityLabel = (s: string) => s === 'critical' ? '🔴 Critique' : s === 'warning' ? '🟡 Avertissement' : '🔵 Info';

  const correctionOptions: Record<string, { label: string; value: string }[]> = {
    missing: [
      { label: '🔢 Imputation par médiane (recommandé)', value: 'median' },
      { label: '📊 Imputation par moyenne', value: 'mean' },
      { label: '🏷️ Imputation par mode', value: 'mode' },
      { label: '❌ Supprimer les lignes concernées', value: 'drop' },
      { label: '⏭️ Ignorer', value: 'ignore' },
    ],
    duplicates: [
      { label: '✅ Supprimer (garder première)', value: 'keep_first' },
      { label: '✅ Supprimer (garder dernière)', value: 'keep_last' },
      { label: '⏭️ Ignorer', value: 'ignore' },
    ],
    outliers: [
      { label: '✂️ Clipper 1%-99%', value: 'clip_1_99' },
      { label: '✂️ Clipper 5%-95%', value: 'clip_5_95' },
      { label: '🔄 Remplacer par médiane', value: 'median' },
      { label: '⏭️ Ignorer', value: 'ignore' },
    ],
    imbalance: [
      { label: '⚖️ Oversampling SMOTE', value: 'smote' },
      { label: '⚖️ Undersampling', value: 'undersample' },
      { label: '📏 Pondération des classes', value: 'class_weight' },
      { label: '⏭️ Ignorer', value: 'ignore' },
    ],
    correlation: [
      { label: '🗑️ Supprimer la moins informative', value: 'drop_least' },
      { label: '➕ Garder les deux (PCA)', value: 'pca' },
      { label: '⏭️ Ignorer', value: 'ignore' },
    ],
  };

  const handleApplyCorrections = () => {
    setCorrApplied(true);
    Object.entries(corrections).forEach(([issueId, method]) => {
      if (method !== 'ignore') applyCorrection({ issueId, method, impact: 'Applied' });
    });
    if (id) updateProject(id, { qualityScore: 96, pipelineProgress: 60 });
    setDataset({ qualityScore: 96 });
  };

  const handleStartTraining = () => {
    setTrainingStarted(true);
    const steps = ['🔍 Agent Secteur — Détection du secteur...', '📊 Agent Data — Préparation des features...', '🤖 Agent ML — Entraînement du modèle XGBoost...', '📈 Agent Évaluation — Calcul des métriques...', '💡 Agent Insights — Génération des explications...', '✅ Pipeline terminé !'];
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setTrainingStep(i);
      if (i >= steps.length) {
        clearInterval(interval);
        if (id) updateProject(id, { status: 'analysis', pipelineProgress: 100, algorithm: 'XGBoost', qualityScore: 96 });
        setTimeout(() => navigate(`/app/projects/${id}/analysis`), 1500);
      }
    }, 1200);
  };

  const trainingLabels = ['🔍 Agent Secteur — Détection du secteur...', '📊 Agent Data — Préparation des features...', '🤖 Agent ML — Entraînement du modèle XGBoost...', '📈 Agent Évaluation — Calcul des métriques...', '💡 Agent Insights — Génération des explications...', '✅ Pipeline terminé !'];

  const qualityScoreColor = (s: number) => s >= 80 ? 'text-dxc-royal' : s >= 60 ? 'text-dxc-gold' : 'text-dxc-red';

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {/* Sidebar */}
      <div className="w-56 bg-dxc-midnight shrink-0 p-3 overflow-y-auto">
        {navSteps.map((ns) => {
          const isActive = step === ns.key;
          const idx = navSteps.findIndex((n) => n.key === ns.key);
          const currentIdx = navSteps.findIndex((n) => n.key === step);
          const done = idx < currentIdx || (ns.key === 'corrections' && correctionsApplied);
          return (
            <button key={ns.key} onClick={() => setDataPrepStep(ns.key)}
              className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg mb-1 text-left text-sm transition-colors ${isActive ? 'bg-dxc-royal text-dxc-white' : done ? 'text-dxc-white/80 hover:bg-dxc-royal/20' : 'text-dxc-white/40 hover:bg-dxc-royal/10'}`}>
              {done ? <CheckCircle2 className="h-4 w-4 text-dxc-sky shrink-0" /> : <ns.icon className="h-4 w-4 shrink-0" />}
              <span className="truncate">{ns.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* UPLOAD */}
        {step === 'upload' && (
          <div>
            <h2 className="text-xl font-bold text-foreground mb-6">Upload de vos données</h2>
            {!uploaded ? (
              <div {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-16 text-center cursor-pointer transition-colors ${isDragActive ? 'border-dxc-royal bg-dxc-royal/5' : 'border-dxc-sky bg-card'}`}>
                <input {...getInputProps()} />
                {uploading ? (
                  <div className="flex flex-col items-center">
                    <div className="h-12 w-12 border-4 border-dxc-royal border-t-transparent rounded-full animate-spin mb-4" />
                    <p className="font-bold text-foreground">Traitement en cours...</p>
                  </div>
                ) : (
                  <>
                    <Upload className="h-12 w-12 text-dxc-royal mx-auto mb-4" />
                    <p className="font-bold text-lg text-foreground mb-1">Glissez votre fichier ici</p>
                    <p className="text-dxc-royal/60 text-sm mb-4">CSV, Excel (.xlsx), JSON — max 100 MB</p>
                    <span className="inline-block bg-dxc-royal text-dxc-white px-5 py-2 rounded-lg font-medium text-sm">Parcourir mes fichiers</span>
                  </>
                )}
              </div>
            ) : (
              <div className="bg-card rounded-xl border border-border p-6">
                <div className="flex items-center gap-3 mb-4">
                  <FileText className="h-8 w-8 text-dxc-royal" />
                  <div>
                    <p className="font-bold text-foreground">{dataset.fileName}</p>
                    <p className="text-sm text-muted-foreground">2.4 MB · ✅ Importé avec succès</p>
                  </div>
                </div>
                <div className="flex gap-2 mb-6">
                  <span className="text-xs bg-dxc-royal/10 text-dxc-royal px-2 py-1 rounded-full font-medium">{dataset.rowCount.toLocaleString()} lignes</span>
                  <span className="text-xs bg-dxc-melon/10 text-dxc-melon px-2 py-1 rounded-full font-medium">{dataset.columnCount} colonnes</span>
                </div>
                <button onClick={() => setDataPrepStep('preview')} className="bg-dxc-melon text-dxc-white px-6 py-2.5 rounded-lg font-bold text-sm hover:opacity-90 transition-opacity">
                  Continuer vers l'aperçu →
                </button>
              </div>
            )}
          </div>
        )}

        {/* PREVIEW */}
        {step === 'preview' && (
          <div>
            <h2 className="text-xl font-bold text-foreground mb-6">Aperçu & Profil des données</h2>
            {/* Sample table */}
            <div className="bg-card rounded-xl border border-border overflow-hidden mb-8">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-dxc-midnight">
                      {mockColumns.slice(0, 8).map((c) => (
                        <th key={c.originalName} className="px-3 py-2 text-left text-dxc-peach font-bold whitespace-nowrap">{c.originalName}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {mockSampleData.slice(0, 10).map((row, i) => (
                      <tr key={i} className={i % 2 === 0 ? 'bg-card' : 'bg-dxc-canvas'}>
                        {Object.values(row).slice(0, 8).map((v, j) => (
                          <td key={j} className="px-3 py-2 whitespace-nowrap text-card-foreground">{v === null ? <span className="text-dxc-red/50">null</span> : String(v)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Column profiles */}
            <h3 className="font-bold text-foreground mb-4">Profil des colonnes</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {mockColumns.map((col) => {
                const completeness = 100 - col.stats.missingPct;
                return (
                  <div key={col.originalName} className="bg-card rounded-xl border border-border p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold text-sm text-card-foreground">{col.originalName}</span>
                      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${col.type === 'target' ? 'bg-dxc-melon/20 text-dxc-melon' : col.type === 'numeric' ? 'bg-dxc-royal/20 text-dxc-royal' : 'bg-dxc-sky/20 text-dxc-blue'}`}>{col.type}</span>
                    </div>
                    {col.stats.min !== undefined && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">min: {col.stats.min}</span>
                        <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">max: {col.stats.max}</span>
                        <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">moy: {col.stats.mean}</span>
                      </div>
                    )}
                    {col.stats.topValues && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {col.stats.topValues.map((v) => (
                          <span key={v} className="text-[10px] bg-dxc-sky/15 text-dxc-blue px-1.5 py-0.5 rounded">{v}</span>
                        ))}
                      </div>
                    )}
                    <div className="mt-2">
                      <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                        <span>Complétude</span><span>{completeness.toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 bg-border rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all" style={{ width: `${completeness}%`, background: completeness > 95 ? '#004AAC' : '#FF7E51' }} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <button onClick={() => setDataPrepStep('metadata')} className="mt-6 bg-dxc-melon text-dxc-white px-6 py-2.5 rounded-lg font-bold text-sm hover:opacity-90">
              Continuer vers les métadonnées →
            </button>
          </div>
        )}

        {/* METADATA */}
        {step === 'metadata' && (
          <div>
            <h2 className="text-xl font-bold text-foreground mb-6">Configuration des métadonnées</h2>
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
              <div className="lg:col-span-3">
                <div className="bg-card rounded-xl border border-border overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-dxc-midnight text-dxc-peach text-xs">
                        <th className="px-3 py-2 text-left">Colonne</th>
                        <th className="px-3 py-2 text-left">Nom métier</th>
                        <th className="px-3 py-2 text-left">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mockColumns.map((col, i) => (
                        <tr key={col.originalName} className={i % 2 === 0 ? 'bg-card' : 'bg-dxc-canvas'}>
                          <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{col.originalName}</td>
                          <td className="px-3 py-2 text-card-foreground font-medium">{col.businessName}</td>
                          <td className="px-3 py-2">
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${col.type === 'target' ? 'bg-dxc-melon/20 text-dxc-melon' : col.type === 'numeric' ? 'bg-dxc-royal/20 text-dxc-royal' : col.type === 'identifier' ? 'bg-muted text-muted-foreground' : 'bg-dxc-sky/20 text-dxc-blue'}`}>
                              {col.type === 'target' ? '🎯 Cible' : col.type === 'numeric' ? '🔢 Numérique' : col.type === 'category' ? '🏷️ Catégorie' : col.type === 'identifier' ? '🆔 ID' : col.type}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="lg:col-span-2">
                <div className="bg-dxc-midnight rounded-xl p-5 text-dxc-white">
                  <h3 className="font-bold mb-3 text-dxc-peach">🧠 Compréhension du système</h3>
                  <ul className="space-y-2 text-sm text-dxc-white/80">
                    <li>📊 <strong>{dataset.rowCount.toLocaleString()}</strong> observations chargées</li>
                    <li>🎯 Variable cible : <span className="text-dxc-melon font-bold">churn</span></li>
                    <li>⚙️ <strong>{mockColumns.filter((c) => c.type === 'numeric' || c.type === 'category' || c.type === 'feature').length}</strong> features détectées</li>
                    <li>🏦 Secteur détecté : <span className="bg-dxc-royal/30 px-2 py-0.5 rounded-full text-dxc-sky text-xs font-medium">{project?.sector}</span></li>
                  </ul>
                </div>
              </div>
            </div>
            <button onClick={() => setDataPrepStep('quality')} className="mt-6 bg-dxc-melon text-dxc-white px-6 py-2.5 rounded-lg font-bold text-sm hover:opacity-90">
              Vérifier la qualité →
            </button>
          </div>
        )}

        {/* QUALITY */}
        {step === 'quality' && (
          <div>
            <h2 className="text-xl font-bold text-foreground mb-6">Qualité des données</h2>
            {/* Score cards */}
            <div className="grid grid-cols-3 gap-4 mb-8">
              {[
                { label: 'Complétude', score: 91 },
                { label: 'Cohérence', score: 84 },
                { label: 'Unicité', score: 97 },
              ].map((s) => (
                <div key={s.label} className="bg-card rounded-xl border border-border p-6 text-center">
                  <div className={`text-3xl font-bold mb-1 ${qualityScoreColor(s.score)}`}>{s.score}%</div>
                  <div className="text-sm text-muted-foreground">{s.label}</div>
                </div>
              ))}
            </div>

            {/* Issues */}
            <h3 className="font-bold text-foreground mb-4">Problèmes détectés</h3>
            <div className="space-y-3 mb-8">
              {mockQualityIssues.map((issue) => (
                <div key={issue.id} className="bg-card rounded-xl border border-border p-4">
                  <div className="flex items-start gap-3">
                    {severityIcon(issue.severity)}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${severityBadge(issue.severity)}`}>{severityLabel(issue.severity)}</span>
                      </div>
                      <h4 className="font-bold text-card-foreground text-sm">{issue.title}</h4>
                      <p className="text-xs text-muted-foreground mt-1">{issue.description}</p>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {issue.affectedColumns.filter((c) => c !== 'all').map((c) => (
                          <span key={c} className="text-[10px] bg-muted px-2 py-0.5 rounded-full text-muted-foreground">{c}</span>
                        ))}
                        {issue.affectedRows > 0 && <span className="text-[10px] text-muted-foreground">{issue.affectedRows.toLocaleString()} lignes concernées</span>}
                      </div>
                    </div>
                    <button onClick={() => { setDataPrepStep('corrections'); setSelectedIssue(issue.id); }}
                      className="bg-dxc-melon text-dxc-white text-xs px-3 py-1.5 rounded-lg font-medium shrink-0 hover:opacity-90">
                      🔧 Corriger
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Distribution chart */}
            <h3 className="font-bold text-foreground mb-4">Distribution de la variable cible</h3>
            <div className="bg-card rounded-xl border border-border p-4 h-48 mb-6">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={[{ name: 'Classe 0 (Non-churn)', value: 38927 }, { name: 'Classe 1 (Churn)', value: 3385 }]}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    <Cell fill="#004AAC" />
                    <Cell fill="#FF7E51" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <button onClick={() => setDataPrepStep('corrections')} className="bg-dxc-melon text-dxc-white px-6 py-2.5 rounded-lg font-bold text-sm hover:opacity-90">
              Configurer les corrections →
            </button>
          </div>
        )}

        {/* CORRECTIONS */}
        {step === 'corrections' && (
          <div>
            <h2 className="text-xl font-bold text-foreground mb-6">Corrections</h2>
            {correctionsApplied ? (
              <div className="bg-card rounded-xl border border-border p-6">
                <h3 className="font-bold text-foreground mb-4 text-lg">✅ Corrections appliquées</h3>
                <div className="grid grid-cols-2 gap-6 text-sm">
                  <div>
                    <p className="text-muted-foreground mb-1">Avant</p>
                    <p className="font-bold text-foreground">{dataset.rowCount.toLocaleString()} lignes</p>
                    <p className="text-dxc-gold">8.3% valeurs nulles</p>
                    <p className="text-dxc-gold">14 outliers</p>
                    <p className="text-dxc-gold">Score : 78%</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1">Après</p>
                    <p className="font-bold text-foreground">41 203 lignes</p>
                    <p className="text-dxc-royal">0.0% valeurs nulles</p>
                    <p className="text-dxc-royal">0 outliers</p>
                    <p className="text-dxc-royal font-bold">Score : 96%</p>
                  </div>
                </div>
                <button onClick={() => setDataPrepStep('validation')} className="mt-6 bg-dxc-melon text-dxc-white px-6 py-2.5 rounded-lg font-bold text-sm hover:opacity-90">
                  Continuer vers la validation →
                </button>
              </div>
            ) : (
              <div className="flex gap-6">
                {/* Issues list */}
                <div className="w-72 shrink-0 space-y-2">
                  {mockQualityIssues.map((issue) => (
                    <button key={issue.id} onClick={() => setSelectedIssue(issue.id)}
                      className={`w-full text-left p-3 rounded-lg border text-sm transition-colors ${selectedIssue === issue.id ? 'border-dxc-royal bg-dxc-royal/5' : 'border-border bg-card hover:border-dxc-royal/30'}`}>
                      <div className="flex items-center gap-2">
                        {severityIcon(issue.severity)}
                        <span className="font-medium text-card-foreground text-xs line-clamp-1">{issue.title}</span>
                      </div>
                      {corrections[issue.id] && corrections[issue.id] !== 'ignore' && (
                        <span className="text-[10px] bg-dxc-royal/15 text-dxc-royal px-2 py-0.5 rounded-full mt-1 inline-block">✅ Configuré</span>
                      )}
                    </button>
                  ))}
                  <div className="pt-4 border-t border-border">
                    <p className="text-xs text-muted-foreground mb-2">{Object.keys(corrections).filter((k) => corrections[k] !== 'ignore').length} corrections configurées</p>
                    <button onClick={handleApplyCorrections} disabled={Object.keys(corrections).length === 0}
                      className="w-full bg-dxc-melon text-dxc-white py-2.5 rounded-lg font-bold text-sm hover:opacity-90 disabled:opacity-40">
                      Appliquer toutes
                    </button>
                  </div>
                </div>

                {/* Detail panel */}
                <div className="flex-1">
                  {selectedIssue ? (() => {
                    const issue = mockQualityIssues.find((i) => i.id === selectedIssue)!;
                    const options = correctionOptions[issue.type] || correctionOptions.missing;
                    return (
                      <div className="bg-card rounded-xl border border-border p-6">
                        <div className="flex items-center gap-2 mb-2">
                          {severityIcon(issue.severity)}
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${severityBadge(issue.severity)}`}>{severityLabel(issue.severity)}</span>
                        </div>
                        <h3 className="font-bold text-card-foreground mb-2">{issue.title}</h3>
                        <p className="text-sm text-muted-foreground mb-6">{issue.description}</p>
                        <div className="space-y-2">
                          {options.map((opt) => (
                            <label key={opt.value} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${corrections[issue.id] === opt.value ? 'border-dxc-royal bg-dxc-royal/5' : 'border-border hover:border-dxc-royal/30'}`}>
                              <input type="radio" name={`correction-${issue.id}`} checked={corrections[issue.id] === opt.value}
                                onChange={() => setCorrections((c) => ({ ...c, [issue.id]: opt.value }))} className="accent-dxc-royal" />
                              <span className="text-sm text-card-foreground">{opt.label}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    );
                  })() : (
                    <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
                      ← Sélectionnez un problème pour configurer sa correction
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* VALIDATION */}
        {step === 'validation' && (
          <div>
            <h2 className="text-xl font-bold text-foreground mb-6">Validation finale</h2>
            {!trainingStarted ? (
              <div className="space-y-6">
                <div className="bg-card rounded-xl border border-border p-6 text-center">
                  <div className={`text-5xl font-bold mb-2 ${qualityScoreColor(dataset.qualityScore || 96)}`}>{dataset.qualityScore || 96}%</div>
                  <p className="text-muted-foreground">Score de qualité final</p>
                </div>
                <div className="bg-card rounded-xl border border-border p-6">
                  <h3 className="font-bold text-foreground mb-3">Résumé</h3>
                  <ul className="space-y-2 text-sm text-card-foreground">
                    <li>📁 Dataset : <strong>{dataset.fileName}</strong></li>
                    <li>📊 {dataset.rowCount.toLocaleString()} lignes × {dataset.columnCount} colonnes</li>
                    <li>🎯 Variable cible : <strong>churn</strong></li>
                    <li>🔧 {dataset.appliedCorrections.length} corrections appliquées</li>
                    <li>🏦 Secteur : <strong>{project?.sector}</strong></li>
                  </ul>
                </div>
                <div className="flex gap-3">
                  <button onClick={() => setDataPrepStep('corrections')} className="border border-dxc-royal text-dxc-royal px-6 py-3 rounded-lg font-medium text-sm hover:bg-dxc-royal/5">
                    Retour aux corrections
                  </button>
                  <button onClick={handleStartTraining} className="flex-1 bg-dxc-melon text-dxc-white py-3 rounded-lg font-bold text-sm hover:opacity-90">
                    🚀 Lancer l'entraînement ML
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-card rounded-xl border border-border p-8">
                <h3 className="font-bold text-foreground mb-6 text-center text-lg">Pipeline en cours...</h3>
                <div className="max-w-md mx-auto space-y-3">
                  {trainingLabels.map((label, i) => (
                    <div key={i} className={`flex items-center gap-3 p-3 rounded-lg transition-all ${i < trainingStep ? 'bg-dxc-royal/10 text-dxc-royal' : i === trainingStep ? 'bg-dxc-melon/10 text-dxc-melon animate-pulse-agent' : 'text-muted-foreground/40'}`}>
                      {i < trainingStep ? <CheckCircle2 className="h-5 w-5 shrink-0" /> : <div className="h-5 w-5 shrink-0 rounded-full border-2 border-current" />}
                      <span className="text-sm font-medium">{label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
