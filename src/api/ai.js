const API_KEY = import.meta.env.VITE_GEMINI_API_KEY;

export async function getAIReport(prompt) {

    if (!API_KEY) {

        return "AI analysis is not configured for this public deployment.";

    }

    const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${API_KEY}`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                contents: [
                    {
                        parts: [
                            {
                                text: prompt
                            }
                        ]
                    }
                ]
            })
        }
    );

    const json = await response.json();

    return json.candidates?.[0]?.content?.parts?.[0]?.text
        ?? "No response.";
}
