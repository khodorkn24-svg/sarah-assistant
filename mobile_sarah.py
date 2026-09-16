from flask import Flask, request, render_template_string
from openai import OpenAI
import os

app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

latest_call_report = ""

SYSTEM = """
Your name is Sarah.
You are Khodor's personal work and maintenance assistant.

Speak to Khodor in natural Lebanese Arabic.
Understand Lebanese Arabic, English, and mixed Arabic-English.
Be practical and concise.
Help with restaurant maintenance, troubleshooting, planning and writing.

If Khodor asks for a message to an English-speaking person,
write it in natural English.

You currently have NO access to Gmail, WhatsApp, computer files,
purchasing, or other private accounts.

Never claim you performed an action unless you actually have the tool.
Never purchase anything.
"""

HTML = """
<!doctype html>
<html lang="ar">
<head>

<meta name="viewport" content="width=device-width, initial-scale=1">

<title>Sarah</title>

<style>

body {
    font-family: Arial, sans-serif;
    max-width: 700px;
    margin: 30px auto;
    padding: 15px;
    background: #f4f4f4;
}

h1 {
    text-align: center;
}

.box {
    background: white;
    padding: 20px;
    border-radius: 15px;
}

textarea {
    width: 100%;
    height: 100px;
    font-size: 18px;
    box-sizing: border-box;
}

button {
    width: 100%;
    padding: 15px;
    margin-top: 10px;
    font-size: 18px;
}

.answer {
    margin-top: 20px;
    padding: 15px;
    background: #eeeeee;
    border-radius: 10px;
    white-space: pre-wrap;
    direction: rtl;
}

.report {
    margin-top: 20px;
    padding: 15px;
    background: #ffffff;
    border: 2px solid #dddddd;
    border-radius: 10px;
    white-space: pre-wrap;
}

</style>

</head>

<body>

<h1>Sarah</h1>

<div class="box">

<form method="post">

<textarea
name="message"
placeholder="احكي مع ساره..."
required></textarea>

<button type="submit">
إبعث لساره
</button>

</form>

{% if answer %}

<div class="answer">
{{ answer }}
</div>

{% endif %}


{% if latest_call_report %}

<div class="report">

<strong>📞 آخر تقرير مكالمة</strong>

<br><br>

{{ latest_call_report }}

</div>

{% endif %}

</div>

</body>

</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():

    global latest_call_report

    answer = ""

    if request.method == "POST":

        message = request.form.get("message", "")

        try:

            response = client.responses.create(
                model="gpt-5.6-luna",
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            )

            answer = response.output_text

        except Exception as e:

            answer = "صار خطأ: " + str(e)

    return render_template_string(
        HTML,
        answer=answer,
        latest_call_report=latest_call_report
    )


@app.route("/call-report", methods=["POST"])
def call_report():

    global latest_call_report

    data = request.get_json(silent=True) or {}

    latest_call_report = data.get(
        "message",
        "No report received"
    )

    return {
        "status": "ok"
    }


@app.route("/latest-call", methods=["GET"])
def latest_call():

    return {
        "message": latest_call_report
    }


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )