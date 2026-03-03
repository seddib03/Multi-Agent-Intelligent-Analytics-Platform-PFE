import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { detectSector } from '@/data/mockData';
import type { AnalysisType, Sector } from '@/types';

const analysisTypes: { value: AnalysisType; label: string; desc: string }[] = [
  { value: 'classification', label: '🎯 Classification', desc: 'Prédire une catégorie (churn oui/non, fraude, etc.)' },
  { value: 'regression', label: '📈 Régression', desc: 'Prédire une valeur numérique (prix, quantité, etc.)' },
  { value: 'clustering', label: '🔬 Clustering', desc: 'Segmenter vos données en groupes' },
  { value: 'timeseries', label: '📅 Séries temporelles', desc: 'Prédire des tendances futures' },
];

export default function NewProject() {
  const [title, setTitle] = useState('');
  const [useCase, setUseCase] = useState('');
  const [type, setType] = useState<AnalysisType>('classification');
  const [timeHorizon, setTimeHorizon] = useState('3 mois');
  const { addProject } = useAppStore();
  const navigate = useNavigate();

  const detectedSector = detectSector(useCase) as Sector;
  const sectorLabels: Record<string, string> = { finance: '🏦 Finance', transport: '🚌 Transport', retail: '🛍️ Retail', manufacturing: '🏭 Manufacturing', public: '🏛️ Public' };

  const handleCreate = () => {
    if (!title || !useCase) return;
    const id = 'proj-' + Date.now();
    addProject({
      id, title, useCaseDescription: useCase, analysisType: type, timeHorizon,
      sector: detectedSector, status: 'preparation', createdAt: new Date().toISOString().split('T')[0],
      rowCount: 0, columnCount: 0, algorithm: '', fileName: '', qualityScore: 0, pipelineProgress: 5,
    });
    navigate(`/app/projects/${id}/data`);
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-foreground mb-2">Nouveau Projet</h1>
      <p className="text-muted-foreground mb-8">Décrivez votre besoin et le système configurera l'analyse automatiquement</p>

      <div className="space-y-6">
        <div>
          <label className="text-sm font-medium mb-1 block">Nom du projet</label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Ex: Prédiction du churn client Q1" />
        </div>

        <div>
          <label className="text-sm font-medium mb-1 block">Décrivez votre cas d'usage</label>
          <Textarea value={useCase} onChange={(e) => setUseCase(e.target.value)} rows={4} placeholder="Ex: Je veux prédire quels clients vont résilier leur abonnement dans les 3 prochains mois en me basant sur leur historique d'utilisation..." />
          {useCase.length > 10 && (
            <div className="mt-2 inline-flex items-center gap-2 bg-dxc-royal/10 text-dxc-royal text-xs px-3 py-1.5 rounded-full font-medium">
              Secteur détecté : {sectorLabels[detectedSector]}
            </div>
          )}
        </div>

        <div>
          <label className="text-sm font-medium mb-2 block">Type d'analyse</label>
          <div className="grid grid-cols-2 gap-3">
            {analysisTypes.map((a) => (
              <button key={a.value} onClick={() => setType(a.value)}
                className={`p-4 rounded-xl border text-left transition-all ${type === a.value ? 'border-dxc-royal bg-dxc-royal/5 shadow-sm' : 'border-border hover:border-dxc-royal/30'}`}>
                <p className="font-bold text-sm mb-1">{a.label}</p>
                <p className="text-xs text-muted-foreground">{a.desc}</p>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-sm font-medium mb-1 block">Horizon temporel</label>
          <Input value={timeHorizon} onChange={(e) => setTimeHorizon(e.target.value)} placeholder="Ex: 3 mois, 1 semaine..." />
        </div>

        <button onClick={handleCreate} disabled={!title || !useCase}
          className="w-full bg-dxc-melon text-dxc-white py-3.5 rounded-lg font-bold hover:opacity-90 transition-opacity disabled:opacity-40">
          Créer le projet et uploader les données →
        </button>
      </div>
    </div>
  );
}
