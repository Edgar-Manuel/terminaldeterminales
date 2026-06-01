# Bridge Terminal

Una "terminal de terminales" inspirada en BridgeMind / BridgeSpace.
Ejecuta varios modelos de IA en paralelo (Ollama local, Groq, DeepSeek, OpenRouter, etc.) dentro de la misma TUI, con:

- 4 paneles de chat simultaneos (cada uno con su propio modelo y rol)
- Streaming token-a-token
- Memoria compartida en SQLite (los agentes se ven entre si)
- Kanban de tareas
- Shell sandboxed (los agentes pueden pedir ejecutar `sh ...`)
- Sistema de agentes con roles: builder, reviewer, tester, free

## Instalacion

```sh
cd bridge-terminal
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` y rellena las API keys que vayas a usar. Modelos soportados (mediante LiteLLM):

- `ollama/<modelo>` -> `ollama pull qwen2.5-coder:7b` (gratis, local)
- `groq/<modelo>` -> https://console.groq.com (tier gratuito)
- `deepseek/<modelo>` -> https://platform.deepseek.com (barato)
- `openrouter/<vendor>/<modelo>` -> https://openrouter.ai (tiene modelos `:free`)

## Configuracion

Edita `config.json` para definir tus 4 paneles. Cada panel tiene:

```json
{
  "id": "builder",
  "title": "Builder (DeepSeek)",
  "model": "deepseek/deepseek-chat",
  "role": "builder",
  "system_prompt": "..."
}
```

## Ejecutar

```sh
python run.py
```

## Atajos

| Tecla    | Accion |
|----------|--------|
| `Ctrl+B` | Foco en barra de broadcast (envia a todos) |
| `Ctrl+E` | Toggle auto-ejecucion de bloques `sh` |
| `Ctrl+K` | Cambiar a pestania Kanban |
| `Ctrl+S` | Cambiar a pestania Shell |
| `Ctrl+L` | Limpiar el panel enfocado |
| `Ctrl+Q` | Salir |
| `F1`     | Ayuda rapida |

En la barra de broadcast:

- `texto` -> se envia a los 4 agentes en paralelo
- `@builder texto` -> se envia solo al agente `builder`

## Memoria compartida

Cualquier agente puede dejar notas para los demas escribiendo en su respuesta:

```
MEMO[tag]: esto otro agente lo vera
```

Se guarda en `bridge.db` y se inyecta en el prompt de los demas en el siguiente turno.

## Ejecucion de shell

Si un agente responde con un bloque:

\`\`\`sh
ls -la
\`\`\`

- Con `auto-exec OFF` (default): se detecta pero no se ejecuta
- Con `auto-exec ON` (`Ctrl+E`): se ejecuta dentro de `./workspace`

Hay un filtro de patrones peligrosos (`rm -rf /`, fork bombs, `mkfs`, etc.) que bloquea esos comandos.

## Estructura

```
bridge-terminal/
  bridge_terminal/
    app.py                   # App principal Textual
    core/
      config.py              # carga config.json + .env
      models.py              # wrapper async sobre LiteLLM (stream/complete)
      memory.py              # SQLite: messages, notes, tasks
      shell.py               # runner sandboxed con streaming
      agents.py              # Agent = panel + role + memoria
    widgets/
      chat_panel.py          # chat con streaming + auto-exec
      kanban.py              # tablero Kanban
      shell_panel.py         # shell interactivo
  config.json
  requirements.txt
  .env.example
  run.py
```

## Roadmap sugerido

- [ ] Persistencia de mensajes al cerrar (ya guardados en SQLite, falta hidratar en UI)
- [ ] Subagentes spawneados desde un agente
- [ ] MCP server para que herramientas externas escriban a la memoria
- [ ] Voz (Whisper + TTS local)
- [ ] Multimodal (imagenes -> LLaVA / GPT-4o)
- [ ] Hasta 16 paneles (grid configurable)
