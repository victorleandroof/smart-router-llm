PYTHON := python3.12
VENV := .venv
REQUIREMENTS := requirements.txt

# Ativar o ambiente virtual
.venv:
	@echo "Criando ambiente virtual com Python 3.12..."
	$(PYTHON) -m venv $(VENV)

# Instalar dependências
install:
	@echo "Instalando dependências..."
	$(VENV)/bin/pip install -r $(REQUIREMENTS)

# Iniciar o Redis
redis:
	bash scripts/init_redis.sh

# Iniciar o Ollama
ollama:
	bash scripts/init_ollama.sh

# Pull do modelo Ollama
ollama-pull:
	bash scripts/pull_ollama_model.sh

# Iniciar o LiteLLM (via app/main.py, não via CLI `litellm` — só assim o
# middleware StripAnthropicBeta é registrado, ver docs/known-gotchas.md)
litellm:
	$(VENV)/bin/python app/main.py > ./litellm.log 2>&1 & echo "LiteLLM rodando em :4000"

# Sobe toda a infraestrutura (Redis, Ollama, LiteLLM)
up: redis ollama litellm

# Encerra todos os serviços
down:
	pkill -f "python app/main.py" || true
	pkill -f "redis-server" || true
	pkill -f "ollama serve" || true
	echo "Serviços parados."

# Acompanha os logs do proxy em tempo real
logs:
	tail -f litellm.log

# Valida a conectividade com os modelos do gateway
validate:
	$(VENV)/bin/python scripts/valida_modelos.py

# Limpa caches, logs e arquivos temporários
clean:
	rm -f litellm.log ollama.log redis.log dump.rdb
	rm -rf appendonlydir/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.PHONY: .venv install redis ollama ollama-pull litellm up down logs clean validate