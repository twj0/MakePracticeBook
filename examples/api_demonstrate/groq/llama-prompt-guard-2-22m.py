from groq import Groq

client = Groq()
completion = client.chat.completions.create(
    model="meta-llama/llama-prompt-guard-2-22m",
    messages=[
      {
        "role": "user",
        "content": ""
      }
    ],
    temperature=1,
    max_completion_tokens=1,
    top_p=1,
    stream=False,
    stop=None
)

print(completion.choices[0].message)
