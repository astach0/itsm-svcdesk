# ai-generated: 100% - captures one real OpenAI-compatible chat call with the Lab 3 GenAI instrumentation
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI
from opentelemetry import trace
from opentelemetry.exporter.otlp.json.file import FileSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor

OUT = Path("spans.json")
DIFF = Path("DIFF.md")
SPEC_REF = "semantic-conventions-genai@e57c543b4889619eb2a05702471937db5119165d"

# Keys in the selected GenAI registry; all are marked development in that snapshot.
KNOWN = {
    "gen_ai.operation.name": "development",
    "gen_ai.provider.name": "development",
    "gen_ai.request.model": "development",
    "gen_ai.request.max_tokens": "development",
    "gen_ai.request.temperature": "development",
    "gen_ai.request.choice.count": "development",
    "gen_ai.response.id": "development",
    "gen_ai.response.model": "development",
    "gen_ai.response.finish_reasons": "development",
    "gen_ai.usage.input_tokens": "development",
    "gen_ai.usage.output_tokens": "development",
}


def otlp_genai_keys(path: Path) -> set[str]:
    found: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        document = json.loads(raw)
        for resource_span in document.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    for attribute in span.get("attributes", []):
                        key = attribute.get("key", "")
                        if key.startswith("gen_ai."):
                            found.add(key)
    return found


def main() -> None:
    base_url = os.environ.get("OPENAI_BASE_URL", "http://host.docker.internal:11434/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "ollama")
    model = os.environ.get("GENAI_MODEL", "qwen2.5:0.5b")
    if OUT.exists():
        OUT.unlink()

    provider = TracerProvider(resource=Resource.create({"service.name": "lab3-genai-diff"}))
    provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter(str(OUT))))
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument()

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=180.0)
    try:
        result = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Reply with exactly: GENAI_TRACE_OK"},
            ],
            temperature=0,
            max_tokens=24,
        )
        text = result.choices[0].message.content or ""
        print(f"Instrumented one chat completion using model {model!r}; response length={len(text)} chars.")
    finally:
        provider.force_flush()
        provider.shutdown()
        client.close()

    if not OUT.exists() or OUT.stat().st_size == 0:
        raise RuntimeError("The exporter produced no spans.json. Check the OpenAI-compatible endpoint.")
    emitted = otlp_genai_keys(OUT)
    if not emitted:
        raise RuntimeError("The captured spans contain no gen_ai.* attributes; refusing to write a false diff.")

    # Include every observed GenAI attribute. For observed keys outside this registry snapshot, declare in_spec=false.
    rows: list[tuple[str, bool, bool, str | None]] = []
    for name in sorted(emitted):
        if name in KNOWN:
            rows.append((name, True, True, KNOWN[name]))
        else:
            rows.append((name, True, False, None))
    # At least five declared attributes are required. Add known-but-not-emitted entries without claiming emission.
    for name in sorted(KNOWN):
        if len(rows) >= 5:
            break
        if name not in emitted:
            rows.append((name, False, True, KNOWN[name]))
    # Keep at least five rows while retaining all emitted keys.
    for name in sorted(KNOWN):
        if len(rows) >= 5:
            break
        if all(existing[0] != name for existing in rows):
            rows.append((name, False, True, KNOWN[name]))

    header = [
        "---",
        "lab3_genai_diff:",
        '  instrumentation: "opentelemetry-instrumentation-genai-openai==1.2b0; openai==3.19.2; opentelemetry-sdk==1.45.0; opentelemetry-exporter-otlp-json-file==0.66b0"',
        f'  spec_ref: "{SPEC_REF}"',
        "  attributes:",
    ]
    for name, is_emitted, in_spec, stability in rows:
        line = f"    - name: {name}\n      emitted: {'true' if is_emitted else 'false'}\n      in_spec: {'true' if in_spec else 'false'}"
        if in_spec and stability:
            line += f"\n      stability: {stability}"
        header.append(line)
    header.append("---")
    header.append("<!-- ai-generated: 100% - generated from the captured OpenTelemetry GenAI span keys and the selected registry snapshot -->")
    header.extend([
        "",
        "# What the library emits, against the spec",
        "",
        "The capture was produced by one non-streaming chat-completions request through the OpenAI Python SDK with `OpenAIInstrumentor` enabled. The OTLP JSON exporter wrote the span data to `genai/spans.json`; the attribute declarations above were generated by reading that file, so all `emitted: true` names correspond to captured `gen_ai.*` keys.",
        "",
        "The registry comparison uses the exact GenAI semantic-conventions snapshot named in the front matter. Attributes with `emitted: false` are defined by that snapshot but were not present in this particular call. Attributes emitted by the library that are absent from the selected registry snapshot are declared `in_spec: false`, rather than being silently treated as standardized.",
        "",
        "For a dashboard, prefer low-cardinality attributes such as operation, provider, model, and token counts. Do not use prompt or completion text as labels: content is high-cardinality and may contain sensitive user data.",
        "",
    ])
    DIFF.write_text("\n".join(header), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes) and {DIFF}.")
    print("Captured gen_ai.* keys:")
    for key in sorted(emitted):
        print(f"  {key}")


if __name__ == "__main__":
    main()