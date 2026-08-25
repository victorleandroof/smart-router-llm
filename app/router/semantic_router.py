import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    SEMANTIC_ROUTER_AVAILABLE = True
except ImportError:
    SEMANTIC_ROUTER_AVAILABLE = False
    logger.warning("sentence-transformers/faiss não instalados — fallback para regex")

class SemanticRouter:
    REFERENCE_PROMPTS = {
        "simple": [
            "create a basic CRUD controller",
            "generate a TypeScript interface for a user",
            "write a simple getter and setter",
            "create an enum for status codes",
            "generate boilerplate code for a REST endpoint",
            "criar uma classe simples de DTO",
            "gerar um tipo básico",
            "criar um controller básico",
            "scaffold a new module",
            "create a mapper class",
        ],
        "local": [
            "create a simple HTML landing page",
            "generate an HTML form with CSS styling",
            "write a standalone utility script",
            "create a static HTML page with a table",
            "generate a small script to parse a CSV file",
            "criar uma página HTML simples com formulário",
            "gerar um script utilitário independente",
            "criar uma landing page estática em HTML e CSS",
            "escrever uma função utilitária simples",
            "gerar um template HTML básico",
        ],
        "standard": [
            "explain how this function works",
            "refactor this method to be cleaner",
            "write a unit test for this component",
            "summarize what this module does",
            "translate this comment to English",
            "generate documentation for this API",
            "fix a bug in this function",
            "explain the difference between two approaches",
            "review this pull request",
            "add error handling to this method",
            "write a spec document for a new application",
            "create a product requirements document",
            "criar um documento de especificação para uma nova aplicação",
            "escrever uma especificação técnica de um sistema",
            "criar documentação de planejamento para um projeto",
        ],
        "complex": [
            "debug a race condition in async code",
            "analyze memory leak in production",
            "optimize algorithm complexity from O(n²) to O(n log n)",
            "design a distributed system architecture",
            "audit security vulnerabilities in this codebase",
            "migrate legacy monolith to microservices",
            "investigate root cause of production incident",
            "analyze tradeoffs between consistency and availability",
            "design a caching strategy for high throughput",
            "architect event-driven system with saga pattern",
            "code review"
        ],
    }

    def __init__(self):
        if not SEMANTIC_ROUTER_AVAILABLE:
            self.index = None
            self.labels = None
            return

        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

        all_prompts = []
        all_labels = []
        for tier, prompts in self.REFERENCE_PROMPTS.items():
            for p in prompts:
                all_prompts.append(p)
                all_labels.append(tier)

        embeddings = self.embedder.encode(all_prompts, normalize_embeddings=True)
        dim = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings.astype("float32"))
        self.labels = np.array(all_labels)

        logger.info(f"[SemanticRouter] Índice: {len(all_prompts)} prompts de referência")

    def route(self, query: str, threshold: float = 0.75) -> tuple[str, float]:
        if not SEMANTIC_ROUTER_AVAILABLE or self.index is None:
            return ("unknown", 0.0)

        query_vec = self.embedder.encode(
            [query], normalize_embeddings=True
        ).astype("float32")

        similarities, indices = self.index.search(query_vec, k=3)

        best_score = float(similarities[0][0])
        best_tier = self.labels[indices[0][0]]

        if best_score >= threshold:
            return (best_tier, best_score)

        return ("unknown", best_score)