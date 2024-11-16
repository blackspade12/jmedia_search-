import requests
import json
from datetime import datetime
from flask import Flask, jsonify, request
from elasticsearch import Elasticsearch

app = Flask(__name__)

# Elasticsearch initialization

es = Elasticsearch(
    ""http://elasticsearch:9200",  # Replace with your Elasticsearch endpoint
    basic_auth=("elastic", "ZH6qQzes3AvVypDAlmDvPqmw")  # Replace with your username and password
)

# News API key
api_key = "bed983842fff4c239027006d10fd8fc5"  # Replace with your actual NewsAPI key

# File to store user preferences
USER_PREFERENCES_FILE = 'user_preferences.json'


# Load user preferences from file
def load_preferences():
    try:
        with open(USER_PREFERENCES_FILE, 'r') as file:
            preferences = json.load(file)
            return preferences
    except FileNotFoundError:
        return {"title_weight": 3, "content_weight": 2, "date_sort": "desc"}


# Save user preferences to file
def save_preferences(preferences):
    with open(USER_PREFERENCES_FILE, 'w') as file:
        json.dump(preferences, file)


# Function to fetch news articles based on user input
def get_news_by_topic(api_key, topic):
    url = "https://newsapi.org/v2/everything"
    
    params = {
        "q": topic,  # User-specified topic (e.g., "technology", "sports", etc.)
        "sortBy": "relevancy",  # Sort articles by publication date
        "apiKey": api_key,
        "language": "en"  # Filter for English articles
    }
    
    response = requests.get(url, params=params)

    if response.status_code == 200:
        articles = response.json().get("articles", [])
        # Filter out articles where title is "[Removed]"
        return [article for article in articles if article.get("title") != "[Removed]"]
    else:
        print(f"Error: Unable to fetch articles. Status code: {response.status_code}")
        return []


# Save articles to Elasticsearch
def save_to_elasticsearch(articles):
    # Delete the old index if it exists (optional)
    es.indices.delete(index='news_articles', ignore=[400, 404])  # 400/404 ignores errors if index doesn't exist
    
    # Create a new index (optional, if you want to start fresh)
    es.indices.create(index='news_articles', ignore=400)  # Ignore 400 error if index already exists

    for article in articles:
        doc = {
            "id": article.get("url", "Unknown URL"),
            "title": article.get("title", "No Title"),
            "content": article.get("content", "No Content"),
            "tags": [],
            "category": article.get("category", "Uncategorized"),
            "publication_date": article.get("publishedAt", "Unknown Date"),
            "publisher": article.get("source", {}).get("name", "Unknown Publisher"),
            "popularity": 0
        }

        # Index document in Elasticsearch
        es.index(index='news_articles', document=doc)


# Load articles from Elasticsearch
def load_articles_from_elasticsearch():
    # Search all articles in Elasticsearch
    result = es.search(index='news_articles', body={
        "query": {
            "match_all": {}
        },
        "_source": ["id", "title", "content", "publisher", "publication_date", "category"],  # Include content in the source
        "size": 100  # Adjust size based on how many articles you want to fetch
    })
    return result['hits']['hits']


# Filter articles based on given criteria
def filter_articles(articles, category=None, start_date=None, end_date=None, publisher=None, title=None, preferences=None):
    filtered_articles = articles

    if category:
        filtered_articles = [article for article in filtered_articles if category.lower() in article["_source"]['category'].lower()]

    if start_date:
        filtered_articles = [article for article in filtered_articles if article["_source"]['publication_date'] >= start_date]

    if end_date:
        filtered_articles = [article for article in filtered_articles if article["_source"]['publication_date'] <= end_date]

    if publisher:
        filtered_articles = [article for article in filtered_articles if publisher.lower() in article["_source"]['publisher'].lower()]

    if title:
        filtered_articles = [article for article in filtered_articles if title.lower() in article["_source"]['title'].lower()]

    # Apply ranking preferences (customized ranking)
    title_weight = preferences.get("title_weight", 3)
    content_weight = preferences.get("content_weight", 2)
    date_sort = preferences.get("date_sort", "desc")

    # Sort articles by title, content, and publication date (using a simple example, this can be more complex)
    filtered_articles.sort(
    key=lambda article: (
        title_weight * (article["_source"].get("title", "").lower().count(title.lower()) if title else 0),
        content_weight * (article["_source"].get("content", "").lower().count(title.lower()) if title else 0),
        article["_source"].get("publication_date", 0) if date_sort == "desc" else -article["_source"].get("publication_date", 0)
    ),
    reverse=True
)


    return filtered_articles


# Flask API routes

@app.route('/fetch_news', methods=['GET'])
def fetch_news():
    topic = request.args.get('topic')
    if not topic:
        return jsonify({"error": "Topic parameter is required"}), 400
    
    # Fetch news articles
    articles = get_news_by_topic(api_key, topic)
    if not articles:
        return jsonify({"message": "No articles found for the given topic"}), 404
    
    # Save to Elasticsearch
    save_to_elasticsearch(articles)
    
    return jsonify({"message": f"{len(articles)} articles fetched and saved."}), 200


@app.route('/get_filtered_articles', methods=['GET'])
def get_filtered_articles():
    category_filter = request.args.get('category')
    publisher_filter = request.args.get('publisher')
    start_date_filter = request.args.get('start_date')
    end_date_filter = request.args.get('end_date')
    title_filter = request.args.get('title')
    
    # Load user preferences
    preferences = load_preferences()

    # Load articles from Elasticsearch
    articles = load_articles_from_elasticsearch()

    # Filter articles based on provided parameters and preferences
    filtered_articles = filter_articles(articles, category=category_filter, start_date=start_date_filter, 
                                         end_date=end_date_filter, publisher=publisher_filter, title=title_filter, preferences=preferences)
    
    # Prepare response with the necessary fields, including content
    filtered_results = [{
        "id": article["_id"],
        "title": article["_source"]["title"],
        "content": article["_source"]["content"],  # Include content here
        "publisher": article["_source"].get("publisher"),
        "publication_date": article["_source"].get("publication_date"),
        "category": article["_source"].get("category"),
        "score": article["_score"]
    } for article in filtered_articles]

    return jsonify({"filtered_articles": filtered_results}), 200


@app.route('/get_all_articles', methods=['GET'])
def get_all_articles():
    # Load articles from Elasticsearch
    articles = load_articles_from_elasticsearch()

    # Prepare response with the necessary fields, including content
    all_results = [{
        "id": article["_id"],
        "title": article["_source"]["title"],
        "content": article["_source"]["content"],  # Include content here
        "publisher": article["_source"].get("publisher"),
        "publication_date": article["_source"].get("publication_date"),
        "category": article["_source"].get("category"),
        "score": article["_score"]
    } for article in articles]

    return jsonify({"all_articles": all_results}), 200


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """
    Handle user preferences for ranking.
    """
    if request.method == 'GET':
        # Return current preferences
        preferences = load_preferences()
        return jsonify(preferences)
    
    if request.method == 'POST':
        # Save updated preferences
        preferences = request.json
        save_preferences(preferences)
        return jsonify({"message": "Preferences saved successfully!"})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')

