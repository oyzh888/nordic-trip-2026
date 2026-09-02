#!/usr/bin/env python3
"""Grounded web research via Gemini + Google Search (Foundry Gateway -> Vertex).

Usage: python3 gsearch.py <queries_file.json> <out_dir>
queries_file: {"slug": "question text", ...}
Writes <out_dir>/<slug>.md with answer + source URLs.
"""
import json
import sys
import pathlib
import concurrent.futures as cf

import requests
from google.oauth2.credentials import Credentials
from google import genai
from google.genai import types

TOKEN_FILE = "/sensei-fs-3/users/zouyang/.secrets/pluto-auth-token-steve-train.txt"


def client():
    token = open(TOKEN_FILE).read().strip()
    data = requests.get(
        "https://foundry-aws-pluto.adobe.io/iam/credentials/gcp",
        headers={"x-pluto-token": token},
        timeout=30,
    ).json()
    return genai.Client(
        vertexai=True,
        project=data["project_id"],
        location="global",
        credentials=Credentials(token=data["token"]),
    )


def ask(cl, question):
    r = cl.models.generate_content(
        model="gemini-2.5-pro",
        contents=question,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        ),
    )
    urls = []
    for c in r.candidates or []:
        gm = getattr(c, "grounding_metadata", None)
        for chunk in (getattr(gm, "grounding_chunks", None) or []) if gm else []:
            w = getattr(chunk, "web", None)
            if w and w.uri:
                urls.append(f"{getattr(w, 'title', '')} — {w.uri}")
    return r.text or "(empty)", sorted(set(urls))


def main():
    queries = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cl = client()

    def one(item):
        slug, q = item
        try:
            text, urls = ask(cl, q)
        except Exception as e:  # noqa: BLE001
            text, urls = f"ERROR: {type(e).__name__}: {e}", []
        body = f"# {slug}\n\n**Q:** {q}\n\n{text}\n\n## Sources\n" + "\n".join(
            f"- {u}" for u in urls
        )
        (out / f"{slug}.md").write_text(body)
        return slug, len(text), len(urls)

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for slug, n, nu in ex.map(one, queries.items()):
            print(f"{slug}: {n} chars, {nu} sources")


if __name__ == "__main__":
    main()
