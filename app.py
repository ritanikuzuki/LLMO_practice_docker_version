import os
import json
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import markdown
import urllib.request
import urllib.parse

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate-titles", methods=["POST"])
def generate_titles():
    """キーワードと概要からタイトル案を5〜10個生成する"""
    data = request.get_json()
    keyword = data.get("keyword", "").strip()
    summary = data.get("summary", "").strip()
    experience = data.get("experience", "").strip()
    platform = data.get("platform", "blog")

    if not keyword:
        return jsonify({"error": "キーワードを入力してください"}), 400

    platform_instruction = ""
    if platform == "qiita":
        platform_instruction = "Qiita向け: 技術的な正確性を重視し、[Python] のように主要技術をブラケットで囲む案も含めてください。"
    elif platform == "zenn":
        platform_instruction = "Zenn向け: 開発者の知的好奇心を刺激する、スッキリとした知的なタイトルにしてください。"
    elif platform == "note":
        platform_instruction = "note向け: 親しみやすく、個人の体験や気づきを感じさせるキャッチーなタイトルにしてください。"
    else:
        platform_instruction = "ブログ向け: SEOとLLMO（AI引用最適化）を両立した、検索されやすいタイトルにしてください。"

    summary_section = ""
    if summary:
        summary_section = f"""
    また、以下の記事概要・既存コンテンツも参考にしてください:
    {summary}
    """

    experience_section = ""
    if experience:
        experience_section = f"""
    【独自のエピソード・一次情報】
    以下の経験談やデータを考慮し、より独自性の高いタイトル案も含めてください:
    {experience}
    """

    prompt = f"""あなたはLLMO（LLM Optimization）の専門家です。
    以下のキーワードに基づいて、ChatGPT・Claude・Gemini等の生成AIに引用・参照されやすい
    ブログ記事のタイトル案を7個生成してください。
    {platform_instruction}
    {summary_section}
    {experience_section}
    キーワード: {keyword}

    タイトル生成の条件:
    ・読者が検索しそうな具体的な課題や疑問に答える形式
    ・「〜とは」「〜の方法」「〜完全ガイド」など、AIが定義・解説として引用しやすい形式を含む
    ・具体的な数字やデータを示唆するもの（例: 「5つのステップ」「2025年版」）
    ・比較・対照を含むもの（例: 「AとBの違い」）
    ・実務で使える具体性のあるもの

    出力形式: JSON配列で返してください。各要素は title キーを持つオブジェクトです。
    余計な説明やマークダウンの装飾は不要です。純粋なJSON配列のみを返してください。
    例: [{{"title": "タイトル1"}}, {{"title": "タイトル2"}}]
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        content = response.choices[0].message.content.strip()

        # JSON部分を抽出（```json ... ``` で囲まれている場合の対応）
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                if in_block:
                    json_lines.append(line)
            content = "\n".join(json_lines)

        titles = json.loads(content)
        return jsonify({"titles": titles})

    except json.JSONDecodeError:
        return jsonify({"error": "タイトル生成に失敗しました。もう一度お試しください。"}), 500
    except Exception as e:
        return jsonify({"error": f"エラーが発生しました: {str(e)}"}), 500


@app.route("/api/generate-article", methods=["POST"])
def generate_article():
    """選択されたタイトルに基づいて、LLMO最適化された記事を生成する"""
    data = request.get_json()
    title = data.get("title", "").strip()
    keyword = data.get("keyword", "").strip()
    summary = data.get("summary", "").strip()
    experience = data.get("experience", "").strip()
    platform = data.get("platform", "blog")

    if not title:
        return jsonify({"error": "タイトルを選択してください"}), 400

    # プラットフォーム別の指示
    platform_style = ""
    if platform == "qiita":
        platform_style = """
        【Qiita最適化要件】:
        ・エンジニアが「逆引き」で使いやすいよう、コードと解説を交互に配置。
        ・動作環境（OS/言語バージョン）を明記。
        ・「結論から言うと」というセクションを冒頭に置く。
        """
    elif platform == "zenn":
        platform_style = """
        【Zenn最適化要件】:
        ・冒頭にYAML Frontmatterを追加（emoji, type: "tech", topics, published: true）。
        ・モダンな技術スタックを前提とした解説。
        ・図解を意識したテキスト構造（:::message などの独自記法は使わず標準Markdownで）。
        """
    elif platform == "note":
        platform_style = """
        【note最適化要件】:
        ・専門用語には簡単な解説を添える。
        ・「なぜこれが必要か」という背景（ストーリー）を重視。
        ・見出し画像がなくても読みやすい、ゆとりのある段落構成。
        """
    else:
        platform_style = """
        【汎用ブログ/LLMO要件】:
        ・H2, H3の構造を厳格に。
        ・定義文（〜とは）を強調。
        ・JSON-LD的な構造を意識した要約を含める。
        """

    summary_section = ""
    if summary:
        summary_section = f"""
    以下の既存コンテンツ・概要も参考に、内容を充実させてください:
    {summary}
    """

    experience_section = ""
    if experience:
        experience_section = f"""
    【重要: 独自のエピソード・一次情報の組み込み（E-E-A-Tの確立）】
    以下の一次情報を、単なる事実の羅列ではなく「ストーリーテリング形式」で記事内に自然に織り交ぜてください。
    業界の一般論（AIが既に知っている情報）と、この独自のデータを比較する構図を作るなどして、記事の独自性と権威性を圧倒的に高めてください。
    独自情報・経験談:
    {experience}
    """

    prompt = f"""あなたはLLMO（LLM Optimization）の専門家です。
    以下のタイトルとキーワードに基づいて、ChatGPT・Claude・Gemini等の生成AIに
    引用・参照されやすい構造のブログ記事を作成してください。

    {platform_style}

    {summary_section}
    {experience_section}
    タイトル: {title}
    キーワード: {keyword}

    記事作成の共通条件:
    ・導入文: 読者の課題を明確にし、この記事で何が得られるかを簡潔に説明
    ・独自性の強調: あなた自身の経験や一次情報を積極的に盛り込み、E-E-A-Tを高める
    ・見出し構造: H2・H3を適切に使い、論理的な階層構造にする
    ・定義文: 「〜とは」で始まる明確な定義を含める（AIが引用しやすい）
    ・箇条書き: 重要なポイントは箇条書きでまとめる（AIが構造化データとして認識しやすい）
    ・具体例・数値データ: 可能な限り具体的な例やデータを含める
    ・比較表: 適切な場合はテーブル形式で比較を示す
    ・FAQ: よくある質問とその回答を2〜3個含める
    ・まとめ: 記事の要点を箇条書きで振り返る

    出力形式: Markdown形式で記事全文を出力してください。
    ただし、```markdown や ``` などのコードブロックで囲まないでください。純粋なMarkdownテキストのみを出力してください。
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        content = response.choices[0].message.content.strip()

        # GPTが ```markdown ... ``` で囲んでいる場合に除去する
        if content.startswith("```"):
            lines = content.split("\n")
            # 最初の ``` 行を除去
            lines = lines[1:]
            # 最後の ``` 行を除去
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        html_content = markdown.markdown(
            content,
            extensions=["tables", "fenced_code", "nl2br"]
        )
        return jsonify({
            "article_md": content,
            "article_html": html_content
        })

    except Exception as e:
        return jsonify({"error": f"エラーが発生しました: {str(e)}"}), 500


@app.route("/api/post-to-qiita", methods=["POST"])
def post_to_qiita():
    """Qiitaに記事を投稿する"""
    data = request.get_json()
    token = data.get("token", "").strip()
    title = data.get("title", "").strip()
    body = data.get("body", "").strip()
    tags_str = data.get("tags", "LLMO,AI").strip()
    is_private = data.get("private", True)

    if not token:
        return jsonify({"error": "Qiitaアクセストークンが必要です"}), 400
    if not title or not body:
        return jsonify({"error": "タイトルと本文が必要です"}), 400

    # タグの整形 (例: "Python, Flask" -> [{"name": "Python"}, {"name": "Flask"}])
    tags = [{"name": t.strip()} for t in tags_str.split(",") if t.strip()]
    if not tags:
        tags = [{"name": "LLMO"}]

    post_data = {
        "title": title,
        "body": body,
        "tags": tags,
        "private": is_private,
        "tweet": False
    }

    req_url = "https://qiita.com/api/v2/items"
    req_body = json.dumps(post_data).encode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        req = urllib.request.Request(req_url, data=req_body, headers=headers, method="POST")
        with urllib.request.urlopen(req) as res:
            res_body = res.read().decode("utf-8")
            response_json = json.loads(res_body)
            return jsonify({
                "success": True,
                "url": response_json.get("url"),
                "message": "Qiitaに投稿しました！"
            })
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_msg)
            return jsonify({"error": f"Qiita APIエラー: {error_json.get('message')}"}), e.code
        except:
            return jsonify({"error": f"Qiita APIエラー: {e.reason}"}), e.code
    except Exception as e:
        return jsonify({"error": f"投稿中にエラーが発生しました: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
