import { useNavigate } from "react-router-dom";
import { Plus, FolderOpen, Trash2, Play, Calendar } from "lucide-react";
import { AccountMenu } from "@/components/ui/AccountMenu";
import { useAppStore } from "@/stores/appStore";
import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { SECTOR_LABELS } from "@/lib/mockData";
import { useDarkMode } from "@/hooks/useDarkMode";
import { t } from "@/lib/i18n";

export default function Projects() {
  const navigate = useNavigate();
  const { resetProject, loadProject, deleteProject, savedProjects, userPreferences } = useAppStore();
  const lang = userPreferences.language;
  useDarkMode();

  const handleNewProject = () => { resetProject(); navigate("/app"); };
  const handleContinueProject = (id: string) => { loadProject(id); navigate("/app"); };

  const dateLocale = lang === "en" ? "en-US" : "fr-FR";

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-dxc-midnight text-dxc-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <span className="font-bold text-xl">DXC</span>
            <span className="text-dxc-peach text-xs ml-1">{t("insightPlatform", lang)}</span>
          </div>
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
                <AlertDialogAction onClick={handleNewProject} className="bg-primary text-primary-foreground hover:bg-primary/90">{t("confirm", lang)}</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <AccountMenu variant="dark" position="top" />
        </div>
      </header>

      <div className="max-w-4xl mx-auto py-10 px-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">{t("myProjectsTitle", lang)}</h1>
        <p className="text-muted-foreground mb-8">{t("manageProjects", lang)}</p>

        {savedProjects.length === 0 ? (
          <div className="bg-card rounded-2xl shadow-sm p-12 text-center border border-border">
            <FolderOpen size={48} className="mx-auto text-primary/30 mb-4" />
            <p className="text-muted-foreground mb-6">{t("noProjects", lang)}</p>
            <Button onClick={() => { resetProject(); navigate("/app"); }}>
              <Plus size={16} className="mr-2" />
              {t("createFirstProject", lang)}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {savedProjects.map((project) => {
              const sectorInfo = SECTOR_LABELS[project.dataset.detectedSector];
              const status = project.currentPhase >= 2 ? "completed" : "draft";
              return (
                <div key={project.id} className="bg-card rounded-2xl shadow-sm p-6 hover:shadow-md transition-shadow border border-border">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        <h3 className="font-semibold text-foreground truncate">{project.name}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${
                          status === "completed"
                            ? "bg-dxc-gold/10 text-dxc-gold"
                            : "bg-accent/20 text-accent-foreground"
                        }`}>
                          {status === "completed" ? t("completed", lang) : t("draft", lang)}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                        <span className="flex items-center gap-1">
                          <span className="text-base">{sectorInfo.icon}</span>
                          {sectorInfo.label}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar size={12} />
                          {new Date(project.updatedAt).toLocaleDateString(dateLocale)}
                        </span>
                        {project.dataset.rowCount > 0 && (
                          <span>{project.dataset.rowCount.toLocaleString()} {t("records", lang)}</span>
                        )}
                        {project.dataset.fileName && (
                          <span className="truncate max-w-[150px]">{project.dataset.fileName}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button variant="outline" size="sm" onClick={() => handleContinueProject(project.id)}>
                        <Play size={14} className="mr-1" />
                        {t("resume", lang)}
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                       <Button variant="ghost" size="sm" className="text-destructive hover:bg-destructive/10" aria-label={`${t("delete", lang)} ${project.name}`}>
                            <Trash2 size={14} />
                          </Button>
                        </AlertDialogTrigger>
                         <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>{t("confirmDeleteProjectTitle", lang)}</AlertDialogTitle>
                            <AlertDialogDescription>{t("confirmDeleteProjectDesc", lang).replace("{name}", project.name)}</AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t("cancel", lang)}</AlertDialogCancel>
                            <AlertDialogAction onClick={() => deleteProject(project.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">{t("confirm", lang)}</AlertDialogAction>
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
