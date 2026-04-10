export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import QuizClient from "./QuizClient";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

type QuizRow = {
  id: string;
  slug: string;
  title: string;
  description: string;
  category: string;
  featured: boolean;
  show_on_home: boolean;
  home_order: number;
  time_limit_seconds: number;
};

type QuizTagRuleRow = {
  id: string;
  quiz_slug: string;
  tag: string;
};

type DbQuestion = {
  id: string;
  question: string;
  options: string[];
  correct_index: number;
  difficulty: "easy" | "medium" | "hard";
  tags: string[];
  source: string | null;
};

type QuizQuestion = {
  id: string;
  question: string;
  options: string[];
  correctIndex: number;
  difficulty: "easy" | "medium" | "hard";
  tags: string[];
};

function shuffleArray<T>(array: T[]): T[] {
  const copy = [...array];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function pickFromPool<T>(pool: T[]): T | null {
  if (pool.length === 0) return null;
  return pool.shift() ?? null;
}

function weightedPickDifficulty(
  easy: QuizQuestion[],
  medium: QuizQuestion[],
  hard: QuizQuestion[],
  progress: number
): "easy" | "medium" | "hard" | null {
  const available: Array<"easy" | "medium" | "hard"> = [];
  if (easy.length) available.push("easy");
  if (medium.length) available.push("medium");
  if (hard.length) available.push("hard");

  if (available.length === 0) return null;
  if (available.length === 1) return available[0];

  // progress va de 0 a 1
  // inicio: easy 45 / medium 45 / hard 10
  // mitad: easy 15 / medium 50 / hard 35
  // final: easy 5 / medium 30 / hard 65
  let weights = {
    easy: 45,
    medium: 45,
    hard: 10,
  };

  if (progress >= 0.33 && progress < 0.7) {
    weights = {
      easy: 15,
      medium: 50,
      hard: 35,
    };
  } else if (progress >= 0.7) {
    weights = {
      easy: 5,
      medium: 30,
      hard: 65,
    };
  }

  const filteredWeights = available.map((key) => ({
    key,
    weight: weights[key],
  }));

  const total = filteredWeights.reduce((sum, item) => sum + item.weight, 0);
  let roll = Math.random() * total;

  for (const item of filteredWeights) {
    roll -= item.weight;
    if (roll <= 0) return item.key;
  }

  return filteredWeights[filteredWeights.length - 1].key;
}

function buildProgressiveQuestionOrder(questions: QuizQuestion[]): QuizQuestion[] {
  const easy = shuffleArray(questions.filter((q) => q.difficulty === "easy"));
  const medium = shuffleArray(questions.filter((q) => q.difficulty === "medium"));
  const hard = shuffleArray(questions.filter((q) => q.difficulty === "hard"));

  const total = questions.length;
  const ordered: QuizQuestion[] = [];

  while (ordered.length < total) {
    const progress = total <= 1 ? 1 : ordered.length / (total - 1);
    const difficulty = weightedPickDifficulty(easy, medium, hard, progress);

    if (!difficulty) break;

    let picked: QuizQuestion | null = null;

    if (difficulty === "easy") picked = pickFromPool(easy);
    if (difficulty === "medium") picked = pickFromPool(medium);
    if (difficulty === "hard") picked = pickFromPool(hard);

    if (!picked) {
      // fallback por si justo se vacía un pool
      picked = pickFromPool(medium) ?? pickFromPool(hard) ?? pickFromPool(easy);
    }

    if (!picked) break;
    ordered.push(picked);
  }

  return ordered;
}

export default async function QuizPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  // 1) Metadatos del quiz desde Supabase
  const { data: quizMeta, error: quizError } = await supabase
    .from("quizzes")
    .select("*")
    .eq("slug", slug)
    .single<QuizRow>();

  if (quizError || !quizMeta) {
    notFound();
  }

  // 2) Reglas de tags desde Supabase
  const { data: tagRules, error: tagRulesError } = await supabase
    .from("quiz_tag_rules")
    .select("*")
    .eq("quiz_slug", slug)
    .returns<QuizTagRuleRow[]>();

  if (tagRulesError) {
    throw new Error(`Error cargando reglas del quiz: ${tagRulesError.message}`);
  }

  const tags = (tagRules ?? []).map((row) => row.tag).filter(Boolean);

  // 3) Preguntas desde Supabase
  let questionsQuery = supabase.from("questions").select("*");

  // Si no hay tags, trae todo (útil para torneo)
  if (tags.length > 0) {
    questionsQuery = questionsQuery.overlaps("tags", tags);
  }

  const { data: questionsData, error: questionsError } = await questionsQuery;

  if (questionsError) {
    throw new Error(`Error cargando preguntas: ${questionsError.message}`);
  }

  const questions: QuizQuestion[] =
    (questionsData as DbQuestion[] | null)?.map((q) => ({
      id: q.id,
      question: q.question,
      options: q.options,
      correctIndex: q.correct_index,
      difficulty: q.difficulty,
      tags: q.tags ?? [],
    })) ?? [];

  const orderedQuestions = buildProgressiveQuestionOrder(questions);

  console.log("Quiz BD:", slug);
  console.log("Tags reglas:", tags);
  console.log("Preguntas BD:", questions.length);
  console.log("Preguntas ordenadas:", orderedQuestions.length);

  const quiz = {
    slug: quizMeta.slug,
    title: quizMeta.title,
    description: quizMeta.description,
    category: quizMeta.category,
    featured: quizMeta.featured,
    showOnHome: quizMeta.show_on_home,
    homeOrder: quizMeta.home_order,
    timeLimitSeconds: quizMeta.time_limit_seconds,
    questions: orderedQuestions,
  };

  return <QuizClient quiz={quiz} />;
}