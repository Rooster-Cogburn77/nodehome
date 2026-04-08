# Karpathy Research Dossier

**Last Updated:** 2026-04-04
**Relevance:** Direct - his tools and philosophy align exactly with Sovereign Node's purpose

## Most Relevant to Sovereign Node

### AutoResearch (March 2026) - NEWEST REPO
- 65K stars, updated March 26, 2026
- AI agents automatically run nanochat training research on a **single GPU**
- One markdown prompt + 630 lines of training code = 700 experiments in 2 days, discovering 20 optimizations
- Core idea: "you're programming the program.md Markdown files that provide context to the AI agents"
- **Sovereign Node fit:** 3x 3090s = 3 parallel autoresearch streams

### The "Cognitive Core" Concept
- A few-billion-parameter model living always-on by default on every computer
- Natively multimodal text/vision/audio at input and output
- Matryoshka-style architecture (dial capability up/down at runtime)
- Reasoning with a dial (system 2)
- On-device finetuning via LoRA slots for personalization
- Key quote: "What LLM personal computing lacks in broad world knowledge it makes up in super low interaction latency, direct/private access to data and state, offline continuity, and sovereignty."

### LLM Knowledge Base Workflow (Obsidian Wiki)
- `/raw` directory for source materials (articles, papers, repos, images)
- `wiki/` directory of compiled `.md` files maintained by the LLM
- **Obsidian** as reading/viewing layer + Web Clipper extension
- LLM writes and maintains all wiki data - rarely touched directly
- At ~100 articles / 400K words, complex queries work without fancy RAG
- LLM auto-maintains index files and reads relevant docs
- Outputs: markdown files, slideshows (Marp format), matplotlib images
- "Health checks" find inconsistent data, impute missing data, surface candidates for new articles
- **Feedback loop:** useful query answers get written back as new wiki entries
- Future: synthetic data + fine-tuning so LLM internalizes domain knowledge in weights
- Limitation: "This workflow doesn't work at a million documents. But for a focused research domain? You probably don't need a million documents."

### Nanochat ("The $100 ChatGPT") - 51K stars
- Single codebase: tokenization, pretraining, finetuning, eval, inference, chat UI
- Train GPT-2-class model for ~$92 on 8xH100 in ~4 hours
- Complexity dial: `--depth` (number of transformer layers)
- Not a framework - no config objects, model factories, or if-then-else monsters

### "Agentic Engineering" (Feb 2026)
- Karpathy's proposed term to differentiate from "vibe coding"
- "You are not writing the code directly 99% of the time, you are orchestrating agents who do and acting as oversight."

## Full GitHub Repo Inventory (Top 30 by Stars/Recency)

| Repo | Stars | Description |
|------|-------|-------------|
| autoresearch | 65K | AI agents running single-GPU research autonomously |
| nanoGPT | 56K | Train/finetune medium GPTs |
| nanochat | 51K | Full ChatGPT training pipeline, minimal |
| LLM101n | 37K | "Build a Storyteller" (archived) |
| llm.c | 29K | LLM training in raw C/CUDA |
| minGPT | 24K | PyTorch reimplementation of GPT training |
| nn-zero-to-hero | 21K | Neural Networks: Zero to Hero course |
| llama2.c | 19K | Llama 2 inference in one C file |
| llm-council | 17K | Multiple LLMs collaborate on hard questions |
| micrograd | 15K | Tiny autograd engine |
| char-rnn | 12K | Multi-layer RNNs in Torch |
| convnetjs | 11K | Deep Learning in Javascript |
| minbpe | 10K | Minimal BPE algorithm |
| reader3 | 3.4K | Reading books together with LLMs |
| rendergit | 2.1K | Render git repos to static HTML for LLMs |
| jobs | 1.3K | BLS occupation AI exposure scoring |

## AI Exposure / Jobs Research (March 2026)
- Scored 342 occupations on AI exposure (0-10)
- Overall weighted score: 4.9
- >$100K jobs scored worst (6.7), <$35K scored lowest exposure (3.4)
- Medical transcriptionists: 10/10
- Software developers: 8-9
- Construction/trades: 1
- He pulled the data shortly after posting

## microGPT (Feb 2026)
- 200 lines of pure Python, no dependencies
- Contains: dataset, tokenizer, autograd engine, GPT-2 architecture, Adam optimizer, training loop, inference loop

## Key Stance: Open Source + Local
- Entire body of work oriented around making AI accessible, minimal, runnable without cloud
- Advocates for open-weight models
- "Cognitive core" explicitly envisions local models as default, cloud as supplementary
