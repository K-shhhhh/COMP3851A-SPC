# AI extension point: split extracted text into retrievable chunks.
# Owner: Krish
#
# Ported unchanged from rag_pipeline.ipynb.

import re
from typing import List, Dict

import nltk


def chunk_text(text: str, chunk_size_words: int = 350, overlap_words: int = 60) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

    units = []
    for para in paragraphs:
        sentences = nltk.sent_tokenize(para)
        units.extend([s.strip() for s in sentences if s.strip()])

    chunks = []
    current_words = []
    for unit in units:
        unit_words = unit.split()
        if len(current_words) + len(unit_words) > chunk_size_words and current_words:
            chunks.append(" ".join(current_words))
            current_words = current_words[-overlap_words:] if overlap_words else []
        current_words.extend(unit_words)
    if current_words:
        chunks.append(" ".join(current_words))
    return chunks


def chunk_documents(pages: List[Dict], chunk_size_words: int = 350, overlap_words: int = 60) -> List[Dict]:
    all_chunks = []
    chunk_id = 0
    for page in pages:
        page_chunks = chunk_text(page["content"], chunk_size_words, overlap_words)
        for c in page_chunks:
            all_chunks.append({
                "chunk_id": chunk_id,
                "text": c,
                "source_page": page["page_num"],
                "source_type": page.get("type", "text"),
                "word_count": len(c.split())
            })
            chunk_id += 1
    return all_chunks
