# 💊 MedRec - AI-Powered Medicine Recommendation & Info Chatbot

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/django-5.2+-green.svg)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-RAG-purple.svg)
![Supabase](https://img.shields.io/badge/Supabase-pgvector-emerald.svg)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Inference%20API-yellow.svg)
![Gemini](https://img.shields.io/badge/Google-Gemini%202.5-orange.svg)

**MedRec** is an advanced, production-ready AI chatbot designed to provide instant, accurate, and reliable information about medicines. Built using a robust **Retrieval-Augmented Generation (RAG)** architecture, it leverages a massive dataset of medicine information, storing it in a high-performance vector database to deliver context-aware answers using Google's Gemini LLM.

> **⚠️ Disclaimer:** MedRec is designed for informational and educational purposes only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition.

---

## ✨ Key Features

- **🧠 Advanced RAG Pipeline:** Combines the reasoning power of Gemini 2.5 with a highly structured medical database to prevent hallucination and ensure accurate responses.
- **⚡ Serverless & Lightweight:** Completely relies on cloud APIs (Hugging Face & Gemini) for ML operations, drastically reducing memory footprint and deployment costs.
- **☁️ Cloud Vector Storage:** Uses Supabase `pgvector` for lighting-fast semantic search across ~114,000+ medical data chunks.
- **💬 Dual-Response System:** Provides answers strictly from the verified medical knowledge base alongside a generalized AI response.
- **🔒 Secure User Sessions:** Built with Django authentication. User chat histories are securely saved in a PostgreSQL database.
- **🚀 Production Ready:** Fully configured with `gunicorn`, `whitenoise`, and deployment scripts for seamless hosting on platforms like Render or Railway.

---

## 🛠️ Tech Stack

- **Backend Framework:** Django 5.2
- **LLM Orchestration:** LlamaIndex
- **Generative AI:** Google Gemini (2.5 Flash / 2.5 Pro)
- **Embedding Model:** Hugging Face Inference API (`BAAI/bge-small-en-v1.5`)
- **Vector Database:** Supabase (`pgvector` via `vecs`)
- **Relational Database:** Supabase PostgreSQL (via `dj-database-url`)

---

## 📂 Project Structure

```text
MedRec/
├── accounts/               # Django app for user authentication
├── app/                    # Main Django app handling chatbot and RAG logic
│   ├── static/             # CSS, JS, and local FAISS vector indices
│   └── views.py            # Chatbot API endpoints and LLM fallback logic
├── data/                   # Directory for storing raw medicine CSV datasets
├── MedRec/                 # Django project settings and root configurations
├── templates/              # HTML templates (accounts and chatbot UI)
├── .env                    # Environment variables (API keys, DB URLs)
├── build.sh                # Deployment build script for Render
├── manage.py               # Django command-line utility
├── requirements.txt        # Python dependencies
└── upload_to_supabase.py   # One-time script for ingesting data to Supabase
```

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following API keys and URLs ready:
1. **Google AI API Key** (For Gemini LLM)
2. **Hugging Face Access Token** (Fine-grained token with *Inference API* permissions)
3. **Supabase Database URL** (PostgreSQL connection string with a valid password)

---

## 🚀 Installation & Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/ArkaKarmoker/MedRec.git
cd MedRec
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: .\venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory and add your credentials:
```env
GEMINI_API_KEY=your_gemini_api_key_here
HF_TOKEN=your_huggingface_fine_grained_token_here
SUPABASE_DB_URL=postgresql://postgres.xxx:yourpassword@aws-xxx.pooler.supabase.com:5432/postgres
SECRET_KEY=your_django_secret_key_here
DEBUG=True
```

### 5. Run Database Migrations
Since Django is connected to Supabase PostgreSQL, this will create the necessary auth and session tables in the cloud.
```bash
python manage.py migrate
```

### 6. Start the Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 📊 Dataset Ingestion (One-time Setup)

If you have a new CSV dataset of medicines and need to upload it to Supabase for the very first time:

1. Place your CSV file in the `data/` folder.
2. Update the file path in `upload_to_supabase.py`.
3. Run the ingestion script (This will take some time depending on dataset size):
```bash
python upload_to_supabase.py
```
*Note: This script generates embeddings locally via `SentenceTransformers` and saves them to both Supabase and a local FAISS index (as backup).*

---

## 🌍 Deployment (Render.com)

This project is fully optimized for free-tier deployments on [Render](https://render.com/).

1. Create a **New Web Service** and connect this GitHub repository.
2. Set the **Build Command** to:
   ```bash
   ./build.sh
   ```
3. Set the **Start Command** to:
   ```bash
   gunicorn MedRec.wsgi:application
   ```
4. Add all environment variables from your `.env` file into Render's **Environment Variables** dashboard (Set `DEBUG` to `False`).
5. Click **Deploy**.

---

<p align="center">
  <b>&copy; 2026 Arka Karmoker. All rights reserved.</b>
</p>

