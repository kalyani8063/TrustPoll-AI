"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<1 | 2>(1);
  const [cooldown, setCooldown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [regMessage, setRegMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const handleStartVerification = async () => {
    if (loading) return;
    const cleanEmail = email.trim();

    if (!cleanEmail) {
      setRegMessage({ text: "Please fill in all fields.", type: "error" });
      return;
    }

    setLoading(true);
    setRegMessage(null);

    try {
      const res = await fetch(`${API_BASE}/register/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cleanEmail }),
      });

      const data = await res.json();

      if (res.ok) {
        setRegMessage({ text: data.message || "Verification code sent.", type: "success" });
        setStep(2);
        setCooldown(30);
      } else {
        setRegMessage({ text: data.error || "Failed to send verification code.", type: "error" });
      }
    } catch (err) {
      setRegMessage({ text: "Network error. Please try again.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (loading) return;
    const cleanEmail = email.trim();
    const cleanOtp = otp.trim();
    const cleanPassword = password.trim();

    if (!cleanOtp) {
      setRegMessage({ text: "Please enter the verification code.", type: "error" });
      return;
    }
    if (cleanPassword.length < 8) {
      setRegMessage({ text: "Password must be at least 8 characters.", type: "error" });
      return;
    }

    setLoading(true);
    setRegMessage(null);

    try {
      const res = await fetch(`${API_BASE}/register/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cleanEmail, otp: cleanOtp, password: cleanPassword }),
      });

      const data = await res.json();

      if (res.ok) {
        setRegMessage({ text: data.message || "Registration complete!", type: "success" });
        setTimeout(() => {
          router.push("/login");
        }, 1500);
      } else {
        setRegMessage({ text: data.error || "Verification failed.", type: "error" });
      }
    } catch {
      setRegMessage({ text: "Network error. Please try again.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((v) => v - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  return (
    <div className="relative min-h-screen overflow-hidden text-slate-100">
      <div className="pointer-events-none absolute inset-0 grid-overlay" />
      <div className="pointer-events-none absolute inset-0 noise-overlay" />
      <div className="pointer-events-none absolute left-[-10%] top-[-20%] h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="pointer-events-none absolute right-[-10%] top-[10%] h-[28rem] w-[28rem] rounded-full bg-amber-300/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-[-10%] left-[20%] h-[24rem] w-[24rem] rounded-full bg-violet-500/10 blur-3xl" />
      <div className="pointer-events-none absolute right-[10%] top-[25%] h-64 w-64 rounded-full aurora" />

      <div className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-16">
        <div className="grid w-full gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-3 rounded-full border border-slate-700/60 bg-slate-950/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-slate-300 shadow-sm fade-in-up">
              TrustPoll Protocol
              <span className="h-1.5 w-6 rounded-full bg-gradient-to-r from-cyan-400 via-sky-400 to-amber-300" />
            </div>
            <div className="space-y-4 fade-in-up delay-1">
              <h1 className="font-display text-4xl font-semibold tracking-tight text-slate-100 sm:text-6xl">
                Campus voting with verifiable trust and AI oversight.
              </h1>
              <p className="max-w-xl text-base text-slate-300 sm:text-lg">
                A blockchain-inspired ballot experience with rapid anomaly detection. Every vote is
                accountable, transparent, and protected from abuse.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-700/70 bg-slate-900/70 p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-100">Email-verified identity</p>
                <p className="mt-1 text-sm text-slate-400">One verified student, one vote.</p>
              </div>
              <div className="panel rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-100">On-chain audit trail</p>
                <p className="mt-1 text-sm text-slate-400">Every decision hash anchored to Algorand.</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3 text-xs uppercase tracking-[0.2em] text-slate-400 fade-in-up delay-3">
              <span className="chip rounded-full px-3 py-2">Email OTP</span>
              <span className="chip rounded-full px-3 py-2">Consensus checks</span>
              <span className="chip rounded-full px-3 py-2">Tamper detection</span>
            </div>
          </div>

          <div className="glass-panel rounded-3xl p-8 shadow-2xl">
            <div className="space-y-6">
              <div>
                <h2 className="font-display text-2xl font-semibold text-slate-100">
                  Start Voting
                </h2>
                <p className="mt-2 text-sm text-slate-400">
                  Register your VIT email to access the ballot.
                </p>
              </div>

              <div className="space-y-3">
                <Link
                  href="/register"
                  className="glow-button inline-flex w-full items-center justify-center rounded-xl bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-sky-400"
                >
                  Register to Vote
                </Link>
                <Link
                  href="/login"
                  className="inline-flex w-full items-center justify-center rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-sky-400/60"
                >
                  Log In
                </Link>
              </div>

              <div className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-slate-300">
                    Email Address
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    placeholder="VIT Email (@vit.edu)"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="mt-2 block w-full rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm text-slate-100 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
                  />
                </div>

                {step === 2 && (
                  <div>
                    <label htmlFor="otp" className="block text-sm font-medium text-slate-300">
                      Verification Code
                    </label>
                    <input
                      id="otp"
                      name="otp"
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      placeholder="Enter 6-digit code"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      className="mt-2 block w-full rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm text-slate-100 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
                    />
                  </div>
                )}
                {step === 2 && (
                  <div>
                    <label htmlFor="password" className="block text-sm font-medium text-slate-300">
                      Password
                    </label>
                    <input
                      id="password"
                      name="password"
                      type="password"
                      minLength={8}
                      placeholder="Set account password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="mt-2 block w-full rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm text-slate-100 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
                    />
                  </div>
                )}
              </div>

              {step === 1 ? (
                <button
                  onClick={handleStartVerification}
                  disabled={loading || cooldown > 0}
                  className="glow-button inline-flex w-full items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {cooldown > 0 ? `Resend in ${cooldown}s` : loading ? "Sending..." : "Send Verification Code"}
                </button>
              ) : (
                <div className="space-y-3">
                  <button
                    onClick={handleVerify}
                    disabled={loading}
                    className="glow-button inline-flex w-full items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loading ? "Verifying..." : "Verify & Register"}
                  </button>
                  <button
                    onClick={handleStartVerification}
                    disabled={loading || cooldown > 0}
                    className="w-full text-sm font-semibold text-sky-300 transition hover:text-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend verification code"}
                  </button>
                </div>
              )}

              {regMessage && (
                <div
                  className={`rounded-xl border px-4 py-3 text-sm font-medium ${
                    regMessage.type === "success"
                      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                      : "border-rose-500/40 bg-rose-500/10 text-rose-200"
                  }`}
                >
                  {regMessage.text}
                </div>
              )}

              <div className="text-center">
                <p className="text-sm text-slate-400">
                  Already registered?{" "}
                  <Link href="/login" className="font-semibold text-sky-300 hover:text-sky-200">
                    Log in here
                  </Link>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto w-full max-w-6xl px-6 pb-20">
        <div className="panel-strong rounded-3xl p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="font-display text-2xl font-semibold text-slate-100">Public Results</h3>
              <p className="mt-2 text-sm text-slate-400">
                Results appear only after an admin publishes them.
              </p>
            </div>
            <span className="chip rounded-full px-3 py-2 text-xs uppercase tracking-[0.2em] text-slate-300">
              Transparency
            </span>
          </div>

          <div className="mt-6">
            {!published && (
              <div className="rounded-2xl border border-slate-700/70 bg-slate-900/60 px-4 py-6 text-center text-sm text-slate-400">
                Results are not yet published.
              </div>
            )}
            {published && resultsError && (
              <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-6 text-center text-sm text-rose-200">
                {resultsError}
              </div>
            )}
            {published && !resultsError && (
              <div className="space-y-6">
                {governanceWarning && (
                  <div className="rounded-2xl border border-rose-500/50 bg-rose-500/10 px-4 py-4 text-sm font-semibold text-rose-200">
                    ⚠ Governance Integrity Compromised
                  </div>
                )}

                <div className="grid gap-4 md:grid-cols-2">
                  {results.length === 0 ? (
                    <div className="rounded-2xl border border-slate-700/70 bg-slate-900/60 px-4 py-6 text-center text-sm text-slate-400">
                      No votes recorded yet.
                    </div>
                  ) : (
                    results.map((entry) => (
                      <div key={entry.id} className="rounded-2xl border border-slate-700/70 bg-slate-900/60 px-4 py-4">
                        <p className="text-sm font-semibold text-slate-100">{entry.name}</p>
                        <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                          Votes
                        </p>
                        <p className="mt-1 text-2xl font-semibold text-emerald-200">{entry.votes}</p>
                      </div>
                    ))
                  )}
                </div>

                <div className="rounded-2xl border border-slate-700/70 bg-slate-900/60 px-4 py-4">
                  <h4 className="text-sm font-semibold text-slate-100">Governance Integrity Audit</h4>
                  {!governanceAudit ? (
                    <p className="mt-2 text-sm text-slate-400">Governance audit data not available yet.</p>
                  ) : (
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <p className="text-sm text-slate-300">Total admin high-risk events: <span className="font-semibold text-slate-100">{governanceAudit.total_admin_high_risk_events}</span></p>
                      <p className="text-sm text-slate-300">Total critical events: <span className="font-semibold text-slate-100">{governanceAudit.total_admin_critical_events}</span></p>
                      <p className="text-sm text-slate-300">Blockchain verification: <span className="font-semibold text-slate-100">{governanceAudit.blockchain_verification_status}</span></p>
                      <p className="text-sm text-slate-300">Tampering detection: <span className="font-semibold text-slate-100">{governanceAudit.tampering_detection_result}</span></p>
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-700/70 bg-slate-900/60 px-4 py-4">
                  <h4 className="text-sm font-semibold text-slate-100">Election Fairness Index</h4>
                  {!fairnessIndex ? (
                    <p className="mt-2 text-sm text-slate-400">Fairness index has not been generated yet.</p>
                  ) : (
                    <div className="mt-3 space-y-3">
                      <p className="text-3xl font-semibold text-emerald-200">{fairnessIndex.fairness_score.toFixed(1)}%</p>
                      <p className="text-xs text-slate-400">{fairnessIndex.formula?.equation || "Transparent scoring formula applied."}</p>
                      <div className="grid gap-2 md:grid-cols-2">
                        <p className="text-sm text-slate-300">Tampering attempts: <span className="font-semibold text-slate-100">{fairnessIndex.metrics?.tampering_attempts_detected ?? 0}</span></p>
                        <p className="text-sm text-slate-300">Duplicate blocked: <span className="font-semibold text-slate-100">{fairnessIndex.metrics?.duplicate_attempts_blocked ?? 0}</span></p>
                        <p className="text-sm text-slate-300">Timing clusters: <span className="font-semibold text-slate-100">{fairnessIndex.metrics?.abnormal_timing_clusters ?? 0}</span></p>
                        <p className="text-sm text-slate-300">Suspicious IP clusters: <span className="font-semibold text-slate-100">{fairnessIndex.metrics?.suspicious_ip_clusters ?? 0}</span></p>
                        <p className="text-sm text-slate-300">Admin high-risk events: <span className="font-semibold text-slate-100">{fairnessIndex.metrics?.admin_high_risk_events ?? 0}</span></p>
                        <p className="text-sm text-slate-300">Admin critical events: <span className="font-semibold text-slate-100">{fairnessIndex.metrics?.admin_critical_events ?? 0}</span></p>
                      </div>
                      <p className="text-xs text-slate-400">
                        Hash: {fairnessIndex.fairness_hash || "N/A"} | Tx: {fairnessIndex.algorand_tx_id || "Not anchored"} | Computed: {fairnessIndex.computed_at ? new Date(fairnessIndex.computed_at).toLocaleString() : "Unknown"}
                      </p>
                      {fairnessIndex.governance_risk_flag && (
                        <p className="text-xs font-semibold text-rose-300">Governance risk impacted this score.</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
