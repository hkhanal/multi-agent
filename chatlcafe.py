import json
import urllib.request
import urllib.error
import urllib.parse
from time import sleep

class ChatLcafe:
    def __init__(
        self,
        model="gpt-4o",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=None,
        base_url="https://api.openai.com/v1",
        organization=None
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.organization = organization
    
    def invoke(self, messages):
        """Send messages to the chat API and return the generated response."""
        url = f"{self.base_url}/chat/completions"
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        last_exception = None
        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    response_data = json.load(response)
                    return response_data['choices'][0]['message']['content']
                    
            except urllib.error.HTTPError as e:
                last_exception = e
                if e.code in {429, 500, 502, 503, 504}:  # Retriable errors
                    if attempt < self.max_retries:
                        sleep(2 ** attempt)  # Exponential backoff
                        continue
                raise self._handle_http_error(e) from None
                
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    sleep(1)  # Short delay for network issues
                    continue
                raise ConnectionError("Network error after retries") from e
                
        raise RuntimeError(f"All retries failed: {str(last_exception)}")
    
    def _handle_http_error(self, error):
        """Create descriptive error message from HTTP response."""
        try:
            body = error.read().decode()
            details = json.loads(body).get('error', {})
            msg = details.get('message', 'Unknown error')
            return Exception(f"API Error [{error.code}]: {msg}")
        except:
            return Exception(f"HTTP Error [{error.code}]: {error.reason}")
    
    # Optional: Make the instance callable like LangChain's model
    def __call__(self, messages):
        return self.invoke(messages)

# Usage Example
if __name__ == "__main__":
    # Initialize with parameters (API key should typically come from environment variables)
    import os
    from dotenv import load_dotenv

    api_key = os.getenv("OPENAI_API_KEY")
    chat = ChatLcafe(
        model="gpt-4o",
        api_key=api_key,
        base_url="https://api.openai.com/v1",
        temperature=0.7,
        max_retries=2,
        timeout=30
    )
    
    # Define chat messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"}
    ]
    
    try:
        response = chat.invoke(messages)
        print("Assistant:", response)
    except Exception as e:
        print("Error:", str(e))