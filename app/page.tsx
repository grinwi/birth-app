'use client';

import { useEffect, useMemo, useState } from 'react';

type Row = {
  first_name: string;
  last_name: string;
  day: string;
  month: string;
  year: string;
};

type SortKey = 'first_name' | 'last_name' | 'day' | 'month' | 'year' | 'age';
type Period =
  | 'all'
  | 'today'
  | 'this-week'
  | 'next-week'
  | 'this-month'
  | 'next-month'
  | 'this-quarter'
  | 'next-quarter'
  | 'this-year'
  | 'next-year';


const HEADER_KEYS: (keyof Row)[] = ['first_name', 'last_name', 'day', 'month', 'year'];

function ensureString(v: unknown) {
  return v == null ? '' : String(v).trim();
}




function validateRowClient(row: Row): string | null {
  const r = {
    first_name: (row.first_name || '').trim(),
    last_name: (row.last_name || '').trim(),
    day: (row.day || '').trim(),
    month: (row.month || '').trim(),
    year: (row.year || '').trim(),
  };
  if (!r.first_name) return 'first_name is required';
  if (!r.last_name) return 'last_name is required';
  let d = 0, m = 0, y = 0;
  try {
    d = parseInt(r.day, 10);
    m = parseInt(r.month, 10);
    y = parseInt(r.year, 10);
  } catch {
    return 'day/month/year must be integers';
  }
  if (!Number.isFinite(d) || !Number.isFinite(m) || !Number.isFinite(y)) return 'day/month/year must be integers';
  if (d < 1 || d > 31) return 'day must be 1-31';
  if (m < 1 || m > 12) return 'month must be 1-12';
  if (y < 1900 || y > 3000) return 'year must be a realistic year (1900..3000)';
  try {
    // Validate date
    const test = new Date(y, m - 1, d);
    if (test.getFullYear() !== y || test.getMonth() !== (m - 1) || test.getDate() !== d) {
      return 'Invalid calendar date';
    }
  } catch {
    return 'Invalid calendar date';
  }
  return null;
}

function getPeriodRange(period: Exclude<Period, 'all'>) {
  const today = new Date();
  let start: Date | null = null;
  let end: Date | null = null;
  switch (period) {
    case 'today':
      start = new Date(today);
      start.setHours(0, 0, 0, 0);
      end = new Date(today);
      end.setHours(23, 59, 59, 999);
      break;
    case 'this-week': {
      start = new Date(today);
      start.setHours(0, 0, 0, 0);
      end = new Date(today);
      end.setDate(end.getDate() + ((7 - end.getDay()) % 7));
      end.setHours(23, 59, 59, 999);
      break;
    }
    case 'next-week': {
      start = new Date(today);
      const daysToMonday = ((8 - start.getDay()) % 7) || 7;
      start.setDate(start.getDate() + daysToMonday);
      start.setHours(0, 0, 0, 0);
      end = new Date(start);
      end.setDate(start.getDate() + 6);
      end.setHours(23, 59, 59, 999);
      break;
    }
    case 'this-month': {
      start = new Date(today.getFullYear(), today.getMonth(), 1, 0, 0, 0, 0);
      end = new Date(today.getFullYear(), today.getMonth() + 1, 0, 23, 59, 59, 999);
      break;
    }
    case 'next-month': {
      start = new Date(today.getFullYear(), today.getMonth() + 1, 1, 0, 0, 0, 0);
      end = new Date(today.getFullYear(), today.getMonth() + 2, 0, 23, 59, 59, 999);
      break;
    }
    case 'this-quarter': {
      const thisQ = Math.floor(today.getMonth() / 3);
      start = new Date(today.getFullYear(), thisQ * 3, 1, 0, 0, 0, 0);
      end = new Date(today.getFullYear(), thisQ * 3 + 3, 0, 23, 59, 59, 999);
      break;
    }
    case 'next-quarter': {
      let nextQ = Math.floor(today.getMonth() / 3) + 1;
      let year = today.getFullYear();
      if (nextQ > 3) {
        nextQ = 0;
        year += 1;
      }
      start = new Date(year, nextQ * 3, 1, 0, 0, 0, 0);
      end = new Date(year, nextQ * 3 + 3, 0, 23, 59, 59, 999);
      break;
    }
    case 'this-year': {
      start = new Date(today.getFullYear(), 0, 1, 0, 0, 0, 0);
      end = new Date(today.getFullYear(), 11, 31, 23, 59, 59, 999);
      break;
    }
    case 'next-year': {
      start = new Date(today.getFullYear() + 1, 0, 1, 0, 0, 0, 0);
      end = new Date(today.getFullYear() + 1, 11, 31, 23, 59, 59, 999);
      break;
    }
  }
  return { start, end };
}

function computeAge(row: Row) {
  const today = new Date();
  let age = today.getFullYear() - parseInt(row.year || '0', 10);
  const bdayThisYear = new Date(
    today.getFullYear(),
    parseInt(row.month || '1', 10) - 1,
    parseInt(row.day || '1', 10),
  );
  if (bdayThisYear > today) age--;
  return age;
}

function computeNextBirthdayDisplay(row: Row, periodRange: { start: Date; end: Date } | null) {
  const today = new Date();
  let targetDate = today;
  if (periodRange?.end) targetDate = periodRange.end;
  let nY = targetDate.getFullYear();
  let nBDay = new Date(nY, parseInt(row.month || '1', 10) - 1, parseInt(row.day || '1', 10));
  if (nBDay < targetDate) nBDay.setFullYear(nY + 1);
  const nextBirthdayAge = nBDay.getFullYear() - parseInt(row.year || '0', 10);

  let birthdayInRange: Date | null = null;
  if (periodRange?.start && periodRange?.end) {
    let y = periodRange.start.getFullYear();
    let dt = new Date(y, parseInt(row.month || '1', 10) - 1, parseInt(row.day || '1', 10));
    if (dt >= periodRange.start && dt <= periodRange.end) {
      birthdayInRange = dt;
    } else {
      y = periodRange.end.getFullYear();
      dt = new Date(y, parseInt(row.month || '1', 10) - 1, parseInt(row.day || '1', 10));
      if (dt >= periodRange.start && dt <= periodRange.end) birthdayInRange = dt;
    }
  }

  const fmt = (d: Date) =>
    `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1)
      .toString()
      .padStart(2, '0')}.${d.getFullYear()}`;
  if (birthdayInRange) {
    return `${birthdayInRange.getFullYear() - parseInt(row.year || '0', 10)} (${fmt(
      birthdayInRange,
    )})`;
  }
  return `${nextBirthdayAge} (${fmt(nBDay)})`;
}

export default function Page() {
  const [apiBase, setApiBase] = useState<string>('/api');
  const [backendReachable, setBackendReachable] = useState<boolean>(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [activePeriod, setActivePeriod] = useState<Period>('all');
  const [modulo, setModulo] = useState<'none' | '5' | '10'>('none');
  const [currentSort, setCurrentSort] = useState<{ type: SortKey; order: 'asc' | 'desc' }[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValues, setEditValues] = useState<Partial<Row>>({});

  // Init API base from localStorage once on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('APP_API_BASE');
      if (saved && typeof saved === 'string') {
        const value = saved.trim().replace(/\/$/, '') || '/api';
        setApiBase(value);
      }
    } catch {}
  }, []);

  // Load initial data whenever apiBase changes (or on first render)
  useEffect(() => {
    let aborted = false;
    async function load() {
      // Try backend first
      try {
        const res = await fetch(`${apiBase}/people`, {
          headers: { Accept: 'application/json' },
          credentials: 'include',
        });
        if (res.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!res.ok) throw new Error(`GET /people failed ${res.status}`);
        const json = (await res.json()) as { data?: Row[] };
        if (!aborted) {
          setBackendReachable(true);
          setRows(Array.isArray(json.data) ? json.data : []);
        }
        return;
      } catch {
        if (!aborted) setBackendReachable(false);
      }
    }
    load();
    return () => {
      aborted = true;
    };
  }, [apiBase]);

  // Derived filtered rows by period and modulo
  const filteredRows = useMemo(() => {
    let out = [...rows];
    const periodRange =
      activePeriod !== 'all' ? (getPeriodRange(activePeriod) as { start: Date; end: Date }) : null;

    if (periodRange?.start && periodRange?.end) {
      out = out.filter((row) => {
        const birthMonth = parseInt(row.month || '0', 10);
        const birthDay = parseInt(row.day || '0', 10);
        const candidates = [
          new Date(periodRange.start.getFullYear(), birthMonth - 1, birthDay),
          new Date(periodRange.end.getFullYear(), birthMonth - 1, birthDay),
        ];
        return candidates.some((d) => d >= periodRange.start! && d <= periodRange.end!);
      });
    }

    if (modulo === '5' || modulo === '10') {
      const mod = parseInt(modulo, 10);
      out = out.filter((row) => {
        let ageInPeriod: number | null = null;
        if (periodRange?.start && periodRange?.end) {
          const y = periodRange.start.getFullYear();
          let bDate = new Date(y, parseInt(row.month || '1', 10) - 1, parseInt(row.day || '1', 10));
          if (bDate < periodRange.start) bDate.setFullYear(y + 1);
          if (bDate >= periodRange.start && bDate <= periodRange.end) {
            ageInPeriod = bDate.getFullYear() - parseInt(row.year || '0', 10);
          }
        }
        if (ageInPeriod === null) {
          ageInPeriod = computeAge(row);
        }
        return ageInPeriod % mod === 0;
      });
    }

    // Apply multi-sort
    const cmpFor =
      (type: SortKey, order: 'asc' | 'desc') =>
      (a: Row, b: Row) => {
        const dir = order === 'desc' ? -1 : 1;
        switch (type) {
          case 'first_name':
            return dir * a.first_name.localeCompare(b.first_name);
          case 'last_name':
            return dir * a.last_name.localeCompare(b.last_name);
          case 'day':
            return dir * (parseInt(a.day || '0') - parseInt(b.day || '0'));
          case 'month':
            return dir * (parseInt(a.month || '0') - parseInt(b.month || '0'));
          case 'year':
            return dir * (parseInt(a.year || '0') - parseInt(b.year || '0'));
          case 'age':
            return dir * (computeAge(a) - computeAge(b));
          default:
            return 0;
        }
      };
    if (currentSort.length) {
      out.sort((a, b) => {
        for (const s of currentSort) {
          const r = cmpFor(s.type, s.order)(a, b);
          if (r !== 0) return r;
        }
        return 0;
      });
    }

    return out;
  }, [rows, activePeriod, modulo, currentSort]);

  const backendStatusText = backendReachable
    ? `Backend OK: ${apiBase}`
    : `Backend unavailable`;

  const backendStatusColor = backendReachable ? '#2c7' : '#c72';

  function toggleSort(type: SortKey) {
    // cycle: none -> asc -> desc -> none
    const idx = currentSort.findIndex((s) => s.type === type);
    const next = [...currentSort];
    if (idx === -1) {
      next.unshift({ type, order: 'asc' });
    } else {
      const cur = next[idx];
      if (cur.order === 'asc') {
        next[idx] = { type, order: 'desc' };
        // bring to front
        const s = next.splice(idx, 1)[0];
        next.unshift(s);
      } else if (cur.order === 'desc') {
        next.splice(idx, 1); // remove (back to neutral)
      }
    }
    setCurrentSort(next);
  }

  const sortIndicator = (type: SortKey) => {
    const match = currentSort.find((s) => s.type === type);
    if (!match) return '↔';
    return match.order === 'asc' ? '↑' : '↓';
  };

  async function handleAddRow() {
    const newRow: Row = {
      first_name: (prompt('Enter first name') as string) || '',
      last_name: (prompt('Enter last name') as string) || '',
      day: (prompt('Enter day') as string) || '',
      month: (prompt('Enter month') as string) || '',
      year: (prompt('Enter year') as string) || '',
    };
    if (backendReachable) {
      try {
        const res = await fetch(`${apiBase}/people`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(newRow),
        });
        if (res.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!res.ok) throw new Error(await res.text());
        const json = (await res.json()) as { data?: Row[] };
        setRows(Array.isArray(json.data) ? json.data : []);
      } catch (e: any) {
        alert(`Failed to add row: ${e?.message || 'Unknown error'}`);
      }
    } else {
      setRows((prev) => [...prev, newRow]);
    }
  }

  function startEdit(index: number, row: Row) {
    setEditingIndex(index);
    setEditValues({ ...row });
  }

  function cancelEdit() {
    setEditingIndex(null);
    setEditValues({});
  }

  async function saveEdit(index: number) {
    if (editingIndex !== index) return;
    if (backendReachable) {
      try {
        const res = await fetch(`/api/people_index.py?index=${index}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-HTTP-Method-Override': 'PUT' },
          credentials: 'include',
          body: JSON.stringify({ ...rows[index], ...(editValues as Row) }),
        });
        if (res.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!res.ok) throw new Error(await res.text());
        const json = (await res.json()) as { data?: Row[] };
        setRows(Array.isArray(json.data) ? json.data : []);
      } catch (e: any) {
        alert(`Failed to save row: ${e?.message || 'Unknown error'}`);
        return;
      }
    } else {
      setRows((prev) => {
        const next = [...prev];
        next[index] = { ...(editValues as Row) };
        return next;
      });
    }
    setEditingIndex(null);
    setEditValues({});
  }

  async function handleDelete(index: number) {
    if (backendReachable) {
      try {
        const res = await fetch(`/api/people_index.py?index=${index}`, {
          method: 'POST',
          headers: { 'X-HTTP-Method-Override': 'DELETE' },
          credentials: 'include',
        });
        if (res.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!res.ok) throw new Error(await res.text());
        const json = (await res.json()) as { data?: Row[] };
        setRows(Array.isArray(json.data) ? json.data : []);
      } catch (e: any) {
        alert(`Failed to delete row: ${e?.message || 'Unknown error'}`);
      }
    } else {
      setRows((prev) => {
        const next = [...prev];
        next.splice(index, 1);
        return next;
      });
    }
  }



  async function saveToGitHub() {
    if (!rows.length) {
      alert('No data to save.');
      return;
    }
    // Validate all rows client-side before pushing to backend/PR
    for (let i = 0; i < rows.length; i++) {
      const err = validateRowClient(rows[i]);
      if (err) {
        alert(`Cannot push to GitHub: Row ${i} invalid: ${err}`);
        return;
      }
    }
    try {
      const res = await fetch(`${apiBase}/json?strict=false`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ data: rows }),
      });
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      if (res.status === 403) {
        alert('Forbidden: admin required to push to GitHub.');
        return;
      }
      const text = await res.text();
      if (!res.ok) {
        // Try to surface structured backend error if present
        try {
          const j = JSON.parse(text);
          const details =
            j?.warning || j?.error || j?.message || (typeof j === 'string' ? j : '');
          alert(`GitHub push failed (${res.status}): ${details || 'Unknown error'}`);
        } catch {
          alert(`GitHub push failed (${res.status}): ${text || 'Unknown error'}`);
        }
        return;
      }
      // OK path: show PR URL or warning if PR creation failed gracefully
      let j: any = null;
      try {
        j = text ? JSON.parse(text) : null;
      } catch {}
      if (j?.pr_url) {
        alert(`Change submitted. GitHub PR: ${j.pr_url}`);
      } else if (j?.warning) {
        alert(`JSON saved, but PR not created: ${j.warning}`);
      } else {
        alert('Change submitted to GitHub (JSON).');
      }
    } catch (e: any) {
      alert(`Failed to push data to GitHub: ${e?.message || 'Network error'}`);
    }
  }

  function setBackendUrl() {
    const url = prompt('Enter backend API base URL (e.g., https://your-api.example.com)', apiBase || '');
    if (url != null) {
      const cleaned = url.trim().replace(/\/$/, '') || '/api';
      setApiBase(cleaned);
      try {
        localStorage.setItem('APP_API_BASE', cleaned);
      } catch {}
      setBackendReachable(false);
    }
  }

  function periodBtn(id: string, label: string, value: Period) {
    const active = activePeriod === value;
    return (
      <button
        key={id}
        id={id}
        className={`period-btn${active ? ' active' : ''}`}
        onClick={() => setActivePeriod(value)}
      >
        {label}
      </button>
    );
  }

  return (
    <div>
      <h1>Birthdays App</h1>
      <p
        id="backend-status"
        aria-live="polite"
        style={{ margin: '8px 0', fontSize: '0.9rem', color: backendStatusColor }}
      >
        {backendStatusText}
      </p>


      <div className="filters">
        {periodBtn('all-btn', 'ALL', 'all')}
        {periodBtn('today-btn', 'Today', 'today')}
        {periodBtn('this-week-btn', 'This Week', 'this-week')}
        {periodBtn('next-week-btn', 'Next Week', 'next-week')}
        {periodBtn('this-month-btn', 'This Month', 'this-month')}
        {periodBtn('next-month-btn', 'Next Month', 'next-month')}
        {periodBtn('this-quarter-btn', 'This Quarter', 'this-quarter')}
        {periodBtn('next-quarter-btn', 'Next Quarter', 'next-quarter')}
        {periodBtn('this-year-btn', 'This Year', 'this-year')}
        {periodBtn('next-year-btn', 'Next Year', 'next-year')}

        <label htmlFor="modulo-select" style={{ alignSelf: 'center' }}>
          Modulo Age:{' '}
        </label>
        <select
          id="modulo-select"
          value={modulo}
          onChange={(e) => setModulo(e.target.value as 'none' | '5' | '10')}
        >
          <option value="none">None</option>
          <option value="5">Modulo 5</option>
          <option value="10">Modulo 10</option>
        </select>
      </div>

      <table id="birthdays-table">
        <thead>
          <tr>
            <th>
              First Name
              <button
                id="sort-first-name-btn"
                onClick={() => toggleSort('first_name')}
                className="sort-btn"
                style={{ color: 'grey', marginLeft: 8 }}
              >
                <span>{sortIndicator('first_name')}</span>
              </button>
            </th>
            <th>
              Last Name
              <button
                id="sort-last-name-btn"
                onClick={() => toggleSort('last_name')}
                className="sort-btn"
                style={{ color: 'grey', marginLeft: 8 }}
              >
                <span>{sortIndicator('last_name')}</span>
              </button>
            </th>
            <th>
              Day
              <button
                id="sort-day-btn"
                onClick={() => toggleSort('day')}
                className="sort-btn"
                style={{ color: 'grey', marginLeft: 8 }}
              >
                <span>{sortIndicator('day')}</span>
              </button>
            </th>
            <th>
              Month
              <button
                id="sort-month-btn"
                onClick={() => toggleSort('month')}
                className="sort-btn"
                style={{ color: 'grey', marginLeft: 8 }}
              >
                <span>{sortIndicator('month')}</span>
              </button>
            </th>
            <th>
              Year
              <button
                id="sort-year-btn"
                onClick={() => toggleSort('year')}
                className="sort-btn"
                style={{ color: 'grey', marginLeft: 8 }}
              >
                <span>{sortIndicator('year')}</span>
              </button>
            </th>
            <th>
              Age
              <button
                id="sort-age-btn"
                onClick={() => toggleSort('age')}
                className="sort-btn"
                style={{ color: 'grey', marginLeft: 8 }}
              >
                <span>{sortIndicator('age')}</span>
              </button>
            </th>
            <th>Next Birthday</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="birthdays-tbody">
          {filteredRows.map((row, i) => {
            const inEdit = editingIndex === i;
            const periodRange =
              activePeriod !== 'all' ? (getPeriodRange(activePeriod) as any) : null;
            return (
              <tr key={i}>
                {inEdit ? (
                  <>
                    {['first_name', 'last_name', 'day', 'month', 'year'].map((k) => (
                      <td key={k}>
                        <input
                          id={`edit-input-${i}-${k}`}
                          type={k === 'day' || k === 'month' || k === 'year' ? 'number' : 'text'}
                          min={k === 'day' ? 1 : k === 'month' ? 1 : k === 'year' ? 1900 : undefined}
                          max={k === 'day' ? 31 : k === 'month' ? 12 : undefined}
                          style={{ width: '90%' }}
                          value={(editValues as any)[k] ?? ''}
                          onChange={(e) =>
                            setEditValues((prev) => ({ ...prev, [k]: e.target.value }))
                          }
                        />
                      </td>
                    ))}
                  </>
                ) : (
                  <>
                    {HEADER_KEYS.map((k) => (
                      <td key={k}>{row[k]}</td>
                    ))}
                  </>
                )}
                <td>{computeAge(row)}</td>
                <td>{computeNextBirthdayDisplay(row, periodRange)}</td>
                <td>
                  {inEdit ? (
                    <>
                      <button className="btn-save" onClick={() => saveEdit(i)} style={{ marginRight: 8 }}>
                        Save
                      </button>
                      <button className="btn-cancel" onClick={cancelEdit}>Cancel</button>
                    </>
                  ) : (
                    <>
                      <button className="btn-edit" onClick={() => startEdit(i, row)} style={{ marginRight: 8 }}>
                        Edit
                      </button>
                      <button className="btn-delete" onClick={() => handleDelete(i)}>Delete</button>
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button id="add-row-btn" onClick={handleAddRow}>Add Row</button>
        <button id="save-github-btn" onClick={saveToGitHub}>Save to GitHub</button>
        <button id="set-api-base-btn" onClick={setBackendUrl}>Set Backend URL</button>
      </div>
    </div>
  );
}
