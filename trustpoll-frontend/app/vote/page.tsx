"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Candidate {
  id: number;
  name: string;
}

export default function VotePage() {
  const router = useRouter();
  const [wallet, setWallet] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    const storedWallet = localStorage.getItem("user_wallet");
    if (!storedWallet) {
      router.push("/login");
      return;
    }
    setWallet(storedWallet);

    const loadCandidates = async () => {
      try {
        const res = await fetch(`${API_BASE}/candidates`);
        if (res.ok) {
          const data = await res.json();
          setCandidates(data);
        } else {
          setStatus({ type: "error", text: "Failed to load candidates." });
        }
      } catch {
        setStatus({ type: "error", text: "Network error while loading candidates." });
      }
    };

    loadCandidates();
  }, [router]);

  const handleVote = async () => {
    if (!selectedCandidate) {
      setStatus({ type: "error", text: "Please select a candidate." });
      return;
    }

    const selected = candidates.find((c) => c.id === selectedCandidate);
    const confirmed = window.confirm(
      `Confirm your vote for ${selected?.name || "this candidate"}? This action cannot be undone.`
    );
    if (!confirmed) return;

    setLoading(true);
    setStatus(null);

    try {
      const voteRes = await fetch(`${API_BASE}/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wallet, candidate_id: selectedCandidate }),
      });

      const voteData = await voteRes.json();
      if (voteRes.ok) {
        setStatus({ type: "success", text: voteData.message || "Vote cast successfully." });
        setSelectedCandidate(null);
      } else {
        setStatus({ type: "error", text: voteData.error || "Failed to cast vote." });
      }
    } catch {
      setStatus({ type: "error", text: "Network error. Please try again." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4 py-12 dark:bg-zinc-900 sm:px-6 lg:px-8">
      <div className="w-full max-w-2xl space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
            Cast Your Vote
          </h1>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Logged in wallet: <span className="font-semibold">{wallet || "Loading..."}</span>
          </p>
        </div>

        <div className="rounded-xl bg-white p-8 shadow-lg dark:bg-zinc-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Select a Candidate</h2>

          <div className="mt-4 space-y-3">
            {candidates.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">No candidates available.</p>
            ) : (
              candidates.map((candidate) => (
                <label
                  key={candidate.id}
                  className="flex items-center gap-3 rounded-md border border-gray-200 px-4 py-3 text-sm text-gray-900 hover:border-indigo-400 dark:border-zinc-700 dark:text-white"
                >
                  <input
                    type="radio"
                    name="candidate"
                    value={candidate.id}
                    checked={selectedCandidate === candidate.id}
                    onChange={() => setSelectedCandidate(candidate.id)}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500"
                  />
                  {candidate.name}
                </label>
              ))
            )}
          </div>

          {status && (
            <div
              className={`mt-6 rounded-md p-4 ${
                status.type === "success"
                  ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                  : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
              }`}
            >
              <p className="text-sm font-medium">{status.text}</p>
            </div>
          )}

          <button
            onClick={handleVote}
            disabled={loading || candidates.length === 0}
            className="mt-6 flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Submitting..." : "Submit Vote"}
          </button>

        </div>
      </div>
    </div>
  );
}
