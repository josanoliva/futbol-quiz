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

function sortScores(scores: ScoreEntry[]) {
  return scores.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });
}

export async function GET() {
  try {
    let scores: ScoreEntry[] = [];

    if (fs.existsSync(scoresFile)) {
      const raw = fs.readFileSync(scoresFile, "utf-8");
      scores = JSON.parse(raw) as ScoreEntry[];
    }

    const sorted = sortScores(scores).slice(0, 100);

    return NextResponse.json(sorted);
  } catch {
    return NextResponse.json(
      { error: "No se pudo leer el ranking general" },
      { status: 500 }
    );
  }
}