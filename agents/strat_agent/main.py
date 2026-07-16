import os
import io
import uvicorn
from dotenv import load_dotenv
import pypdf
from google.cloud import storage

from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Load environment variables (searches up to finding .env at repo root)
load_dotenv()

def inspect_strategy_documents() -> str:
    """Lists and extracts text from all strategy PDF documents in the corpus.

    Dynamically switches between local directory (assets/docs) and a Google Cloud
    Storage bucket based on the presence of the 'STRATEGY_DOCS_BUCKET' env variable.

    Returns:
        str: Concatenated text content extracted from all PDFs, or an explanation if none are found.
    """
    bucket_name = os.getenv("STRATEGY_DOCS_BUCKET")
    extracted_texts = []

    if bucket_name:
        # Production: Fetch from GCS bucket
        print(f"[Strategy Agent] Running in cloud mode. Inspecting GCS bucket: '{bucket_name}'...")
        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            # List all blobs and filter for .pdf
            blobs = list(bucket.list_blobs())
            pdf_blobs = [b for b in blobs if b.name.lower().endswith(".pdf")]

            if not pdf_blobs:
                return f"No PDF documents found in GCS bucket '{bucket_name}'."

            for blob in pdf_blobs:
                print(f"[Strategy Agent] Fetching and parsing GCS blob: '{blob.name}'...")
                pdf_data = blob.download_as_bytes()
                pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_data))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
                extracted_texts.append(f"--- Document (GCS): {blob.name} ---\n{text}\n")

        except Exception as e:
            return f"Error connecting to or reading from GCS bucket '{bucket_name}': {str(e)}"
    else:
        # Local Development: Fetch from assets/docs
        current_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(os.path.dirname(current_dir))
        local_docs_dir = os.path.join(repo_root, "assets", "docs")
        print(f"[Strategy Agent] Running in local mode. Inspecting local directory: '{local_docs_dir}'...")

        if not os.path.exists(local_docs_dir):
            return f"Local strategy documents directory not found at '{local_docs_dir}'."

        try:
            pdf_files = [f for f in os.listdir(local_docs_dir) if f.lower().endswith(".pdf")]
        except Exception as e:
            return f"Error listing local directory '{local_docs_dir}': {str(e)}"

        if not pdf_files:
            return f"No PDF documents found in local directory '{local_docs_dir}'."

        for file_name in pdf_files:
            file_path = os.path.join(local_docs_dir, file_name)
            print(f"[Strategy Agent] Parsing local PDF: '{file_name}'...")
            try:
                pdf_reader = pypdf.PdfReader(file_path)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
                extracted_texts.append(f"--- Document (Local): {file_name} ---\n{text}\n")
            except Exception as e:
                extracted_texts.append(f"--- Document (Local): {file_name} ---\nError parsing PDF: {str(e)}\n")

    return "\n\n".join(extracted_texts)


# Define the ADK Agent
strategy_agent = Agent(
    model="gemini-2.5-flash",
    name="strategy_agent",
    description="Analyzes corporate strategy documents and returns a brief strategic summary.",
    instruction=(
        "You are an expert strategic analyst. Your task is to analyze the text "
        "provided by the 'inspect_strategy_documents' tool and summarize the corporate strategy "
        "implied by those documents.\n\n"
        "Rules for your output:\n"
        "1. Your summary must be terse and directly to the point.\n"
        "2. It must include clear, brief assertions as bullet points.\n"
        "3. It must use high-quality markdown formatting.\n"
        "4. Do not assume or hallucinate outside the contents of the provided documents.\n"
        "5. You must call the 'inspect_strategy_documents' tool first to retrieve the facts."
    ),
    tools=[inspect_strategy_documents],
)

# Convert the ADK Agent to an A2A-compliant FastAPI application
port = int(os.getenv("PORT", 8080))
a2a_app = to_a2a(strategy_agent, port=port)

if __name__ == "__main__":
    print(f"[Strategy Agent] Starting A2A Agent server on port {port}...")
    uvicorn.run(a2a_app, host="0.0.0.0", port=port)
