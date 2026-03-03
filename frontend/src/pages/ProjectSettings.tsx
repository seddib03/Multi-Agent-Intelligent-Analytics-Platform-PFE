import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertTriangle } from 'lucide-react';
import type { Density, ChartStyle, AccentTheme } from '@/types';

export default function ProjectSettings() {
  const { id } = useParams<{ id: string }>();
  const { projects, updateProject, deleteProject, userPreferences, updatePreferences } = useAppStore();
  const project = projects.find((p) => p.id === id);
  const [useCase, setUseCase] = useState(project?.useCaseDescription || '');
  const [saved, setSaved] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');

  if (!project) return <div className="p-8 text-center text-muted-foreground">Projet introuvable</div>;

  const handleSaveUseCase = () => {
    updateProject(id!, { useCaseDescription: useCase });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-xl font-bold text-foreground">{project.title}</h1>
        <span className="text-xs bg-dxc-royal/15 text-dxc-royal px-2 py-0.5 rounded-full font-medium">{project.sector}</span>
      </div>

      <Tabs defaultValue="usecase">
        <TabsList className="bg-muted mb-6">
          <TabsTrigger value="usecase">Use Case</TabsTrigger>
          <TabsTrigger value="dataset">Dataset</TabsTrigger>
          <TabsTrigger value="preferences">Préférences</TabsTrigger>
          <TabsTrigger value="danger">Danger Zone</TabsTrigger>
        </TabsList>

        <TabsContent value="usecase" className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1 block">Description du use case</label>
            <Textarea value={useCase} onChange={(e) => setUseCase(e.target.value)} rows={4} />
          </div>
          <div className="bg-dxc-gold/10 border border-dxc-gold/30 rounded-lg p-3 text-sm text-dxc-gold flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            Modifier le use case peut changer le secteur détecté et nécessitera de relancer l'entraînement ML.
          </div>
          <button onClick={handleSaveUseCase} className="bg-dxc-royal text-dxc-white px-5 py-2.5 rounded-lg font-medium text-sm hover:bg-dxc-blue transition-colors">
            {saved ? '✅ Sauvegardé !' : 'Sauvegarder le use case'}
          </button>
        </TabsContent>

        <TabsContent value="dataset" className="space-y-4">
          <div className="bg-card rounded-xl border border-border p-5">
            <h3 className="font-bold text-card-foreground mb-2">Dataset actuel</h3>
            <p className="text-sm text-muted-foreground">{project.fileName || 'Aucun dataset'} · {project.rowCount.toLocaleString()} lignes · Score qualité : {project.qualityScore}%</p>
          </div>
          <div className="flex gap-3">
            <Link to={`/app/projects/${id}/data`} className="border border-dxc-royal text-dxc-royal px-5 py-2.5 rounded-lg font-medium text-sm hover:bg-dxc-royal/5">
              Éditer les métadonnées
            </Link>
            <Link to={`/app/projects/${id}/data`} className="border border-dxc-royal text-dxc-royal px-5 py-2.5 rounded-lg font-medium text-sm hover:bg-dxc-royal/5">
              Retourner à la préparation
            </Link>
          </div>
        </TabsContent>

        <TabsContent value="preferences" className="space-y-6">
          <div>
            <label className="text-sm font-medium mb-2 block">Mode</label>
            <div className="flex gap-2">
              {[false, true].map((dark) => (
                <button key={String(dark)} onClick={() => {
                  updatePreferences({ darkMode: dark });
                  document.documentElement.classList.toggle('dark', dark);
                }}
                  className={`px-4 py-2 rounded-lg text-sm border transition-colors ${userPreferences.darkMode === dark ? 'border-dxc-royal bg-dxc-royal/10 text-foreground font-medium' : 'border-border text-muted-foreground hover:border-dxc-royal/30'}`}>
                  {dark ? '🌙 Sombre' : '☀️ Clair'}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Style de graphiques</label>
            <div className="flex gap-2">
              {(['bar', 'line', 'area'] as ChartStyle[]).map((s) => (
                <button key={s} onClick={() => updatePreferences({ chartStyle: s })}
                  className={`px-4 py-2 rounded-lg text-sm border capitalize transition-colors ${userPreferences.chartStyle === s ? 'border-dxc-royal bg-dxc-royal/10 text-foreground font-medium' : 'border-border text-muted-foreground hover:border-dxc-royal/30'}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Densité</label>
            <div className="flex gap-2">
              {(['simplified', 'standard', 'expert'] as Density[]).map((d) => (
                <button key={d} onClick={() => updatePreferences({ density: d })}
                  className={`px-4 py-2 rounded-lg text-sm border capitalize transition-colors ${userPreferences.density === d ? 'border-dxc-royal bg-dxc-royal/10 text-foreground font-medium' : 'border-border text-muted-foreground hover:border-dxc-royal/30'}`}>
                  {d === 'simplified' ? 'Simplifié' : d === 'standard' ? 'Standard' : 'Expert'}
                </button>
              ))}
            </div>
          </div>

          <button className="bg-dxc-royal text-dxc-white px-5 py-2.5 rounded-lg font-medium text-sm hover:bg-dxc-blue transition-colors">
            Sauvegarder
          </button>
        </TabsContent>

        <TabsContent value="danger">
          <div className="bg-dxc-canvas border border-dxc-red rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-bold text-card-foreground">Archiver ce projet</p>
                <p className="text-xs text-muted-foreground">Désactive sans supprimer</p>
              </div>
              <button onClick={() => updateProject(id!, { status: 'archived' })} className="border border-dxc-gold text-dxc-gold px-4 py-2 rounded-lg text-sm font-medium hover:bg-dxc-gold/10">
                Archiver
              </button>
            </div>
            <div className="border-t border-dxc-red/20" />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-bold text-card-foreground">Supprimer ce projet</p>
                <p className="text-xs text-muted-foreground">Irréversible</p>
              </div>
              <div className="flex items-center gap-2">
                <Input value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} placeholder={project.title} className="w-40 text-xs" />
                <button onClick={() => { if (deleteConfirm === project.title) deleteProject(id!); }}
                  disabled={deleteConfirm !== project.title}
                  className="bg-dxc-red text-dxc-white px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-40">
                  Supprimer
                </button>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
