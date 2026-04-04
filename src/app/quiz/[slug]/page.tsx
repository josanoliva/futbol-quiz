import { notFound } from "next/navigation";
import QuizClient from "./QuizClient";
import { getQuizBySlug } from "@/lib/quizzes";

export default async function QuizPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const quiz = getQuizBySlug(slug);

  if (!quiz) {
    notFound();
  }

  return <QuizClient quiz={quiz} />;
}