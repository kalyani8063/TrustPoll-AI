"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
const ADMIN_EMAIL = "kalyani.bhintade@vit.edu";

interface Stats {
  users: number;
  vote_attempts: number;
  ai_flags: number;
}

interface AiFlag {
  wallet: string;
  reason: string;
  severity: number;
  created_at: string;
}

interface Candidate {
  id: number;
  name: string;
  votes: number;
}

export default function AdminPage() {
  const [email, setEmail] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authError, setAuthError] = useState("");
  
  const [stats, setStats] = useState<Stats | null>(null);
  const [flags, setFlags] = useState<AiFlag[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [newCandidate, setNewCandidate] = useState("");
  const [addingCandidate, setAddingCandidate] = useState(false);
  const [candidateMessage, setCandidateMessage] = useState<string | null>(null);

  const handleLogin = () => {
    if (email.trim() === ADMIN_EMAIL) {
      setIsAuthenticated(true);
      setAuthError("");
      fetchDashboardData();
    } else {
      setAuthError("Unauthorized access");
    }
  };

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [statsRes, flagsRes, candidatesRes] = await Promise.all([
        fetch(`${API_BASE}/admin/stats`),
        fetch(`${API_BASE}/admin/ai-flags`),
        fetch(`${API_BASE}/admin/candidates`)
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
      
      if (flagsRes.ok) {
        const flagsData = await flagsRes.json();
        setFlags(flagsData);
      }

      if (candidatesRes.ok) {
        const candidatesData = await candidatesRes.json();
        setCandidates(candidatesData);
      }
    } catch (error) {
      console.error("Failed to fetch admin data", error);
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (wallet: string) => {
    setActionLoading(wallet);
    try {
      const res = await fetch(`${API_BASE}/admin/acknowledge-flag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wallet }),
      });

      if (res.ok) {
        const flagsRes = await fetch(`${API_BASE}/admin/ai-flags`);
        if (flagsRes.ok) {
          const flagsData = await flagsRes.json();
          setFlags(flagsData);
        }
      }
    } catch (error) {
      console.error("Failed to acknowledge flag", error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddCandidate = async () => {
    const trimmedName = newCandidate.trim();
    if (!trimmedName) return;
    setAddingCandidate(true);
    setCandidateMessage(null);
    try {
      const res = await fetch(`${API_BASE}/admin/add-candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmedName }),
      });
      if (res.ok) {
        setNewCandidate("");
        setCandidateMessage("Candidate added. Voters can refresh to see the update.");
        // Refresh candidates
        const cRes = await fetch(`${API_BASE}/admin/candidates`);
        if (cRes.ok) setCandidates(await cRes.json());
      } else {
        const data = await res.json();
        setCandidateMessage(data.error || "Failed to add candidate.");
      }
    } catch (error) {
      console.error("Failed to add candidate");
      setCandidateMessage("Network error while adding candidate.");
    } finally {
      setAddingCandidate(false);
    }
  };

  const getSeverityColor = (severity: number) => {
    if (severity >= 7) return "text-red-600 bg-red-50 border-red-200";
    if (severity >= 4) return "text-yellow-600 bg-yellow-50 border-yellow-200";
    return "text-green-600 bg-green-50 border-green-200";
  };

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-zinc-900">
        <div className="w-full max-w-md space-y-8 rounded-xl bg-white p-8 shadow-lg dark:bg-zinc-800">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Access</h2>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              Enter authorized email to view dashboard
            </p>
          </div>
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Admin Email
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-indigo-500 dark:bg-zinc-700 dark:border-zinc-600 dark:text-white"
                placeholder="admin@vit.edu"
              />
            </div>
            {authError && <p className="text-sm text-red-600">{authError}</p>}
            <button
              onClick={handleLogin}
              className="w-full rounded-md bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              Access Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8 dark:bg-zinc-900">
      <div className="mx-auto max-w-5xl space-y-8">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Admin Dashboard</h1>
          <button 
            onClick={() => setIsAuthenticated(false)}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Logout
          </button>
        </div>

        {loading && !stats ? (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">Loading dashboard data...</div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
              <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
                <dt className="truncate text-sm font-medium text-gray-500 dark:text-gray-400">Total Registered Users</dt>
                <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">{stats?.users || 0}</dd>
              </div>
              <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
                <dt className="truncate text-sm font-medium text-gray-500 dark:text-gray-400">Total Vote Attempts</dt>
                <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">{stats?.vote_attempts || 0}</dd>
              </div>
              <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
                <dt className="truncate text-sm font-medium text-gray-500 dark:text-gray-400">Total AI Flags</dt>
                <dd className="mt-1 text-3xl font-semibold tracking-tight text-red-600 dark:text-red-400">{stats?.ai_flags || 0}</dd>
              </div>
            </div>

            {/* Candidate Management */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white">Add Candidate</h3>
                <div className="mt-4 flex gap-4">
                  <input
                    type="text"
                    value={newCandidate}
                    onChange={(e) => setNewCandidate(e.target.value)}
                    placeholder="Candidate Name"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-zinc-700 dark:border-zinc-600 dark:text-white sm:text-sm"
                  />
                  <button
                    onClick={handleAddCandidate}
                    disabled={addingCandidate}
                    className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {addingCandidate ? "Adding..." : "Add"}
                  </button>
                </div>
                {candidateMessage && (
                  <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">{candidateMessage}</p>
                )}
              </div>

              <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white">Live Vote Counts</h3>
                <div className="mt-4 flow-root">
                  <ul className="-my-5 divide-y divide-gray-200 dark:divide-zinc-700">
                    {candidates.map((candidate) => (
                      <li key={candidate.id} className="py-4">
                        <div className="flex items-center space-x-4">
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                              {candidate.name}
                            </p>
                          </div>
                          <div className="inline-flex items-center text-base font-semibold text-gray-900 dark:text-white">
                            {candidate.votes} votes
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            <div className="overflow-hidden rounded-lg bg-white shadow dark:bg-zinc-800">
              <div className="border-b border-gray-200 px-6 py-4 dark:border-zinc-700">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white">AI Anomaly Flags</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-zinc-700">
                  <thead className="bg-gray-50 dark:bg-zinc-900">
                    <tr>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Wallet</th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Reason</th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Severity</th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Time</th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white dark:divide-zinc-700 dark:bg-zinc-800">
                    {flags.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                          No active flags detected.
                        </td>
                      </tr>
                    ) : (
                      flags.map((flag, idx) => (
                        <tr key={`${flag.wallet}-${idx}`}>
                          <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">
                            {flag.wallet}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                            {flag.reason}
                          </td>
                          <td className="whitespace-nowrap px-6 py-4 text-sm">
                            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border ${getSeverityColor(flag.severity)}`}>
                              {flag.severity}/10
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                            {new Date(flag.created_at).toLocaleString()}
                          </td>
                          <td className="whitespace-nowrap px-6 py-4 text-sm">
                            <button
                              onClick={() => handleAcknowledge(flag.wallet)}
                              disabled={actionLoading === flag.wallet}
                              className="rounded bg-indigo-50 px-2 py-1 text-xs font-semibold text-indigo-600 shadow-sm hover:bg-indigo-100 disabled:opacity-50 dark:bg-indigo-900/30 dark:text-indigo-400 dark:hover:bg-indigo-900/50"
                            >
                              {actionLoading === flag.wallet ? "Processing..." : "Mark as Reviewed"}
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
