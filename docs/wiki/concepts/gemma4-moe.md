# Gemma 4 26B MoE (Mixture of Experts)

**Last Updated:** 2026-04-04

## What It Is
Google's Gemma 4 includes a 26B parameter Mixture of Experts model with only 3.8B active parameters per inference pass. This means:
- Total model size: 26B parameters (stored in VRAM)
- Active computation per token: only 3.8B parameters
- Result: Near-7B-model speed with much higher quality output

## Why It Matters for Sovereign Node
- **Fits on a single RTX 3090** (24GB VRAM) with room to spare
- **Fast inference** due to only 3.8B active params per forward pass
- **Quality punches above its weight** - MoE architecture routes each token to the most relevant expert subnetworks

## Swarm Architecture Fit
With 3x RTX 3090s, Gemma 4 26B MoE enables:
- **GPU 0:** Gemma 4 as the "cognitive core" (always-on, fast responses)
- **GPU 1-2:** Load a 70B model for complex tasks on demand
- OR: **3x independent Gemma 4 instances** for parallel agent swarm

This maps directly to Karpathy's cognitive core vision - a small, fast, always-on model handling routine tasks while larger models are called in for heavy lifting.

## MoE Explained Simply
Traditional models: every parameter participates in every token generation.
MoE models: tokens are routed to specialized "expert" subnetworks. Only a fraction of total parameters fire per token. This gives you a larger model's knowledge in a smaller model's compute budget.

## Discovery Context
User found this during the build process. It was an immediate fit for the multi-GPU architecture we were already designing.
