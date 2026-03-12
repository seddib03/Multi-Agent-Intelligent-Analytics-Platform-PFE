import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, FolderOpen, Trash2, Play, Calendar, Loader2 } from "lucide-react";
import { AccountMenu } from "@/components/ui/AccountMenu";
import { useAppStore } from "@/stores/appStore";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useDarkMode } from "@/hooks/useDarkMode";
import { t } from "@/lib/i18n";
import BrandLogo from "@/components/BrandLogo";
import {
  listProjects,
  deleteProject as apiDeleteProject,
  type Project,
} from "@/lib/projectsApi";

const SUPPORTED_SECTORS = ["finance", "transport", "retail", "manufacturing", "public"] as const;

function normalizeSector(value: string | null | undefined): (typeof SUPPORTED_SECTORS)[number] {
  if (value && (SUPPORTED_SECTORS as readonly string[]).includes(value)) {
    return value as (typeof SUPPORTED_SECTORS)[number];
  }
  return "public";
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  CREATED:             { label: "Créé",            color: "bg-accent/20 text-accent-foreground" },
  DATA_UPLOADED:       { label: "Données chargées", color: "bg-blue-100 text-blue-700" },
  METADATA_CONFIGURED: { label: "Configuré",        color: "bg-purple-100 text-purple-700" },
  TRAINING:            { label: "En training",      color: "bg-yellow-100 text-yellow-700" },
  READY:               { label: "Prêt",             color: "bg-dxc-gold/10 text-dxc-gold" },
  FAILED:              { label: "Échoué",           color: "bg-red-100 text-red-700" },
  ARCHIVED:            { label: "Archivé",          color: "bg-gray-100 text-gray-500" },
};

export default function Projects() {
  const navigate = useNavigate();
  const { resetProject, userPreferences } = useAppStore();
  const lang = userPreferences.language;
  useDarkMode();

  const [projects, setProjects]   = useState<Project[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [deleting, setDeleting]   = useState<string | null>(null);

  // ── Fetch projects from backend ──────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listProjects()
      .then((data) => { if (!cancelled) { setProjects(data); setError(null); } })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleNewProject = () => {
    resetProject();
    navigate("/app");
  };

  const handleContinueProject = (project: Project) => {
    // Reprendre un projet ouvre directement son dashboard.
    useAppStore.setState((state) => ({
      currentProjectId: project.id,
      currentPhase: 3,
      onboardingStep: 4,
      onboarding: {
        ...state.onboarding,
        useCaseDescription: project.use_case ?? state.onboarding.useCaseDescription,
      },
      dataset: {
        ...state.dataset,
        detectedSector: normalizeSector(project.detected_sector),
        businessRules: project.business_rules ?? state.dataset.businessRules,
      },
    }));
    navigate("/app");
  };

  const handleDeleteProject = async (projectId: string) => {
    setDeleting(projectId);
    try {
      await apiDeleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de la suppression");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="h-16 bg-dxc-midnight px-4 text-dxc-white md:px-6">
        <div className="flex h-full items-center justify-between">
          <div className="flex items-center gap-4">
            <BrandLogo logoClassName="h-7" subtitleClassName="text-[13px] font-semibold" />
          </div>
          <div className="flex items-center gap-3">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button className="bg-accent text-accent-foreground hover:opacity-90">
                  <Plus size={16} className="mr-2" />
                  {t("newProject", lang)}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t("confirmNewProjectTitle", lang)}</AlertDialogTitle>
                  <AlertDialogDescription>{t("confirmNewProjectDesc", lang)}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t("cancel", lang)}</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleNewProject}
                    className="bg-primary text-primary-foreground hover:bg-primary/90"
                  >
                    {t("confirm", lang)}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <AccountMenu variant="dark" position="top" />
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto py-10 px-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">{t("myProjectsTitle", lang)}</h1>
        <p className="text-muted-foreground mb-8">{t("manageProjects", lang)}</p>

        {/* ── Error ── */}
        {error && (
          <div className="mb-4 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* ── Loading ── */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
            <Loader2 size={20} className="animate-spin" />
            <span>Chargement des projets…</span>
          </div>
        ) : projects.length === 0 ? (
          <div className="bg-card rounded-2xl shadow-sm p-12 text-center border border-border">
            <FolderOpen size={48} className="mx-auto text-primary/30 mb-4" />
            <p className="text-muted-foreground mb-6">{t("noProjects", lang)}</p>
            <Button onClick={handleNewProject}>
              <Plus size={16} className="mr-2" />
              {t("createFirstProject", lang)}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {projects.map((project) => {
              const statusInfo = STATUS_LABELS[project.status] ?? STATUS_LABELS.CREATED;
              return (
                <div
                  key={project.id}
                  className="bg-card rounded-2xl shadow-sm p-6 hover:shadow-md transition-shadow border border-border"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        <h3 className="font-semibold text-foreground truncate">{project.name}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
                        {project.detected_sector && (
                          <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 shrink-0">
                            {project.detected_sector}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                        {project.description && (
                          <span className="truncate max-w-[250px]">{project.description}</span>
                        )}
                        <span className="flex items-center gap-1">
                          <Calendar size={12} />
                          {new Date(project.updated_at).toLocaleDateString(
                            lang === "en" ? "en-US" : "fr-FR"
                          )}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleContinueProject(project)}
                      >
                        <Play size={14} className="mr-1" />
                        {t("resume", lang)}
                      </Button>

                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:bg-destructive/10"
                            disabled={deleting === project.id}
                            aria-label={`${t("delete", lang)} ${project.name}`}
                          >
                            {deleting === project.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <Trash2 size={14} />
                            )}
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>{t("confirmDeleteProjectTitle", lang)}</AlertDialogTitle>
                            <AlertDialogDescription>
                              {t("confirmDeleteProjectDesc", lang).replace("{name}", project.name)}
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t("cancel", lang)}</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDeleteProject(project.id)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              {t("confirm", lang)}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}