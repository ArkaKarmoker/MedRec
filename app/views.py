from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required  # <-- ADDED
from django.utils import timezone
from decouple import config
import os
import json
import logging
from django.conf import settings
import uuid
from .models import ChatSession, ChatMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Note: CSV and FAISS processing has been moved to upload_to_supabase.py

# Global query engine
query_engine = None
llm = None


def initialize_rag_pipeline():
    global query_engine, llm
    if query_engine is not None:
        return query_engine
    try:
        logger.info("Initializing MedRec RAG Pipeline...")
        # === IMPORTS (Lazy to avoid heavy load if not needed) ===
        from llama_index.core import VectorStoreIndex, Settings
        from llama_index.core.query_engine import RetrieverQueryEngine
        from llama_index.core.retrievers import VectorIndexRetriever
        from llama_index.core import get_response_synthesizer
        from llama_index.core.postprocessor import SimilarityPostprocessor
        from llama_index.core.prompts import PromptTemplate
        from llama_index.llms.google_genai import GoogleGenAI
        from llama_index.embeddings.huggingface import HuggingFaceInferenceAPIEmbedding
        from llama_index.vector_stores.supabase import SupabaseVectorStore

        # === GEMINI LLM SETUP ===
        gemini_api_key = config('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in .env")
        llm = GoogleGenAI(
            model="gemini-2.5-flash",
            api_key=gemini_api_key,
            temperature=0.7,
            max_tokens=4096
        )
        Settings.llm = llm

        # === LOAD HUGGING FACE INFERENCE API EMBEDDING MODEL ===
        hf_token = config('HF_TOKEN')
        if not hf_token:
            raise ValueError("HF_TOKEN not found in .env")
        
        logger.info("Connecting to Hugging Face Inference API...")
        embed_model = HuggingFaceInferenceAPIEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            token=hf_token
        )
        Settings.embed_model = embed_model

        # === CONNECT TO SUPABASE VECTOR STORE ===
        supabase_db_url = config('SUPABASE_DB_URL')
        if not supabase_db_url:
            raise ValueError("SUPABASE_DB_URL not found in .env")

        logger.info("Connecting to Supabase Database...")
        vector_store = SupabaseVectorStore(
            postgres_connection_string=supabase_db_url,
            collection_name="medicine_data",
            dimension=384
        )

        # Load the index directly from Supabase
        logger.info("Loading VectorStoreIndex from Supabase...")
        index = VectorStoreIndex.from_vector_store(vector_store)
        logger.info("Supabase Vector Store index loaded successfully.")

        # === QUERY ENGINE ===
        qa_prompt_tmpl_str = (
            "Using only the information in the context below, provide a concise, accurate answer to the question in key points or bullet points format. "
            "Include only the most relevant details like indications, side effects, dosage, generics, or brand names as specified in the question. "
            "Do not generate any information not explicitly stated in the context. If the information is not in the context, say 'Information not found in dataset.'\n\n"
            "Context:\n{context_str}\n\n"
            "Question: {query_str}\n"
            "Answer: "
        )
        qa_prompt = PromptTemplate(qa_prompt_tmpl_str)
        
        # We lower the similarity cutoff slightly to accommodate BGE-small differences compared to all-mpnet
        retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=5,
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.60)]
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

@login_required  # <-- ADDED: Requires login to access the UI
def app(request):
    """Render chatbot UI"""
    return render(request, 'app/app.html')


@csrf_exempt
@login_required  # <-- ADDED: Requires login to use the chat API
def gemini_chat(request):
    """API endpoint for RAG-powered chatbot"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        user_query = data.get('query', '').strip()
        selected_model = data.get('model', 'gemini-2.5-flash')
        dual_response = data.get('dual_response', True)
        session_id = data.get('session_id')
        if not user_query:
            return JsonResponse({'error': 'Query required'}, status=400)

        # Get session if provided
        session = None
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                pass

        # Save user message to session
        if session:
            ChatMessage.objects.create(session=session, role='user', content=user_query)

        # Greetings
        if any(x in user_query.lower() for x in ["hi", "hello", "hey"]):
            greeting_text = (
                "Hello 👋! I'm **MedRec**, your medicine info assistant.\n"
                "Ask about generics, side effects, dosage, etc.\n\n"
                "> **⚠ Warning: Always consult a doctor before use.**"
            )
            if session:
                ChatMessage.objects.create(session=session, role='bot', content=greeting_text, model_name=selected_model)
                _auto_title_session(session, user_query)
            return JsonResponse({'response': greeting_text, 'model': selected_model,
                'session_id': session.id if session else None, 'title': session.title if session else None})

        if query_engine is None:
            return JsonResponse({'error': 'RAG engine not ready'}, status=503)

        # Dynamically set the LLM to the user-selected model for this request
        from llama_index.llms.google_genai import GoogleGenAI
        gemini_api_key = config('GEMINI_API_KEY')
        request_llm = GoogleGenAI(
            model=selected_model,
            api_key=gemini_api_key,
            temperature=0.7,
            max_tokens=4096
        )
        query_engine._response_synthesizer._llm = request_llm

        rag_result = query_engine.query(user_query)
        rag_response = str(rag_result).strip()
        if not rag_response or "not found" in rag_response.lower():
            rag_response = "No reliable info found. Try a specific brand/generic name."

        if dual_response:
            # Direct LLM call uses the same request_llm already created above
            gemini_result = request_llm.complete(user_query)
            gemini_response = str(gemini_result).strip()

            response_text = (
                "**💊 MedRec Knowledge base:**\n\n" + rag_response +
                "\n\n---\n\n**✨ " + selected_model + ":**\n\n" + gemini_response +
                "\n\n> **⚠ Warning: Always consult a licensed doctor or pharmacist. - MedRec**"
            )
            if session:
                ChatMessage.objects.create(session=session, role='bot', content=response_text, model_name=selected_model)
                _auto_title_session(session, user_query)
            return JsonResponse({'response': response_text, 'model': selected_model, 'dual_response': True,
                'session_id': session.id if session else None, 'title': session.title if session else None})
        else:
            response_text = "**💊 MedRec Knowledge base:**\n\n" + rag_response + "\n\n> **⚠ Warning: Always consult a licensed doctor or pharmacist. - MedRec**"
            if session:
                ChatMessage.objects.create(session=session, role='bot', content=response_text, model_name='MedRec KB')
                _auto_title_session(session, user_query)
            return JsonResponse({'response': response_text, 'model': 'MedRec KB', 'dual_response': False,
                'session_id': session.id if session else None, 'title': session.title if session else None})
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return JsonResponse({'error': 'Service unavailable'}, status=500)


def _auto_title_session(session, user_query):
    """Auto-title a session from the first user message."""
    if session.title == 'New Chat':
        title = user_query[:40]
        if len(user_query) > 40:
            title += '...'
        session.title = title
        session.save(update_fields=['title'])


# =========================================
# === CHAT HISTORY API ENDPOINTS ===
# =========================================

@csrf_exempt
@login_required
def list_sessions(request):
    """List all chat sessions for the current user."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    sessions = ChatSession.objects.filter(user=request.user).order_by('-is_pinned', '-updated_at')
    data = [{
        'id': s.id,
        'title': s.title,
        'is_pinned': s.is_pinned,
        'updated_at': s.updated_at.isoformat(),
    } for s in sessions]
    return JsonResponse({'sessions': data})


@csrf_exempt
@login_required
def create_session(request):
    """Create a new chat session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    session = ChatSession.objects.create(user=request.user)
    return JsonResponse({'id': session.id, 'title': session.title})


@csrf_exempt
@login_required
def get_session(request, session_id):
    """Get a single session with all messages."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    messages = [{
        'role': m.role,
        'content': m.content,
        'model_name': m.model_name,
        'created_at': m.created_at.isoformat(),
    } for m in session.messages.all()]
    return JsonResponse({
        'id': session.id,
        'title': session.title,
        'is_pinned': session.is_pinned,
        'share_id': session.share_id,
        'messages': messages,
    })


@csrf_exempt
@login_required
def rename_session(request, session_id):
    """Rename a chat session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    data = json.loads(request.body)
    title = data.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Title required'}, status=400)
    session.title = title[:255]
    session.save(update_fields=['title'])
    return JsonResponse({'id': session.id, 'title': session.title})


@csrf_exempt
@login_required
def toggle_pin_session(request, session_id):
    """Toggle pin status of a chat session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    session.is_pinned = not session.is_pinned
    session.save(update_fields=['is_pinned'])
    return JsonResponse({'id': session.id, 'is_pinned': session.is_pinned})


@csrf_exempt
@login_required
def share_session(request, session_id):
    """Generate or return share link for a session. POST to create, DELETE to revoke."""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    
    if request.method == 'POST':
        if not session.share_id:
            session.share_id = str(uuid.uuid4())
            session.shared_at = timezone.now()
            session.save(update_fields=['share_id', 'shared_at'])
        share_url = request.build_absolute_uri(f'/share/{session.share_id}/')
        return JsonResponse({'share_url': share_url, 'share_id': session.share_id})
    
    elif request.method == 'DELETE':
        session.share_id = None
        session.shared_at = None
        session.save(update_fields=['share_id', 'shared_at'])
        return JsonResponse({'status': 'ok'})
    
    return JsonResponse({'error': 'POST or DELETE required'}, status=405)


@csrf_exempt
@login_required
def delete_session(request, session_id):
    """Delete a chat session."""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    session.delete()
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@login_required
def delete_all_sessions(request):
    """Delete all chat sessions for the current user."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    ChatSession.objects.filter(user=request.user).delete()
    return JsonResponse({'status': 'ok'})


@login_required
def list_shared_links(request):
    """List all shared links for the current user."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    sessions = ChatSession.objects.filter(user=request.user, share_id__isnull=False).order_by('-shared_at')
    links = []
    for s in sessions:
        links.append({
            'id': s.id,
            'title': s.title,
            'share_id': s.share_id,
            'share_url': request.build_absolute_uri(f'/share/{s.share_id}/'),
            'shared_at': s.shared_at.strftime('%B %d, %Y') if s.shared_at else '',
        })
    return JsonResponse({'links': links})


def view_shared_chat(request, share_id):
    """Public read-only view of a shared chat. No login required."""
    try:
        session = ChatSession.objects.get(share_id=share_id)
    except ChatSession.DoesNotExist:
        return render(request, 'app/shared_chat.html', {'error': 'Shared chat not found.'})
    messages = session.messages.all()
    return render(request, 'app/shared_chat.html', {
        'session': session,
        'messages': messages,
    })