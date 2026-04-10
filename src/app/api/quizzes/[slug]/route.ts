import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;

  let tags: string[] = [];

  if (slug === "real-madrid") tags = ["real-madrid"];
  if (slug === "fc-barcelona") tags = ["fc-barcelona", "barcelona"];
  if (slug === "champions-league") tags = ["champions-league"];
  if (slug === "messi") tags = ["messi"];
  if (slug === "mundial") tags = ["mundial"];
  if (slug === "torneo") tags = [];

  let query = supabase.from("questions").select("*");

  if (tags.length > 0) {
    query = query.overlaps("tags", tags);
  }

  const { data, error } = await query;

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify(data ?? []), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}