"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
const WALLET_REGEX = /^WALLET_[A-Z0-9]{4,8}$/;

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [wallet, setWallet] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<1 | 2>(1);
  const [cooldown, setCooldown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [regMessage, setRegMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const handleStartVerification = async () => {
    if (loading) return;
    const cleanEmail = email.trim();
    const cleanWallet = wallet.trim().toUpperCase();

    if (!cleanEmail || !cleanWallet) {
      setRegMessage({ text: "Please fill in all fields.", type: "error" });
      return;
    }
    if (!WALLET_REGEX.test(cleanWallet)) {
      setRegMessage({ text: "Wallet must follow format: WALLET_XXXX", type: "error" });
      return;
    }

    setLoading(true);
    setRegMessage(null);

    try {
      const res = await fetch(`${API_BASE}/register/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cleanEmail, wallet: cleanWallet }),
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
    const cleanWallet = wallet.trim().toUpperCase();
    const cleanOtp = otp.trim();

    if (!cleanOtp) {
      setRegMessage({ text: "Please enter the verification code.", type: "error" });
      return;
    }

    setLoading(true);
    setRegMessage(null);

    try {
      const res = await fetch(`${API_BASE}/register/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cleanEmail, wallet: cleanWallet, otp: cleanOtp }),
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
      <div className="pointer-events-none absolute -top-24 right-0 h-80 w-80 rounded-full bg-sky-500/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 left-10 h-96 w-96 rounded-full bg-cyan-400/20 blur-3xl" />
      <div className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-16">
        <div className="grid w-full gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-900/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-300 shadow-sm">
              TrustPoll Protocol
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
            </div>
            <div className="space-y-4">
              <h1 className="font-display text-4xl font-semibold tracking-tight text-slate-100 sm:text-5xl">
                Campus voting with verifiable trust and AI oversight.
              </h1>
              <p className="max-w-xl text-base text-slate-300 sm:text-lg">
                A blockchain-inspired ballot experience with rapid anomaly detection. Every vote is
                accountable, transparent, and protected from abuse.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-700/70 bg-slate-900/70 p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-100">Wallet-linked identity</p>
                <p className="mt-1 text-sm text-slate-400">One wallet, one vote, enforced by policy.</p>
              </div>
              <div className="rounded-2xl border border-slate-700/70 bg-slate-900/70 p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-100">AI anomaly monitoring</p>
                <p className="mt-1 text-sm text-slate-400">Flags rapid or suspicious attempts.</p>
              </div>
            </div>
          </div>

          <div className="glass-panel rounded-3xl p-8">
            <div className="space-y-6">
              <div>
                <h2 className="font-display text-2xl font-semibold text-slate-100">
                  New Student Registration
                </h2>
                <p className="mt-2 text-sm text-slate-400">
                  Register your VIT email and wallet to access the ballot.
                </p>
              </div>

              <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                <span className={`rounded-full px-3 py-1 ${step === 1 ? "bg-sky-500/20 text-sky-200" : "bg-slate-800/70"}`}>
                  Step 1: Email
                </span>
                <span className={`rounded-full px-3 py-1 ${step === 2 ? "bg-sky-500/20 text-sky-200" : "bg-slate-800/70"}`}>
                  Step 2: OTP
                </span>
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

                <div>
                  <label htmlFor="wallet" className="block text-sm font-medium text-slate-300">
                    Wallet Address
                  </label>
                  <input
                    id="wallet"
                    name="wallet"
                    type="text"
                    required
                    placeholder="WALLET_XXXX"
                    value={wallet}
                    onChange={(e) => setWallet(e.target.value)}
                    className="mt-2 block w-full rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm text-slate-100 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
                  />
                  <p className="mt-2 text-xs text-slate-500">Use demo wallet format: WALLET_XXXX</p>
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
    </div>
  );
}
