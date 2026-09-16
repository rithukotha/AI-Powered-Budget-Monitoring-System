import pandas as pd
import pickle
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

# -----------------------------
# 1. Load Dataset
# -----------------------------
data = pd.read_csv("expense_data.csv")

# -----------------------------
# 2. Simple Text Preprocessing
# -----------------------------
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    return text

data['text'] = data['text'].apply(clean_text)

X = data['text']
y = data['category']

# -----------------------------
# 3. Convert Text → Numbers
# -----------------------------
vectorizer = TfidfVectorizer(
    stop_words='english',
    ngram_range=(1, 2)
)
X_vectorized = vectorizer.fit_transform(X)

# -----------------------------
# 4. Train Naive Bayes Model
# -----------------------------
model = MultinomialNB()
model.fit(X_vectorized, y)

# -----------------------------
# 5. Save Model & Vectorizer
# -----------------------------
pickle.dump(model, open("expense_model.pkl", "wb"))
pickle.dump(vectorizer, open("vectorizer.pkl", "wb"))

print("✅ Expense categorization model trained successfully!")
