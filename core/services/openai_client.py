import openai

class OpenAIClient:
    def __init__(self, api_key, model='gpt-4.1-nano'):
        openai.api_key = api_key
        self.model = model

    def get_response(self, prompt):
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"錯誤：{e}"
