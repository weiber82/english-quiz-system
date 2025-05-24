class GPTExplanationService:
    def __init__(self, gpt_client):
        self.gpt_client = gpt_client

    def explain(self, question, answer, options):
        prompt = self._build_prompt(question, answer, options)
        return self.gpt_client.get_response(prompt)


    def _build_prompt(self, q, a, options):
        options_text = "\n".join([f"{key}. {value}" for key, value in options.items()])
        return f"""請說明為什麼下面的英文選擇題中，選項「{a}」是正確或錯誤的，盡可能在100字以內說明每個選項，要在選項前面備註。
                題目：{q}
                選項：
                {options_text}
                正確答案：{a}
                請用中文母語的觀點解釋，評斷學生可能錯誤的原因，幫助學生學習。"""

