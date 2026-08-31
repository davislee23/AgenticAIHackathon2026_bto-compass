# src/rag/rag_retriever.py
import os
import glob
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Absolute path resolution ensuring Streamlit Cloud finds the files
BASE_DIR = Path(__file__).resolve().parent.parent.parent
POLICY_DIR = BASE_DIR / "data" / "policies"

def load_policies():
    """Loads all markdown files from the policies directory dynamically."""
    documents = []
    filenames = []
    
    # Try absolute path first
    search_path = os.path.join(str(POLICY_DIR), "*.md")
    files = glob.glob(search_path)
    
    # Fallback to relative path if absolute resolution returns empty
    if not files:
        files = glob.glob("data/policies/*.md")

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read().strip()
                if content:
                    documents.append(content)
                    filenames.append(os.path.basename(filepath))
        except Exception as e:
            print(f"[RAG Error] Failed reading policy file {filepath}: {e}")
            
    return documents, filenames

def retrieve_policy(query: str, top_k: int = 2) -> str:
    """Finds the most relevant policy document for a given query."""
    documents, filenames = load_policies()
    
    # Emergency fallback if no markdown files are found on Streamlit Cloud
    if not documents:
        return (
            "--- Source: Fallback Policy Context ---\n"
            "Enhanced CPF Housing Grant (EHG): Up to $120,000 for families and $60,000 for singles (aged 35+). "
            "Family income ceiling is $9,000/mo for grants and $14,000/mo for BTO purchase. "
            "Single income ceiling is $4,500/mo for grants and $7,000/mo for 2-room Flexi BTO purchase."
        )

    # Initialize TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(stop_words='english')
    
    # Combine query with documents
    all_texts = documents + [query]
    
    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        # Cosine similarity between query (last vector) and documents (all except last)
        similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
        
        # Get top_k indices sorted by score
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        retrieved_chunks = []
        for idx in top_indices:
            # Return match if similarity is non-zero, or fallback to top match
            score = similarities[idx]
            if score > 0.001:
                retrieved_chunks.append(f"--- Source: {filenames[idx]} (Relevance: {score:.2f}) ---\n{documents[idx]}")

        # If TF-IDF word matching score was 0.0 for all docs, return the top document anyway
        if not retrieved_chunks:
            retrieved_chunks.append(f"--- Source: {filenames[top_indices[0]]} ---\n{documents[top_indices[0]]}")
            
        return "\n\n".join(retrieved_chunks)

    except Exception as e:
        print(f"[RAG Error] TF-IDF processing failed: {e}")
        return f"--- Source: {filenames[0]} ---\n{documents[0]}"
