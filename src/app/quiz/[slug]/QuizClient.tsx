"use client";

import { useEffect, useMemo, useState } from "react";
import AffiliateBlock from "@/components/AffiliateBlock";

type Difficulty = "easy" | "medium" | "hard";

type QuizQuestion = {
  id: string;
  question: string;
  options: string[];
  correctIndex: number;
  difficulty: Difficulty;
  tags: string[];
};

type QuizData = {
  slug: string;
  title: string;
  description: string;
  category: string;
  featured: boolean;
  showOnHome: boolean;
  homeOrder: number;
  timeLimitSeconds: number;
  questions: QuizQuestion[];
};

type AffiliateItem = {
  id: string;
  title: string;
  description: string;
  url: string;
  cta: string;
};

type FeedbackPayload = {
  quizSlug: string;
  questionId: string;
  selectedOptionIndex: number | null;
  message: string;
};

const affiliateItems: AffiliateItem[] = [
  {
      "id": "camisetas",
      "title": "Camisetas de fútbol",
      "description": "Camisetas de clubes, selecciones y leyendas.",
      "url": "https://amzn.to/48mIhM3",
      "cta": "Ver camisetas"
    },
    {
      "id": "balones",
      "title": "Balones de fútbol",
      "description": "Balones para jugar, entrenar o regalar.",
      "url": "https://amzn.to/3PRDPib",
      "cta": "Ver balones"
    },
    {
      "id": "botas",
      "title": "Botas de fútbol",
      "description": "Botas para césped natural, artificial y sala.",
      "url": "https://amzn.to/47GOxhF",
      "cta": "Ver botas"
    },
    {
      "id": "libros",
      "title": "Libros de fútbol",
      "description": "Biografías, historia y táctica para fans del fútbol.",
      "url": "https://amzn.to/48uEBYK",
      "cta": "Ver libros"
    },
    {
      "id": "regalos",
      "title": "Regalos futboleros",
      "description": "Ideas para fans: posters, tazas, bufandas y más.",
      "url": "https://amzn.to/4tbeTRH",
      "cta": "Ver regalos"
    },
];

function shuffleArray<T>(array: T[]): T[] {
  const copy = [...array];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function buildBalancedQuestionSet(questions: QuizQuestion[]): QuizQuestion[] {
  const easy = shuffleArray(questions.filter((q) => q.difficulty === "easy"));
  const medium = shuffleArray(questions.filter((q) => q.difficulty === "medium"));
  const hard = shuffleArray(questions.filter((q) => q.difficulty === "hard"));

  const easyQueue = [...easy];
  const mediumQueue = [...medium];
  const hardQueue = [...hard];

  const result: QuizQuestion[] = [];

  const difficultyFlow: Difficulty[] = [
    "easy",
    "easy",
    "easy",
    "medium",
    "medium",
    "medium",
    "medium",
    "medium",
    "hard",
    "medium",
    "hard",
    "medium",
    "hard",
    "hard",
    "medium",
    "hard",
    "hard",
    "medium",
    "hard",
    "hard",
    "medium",
    "hard",
    "hard",
    "medium",
    "hard",
  ];

  function pickQuestion(preferred: Difficulty): QuizQuestion | null {
    if (preferred === "easy" && easyQueue.length) return easyQueue.shift() ?? null;
    if (preferred === "medium" && mediumQueue.length) return mediumQueue.shift() ?? null;
    if (preferred === "hard" && hardQueue.length) return hardQueue.shift() ?? null;

    if (preferred === "easy") {
      if (mediumQueue.length) return mediumQueue.shift() ?? null;
      if (hardQueue.length) return hardQueue.shift() ?? null;
    }

    if (preferred === "medium") {
      if (hardQueue.length) return hardQueue.shift() ?? null;
      if (easyQueue.length) return easyQueue.shift() ?? null;
    }

    if (preferred === "hard") {
      if (mediumQueue.length) return mediumQueue.shift() ?? null;
      if (easyQueue.length) return easyQueue.shift() ?? null;
    }

    return null;
  }

  for (const difficulty of difficultyFlow) {
    const question = pickQuestion(difficulty);
    if (!question) break;
    result.push(question);
  }

  const remaining = shuffleArray([...easyQueue, ...mediumQueue, ...hardQueue]);
  return [...result, ...remaining];
}

export default function QuizClient({ quiz }: { quiz: QuizData }) {
  const preparedQuestions = useMemo(() => {
    return buildBalancedQuestionSet(quiz.questions);
  }, [quiz.questions]);

  const [timeLeft, setTimeLeft] = useState(quiz.timeLimitSeconds);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);

  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [showCorrection, setShowCorrection] = useState(false);

  const [showReportBox, setShowReportBox] = useState(false);
  const [reportText, setReportText] = useState("");
  const [reportSent, setReportSent] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");

  const [nickname, setNickname] = useState("");
  const [scoreSaved, setScoreSaved] = useState(false);
  const [savingScore, setSavingScore] = useState(false);
  const [scoreError, setScoreError] = useState("");

  useEffect(() => {
    if (finished) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setFinished(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [finished]);

  const currentQuestion = useMemo(() => {
    return preparedQuestions[currentIndex] ?? null;
  }, [preparedQuestions, currentIndex]);

  function moveToNextQuestion() {
    const nextIndex = currentIndex + 1;

    setSelectedAnswer(null);
    setShowCorrection(false);
    setShowReportBox(false);
    setReportText("");
    setReportSent(false);
    setReportLoading(false);
    setReportError("");

    if (nextIndex >= preparedQuestions.length) {
      setFinished(true);
      return;
    }

    setCurrentIndex(nextIndex);
  }

  function handleAnswer(index: number) {
    if (!currentQuestion || finished || showCorrection) return;

    setSelectedAnswer(index);
    setShowCorrection(true);

    if (index === currentQuestion.correctIndex) {
      setScore((prev) => prev + 1);
    }

    setTimeout(() => {
      moveToNextQuestion();
    }, 1500);
  }

  function getOptionClass(index: number) {
    if (!showCorrection || !currentQuestion) {
      return "rounded-2xl border border-slate-700 bg-slate-950 px-4 py-4 text-left hover:bg-slate-800";
    }

    if (index === currentQuestion.correctIndex) {
      return "rounded-2xl border border-green-500 bg-green-950 px-4 py-4 text-left";
    }

    if (index === selectedAnswer && index !== currentQuestion.correctIndex) {
      return "rounded-2xl border border-red-500 bg-red-950 px-4 py-4 text-left";
    }

    return "rounded-2xl border border-slate-700 bg-slate-950 px-4 py-4 text-left opacity-70";
  }

  async function handleReportSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!currentQuestion || !reportText.trim()) return;

    try {
      setReportLoading(true);
      setReportError("");

      const payload: FeedbackPayload = {
        quizSlug: quiz.slug,
        questionId: currentQuestion.id,
        selectedOptionIndex: selectedAnswer,
        message: reportText.trim(),
      };

      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error("No se pudo guardar la sugerencia");
      }

      setReportSent(true);
      setReportText("");
    } catch {
      setReportError("No se pudo guardar la sugerencia. Prueba de nuevo.");
    } finally {
      setReportLoading(false);
    }
  }

  async function handleSaveScore(e: React.FormEvent) {
    e.preventDefault();

    if (!nickname.trim()) {
      setScoreError("Pon un nick para guardar tu score.");
      return;
    }

    try {
      setSavingScore(true);
      setScoreError("");

      const res = await fetch("/api/scores", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          quizSlug: quiz.slug,
          quizTitle: quiz.title,
          nickname: nickname.trim(),
          score,
          totalQuestions: preparedQuestions.length,
        }),
      });

      if (!res.ok) {
        throw new Error("No se pudo guardar el score");
      }

      setScoreSaved(true);
    } catch {
      setScoreError("No se pudo guardar tu score. Prueba otra vez.");
    } finally {
      setSavingScore(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
      <div className="mx-auto max-w-3xl">
        <p className="mb-2 text-sm uppercase tracking-widest text-green-400">
          {quiz.category}
        </p>
        <h1 className="mb-3 text-4xl font-bold">{quiz.title}</h1>
        <p className="mb-8 text-slate-300">{quiz.description}</p>

        <div className="mb-8 flex flex-wrap gap-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
            ⏱ Tiempo: <strong>{timeLeft}s</strong>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
            ✅ Score: <strong>{score}</strong>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
            ❓ Pregunta:{" "}
            <strong>
              {Math.min(currentIndex + 1, preparedQuestions.length)}/{preparedQuestions.length}
            </strong>
          </div>
          {currentQuestion && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
              🎯 Dificultad: <strong>{currentQuestion.difficulty}</strong>
            </div>
          )}
        </div>

        {!finished && currentQuestion ? (
          <>
            <section className="rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-lg">
              <h2 className="mb-6 text-2xl font-semibold">
                {currentQuestion.question}
              </h2>

              <div className="grid gap-3">
                {currentQuestion.options.map((option, index) => (
                  <button
                    key={`${currentQuestion.id}-${index}`}
                    onClick={() => handleAnswer(index)}
                    disabled={showCorrection}
                    className={getOptionClass(index)}
                  >
                    {option}
                  </button>
                ))}
              </div>

              {showCorrection && (
                <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-950 p-4">
                  {selectedAnswer === currentQuestion.correctIndex ? (
                    <p className="font-semibold text-green-400">✅ Correcto</p>
                  ) : (
                    <>
                      <p className="mb-2 font-semibold text-red-400">❌ Incorrecto</p>
                      <p className="text-slate-300">
                        La respuesta correcta es:{" "}
                        <strong className="text-green-400">
                          {currentQuestion.options[currentQuestion.correctIndex]}
                        </strong>
                      </p>
                    </>
                  )}
                </div>
              )}

              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => setShowReportBox((prev) => !prev)}
                  className="text-sm text-slate-400 underline hover:text-slate-200"
                >
                  ¿Ves un error en esta pregunta o respuesta?
                </button>
              </div>

              {showReportBox && (
                <form
                  onSubmit={handleReportSubmit}
                  className="mt-4 rounded-2xl border border-slate-700 bg-slate-950 p-4"
                >
                  <p className="mb-3 text-sm text-slate-300">
                    Cuéntanos qué crees que está mal y lo revisaremos.
                  </p>

                  <textarea
                    value={reportText}
                    onChange={(e) => setReportText(e.target.value)}
                    rows={4}
                    className="w-full rounded-xl border border-slate-700 bg-slate-900 p-3 text-white outline-none"
                    placeholder="Ejemplo: creo que la correcta debería ser otra, o la pregunta es ambigua..."
                  />

                  <div className="mt-3 flex items-center gap-3">
                    <button
                      type="submit"
                      disabled={reportLoading}
                      className="rounded-2xl bg-white px-4 py-2 font-medium text-slate-950 hover:bg-slate-200 disabled:opacity-50"
                    >
                      {reportLoading ? "Enviando..." : "Enviar sugerencia"}
                    </button>

                    {reportSent && (
                      <span className="text-sm text-green-400">
                        Sugerencia enviada correctamente.
                      </span>
                    )}

                    {reportError && (
                      <span className="text-sm text-red-400">{reportError}</span>
                    )}
                  </div>
                </form>
              )}
            </section>

            <div className="mt-8">
              <AffiliateBlock
                title="Productos para fans del fútbol"
                description="Camisetas, balones, botas, libros y regalos futboleros."
                items={affiliateItems}
              />
            </div>
          </>
        ) : (
          <>
            <section className="rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-lg">
              <h2 className="mb-3 text-3xl font-bold">Quiz terminado</h2>
              <p className="mb-6 text-slate-300">
                Tu puntuación final en <strong>{quiz.title}</strong> es:
              </p>
              <p className="mb-8 text-5xl font-extrabold text-green-400">{score}</p>

              <form
                onSubmit={handleSaveScore}
                className="mb-8 rounded-2xl border border-slate-800 bg-slate-950 p-4"
              >
                <label className="mb-2 block text-sm text-slate-300">
                  Guarda tu score en el ranking
                </label>

                <div className="flex flex-col gap-3 md:flex-row">
                  <input
                    type="text"
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                    maxLength={30}
                    placeholder="Tu nick"
                    className="w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none"
                  />
                  <button
                    type="submit"
                    disabled={savingScore || scoreSaved}
                    className="rounded-2xl bg-white px-5 py-3 font-semibold text-slate-950 hover:bg-slate-200 disabled:opacity-50"
                  >
                    {scoreSaved
                      ? "Score guardado"
                      : savingScore
                      ? "Guardando..."
                      : "Guardar score"}
                  </button>
                </div>

                {scoreSaved && (
                  <p className="mt-3 text-sm text-green-400">
                    Tu score se ha guardado correctamente.
                  </p>
                )}

                {scoreError && (
                  <p className="mt-3 text-sm text-red-400">{scoreError}</p>
                )}
              </form>

              <div className="flex gap-3">
                <a
                  href={`/quiz/${quiz.slug}`}
                  className="rounded-2xl bg-green-500 px-5 py-3 font-semibold text-slate-950 hover:bg-green-400"
                >
                  Jugar otra vez
                </a>
                <a
                  href={`/ranking/${quiz.slug}`}
                  className="rounded-2xl border border-slate-700 px-5 py-3 font-semibold text-white hover:bg-slate-800"
                >
                  Ver ranking
                </a>
                <a
                  href="/"
                  className="rounded-2xl border border-slate-700 px-5 py-3 font-semibold text-white hover:bg-slate-800"
                >
                  Volver a la home
                </a>
              </div>
            </section>

            <div className="mt-8">
              <AffiliateBlock
                title="Productos para fans del fútbol"
                description="Camisetas, balones, botas, libros y regalos futboleros."
                items={affiliateItems}
              />
            </div>
          </>
        )}
      </div>
    </main>
  );
}