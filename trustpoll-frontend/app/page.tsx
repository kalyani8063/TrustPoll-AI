"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
const WALLET_REGEX = /^WALLET_[A-Z0-9]{4,8}$/;

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [wallet, setWallet] = useState("");
  const [loading, setLoading] = useState(false);
  const [regMessage, setRegMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const handleRegister = async () => {
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
      const res = await fetch(`${API_BASE}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cleanEmail, wallet: cleanWallet }),
      });

      const data = await res.json();

      if (res.status === 409) {
        setRegMessage({
          text: "This wallet address is already registered. Please choose a different WALLET_XXXX.",
          type: "error",
        });
        return;
      }

      if (res.ok) {
        setRegMessage({ text: data.message || "Registration successful!", type: "success" });
        setTimeout(() => {
          router.push("/login");
        }, 1500);
      } else {
        setRegMessage({ text: data.error || "Registration failed.", type: "error" });
      }
    } catch (err) {
      setRegMessage({ text: "Network error. Please try again.", type: "error" });
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
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">New Student Registration</h2>
            
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
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Use demo wallet format: WALLET_XXXX
              </p>
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
          
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Already registered?{" "}
              <Link href="/login" className="font-semibold text-indigo-600 hover:text-indigo-500">
                Log in here
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
