import pickle

model = pickle.load(open("expense_model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer.pkl", "rb"))

tests = [
    "kfc bill",
    "uber trip receipt",
    "electricity board bill",
    "pharmacy invoice",
    "online course payment"
]

for t in tests:
    pred = model.predict(vectorizer.transform([t]))[0]
    print(t, "→", pred)
