# synapse

Agent generated with `agents-cli` version `0.5.0`

## Project Structure

```
synapse/
├── app/         # Core agent logic (deployed to Reasoning Engine)
│   ├── agent.py               
│   └── app_utils/             
├── webhook_handler/    # Cloud Run service for Telegram webhooks
├── tests/                     # Unit, integration, and load tests
├── GEMINI.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

## Deployment

The agent logic is deployed to **Vertex AI Agent Runtime (Reasoning Engine)**. Telegram webhooks are handled by a dedicated Cloud Run service in `webhook_handler/`.

### Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli deploy`  | Deploy agent to Vertex AI Agent Runtime                                                     |
| `gcloud run deploy`  | Deploy Telegram webhook handler (from `webhook_handler/`)                                    |

