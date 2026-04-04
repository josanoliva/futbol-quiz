import Link from "next/link";
import { getHomeQuizzes, getFeaturedQuiz, getCategories } from "@/lib/quizzes";

export default function Home() {
  const quizzes = getHomeQuizzes();
  const featuredQuiz = getFeaturedQuiz();
  const categories = getCategories(quizzes);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <section className="mx-auto max-w-6xl px-6 py-12">
        {featuredQuiz && (
          <div className="mb-10 rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-lg">
            <p className="mb-2 text-sm uppercase tracking-widest text-green-400">
              Quiz destacado
            </p>
            <h1 className="mb-3 text-4xl font-bold">{featuredQuiz.title}</h1>
            <p className="mb-6 max-w-2xl text-slate-300">
              {featuredQuiz.description}
            </p>

            <div className="flex gap-3">
              <Link
                href={`/quiz/${featuredQuiz.slug}`}
                className="rounded-2xl bg-green-500 px-5 py-3 font-semibold text-slate-950 hover:bg-green-400"
              >
                Jugar ahora
              </Link>
              <Link
                href="/ranking"
                className="rounded-2xl border border-slate-700 px-5 py-3 font-semibold text-white hover:bg-slate-800"
              >
                Ver ranking
              </Link>
            </div>
          </div>
        )}

        <section className="mb-10">
          <h2 className="mb-4 text-2xl font-bold">Explora por categoría</h2>
          <div className="flex flex-wrap gap-3">
            <span className="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200">
              Todos
            </span>
            {categories.map((category) => (
              <span
                key={category}
                className="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200"
              >
                {category}
              </span>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-4 text-2xl font-bold">Quizzes disponibles</h2>

          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {quizzes.map((quiz) => (
              <article
                key={quiz.slug}
                className="rounded-3xl border border-slate-800 bg-slate-900 p-6 shadow-lg"
              >
                <p className="mb-2 text-sm text-green-400">{quiz.category}</p>
                <h3 className="mb-3 text-xl font-semibold">{quiz.title}</h3>
                <p className="mb-5 text-slate-300">{quiz.description}</p>

                <div className="flex gap-3">
                  <Link
                    href={`/quiz/${quiz.slug}`}
                    className="rounded-2xl bg-white px-4 py-2 font-medium text-slate-950 hover:bg-slate-200"
                  >
                    Jugar
                  </Link>
                  <Link
                    href={`/ranking/${quiz.slug}`}
                    className="rounded-2xl border border-slate-700 px-4 py-2 font-medium text-white hover:bg-slate-800"
                  >
                    Ranking
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}