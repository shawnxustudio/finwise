import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import meilisearch
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder=".")
CORS(app)

meili = meilisearch.Client(
    os.getenv("MEILI_HOST", "http://localhost:8800"),
    os.getenv("MEILI_MASTER_KEY")
)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/expert_qa/search")
def search_expert_qa():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    hits_per_page = int(request.args.get("hitsPerPage", 20))

    search_params = {
        "hitsPerPage": hits_per_page,
        "page": page,
        "sort": ["expert_last_sort:desc"],
        "attributesToHighlight": ["title"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
        "matchingStrategy": "all",
    }

    if q:
        terms = q.split()
        search_q = " ".join(f'"{t}"' for t in terms)
    else:
        search_q = ""

    result = meili.index("expert_qa").search(search_q, search_params)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8801, debug=False)
