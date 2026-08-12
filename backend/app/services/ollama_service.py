from ollama import chat


def ask_ollama(prompt: str) -> str:
    response = chat(
        model="llama3.2:latest",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    return response.message.content