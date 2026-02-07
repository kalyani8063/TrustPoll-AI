"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export default function Home() {
  const [email, setEmail] = useState("");
  const [wallet, setWallet] = useState("");
  const [loading, setLoading] = useState(false);
  const [regMessage, setRegMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [voteMessage, setVoteMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const handleRegister = async () => {
    if (!email || !wallet) {
      setRegMessage({ text: "Please fill in all fields.", type: "error" });
      return;
    }
    setLoading(true);
    setRegMessage(null);
    setVoteMessage(null);

    try {
      const res = await fetch(`${API_BASE}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, wallet }),
      });

      const data = await res.json();

      if (res.ok) {
        setRegMessage({ text: data.message || "Registration successful!", type: "success" });
      } else {
        setRegMessage({ text: data.error || "Registration failed.", type: "error" });
      }
    } catch (error) {
      setRegMessage({ text: "Network error. Please try again.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleVote = async () => {
    if (!wallet) {
      setVoteMessage({ text: "Please enter a wallet address above.", type: "error" });
      return;
    }
    setLoading(true);
    setVoteMessage(null);
    setRegMessage(null);

    try {
      const res = await fetch(`${API_BASE}/vote-attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wallet }),
      });

      const data = await res.json();

      if (data.allowed) {
        setVoteMessage({ text: "✅ Vote accepted and forwarded to blockchain", type: "success" });
      } else {
        setVoteMessage({ text: `❌ ${data.reason || "Vote rejected"}`, type: "error" });
      }
    } catch (error) {
      setVoteMessage({ text: "❌ Network error during voting.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4 py-12 dark:bg-zinc-900 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white">
            TrustPoll
          </h1>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Decentralized campus voting using Blockchain + AI monitoring
          </p>
        </div>

        <div className="rounded-xl bg-white p-8 shadow-lg dark:bg-zinc-800">
          {/* Registration Section */}
          <div className="space-y-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Registration</h2>
            
            <div>
              <label htmlFor="email" className="block text-sm font-medium leading-6 text-gray-900 dark:text-gray-200">
                Email Address
              </label>
              <div className="mt-2">
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  placeholder="VIT Email (@vit.edu)"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-md border-0 py-1.5 pl-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 dark:bg-zinc-700 dark:text-white dark:ring-zinc-600 sm:text-sm sm:leading-6"
                />
              </div>
            </div>

            <div>
              <label htmlFor="wallet" className="block text-sm font-medium leading-6 text-gray-900 dark:text-gray-200">
                Wallet Address
              </label>
              <div className="mt-2">
                <input
                  id="wallet"
                  name="wallet"
                  type="text"
                  required
                  placeholder="Wallet Address"
                  value={wallet}
                  onChange={(e) => setWallet(e.target.value)}
                  className="block w-full rounded-md border-0 py-1.5 pl-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 dark:bg-zinc-700 dark:text-white dark:ring-zinc-600 sm:text-sm sm:leading-6"
                />
              </div>
            </div>

            <button
              onClick={handleRegister}
              disabled={loading}
              className="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Processing..." : "Register"}
            </button>

            {regMessage && (
              <div className={`rounded-md p-4 ${regMessage.type === 'success' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`}>
                <p className="text-sm font-medium">{regMessage.text}</p>
              </div>
            )}
          </div>

          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center" aria-hidden="true">
              <div className="w-full border-t border-gray-300 dark:border-zinc-600" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-white px-2 text-sm text-gray-500 dark:bg-zinc-800 dark:text-gray-400">
                Voting Section
              </span>
            </div>
          </div>

          {/* Voting Section */}
          <div className="space-y-6">
            <button
              onClick={handleVote}
              disabled={loading}
              className="flex w-full justify-center rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-emerald-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Processing..." : "Vote"}
            </button>

            {voteMessage && (
              <div className={`rounded-md p-4 ${voteMessage.type === 'success' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`}>
                <p className="text-sm font-medium">{voteMessage.text}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
