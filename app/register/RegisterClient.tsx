'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function RegisterClient() {
  const router = useRouter();
  const params = useSearchParams();
  const [token, setToken] = useState<string>('');
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [busy, setBusy] = useState<boolean>(false);
  const [msg, setMsg] = useState<string>('');

  useEffect(() => {
    const t = params.get('invite') || params.get('token');
    if (t) setToken(t);
  }, [params]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    try {
      const res = await fetch('/api-py/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ token, username, password }),
      });
      if (!res.ok) {
        const t = await res.text().catch(() => '');
        setMsg(t || 'Registration failed');
        setBusy(false);
        return;
      }
      setMsg('Registered. Redirecting...');
      router.push('/');
      router.refresh();
    } catch {
      setMsg('Network error while registering');
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: '48px auto', background: '#fff', padding: 24, borderRadius: 8, boxShadow: '0 0 10px rgba(0,0,0,0.1)' }}>
      <h1 style={{ marginBottom: 16 }}>Register</h1>
      <form onSubmit={onSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="invite">Invite Token</label>
          <input
            id="invite"
            style={{ display: 'block', width: '100%', padding: 8, marginTop: 4 }}
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </div>
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
            autoComplete="new-password"
          />
        </div>
        <button type="submit" disabled={busy} className="btn-save" style={{ width: '100%' }}>
          {busy ? 'Registering…' : 'Register'}
        </button>
      </form>
      {msg ? <p style={{ marginTop: 12, color: '#c72' }}>{msg}</p> : null}
      <p style={{ marginTop: 16 }}>
        Already have an account? <a href="/login">Sign in</a>.
      </p>
    </div>
  );
}
