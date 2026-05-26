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
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo / header */}
        <div className="text-center space-y-2">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] text-xl font-bold">
            AI
          </div>
          <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">
            CEFIS AI Tutor
          </h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Entre com sua conta CEFIS para começar
          </p>
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
              className="w-full rounded-lg border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] disabled:opacity-50"
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
              className="w-full rounded-lg border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] disabled:opacity-50"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || !email.trim() || !password.trim()}
            className="w-full rounded-lg bg-[hsl(var(--primary))] px-4 py-2.5 text-sm font-semibold text-[hsl(var(--primary-foreground))] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
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
