from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncio
import time

app = FastAPI(title="UltraQuest API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Cadeia de Ranks: índice 0 = mais baixo, 7 = mais alto
# ---------------------------------------------------------------------------
RANKS = [
    {"nome": "DESTRUCTIVE",  "multiplicador": 1.0, "tempo_limite": None},   # 0
    {"nome": "CHAOTIC",      "multiplicador": 1.2, "tempo_limite": 7200},   # 1
    {"nome": "BRUTAL",       "multiplicador": 1.5, "tempo_limite": 7200},   # 2
    {"nome": "ANARCHIC",     "multiplicador": 2.0, "tempo_limite": 5400},   # 3
    {"nome": "SUPREME",      "multiplicador": 2.5, "tempo_limite": 3600},   # 4
    {"nome": "SSADISTIC",    "multiplicador": 3.0, "tempo_limite": 2700},   # 5
    {"nome": "SSSHITSTORM",  "multiplicador": 4.0, "tempo_limite": 1800},   # 6
    {"nome": "ULTRAKILL",    "multiplicador": 5.0, "tempo_limite": 900},    # 7
]

# ---------------------------------------------------------------------------
# Estado global do jogador (in-memory)
# ---------------------------------------------------------------------------
ESTADO_JOGADOR: dict = {
    "rank_index": 0,
    "pontos_totais": 0,
    "ultima_atividade": time.time(),
}


def _estado_publico() -> dict:
    idx = ESTADO_JOGADOR["rank_index"]
    rank = RANKS[idx]
    tempo_restante = None
    if rank["tempo_limite"] is not None:
        elapsed = time.time() - ESTADO_JOGADOR["ultima_atividade"]
        tempo_restante = round(max(0.0, rank["tempo_limite"] - elapsed), 1)
    return {
        "rank": rank["nome"],
        "multiplicador": rank["multiplicador"],
        "pontos_totais": ESTADO_JOGADOR["pontos_totais"],
        "rank_index": idx,
        "tempo_restante": tempo_restante,
        "ultima_atividade": ESTADO_JOGADOR["ultima_atividade"],
    }


# ---------------------------------------------------------------------------
# Loop de decaimento em segundo plano (roda a cada 10 segundos)
# ---------------------------------------------------------------------------
async def _loop_decaimento():
    while True:
        await asyncio.sleep(10)
        idx = ESTADO_JOGADOR["rank_index"]
        if idx == 0:
            continue
        rank = RANKS[idx]
        if rank["tempo_limite"] is None:
            continue
        elapsed = time.time() - ESTADO_JOGADOR["ultima_atividade"]
        if elapsed > rank["tempo_limite"]:
            ESTADO_JOGADOR["rank_index"] = max(0, idx - 1)
            ESTADO_JOGADOR["ultima_atividade"] = time.time()
            print(
                f"[DECAY] Rank rebaixado para {RANKS[ESTADO_JOGADOR['rank_index']]['nome']} "
                f"(inatividade de {int(elapsed)}s)"
            )


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_loop_decaimento())
    print("[UltraQuest] Motor de decaimento iniciado.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/status", summary="Retorna o estado atual do jogador")
def get_status():
    return _estado_publico()


class TarefaPayload(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=120)
    prazo: int = Field(..., ge=1, le=3)
    importancia: int = Field(..., ge=1, le=3)
    dificuldade: int = Field(..., ge=1, le=3)


@app.post("/tarefas/concluir", summary="Conclui uma tarefa e aplica pontuação")
def concluir_tarefa(tarefa: TarefaPayload):
    idx = ESTADO_JOGADOR["rank_index"]
    multiplicador = RANKS[idx]["multiplicador"]

    pontos_base = (tarefa.prazo + tarefa.importancia) * tarefa.dificuldade
    pontos_finais = int(pontos_base * multiplicador)

    ESTADO_JOGADOR["pontos_totais"] += pontos_finais
    novo_idx = min(len(RANKS) - 1, idx + 1)
    ESTADO_JOGADOR["rank_index"] = novo_idx
    ESTADO_JOGADOR["ultima_atividade"] = time.time()

    print(
        f"[TASK] '{tarefa.titulo}' | base={pontos_base} x{multiplicador} = +{pontos_finais}pts "
        f"| rank {RANKS[idx]['nome']} -> {RANKS[novo_idx]['nome']}"
    )

    return {
        **_estado_publico(),
        "pontos_ganhos": pontos_finais,
        "titulo": tarefa.titulo,
        "rank_anterior": RANKS[idx]["nome"],
    }


@app.post("/status/reset", summary="Zera o progresso e volta ao rank base")
def reset_status():
    ESTADO_JOGADOR["rank_index"] = 0
    ESTADO_JOGADOR["pontos_totais"] = 0
    ESTADO_JOGADOR["ultima_atividade"] = time.time()
    print("[RESET] Estado do jogador zerado.")
    return _estado_publico()
