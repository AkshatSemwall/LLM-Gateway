"""
Mock LLM Provider Server — routes /openai, /anthropic, /ollama
Simulates real provider behavior including judge scoring, escalation triggers,
realistic latencies, and token counts so the full routing pipeline runs end-to-end.
"""
import asyncio
import random
import time
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock LLM Provider Server")

# Track calls to the judge so we can simulate a fail→escalate→pass scenario
_judge_call_count = 0

def _tier1_response(prompt: str) -> str:
    return (
        "Sure! Here's a quick answer:\n\n"
        f"The answer to your question about '{prompt[:60]}...' is straightforward. "
        "This is a simple lookup that requires minimal reasoning."
    )

def _tier2_response(prompt: str) -> str:
    return (
        "Great question. Let me break this down:\n\n"
        "**Analysis:**\n"
        "1. First, we need to understand the core concepts involved.\n"
        "2. The key factors here are: context, constraints, and trade-offs.\n"
        "3. Comparing the available options:\n"
        "   - Option A: Faster but less accurate\n"
        "   - Option B: More robust but requires more setup\n\n"
        "**Recommendation:** Based on your use case, Option B is preferable for production workloads."
    )

def _tier3_response(prompt: str) -> str:
    return (
        "# Advanced Architecture Response\n\n"
        "Here is a production-grade approach:\n\n"
        "```python\nimport asyncio\nfrom typing import AsyncGenerator\n\n"
        "class HighPerformancePipeline:\n"
        "    \"\"\"Async pipeline with backpressure and circuit-breaking.\"\"\"\n"
        "    \n"
        "    def __init__(self, concurrency: int = 10):\n"
        "        self.semaphore = asyncio.Semaphore(concurrency)\n"
        "        self._circuit_open = False\n"
        "    \n"
        "    async def process(self, items) -> AsyncGenerator:\n"
        "        async with self.semaphore:\n"
        "            for item in items:\n"
        "                yield await self._execute(item)\n"
        "```\n\n"
        "**Key Engineering Decisions:**\n"
        "- Semaphore-based concurrency control prevents thundering herd\n"
        "- Circuit breaker pattern isolates cascading failures\n"
        "- Async generators enable backpressure-aware streaming\n"
        "- WAL-mode SQLite provides safe concurrent read/write\n\n"
        "This pattern scales to 50k+ RPS on a single node."
    )

def _make_openai_response(content: str, prompt_tokens: int, completion_tokens: int) -> dict:
    return {
        "id": f"chatcmpl-{random.randbytes(8).hex()}",
        "object": "chat.completion",
        "model": "gpt-4o",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens}
    }

@app.post("/openai/v1/chat/completions")
async def openai_completions(request: Request):
    global _judge_call_count
    data = await request.json()
    model = data.get("model", "gpt-4o-mini")
    messages = data.get("messages", [])
    prompt_content = messages[0].get("content", "") if messages else ""

    # Detect if this is the judge evaluation prompt
    is_judge = "SYSTEM: You are an objective quality evaluator" in prompt_content

    if is_judge:
        _judge_call_count += 1
        await asyncio.sleep(random.uniform(0.3, 0.6))

        # First judge call fails (score 4.2) → triggers escalation
        # Subsequent calls pass (score 8.7)
        if _judge_call_count == 1:
            score, reasoning = 4.2, "The response lacks sufficient technical depth and misses key implementation details for this complexity level."
            verdict_label = "FAIL → escalation triggered"
        else:
            score, reasoning = 8.7, "The escalated response demonstrates strong technical mastery with production-grade code and clear architectural reasoning."
            verdict_label = "PASS"

        content = json.dumps({"score": score, "reasoning": reasoning})
        return JSONResponse(_make_openai_response(content, 180, 40))

    # Normal generation — vary response by model tier
    await asyncio.sleep(random.uniform(0.2, 0.5))
    if model == "gpt-4o":
        content = _tier3_response(prompt_content)
        p_tok, c_tok = random.randint(80, 120), random.randint(280, 380)
    else:
        content = _tier2_response(prompt_content)
        p_tok, c_tok = random.randint(40, 80), random.randint(120, 200)

    return JSONResponse(_make_openai_response(content, p_tok, c_tok))


@app.post("/anthropic/v1/messages")
async def anthropic_messages(request: Request):
    data = await request.json()
    model = data.get("model", "claude-haiku-3-5")
    messages = data.get("messages", [])
    prompt_content = messages[0].get("content", "") if messages else ""

    await asyncio.sleep(random.uniform(0.25, 0.55))
    content = _tier2_response(prompt_content)

    return JSONResponse({
        "id": f"msg_{random.randbytes(8).hex()}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": model,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": random.randint(40, 80), "output_tokens": random.randint(110, 190)}
    })


@app.post("/ollama/api/generate")
async def ollama_generate(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    await asyncio.sleep(random.uniform(0.1, 0.3))

    return JSONResponse({
        "model": data.get("model", "llama3.2:1b"),
        "response": _tier1_response(prompt),
        "done": True,
        "prompt_eval_count": random.randint(15, 35),
        "eval_count": random.randint(30, 60),
        "total_duration": int(random.uniform(0.15, 0.35) * 1e9)
    })


@app.get("/ollama/api/version")
async def ollama_version():
    return JSONResponse({"version": "0.3.12"})


@app.get("/health")
async def health():
    return {"status": "healthy", "mock": True}
