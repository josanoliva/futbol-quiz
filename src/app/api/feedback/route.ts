import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";

type FeedbackReport = {
  id: string;
  quizSlug: string;
  questionId: string;
  selectedOptionIndex: number | null;
  message: string;
  createdAt: string;
};

const feedbackFile = path.join(process.cwd(), "data", "feedback", "reports.json");

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const quizSlug = String(body.quizSlug || "").trim();
    const questionId = String(body.questionId || "").trim();
    const message = String(body.message || "").trim();

    const selectedOptionIndex =
      body.selectedOptionIndex === null || body.selectedOptionIndex === undefined
        ? null
        : Number(body.selectedOptionIndex);

    if (!quizSlug || !questionId || !message) {
      return NextResponse.json(
        { error: "Faltan datos obligatorios" },
        { status: 400 }
      );
    }

    let reports: FeedbackReport[] = [];

    if (fs.existsSync(feedbackFile)) {
      const raw = fs.readFileSync(feedbackFile, "utf-8");
      reports = JSON.parse(raw) as FeedbackReport[];
    }

    const newReport: FeedbackReport = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      quizSlug,
      questionId,
      selectedOptionIndex,
      message,
      createdAt: new Date().toISOString(),
    };

    reports.push(newReport);

    fs.writeFileSync(feedbackFile, JSON.stringify(reports, null, 2), "utf-8");

    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json(
      { error: "No se pudo guardar la sugerencia" },
      { status: 500 }
    );
  }
}