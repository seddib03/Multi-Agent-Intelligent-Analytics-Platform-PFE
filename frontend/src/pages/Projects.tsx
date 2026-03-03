import { Link, useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { Plus, BarChart2, Database, LineChart, MoreVertical, FolderOpen } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import type { ProjectStatus } from '@/types';

const statusConfig: Record<ProjectStatus, { label: string; className: string }> = {
  preparation: { label: 'En préparation', className: 'bg-dxc-gold/20 text-dxc-gold border-dxc-gold/30' },
  ready: { label: 'Prêt', className: 'bg-dxc-royal/20 text-dxc-royal border-dxc-royal/30' },
  analysis: { label: 'En analyse', className: 'bg-dxc-melon/20 text-dxc-melon border-dxc-melon/30' },
  archived: { label: 'Archivé', className: 'bg-muted text-muted-foreground border-border' },
};

const sectorLabels: Record<string, string> = { finance: '🏦 Finance', transport: '🚌 Transport', retail: '🛍️ Retail', manufacturing: '🏭 Manufacturing', public: '🏛️ Public' };

export default function Projects() {
  const { projects, currentUser, deleteProject, updateProject } = useAppStore();
  const navigate = useNavigate();

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Mes Projets</h1>
          <p className="text-sm text-dxc-royal italic mt-1">Entreprise : {currentUser?.company}</p>
        </div>
        <Link to="/app/projects/new" className="bg-dxc-melon text-dxc-white px-5 py-2.5 rounded-lg font-bold text-sm hover:opacity-90 transition-opacity inline-flex items-center gap-2">
          <Plus className="h-4 w-4" /> Nouveau Projet
        </Link>
      </div>

      {projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <FolderOpen className="h-16 w-16 text-muted-foreground/30 mb-4" />
          <h2 className="text-xl font-bold text-foreground mb-2">Aucun projet</h2>
          <p className="text-muted-foreground mb-6">Créez votre premier projet d'analyse prédictive</p>
          <Link to="/app/projects/new" className="bg-dxc-melon text-dxc-white px-6 py-3 rounded-lg font-bold hover:opacity-90">
            Créer mon premier projet
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {projects.map((p) => {
            const status = statusConfig[p.status];
            return (
              <div key={p.id} className="bg-card rounded-xl shadow-sm border border-border p-5 flex flex-col">
                <div className="flex items-start justify-between mb-3">
                  <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${status.className}`}>{status.label}</span>
                  <DropdownMenu>
                    <DropdownMenuTrigger className="text-muted-foreground hover:text-foreground"><MoreVertical className="h-4 w-4" /></DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => navigate(`/app/projects/${p.id}/settings`)}>Paramètres</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => updateProject(p.id, { status: 'archived' })}>Archiver</DropdownMenuItem>
                      <DropdownMenuItem className="text-dxc-red" onClick={() => deleteProject(p.id)}>Supprimer</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <h3 className="font-bold text-card-foreground text-base mb-1 line-clamp-2">{p.title}</h3>
                <span className="text-xs text-dxc-royal font-medium mb-3">{sectorLabels[p.sector]}</span>
                <div className="text-xs text-muted-foreground space-y-1 mb-4">
                  <p>Créé le {p.createdAt} · {p.rowCount > 0 ? `${p.rowCount.toLocaleString()} lignes` : 'Pas de données'}</p>
                  {p.algorithm && <p>Modèle : {p.algorithm}</p>}
                </div>
                {/* Pipeline progress */}
                <div className="mb-4">
                  <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                    <span>Data</span><span>ML</span><span>Prêt</span>
                  </div>
                  <div className="h-1.5 bg-border rounded-full overflow-hidden">
                    <div className="h-full bg-dxc-royal rounded-full transition-all" style={{ width: `${p.pipelineProgress}%` }} />
                  </div>
                </div>
                <div className="flex gap-2 mt-auto">
                  <Link to={`/app/projects/${p.id}/data`} className="flex-1 text-center text-xs py-2 rounded-md border border-dxc-royal text-dxc-royal font-medium hover:bg-dxc-royal/5 transition-colors inline-flex items-center justify-center gap-1">
                    <Database className="h-3 w-3" /> Données
                  </Link>
                  <Link to={`/app/projects/${p.id}/analysis`} className="flex-1 text-center text-xs py-2 rounded-md bg-dxc-royal text-dxc-white font-medium hover:bg-dxc-blue transition-colors inline-flex items-center justify-center gap-1">
                    <BarChart2 className="h-3 w-3" /> Analyser
                  </Link>
                  <Link to={`/app/projects/${p.id}/dashboard`} className="flex-1 text-center text-xs py-2 rounded-md border border-dxc-melon text-dxc-melon font-medium hover:bg-dxc-melon/5 transition-colors inline-flex items-center justify-center gap-1">
                    <LineChart className="h-3 w-3" /> Dashboard
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
