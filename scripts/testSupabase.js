const supabaseUrl = "https://kyiwfizgjtwdenkmwrqo.supabase.co";
const supabaseKey = "sb_publishable_OPrKrVpSv9lyeawt-JvyXg_j_wHI20-";

async function test() {
  try {
    console.log("Probando URL:", supabaseUrl);
    console.log("Probando key empieza por:", supabaseKey.slice(0, 20));

    const res = await fetch(`${supabaseUrl}/rest/v1/`, {
      headers: {
        apikey: supabaseKey,
        Authorization: `Bearer ${supabaseKey}`,
      },
    });

    console.log("Status:", res.status);
    const text = await res.text();
    console.log("Respuesta:", text);
  } catch (err) {
    console.error("ERROR REAL:", err);
  }
}

test();