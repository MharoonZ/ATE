import os
from langchain_openai import ChatOpenAI


chat_model = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
    temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.0")),
    streaming=True,
    api_key=os.getenv("OPENAI_API_KEY")
)
