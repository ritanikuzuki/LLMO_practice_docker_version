import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_article(keyword):
    prompt = f"""
    以下のキーワードに基づいて、LLMに引用されやすい構造の記事を作成してください。

    キーワード: {keyword}

    条件:
    ・導入文
    ・見出し（H2, H3）
    ・箇条書き
    ・定義文（〜とは）
    ・最後にまとめ
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content

if __name__ == "__main__":
    keyword = input("キーワードを入力: ")
    article = generate_article(keyword)
    print(article)