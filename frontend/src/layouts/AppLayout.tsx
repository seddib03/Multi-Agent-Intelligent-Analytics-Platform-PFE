import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { ChevronRight, LogOut, User, Settings } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export default function AppLayout() {
  const { currentUser, logout, projects, currentProjectId } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const initials = currentUser ? `${currentUser.firstName[0]}${currentUser.lastName[0]}` : '??';

  // Build breadcrumb
  const parts = location.pathname.replace('/app/', '').split('/');
  const breadcrumbs: { label: string; path?: string }[] = [];
  if (parts[0] === 'projects') {
    breadcrumbs.push({ label: 'Mes Projets', path: '/app/projects' });
    if (parts[1] === 'new') {
      breadcrumbs.push({ label: 'Nouveau Projet' });
    } else if (parts[1]) {
      const project = projects.find((p) => p.id === parts[1]);
      breadcrumbs.push({ label: project?.title || 'Projet', path: `/app/projects/${parts[1]}/data` });
      if (parts[2] === 'data') breadcrumbs.push({ label: 'Données' });
      else if (parts[2] === 'analysis') breadcrumbs.push({ label: 'Analyse' });
      else if (parts[2] === 'dashboard') breadcrumbs.push({ label: 'Dashboard' });
      else if (parts[2] === 'settings') breadcrumbs.push({ label: 'Paramètres' });
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-dxc-midnight h-14 flex items-center px-4 justify-between shrink-0 z-50 sticky top-0">
        <Link to="/app/projects" className="flex items-center gap-2">
          <span className="font-display font-bold text-lg text-dxc-white">DXC</span>
          <span className="text-dxc-peach text-xs font-body">Insight Platform</span>
        </Link>

        <div className="flex items-center gap-1 text-sm">
          {breadcrumbs.map((bc, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <ChevronRight className="h-3 w-3 text-dxc-sky/50" />}
              {bc.path ? (
                <Link to={bc.path} className="text-dxc-sky/70 hover:text-dxc-sky transition-colors">{bc.label}</Link>
              ) : (
                <span className="text-dxc-white">{bc.label}</span>
              )}
            </span>
          ))}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 outline-none">
            <div className="h-8 w-8 rounded-full bg-dxc-royal flex items-center justify-center text-xs font-bold text-dxc-white">{initials}</div>
            <span className="text-dxc-white text-sm hidden sm:block">{currentUser?.firstName}</span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem className="gap-2"><User className="h-4 w-4" /> Profil</DropdownMenuItem>
            <DropdownMenuItem className="gap-2"><Settings className="h-4 w-4" /> Préférences</DropdownMenuItem>
            <DropdownMenuItem className="gap-2 text-dxc-red" onClick={handleLogout}><LogOut className="h-4 w-4" /> Déconnexion</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <main className="flex-1 bg-background">
        <Outlet />
      </main>
    </div>
  );
}
