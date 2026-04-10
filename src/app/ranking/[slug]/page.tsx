"use client";

import { useEffect, useState } from "react";

type ScoreEntry = {
  id: string;
  quizSlug: string;
  quizTitle: string;
  nickname: string;
  score: number;
  totalQuestions: number;
  createdAt: string;
};

export default function QuizRankingPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const [scores, setScores] = useState<ScoreEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [slug, setSlug] = useState("");

  useEffect(() => {
    async function init() {
      const resolved = await params;
      setSlug(resolved.slug);

      const res = await fetch(`/api/rankings/${resolved.slug}`);
      const data = await res.json();
      setScores(data);
      setLoading(false);
    }

    init();
  }, [params]);

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
      <div className="mx-auto max-w-5xl">
        <h1 className="mb-6 text-4xl font-bold">Ranking: {slug}</h1>

        {loading ? (
          <p className="text-slate-300">Cargando ranking...</p>
        ) : scores.length === 0 ? (
          <p className="text-slate-300">Todavía no hay puntuaciones guardadas para este quiz.</p>
        ) : (
          <div className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-900">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-left">
                  <th className="px-4 py-4">#</th>
                  <th className="px-4 py-4">Nick</th>
                  <th className="px-4 py-4">Score</th>
                  <th className="px-4 py-4">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {scores.map((entry, index) => (
                  <tr key={entry.id} className="border-b border-slate-800 last:border-0">
                    <td className="px-4 py-4">{index + 1}</td>
                    <td className="px-4 py-4 font-semibold">{entry.nickname}</td>
                    <td className="px-4 py-4 text-green-400">
                      {entry.score}/{entry.totalQuestions}
                    </td>
                    <td className="px-4 py-4 text-slate-400">
                      {new Date(entry.createdAt).toLocaleString("es-ES")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}