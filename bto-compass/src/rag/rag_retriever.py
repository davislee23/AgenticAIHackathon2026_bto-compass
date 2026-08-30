import os
import glob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

POLICY_DIR = "data/policies/"

def load_policies():
    """Loads all markdown files from the policies directory."""
    documents = []
    filenames = []
    
    # Iterate through all .md files in the folder
    for filepath in glob.glob(os.path.join(POLICY_DIR, "*.md")):
        with open(filepath, "r", encoding="utf-8") as file:
            documents.append(file.read())
            filenames.append(os.path.basename(filepath))
            
    return documents, filenames

def retrieve_policy(query: str, top_k: int = 1) -> str:
    """Finds the most relevant policy document for a given query."""
    documents, filenames = load_policies()
    
    if not documents:
        return "No policy documents found."

    # Initialize TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(stop_words='english')
    
    # Fit and transform the documents, plus the query
    all_texts = documents + [query]
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    
    # Calculate cosine similarity between the query (last item) and the documents
    similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    
    # Get the indices of the top_k most similar documents
    top_indices = similarities.argsort()[-top_k:][::-1]
    
    retrieved_text = ""
    for idx in top_indices:
        if similarities[idx] > 0.05: # Basic threshold to ignore irrelevant results
            retrieved_text += f"\n--- Source: {filenames[idx]} ---\n"
            retrieved_text += documents[idx] + "\n"
            
    return retrieved_text.strip() if retrieved_text else "No highly relevant policy found."
