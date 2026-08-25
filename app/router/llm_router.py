import json
import logging
import os

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")

class LLMRouter:
    CLASSIFICATION_PROMPT = """You are an LLM router. Classify the complexity of this query.

Categories:
- simple: short, single-purpose code generation with no design decisions — CRUD boilerplate, types/enums, getters/setters, basic formatting
- local: self-contained code/markup generation with no design decisions but broader scope than "simple" — standalone HTML/CSS pages, static templates, small independent utility scripts
- standard: requires understanding context or producing structured written output — refactoring, debugging, tests, explanations, writing documentation/specs/planning documents
- complex: requires architectural or systemic reasoning — system design, code review, performance/algorithmic optimization, security audits, distributed systems, incident investigation

Examples:
Query: "create a getter and setter for this class"
{{"tier": "simple", "confidence": 0.9}}

Query: "create a simple HTML landing page with a contact form"
{{"tier": "local", "confidence": 0.9}}

Query: "write a spec document for a gamified todo app"
{{"tier": "standard", "confidence": 0.9}}

Query: "design a distributed caching architecture"
{{"tier": "complex", "confidence": 0.9}}

Query: {query}

Respond with ONLY a JSON object:
{{"tier": "simple|local|standard|complex", "confidence": 0.0-1.0}}"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or OLLAMA_MODEL
        self._available = OLLAMA_AVAILABLE
        if self._available:
            try:
                ollama.Client(host=OLLAMA_HOST)
            except Exception:
                self._available = False
                logger.warning("[LLMRouter] Ollama não acessível")

    def classify(self, query: str) -> tuple[str, float]:
        if not self._available:
            return ("unknown", 0.0)

        try:
            client = ollama.Client(host=OLLAMA_HOST)
            response = client.chat(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a query complexity classifier. Output only JSON.",
                    },
                    {
                        "role": "user",
                        "content": self.CLASSIFICATION_PROMPT.format(query=query[:500]),
                    },
                ],
                format="json",
                options={
                    "temperature": 0.1,
                    "num_predict": 50,
                },
            )

            result = json.loads(response["message"]["content"])
            tier = result.get("tier", "standard")
            confidence = float(result.get("confidence", 0.5))
            return (tier, confidence)

        except Exception as e:
            logger.warning(f"[LLMRouter] Falha: {e}")
            return ("unknown", 0.0)