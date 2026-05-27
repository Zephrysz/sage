'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/hooks/useSession';
import { apiRequest } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const { setSessionId, setUser } = useSession();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const data = await apiRequest<{
        session_id?: string;
        user?: { name: string };
        error?: string;
      }>('/session/init', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (data.error === 'auth_failed') {
        setError('E-mail ou senha incorretos. Verifique suas credenciais CEFIS.');
        return;
      }

      if (data.error === 'timeout') {
        setError('Serviço temporariamente indisponível. Tente novamente em instantes.');
        return;
      }

      if (!data.session_id) {
        setError('Não foi possível iniciar a sessão. Tente novamente.');
        return;
      }

      setSessionId(data.session_id);
      if (data.user) setUser(data.user);

      router.push('/tutor');
    } catch {
      setError('Não foi possível conectar ao servidor. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center px-4 overflow-hidden bg-[hsl(var(--background))]">
      {/* Animated gradient background blobs */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        aria-hidden="true"
      >
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 h-[500px] w-[700px] rounded-full bg-[hsl(174_72%_42%/0.08)] blur-3xl animate-pulse" />
        <div className="absolute bottom-0 right-0 h-[300px] w-[400px] rounded-full bg-[hsl(224_15%_16%/0.6)] blur-2xl" />
      </div>

      {/* Card */}
      <div className="relative w-full max-w-sm space-y-6 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card)/0.8)] p-8 shadow-2xl backdrop-blur-md">
        {/* Logo / header */}
        <div className="text-center space-y-3">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[hsl(174_72%_42%/0.15)] ring-1 ring-[hsl(174_72%_42%/0.4)]">
            <img
              src="/cefis-logo.svg"
              alt="CEFIS AI Tutor"
              width={36}
              height={36}
            />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">
              CEFIS AI Tutor
            </h1>
            <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
              Entre com sua conta CEFIS para começar
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label
              htmlFor="email"
              className="block text-sm font-medium text-[hsl(var(--foreground))]"
            >
              E-mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
              placeholder="seu@email.com"
              className="w-full rounded-xl border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-4 py-2.5 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] disabled:opacity-50 transition-shadow"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="password"
              className="block text-sm font-medium text-[hsl(var(--foreground))]"
            >
              Senha
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              placeholder="••••••••"
              className="w-full rounded-xl border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-4 py-2.5 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] disabled:opacity-50 transition-shadow"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || !email.trim() || !password.trim()}
            className="w-full rounded-xl bg-[hsl(var(--primary))] px-4 py-2.5 text-sm font-semibold text-[hsl(var(--primary-foreground))] transition-all hover:opacity-90 hover:shadow-lg hover:shadow-[hsl(174_72%_42%/0.25)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
        </form>

        <p className="text-center text-xs text-[hsl(var(--muted-foreground))]">
          Use as mesmas credenciais da plataforma CEFIS
        </p>
      </div>
    </main>
  );
}
