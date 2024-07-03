from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Загрузка модели и токенизатора
model_name = "intfloat/multilingual-e5-base"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

# Преобразование текста в векторы
def embed_text(texts):
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    embeddings = outputs.pooler_output.numpy()
    return embeddings


def search_faq(query, pack, threshold=0.848):
    questions = [item['question'] for item in pack]
    question_vectors = embed_text(questions)
    query_vector = embed_text([query])[0].reshape(1, -1)
    similarities = cosine_similarity(question_vectors, query_vector).flatten()
    results = [
        {"question": pack[idx]['question'], "answer": pack[idx]['answer'], "similarity": similarities[idx]}
        for idx in range(len(similarities)) if similarities[idx] > threshold
    ]
    results = sorted(results, key=lambda x: x["similarity"], reverse=True)
    return results