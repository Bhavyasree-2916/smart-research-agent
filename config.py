import os
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY","")
MODEL_SMALL = os.getenv("MODEL_SMALL", "gpt-4o-mini")
MODEL_MAIN = os.getenv("MODEL_MAIN", "gpt-4o")
EMBEDDING_MODEL = "text-embedding-3-small"
