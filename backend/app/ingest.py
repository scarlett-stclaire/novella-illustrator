"""Story ingestion from PDF uploads and URLs (F7, F8).

Both extractors raise ValueError with a user-facing message on failure
(unreadable PDF, unreachable URL, empty result) so routes.py can surface a
clear error rather than a stack trace - "handle extraction failures with a
clear message and a way to retry or change the source" per spec 5.2.
"""

import io

import httpx
import trafilatura
from pypdf import PdfReader
from pypdf.errors import PdfReadError

URL_FETCH_TIMEOUT_SECONDS = 20


def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError as exc:
        raise ValueError(f"Could not read this PDF: {exc}") from exc

    if reader.is_encrypted:
        raise ValueError("This PDF is password-protected and can't be read.")

    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p.strip() for p in pages if p.strip())

    if not text.strip():
        raise ValueError(
            "No extractable text found in this PDF - it may be a scanned "
            "image with no text layer."
        )
    return text


async def extract_url_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=URL_FETCH_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = await client.get(
                url, headers={"User-Agent": "Mozilla/5.0 (NovellaIllustrator)"}
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Could not fetch {url}: {exc}") from exc

    text = trafilatura.extract(
        response.text, url=url, favor_recall=True, include_tables=False
    )
    if not text or not text.strip():
        raise ValueError(f"Could not extract article text from {url}")
    return text.strip()


async def extract_urls_text(urls: list[str]) -> tuple[str, list[dict]]:
    """Fetches every URL independently; a failure on one doesn't block the
    others. Returns (combined_text, per_url_results) so the caller can show
    exactly which sources succeeded."""
    results = []
    texts = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            text = await extract_url_text(url)
            texts.append(text)
            results.append({"url": url, "ok": True, "error": None})
        except ValueError as exc:
            results.append({"url": url, "ok": False, "error": str(exc)})

    if not texts:
        raise ValueError("None of the given URLs could be read.")

    return "\n\n".join(texts), results
