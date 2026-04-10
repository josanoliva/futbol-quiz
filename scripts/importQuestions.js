import fs from "fs";
import path from "path";
import { createClient } from "@supabase/supabase-js";

// 🔑 CONFIG
require("dotenv").config();

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
  throw new Error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el archivo .env");
}

const supabase = createClient(supabaseUrl, supabaseKey);

// 📂 carpeta JSON
const DATA_DIR = path.join(process.cwd(), "data", "quizzes");

async function run() {
  const files = fs.readdirSync(DATA_DIR);

  for (const file of files) {
    if (!file.endsWith(".json")) continue;

    const fullPath = path.join(DATA_DIR, file);
    const raw = fs.readFileSync(fullPath, "utf-8");
    const json = JSON.parse(raw);

    const questions = json.questions;

    console.log(`📦 Importando ${file} (${questions.length} preguntas)`);

    for (const q of questions) {
      const { error } = await supabase.from("questions").insert({
        question: q.question,
        options: q.options,
        correct_index: q.correctIndex,
        difficulty: q.difficulty,
        tags: q.tags,
        source: json.slug,
      });

      if (error) {
        console.error("❌ Error:", error.message);
      }
    }
  }

  console.log("✅ Importación terminada");
}

run();