import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";

type ScoreEntry = {
  id: string;
  quizSlug: string;
  quizTitle: string;
  nickname: string;
  score: number;
  totalQuestions: number;
  createdAt: string;
};

const scoresFile = path.join(process.cwd(), "data", "rankings", "scores.json");

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const quizSlug = String(body.quizSlug || "").trim();
    const quizTitle = String(body.quizTitle || "").trim();
    const nickname = String(body.nickname || "").trim();
    const score = Number(body.score);
    const totalQuestions = Number(body.totalQuestions);

    if (!quizSlug || !quizTitle || !nickname) {
      return NextResponse.json(
        { error: "Faltan datos obligatorios" },
        { status: 400 }
      );
    }

    if (!Number.isFinite(score) || !Number.isFinite(totalQuestions)) {
      return NextResponse.json(
        { error: "Score inválido" },
        { status: 400 }
      );
    }

    let scores: ScoreEntry[] = [];

    if (fs.existsSync(scoresFile)) {
      const raw = fs.readFileSync(scoresFile, "utf-8");
      scores = JSON.parse(raw) as ScoreEntry[];
    }

    const newEntry: ScoreEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      quizSlug,
      quizTitle,
      nickname: nickname.slice(0, 30),
      score,
      totalQuestions,
      createdAt: new Date().toISOString(),
    };

    scores.push(newEntry);

    fs.writeFileSync(scoresFile, JSON.stringify(scores, null, 2), "utf-8");

    return NextResponse.json({ ok: true, entry: newEntry });
  } catch {
    return NextResponse.json(
      { error: "No se pudo guardar el score" },
      { status: 500 }
    );
  }
}