export default async function QuizRankingPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-4 text-4xl font-bold">Ranking: {slug}</h1>
        <p className="text-slate-300">
          Aquí irá el ranking específico de este quiz.
        </p>
      </div>
    </main>
  );
}