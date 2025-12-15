'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState<string>('admin');
  const [password, setPassword] = useState<string>('');
  const [busy, setBusy] = useState<boolean>(false);
  const [msg, setMsg] = useState<string>('');

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    try {
      const res = await fetch('/api-py/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const t = await res.text().catch(() => '');
        setMsg(t || 'Login failed');
        setBusy(false);
        return;
      }
      setMsg('Logged in. Redirecting...');
      router.push('/');
      router.refresh();
    } catch {
      setMsg('Network error while logging in');
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: '48px auto', background: '#fff', padding: 24, borderRadius: 8, boxShadow: '0 0 10px rgba(0,0,0,0.1)' }}>
      <h1 style={{ marginBottom: 16 }}>Sign in</h1>
      <p style={{ marginBottom: 16 }}>
        Tip: The first time, sign in as admin with the environment variable ADMIN_INITIAL_PASSWORD to bootstrap the admin user.
      </p>
      <form onSubmit={onSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="username">Username</label>
          <input
            id="username"
            style={{ display: 'block', width: '100%', padding: 8, marginTop: 4 }}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            style={{ display: 'block', width: '100%', padding: 8, marginTop: 4 }}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        <button type="submit" disabled={busy} className="btn-save" style={{ width: '100%' }}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      {msg ? <p style={{ marginTop: 12, color: '#c72' }}>{msg}</p> : null}
      <p style={{ marginTop: 16 }}>
        Have an invite? Go to <a href="/register">Register</a>.
      </p>
    </div>
  );
}
