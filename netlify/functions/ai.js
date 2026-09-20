export default async function handler(request) {

    if (request.method !== "POST") {

        return new Response("Method not allowed", { status: 405 });

    }

    const apiKey = process.env.GEMINI_API_KEY;

    if (!apiKey) {

        return Response.json(
            { error: "The AI service is not configured." },
            { status: 503 }
        );

    }

    const { prompt } = await request.json();

    const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
        {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }]
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {

        return Response.json(
            { error: data.error?.message ?? "The AI service is unavailable." },
            { status: response.status }
        );

    }

    return Response.json({
        text: data.candidates?.[0]?.content?.parts?.[0]?.text ?? "No response."
    });
}
