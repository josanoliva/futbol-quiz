import fs from "fs";
import path from "path";

export type QuizQuestion = {
  id: string;
  question: string;
  options: string[];
  correctIndex: number;
  difficulty: "easy" | "medium" | "hard";
  tags: string[];
};

export type Quiz = {
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

const quizzesDir = path.join(process.cwd(), "data", "quizzes");

export function getAllQuizzes(): Quiz[] {
  const files = fs.readdirSync(quizzesDir);

  const quizzes = files
    .filter((file) => file.endsWith(".json"))
    .map((file) => {
      const filePath = path.join(quizzesDir, file);
      const raw = fs.readFileSync(filePath, "utf-8");
      return JSON.parse(raw) as Quiz;
    });

  return quizzes.sort((a, b) => a.homeOrder - b.homeOrder);
}

export function getQuizBySlug(slug: string): Quiz | null {
  const filePath = path.join(quizzesDir, `${slug}.json`);

  if (!fs.existsSync(filePath)) {
    return null;
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as Quiz;
}

export function getHomeQuizzes(): Quiz[] {
  return getAllQuizzes().filter((quiz) => quiz.showOnHome);
}

export function getFeaturedQuiz(): Quiz | null {
  const quizzes = getHomeQuizzes().filter((quiz) => quiz.featured);
  return quizzes.length ? quizzes[0] : null;
}

export function getCategories(quizzes: Quiz[]): string[] {
  return Array.from(new Set(quizzes.map((quiz) => quiz.category)));
}