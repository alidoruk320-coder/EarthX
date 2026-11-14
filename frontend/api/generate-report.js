export async function POST(request) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return Response.json({ error: "The AI service is not configured." }, { status: 503 });
  }

  try {
    const { prompt } = await request.json();
    if (typeof prompt !== "string" || !prompt.trim()) {
      return Response.json({ error: "A non-empty prompt is required." }, { status: 400 });
    }
    const upstream = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${encodeURIComponent(apiKey)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
      },
    );
    const payload = await upstream.json();
    if (!upstream.ok) {
      return Response.json({ error: payload?.error?.message || "The AI service is unavailable." }, { status: upstream.status });
    }
    return Response.json({
      text: payload?.candidates?.[0]?.content?.parts?.[0]?.text || "No response.",
    });
  } catch {
    return Response.json({ error: "The AI service could not be reached." }, { status: 502 });
  }
}
