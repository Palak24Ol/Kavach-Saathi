from __future__ import annotations

import time
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from kavach_saathi.agents.review import _CLIP_RELEVANT_THRESHOLD
from kavach_saathi.db.base import SessionLocal
from kavach_saathi.db.models import Product, Review
from kavach_saathi.providers.review_vision import ReviewRelevanceClassifier

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE = 24

# Same decision rule as Agent 4's live single-review path (agents/review.py's
# ReviewFilterAgent.run): media relevance is judged solely by CLIP, so a review's
# text is never hidden here either, only its photo. BERT is deliberately NOT computed
# in this script -- the live agent never uses its score to decide hiding either, so
# running it here would just be discarded work, not a source of extra accuracy.
# Batching multiple (image, text) pairs into one CLIP forward pass (see
# ReviewRelevanceClassifier.clip_batch_similarity) doesn't change any individual
# pair's score, it only amortizes fixed per-call overhead across many reviews.


def main() -> None:
    classifier = ReviewRelevanceClassifier()
    started = time.perf_counter()
    with SessionLocal() as session:
        reviews = session.execute(select(Review).where(Review.media.is_not(None))).scalars().all()
        total = len(reviews)
        print(f"Classifying {total} reviews with photos in batches of {BATCH_SIZE} (CLIP only)...", flush=True)
        flagged = 0
        product_cache: dict[str, Product] = {}
        for batch_start in range(0, total, BATCH_SIZE):
            batch = reviews[batch_start : batch_start + BATCH_SIZE]
            pairs: list[tuple[Image.Image, str]] = []
            for review in batch:
                product = product_cache.get(review.product_id)
                if product is None:
                    product = session.get(Product, review.product_id)
                    product_cache[review.product_id] = product
                image = Image.open(ROOT / review.media).convert("RGB")
                pairs.append((image, f"{product.title}, {product.category}"))

            scores = classifier.clip_batch_similarity(pairs)
            for review, clip_score in zip(batch, scores):
                if clip_score < _CLIP_RELEVANT_THRESHOLD:
                    review.is_hidden_by_agent = True
                    review.hide_reason = (
                        "Review media is unrelated and will be hidden; written review remains visible."
                    )
                    flagged += 1

            session.commit()
            done = batch_start + len(batch)
            elapsed = time.perf_counter() - started
            print(f"  {done}/{total} done ({elapsed:.0f}s elapsed, {flagged} flagged so far)", flush=True)

    elapsed = time.perf_counter() - started
    print(f"Done: {total} reviews classified in {elapsed:.0f}s, {flagged} flagged and hidden.", flush=True)


if __name__ == "__main__":
    main()
