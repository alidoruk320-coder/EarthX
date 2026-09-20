export async function getAIReport(prompt) {

    const response = await fetch(
        "/.netlify/functions/ai",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                prompt
            })
        }
    );

    if (!response.ok) {

        throw new Error("AI report could not be generated.");

    }

    const json = await response.json();

    return json.text ?? "No response.";
}
