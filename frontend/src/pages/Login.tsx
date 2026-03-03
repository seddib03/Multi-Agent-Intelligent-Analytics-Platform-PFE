import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { Eye, EyeOff } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { mockDemoProjects } from '@/data/mockData';

export default function Login() {
  const [email, setEmail] = useState('demo@dxc.com');
  const [password, setPassword] = useState('demo123');
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState('');
  const { login, addProject, projects } = useAppStore();
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError('Tous les champs sont requis'); return; }
    // Mock auth
    login({ id: 'u-1', email, firstName: 'Thomas', lastName: 'Durand', company: 'DXC Technology' });
    // Add demo projects if empty
    if (projects.length === 0) {
      mockDemoProjects.forEach((p) => addProject(p));
    }
    navigate('/app/projects');
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-dxc-midnight flex-col items-center justify-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-dxc-royal/20 to-transparent" />
        <div className="relative z-10 text-center">
          <div className="flex items-center justify-center gap-2 mb-8">
            <span className="font-display font-bold text-3xl text-dxc-white">DXC</span>
            <span className="text-dxc-peach text-sm">Insight Platform</span>
          </div>
          <p className="text-dxc-white/70 text-lg max-w-md">Connectez-vous pour accéder à vos projets d'analyse prédictive</p>
          <div className="mt-12 flex flex-wrap justify-center gap-3">
            {['🏦 Finance', '🚌 Transport', '🛍️ Retail', '🏭 Manufacturing', '🏛️ Public'].map((s, i) => (
              <div key={i} className="glass-card rounded-lg px-4 py-2 text-dxc-peach text-sm">{s}</div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 bg-dxc-canvas flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <h1 className="text-2xl font-bold text-foreground mb-2">Se connecter</h1>
          <p className="text-muted-foreground mb-8">Accédez à votre espace d'analyse</p>

          {error && <div className="bg-dxc-red/10 border border-dxc-red/30 text-dxc-red rounded-lg p-3 mb-4 text-sm">{error}</div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground mb-1 block">Email</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vous@entreprise.com" />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground mb-1 block">Mot de passe</label>
              <div className="relative">
                <Input type={showPw ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="rounded border-border" />
                Se souvenir de moi
              </label>
              <a href="#" className="text-sm text-dxc-royal hover:underline">Mot de passe oublié ?</a>
            </div>
            <button type="submit" className="w-full bg-dxc-royal text-dxc-white py-3 rounded-lg font-bold hover:bg-dxc-blue transition-colors">
              Se connecter
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            Pas encore de compte ? <Link to="/register" className="text-dxc-royal font-medium hover:underline">S'inscrire →</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
