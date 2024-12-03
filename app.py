from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

# Hardcoded API key
NEWS_API_KEY = "bed983842fff4c239027006d10fd8fc5"

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def get_news_by_topic(params):
    url = "https://newsapi.org/v2/everything"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        articles = response.json().get("articles", [])
        return [article for article in articles if article.get("title") != "[Removed]"]
    else:
        return {
            "error": f"Error {response.status_code}: Unable to fetch articles.",
            "details": response.text,
        }

@app.route("/news", methods=["POST"])
def fetch_news():
    # Parse request data
    data = request.get_json()

    # Validate the API key
    if not NEWS_API_KEY:
        return jsonify({"error": "API key is missing or not configured."}), 500

    # Add API key to request parameters
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    data["apiKey"] = NEWS_API_KEY

    # Fetch news using the params
    result = get_news_by_topic(data)

    if isinstance(result, list):  # Successful response
        return jsonify({"articles": result})
    else:  # Error occurred
        return jsonify(result), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Get the PORT environment variable or default to 5000
    app.run(host="0.0.0.0", port=port, debug=True)

