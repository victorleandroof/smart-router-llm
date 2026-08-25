import importlib.resources
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

import typer

app = typer.Typer(help="Smart Router LLM Gateway — CLI de operação.")


def _read_modelfile():
    """Resolve ollama/Modelfile: checkout local (dev) > empacotado (pip install)."""
    repo_root_modelfile = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ollama", "Modelfile"
    )
    if os.path.isfile(repo_root_modelfile):
        with open(repo_root_modelfile) as f:
            return f.read()
    return importlib.resources.files("app").joinpath("data", "Modelfile").read_text()


@app.command()
def serve():
    """Sobe o proxy LiteLLM + SmartRouter (porta 4000). Requer Redis e Ollama já rodando."""
    from app.main import run

    run()


@app.command()
def check():
    """Verifica se Redis e Ollama estão acessíveis antes de subir o serve."""
    ok = True

    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    try:
        import redis as redis_lib

        redis_lib.Redis(host=redis_host, port=redis_port, socket_connect_timeout=3).ping()
        typer.echo(f"✅ Redis OK ({redis_host}:{redis_port})")
    except Exception as e:
        typer.echo(f"❌ Redis inacessível em {redis_host}:{redis_port} — {e}")
        ok = False

    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=3)
        typer.echo(f"✅ Ollama OK ({ollama_host})")
    except Exception as e:
        typer.echo(f"❌ Ollama inacessível em {ollama_host} — {e}")
        ok = False

    if not ok:
        raise typer.Exit(code=1)


@app.command("pull-models")
def pull_models():
    """Baixa os modelos Ollama necessários e cria o custom model 'smart-router'."""
    if shutil.which("ollama") is None:
        typer.echo("❌ comando `ollama` não encontrado no PATH. Instale o Ollama primeiro.")
        raise typer.Exit(code=1)

    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
    local_tier_model = os.environ.get("OLLAMA_LOCAL_TIER_MODEL", "qwen2.5:7b-instruct")

    for m in (model, local_tier_model):
        typer.echo(f"Pulling {m}...")
        subprocess.run(["ollama", "pull", m], check=True)

    modelfile_text = _read_modelfile()
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False) as f:
        f.write(modelfile_text)
        modelfile_path = f.name

    try:
        typer.echo("Creating custom model 'smart-router'...")
        subprocess.run(["ollama", "create", "smart-router", "-f", modelfile_path], check=True)
    finally:
        os.unlink(modelfile_path)

    typer.echo("Modelos prontos.")


@app.command()
def validate():
    """Testa conectividade e resposta de cada modelo configurado no gateway corporativo."""
    token = os.environ.get("LLM_GATEWAY_API_KEY")
    url = os.environ.get("LLM_GATEWAY_BASE_URL")
    if not token or not url:
        typer.echo("❌ LLM_GATEWAY_API_KEY / LLM_GATEWAY_BASE_URL não configurados.")
        raise typer.Exit(code=1)

    req = urllib.request.Request(f"{url}/models", headers={"Authorization": f"Bearer {token}"})
    try:
        data = json.loads(urllib.request.urlopen(req).read())["data"]
    except Exception as e:
        typer.echo(f"❌ Erro ao buscar modelos: {e}")
        raise typer.Exit(code=1)

    typer.echo(f"{len(data)} modelo(s) encontrado(s):\n")
    for m in data:
        mid = m["id"]
        body = json.dumps(
            {"model": mid, "max_tokens": 2, "messages": [{"role": "user", "content": "hi"}]}
        ).encode()
        r = urllib.request.Request(
            f"{url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(r)
            typer.echo(f"✅ {mid}")
        except urllib.error.HTTPError as e:
            typer.echo(f"❌ {mid} (HTTP {e.code})")
        except Exception as e:
            typer.echo(f"❌ {mid} (erro: {e})")


if __name__ == "__main__":
    app()
