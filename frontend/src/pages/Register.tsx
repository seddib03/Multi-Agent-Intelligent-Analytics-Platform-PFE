import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { Input } from '@/components/ui/input';
import BrandLogo from '@/components/BrandLogo';

export default function Register() {
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', company: '', password: '', confirmPassword: '' });
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState('');
  const { register } = useAppStore();
  const navigate = useNavigate();

  const strength = form.password.length === 0 ? 0 : form.password.length < 6 ? 1 : form.password.length < 10 ? 2 : 3;
  const strengthColors = ['', 'bg-dxc-red', 'bg-dxc-gold', 'bg-dxc-royal'];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.firstName || !form.lastName || !form.email || !form.company || !form.password) {
      setError('Tous les champs sont requis'); return;
    }
    if (form.password !== form.confirmPassword) { setError('Les mots de passe ne correspondent pas'); return; }
    if (!agreed) { setError('Veuillez accepter les conditions'); return; }
    register({ id: 'u-' + Date.now(), email: form.email, firstName: form.firstName, lastName: form.lastName, company: form.company });
    navigate('/app/projects');
  };

  const set = (key: string, val: string) => setForm((f) => ({ ...f, [key]: val }));

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 bg-dxc-midnight flex-col items-center justify-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-dxc-royal/20 to-transparent" />
        <div className="relative z-10 text-center">
          <div className="flex items-center justify-center gap-2 mb-8">
            <BrandLogo logoClassName="h-9" subtitleClassName="text-sm" />
          </div>
          <p className="text-dxc-white text-xl font-bold mb-2">Rejoignez des milliers d'équipes</p>
          <p className="text-dxc-white/70 text-lg max-w-md">qui analysent mieux avec l'IA</p>
          <div className="mt-12 flex flex-wrap justify-center gap-3">
            {[' Finance', ' Transport', ' Retail', ' Manufacturing', ' Public'].map((s, i) => (
              <div key={i} className="glass-card rounded-lg px-4 py-2 text-dxc-peach text-sm">{s}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 bg-dxc-canvas flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <h1 className="text-2xl font-bold text-foreground mb-1">Créer votre compte</h1>
          <p className="text-muted-foreground mb-6">Pour votre équipe ou votre entreprise</p>

          {error && <div className="bg-dxc-red/10 border border-dxc-red/30 text-dxc-red rounded-lg p-3 mb-4 text-sm">{error}</div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium mb-1 block">Prénom</label>
                <Input value={form.firstName} onChange={(e) => set('firstName', e.target.value)} placeholder="Thomas" />
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">Nom</label>
                <Input value={form.lastName} onChange={(e) => set('lastName', e.target.value)} placeholder="Durand" />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Email professionnel</label>
              <Input type="email" value={form.email} onChange={(e) => set('email', e.target.value)} placeholder="vous@entreprise.com" />
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Nom de l'entreprise</label>
              <Input value={form.company} onChange={(e) => set('company', e.target.value)} placeholder="DXC Technology" />
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Mot de passe</label>
              <Input type="password" value={form.password} onChange={(e) => set('password', e.target.value)} placeholder="••••••••" />
              {form.password && (
                <div className="flex gap-1 mt-2">
                  {[1, 2, 3].map((level) => (
                    <div key={level} className={`h-1 flex-1 rounded-full ${strength >= level ? strengthColors[strength] : 'bg-border'}`} />
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Confirmer le mot de passe</label>
              <Input type="password" value={form.confirmPassword} onChange={(e) => set('confirmPassword', e.target.value)} placeholder="••••••••" />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="rounded border-border mt-0.5" />
              J'accepte les conditions d'utilisation
            </label>
            <button type="submit" className="w-full bg-dxc-melon text-dxc-white py-3 rounded-lg font-bold hover:opacity-90 transition-opacity">
              Créer mon compte
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            Déjà un compte ? <Link to="/login" className="text-dxc-royal font-medium hover:underline">Se connecter →</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
