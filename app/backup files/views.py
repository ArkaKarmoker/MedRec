from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decouple import config
import os
import json
import logging
from django.conf import settings
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# === RAG CONFIGURATION ===
regenerate_vectors = False # SET TO True TO REBUILD FROM CSV
CSV_PATH = os.path.join(settings.BASE_DIR, 'app', 'data', 'all_medicine_data_[www.medex.com.bd]_06.06.2025.csv')
PERSIST_DIR = os.path.join(settings.BASE_DIR, 'app', 'static', 'faiss_index')
# Global query engine
query_engine = None
def initialize_rag_pipeline():
    global query_engine
    if query_engine is not None:
        return query_engine
    try:
        logger.info("Initializing MedRec RAG Pipeline...")
        # === IMPORTS (Lazy to avoid heavy load if not needed) ===
        from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings, load_index_from_storage
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.core.query_engine import RetrieverQueryEngine
        from llama_index.core.retrievers import VectorIndexRetriever
        from llama_index.core import get_response_synthesizer
        from llama_index.core.postprocessor import SimilarityPostprocessor
        from llama_index.core.prompts import PromptTemplate
        from llama_index.core.storage.docstore import SimpleDocumentStore
        from llama_index.core.storage.index_store import SimpleIndexStore
        from llama_index.llms.google_genai import GoogleGenAI
        from llama_index.vector_stores.faiss import FaissVectorStore
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        import faiss
        import pandas as pd
        import torch
        # === GEMINI LLM SETUP ===
        gemini_api_key = config('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in .env")
        llm = GoogleGenAI(
            model="gemini-2.5-flash",
            api_key=gemini_api_key,
            temperature=0.7,
            max_tokens=2048
        )
        Settings.llm = llm
        # === LOAD EMBEDDING MODEL ===
        embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-mpnet-base-v2",
            device="cuda" if torch.cuda.is_available() else "cpu"
        )
        Settings.embed_model = embed_model
        index = None
        if regenerate_vectors:
            logger.info("Regenerating vectors from CSV...")
            if not os.path.exists(CSV_PATH):
                raise FileNotFoundError(f"CSV not found: {CSV_PATH}")
            # Load and process CSV
            df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
            logger.info(f"Loaded {len(df)} medicine entries.")
            documents = []
            for _, row in df.iterrows():
                row = row.fillna("")
                text = (
                    f"URL: {row.get('url', '')}, Name: {row.get('name', '')}, Strength: {row.get('strength', '')}, "
                    f"Generic Name: {row.get('generic_name', '')}, Manufacturer: {row.get('manufacturer', '')}, "
                    f"Type: {row.get('type', '')}, Dosage Form: {row.get('dosage_form', '')}, "
                    f"Unit Price: {row.get('unit_price', '')}, Strip Price: {row.get('strip_price', '')}, "
                    f"Pack Size Info: {row.get('pack_size_info', '')}, Pack Image URL: {row.get('pack_image_url', '')}, "
                    f"Indications: {row.get('indications', '')}, Side Effects: {row.get('side_effects', '')}, "
                    f"Pharmacology: {row.get('pharmacology', '')}, Dosage Administration: {row.get('dosage_administration', '')}, "
                    f"Interaction: {row.get('interaction', '')}, Contraindications: {row.get('contraindications', '')}, "
                    f"Pregnancy Lactation: {row.get('pregnancy_lactation', '')}, Precautions Warnings: {row.get('precautions_warnings', '')}, "
                    f"Special Populations: {row.get('special_populations', '')}, Overdose Effects: {row.get('overdose_effects', '')}, "
                    f"Therapeutic Class: {row.get('therapeutic_class', '')}, Storage Conditions: {row.get('storage_conditions', '')}, "
                    f"Chemical Structure: {row.get('chemical_structure', '')}, Description: {row.get('description', '')}, "
                    f"Reconstitution: {row.get('reconstitution', '')}, Common Questions: {row.get('common_questions', '')}, "
                    f"Alternate Brands: {row.get('alternate_brands', '')}, Innovators Monograph: {row.get('innovators_monograph', '')}"
                )
                if text.strip():
                    documents.append(Document(text=text.strip()))
            # Deduplicate
            seen = set()
            documents = [d for d in documents if d.text not in seen and seen.add(d.text)]
            # Chunk documents
            node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=128)
            nodes = node_parser.get_nodes_from_documents(documents)
            # Build FAISS index
            dimension = len(embed_model.get_text_embedding("test"))
            faiss_index = faiss.IndexFlatL2(dimension)
            vector_store = FaissVectorStore(faiss_index=faiss_index)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex(nodes, storage_context=storage_context, show_progress=True)
            # Save to disk
            os.makedirs(PERSIST_DIR, exist_ok=True)
            storage_context.persist(persist_dir=PERSIST_DIR)
            faiss.write_index(faiss_index, os.path.join(PERSIST_DIR, 'index.faiss'))
            logger.info(f"Index built and saved to {PERSIST_DIR}")
        else:
            logger.info("Loading pre-saved FAISS index...")
            paths = {
                'faiss': os.path.join(PERSIST_DIR, 'index.faiss'),
                'docstore': os.path.join(PERSIST_DIR, 'docstore.json'),
                'index_store': os.path.join(PERSIST_DIR, 'index_store.json'),
            }
            vector_store_path = os.path.join(PERSIST_DIR, 'vector_stores', 'default__vector_store.json')
            for name, path in paths.items():
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Missing: {path}")
            def safe_load_json(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    with open(path, 'r', encoding='cp1252', errors='replace') as f:
                        return json.load(f)
            faiss_index = faiss.read_index(paths['faiss'])
            docstore = SimpleDocumentStore.from_dict(safe_load_json(paths['docstore']))
            index_store = SimpleIndexStore.from_dict(safe_load_json(paths['index_store']))
            if os.path.exists(vector_store_path):
                vector_store_data = safe_load_json(vector_store_path)
            else:
                vector_store_data = {}
            vector_store = FaissVectorStore(faiss_index=faiss_index, **vector_store_data)
            storage_context = StorageContext.from_defaults(
                docstore=docstore,
                index_store=index_store,
                vector_store=vector_store
            )
            index = load_index_from_storage(storage_context)
            logger.info("Pre-saved index loaded successfully.")
        # === QUERY ENGINE (Same in both modes) ===
        qa_prompt_tmpl_str = """
You are a trusted medicine assistant. Respond to the user query in two distinct sections:

**MedRec Knowledge Base:**
- Use ONLY the provided context from the verified dataset.
- Structure the response in clear bullet points with relevant categories (e.g., Generic Name, Indications, Dosage & Administration, Side Effects, etc.).
- If information is missing, state "Not specified in available data."
- Do not add any external knowledge, assumptions, or generalizations.

**Gemini:**
- Provide a general, unrestricted response as if answering the query directly without any context or filtering, like a raw search engine or general AI response.
- Be comprehensive, helpful, and natural, including any relevant details from general knowledge.

Context (for MedRec Knowledge Base only):
{context_str}

User Query: {query_str}
"""
        qa_prompt = PromptTemplate(qa_prompt_tmpl_str)
        retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=5,
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.65)]
        )
        synthesizer = get_response_synthesizer(
            response_mode="compact",
            text_qa_template=qa_prompt
        )
        query_engine = RetrieverQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
        logger.info("RAG Query Engine ready.")
        return query_engine
    except Exception as e:
        logger.error(f"RAG init failed: {e}")
        return None
# Initialize on startup
initialize_rag_pipeline()
# === DJANGO VIEWS ===
def app(request):
    """Render chatbot UI"""
    return render(request, 'app/app.html')
@csrf_exempt
def gemini_chat(request):
    """API endpoint for RAG-powered chatbot"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        user_query = data.get('query', '').strip()
        if not user_query:
            return JsonResponse({'error': 'Query required'}, status=400)
        # Greetings
        if any(x in user_query.lower() for x in ["hi", "hello", "hey"]):
            return JsonResponse({'response': (
                "Hello! I'm **MedRec**, your medicine info assistant.\n"
                "Ask about generics, side effects, dosage, etc.\n\n"
                "> **Warning: Always consult a doctor before use.**"
            )})
        if query_engine is None:
            return JsonResponse({'error': 'RAG engine not ready'}, status=503)
        result = query_engine.query(user_query)
        response = str(result).strip()
        if not response or "not found" in response.lower():
            response = "No reliable info found. Try a specific brand/generic name."
        response += "\n\n> **Warning: Always consult a licensed doctor or pharmacist.**"
        return JsonResponse({'response': response})
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return JsonResponse({'error': 'Service unavailable'}, status=500)
