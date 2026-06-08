import os
import logging
import pandas as pd
from decouple import config
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.supabase import SupabaseVectorStore
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CSV Path
# The CSV is in the 'data' directory at the root of your project
CSV_PATH = os.path.join(os.getcwd(), 'data', 'all_medicine_data_[www.medex.com.bd]_06.06.2025.csv')

def upload_to_supabase():
    # 1. Load Supabase Connection String from .env
    supabase_db_url = config('SUPABASE_DB_URL', default='')
    if not supabase_db_url:
        logger.error("Please add SUPABASE_DB_URL to your .env file!")
        logger.error("Example: SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres")
        return

    logger.info("Initializing HuggingFace Embedding Model: BAAI/bge-small-en-v1.5 ...")
    # 2. Setup Embedding Model (Runs locally to save API costs)
    embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-small-en-v1.5",
        device="cuda" if torch.cuda.is_available() else "cpu"
    )
    Settings.embed_model = embed_model

    # 3. Read the CSV File
    logger.info(f"Reading CSV from {CSV_PATH} ...")
    if not os.path.exists(CSV_PATH):
        logger.error("CSV file not found!")
        return

    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    logger.info(f"Loaded {len(df)} medicine entries. Preparing documents...")

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
    unique_documents = []
    for d in documents:
        if d.text not in seen:
            seen.add(d.text)
            unique_documents.append(d)
    documents = unique_documents
    logger.info(f"Created {len(documents)} unique documents.")

    # Chunk the documents
    node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=128)
    nodes = node_parser.get_nodes_from_documents(documents)
    logger.info(f"Split documents into {len(nodes)} chunks.")

    # 4. Connect to Supabase
    logger.info("Connecting to Supabase Database...")
    vector_store_supabase = SupabaseVectorStore(
        postgres_connection_string=supabase_db_url,
        collection_name="medicine_data",
        dimension=384 # BAAI/bge-small-en-v1.5 has 384 dimensions
    )
    
    storage_context_supabase = StorageContext.from_defaults(vector_store=vector_store_supabase)

    # 5. Generate Vectors and Upload to Supabase!
    logger.info("Starting embedding generation and Supabase upload. This may take some time...")
    index_supabase = VectorStoreIndex(
        nodes, 
        storage_context=storage_context_supabase, 
        show_progress=True
    )
    logger.info("✅ Supabase Upload Complete!")

    # 6. Save a local copy using FAISS (for testing without internet/supabase)
    logger.info("Saving a local copy to FAISS...")
    import faiss
    from llama_index.vector_stores.faiss import FaissVectorStore
    
    # BAAI/bge-small-en-v1.5 has 384 dimensions
    faiss_index = faiss.IndexFlatL2(384)
    vector_store_faiss = FaissVectorStore(faiss_index=faiss_index)
    storage_context_faiss = StorageContext.from_defaults(vector_store=vector_store_faiss)
    
    # The nodes already have embeddings from the previous step, so this will be instant
    index_faiss = VectorStoreIndex(
        nodes, 
        storage_context=storage_context_faiss, 
        show_progress=True
    )
    
    PERSIST_DIR = os.path.join(os.getcwd(), 'app', 'static', 'faiss_index_bge')
    os.makedirs(PERSIST_DIR, exist_ok=True)
    storage_context_faiss.persist(persist_dir=PERSIST_DIR)
    faiss.write_index(faiss_index, os.path.join(PERSIST_DIR, 'index.faiss'))
    
    logger.info(f"✅ Local FAISS copy saved successfully in {PERSIST_DIR}!")
    logger.info("🎉 All operations completed successfully!")

if __name__ == "__main__":
    upload_to_supabase()
