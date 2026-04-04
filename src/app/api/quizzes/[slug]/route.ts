import { NextResponse } from "next/server";
import { getQuizBySlug } from "@/lib/quizzes";

export async function GET(
  _request: Request,
  context: { params: Promise<{ slug: string }> }
) {
  const params = await context.params;
  const quiz = getQuizBySlug(params.slug);

  if (!quiz) {
    return NextResponse.json({ error: "Quiz no encontrado" }, { status: 404 });
  }

  return NextResponse.json(quiz);
}