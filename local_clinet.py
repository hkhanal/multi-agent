from typing import Iterable, List, Dict, Optional
from openai import OpenAI

class LocalLLMClient:
    """
    Thin wrapper around vLLM's OpenAI-compatible server.
    Usage:
        llm = LocalLLMClient(base_url="http://localhost:8000/v1",
                             api_key="dummy",
                             model="qwen2.5-14b-instruct")
        resp = llm.chat([{"role":"user","content":"Hello"}])
    """
    def __init__(self,
                 base_url: str = "http://localhost:8000/v1",
                 api_key: str = "dummy",
                 model: str = "qwen2.5-14b-instruct",
                 timeout: Optional[float] = 60):
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

    def chat(self, messages: List[Dict], **kwargs) -> str:
        """
        Non-streaming chat completion. Returns assistant text.
        Extra kwargs (e.g., temperature, max_output_tokens) are forwarded.
        """
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return resp.choices[0].message.content or ""

    def stream_chat(self, messages: List[Dict], **kwargs) -> Iterable[str]:
        """
        Streaming chat completion. Yields text chunks.
        """
        with self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs
        ) as stream:
            for event in stream:
                if event.choices and event.choices[0].delta and event.choices[0].delta.content:
                    yield event.choices[0].delta.content

    def json_chat(self, messages: List[Dict], schema: Optional[dict] = None, **kwargs) -> dict:
        """
        Ask the model to return JSON. vLLM supports OpenAI's 'response_format={"type":"json_object"}'.
        Optionally include a schema in system/user text if you want stricter structure.
        """
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            **kwargs
        )
        import json
        return json.loads(resp.choices[0].message.content or "{}")
