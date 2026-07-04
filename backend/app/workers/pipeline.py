"""
Celery canvas wiring for the per-video processing pipeline.

Full chain (Phases 1b–1d):
  fetch_captions
    → chord(
        [summary, thesis, entities, topics, sentiment, quotes, key_numbers, insights],
        mark_analysis_complete        ← fires after all 8 complete
      )
      → chunk_and_embed              ← enqueued by mark_analysis_complete
        → mark_indexed               ← enqueued by chunk_and_embed
"""

from app.core.logging import get_logger

logger = get_logger(__name__)


def build_analysis_chord(video_id: int):
    """
    Return a Celery chord that fans out 8 analysis tasks in parallel,
    then calls mark_analysis_complete.
    """
    from celery import chord, group
    from app.workers.tasks import analysis_tasks as at

    return chord(
        group(
            at.generate_executive_summary.si(video_id).set(queue="analysis"),
            at.extract_investment_thesis.si(video_id).set(queue="analysis"),
            at.extract_companies_and_tickers.si(video_id).set(queue="analysis"),
            at.classify_topics.si(video_id).set(queue="analysis"),
            at.score_sentiment.si(video_id).set(queue="analysis"),
            at.extract_quotes.si(video_id).set(queue="analysis"),
            at.extract_key_numbers.si(video_id).set(queue="analysis"),
            at.generate_actionable_insights.si(video_id).set(queue="analysis"),
        ),
        at.mark_analysis_complete.s(video_id).set(queue="analysis"),
    )


def build_full_pipeline(video_id: int):
    """
    Return the complete pipeline signature:
      transcript → analysis chord → (embedding enqueued by chord callback)
    """
    from celery import chain
    from app.workers.tasks.transcript_tasks import fetch_captions

    return chain(
        fetch_captions.si(video_id).set(queue="transcription"),
        build_analysis_chord(video_id),
    )


def enqueue_pipeline_from(video_id: int, stage: str) -> str:
    """
    Enqueue the pipeline starting from `stage`. Returns the Celery task ID.

    Supported stages:
    - TRANSCRIPT_PENDING  → transcript → analysis → embedding
    - ANALYSIS_PENDING    → analysis chord → embedding
    - EMBEDDING_PENDING   → embedding only
    """
    if stage in ("TRANSCRIPT_PENDING", "DISCOVERED"):
        sig = build_full_pipeline(video_id)
        result = sig.apply_async()
        logger.info("Pipeline enqueued from transcript", extra={"video_id": video_id, "task_id": result.id})
        return result.id

    if stage == "ANALYSIS_PENDING":
        sig = build_analysis_chord(video_id)
        result = sig.apply_async()
        logger.info("Pipeline enqueued from analysis", extra={"video_id": video_id, "task_id": result.id})
        return result.id

    if stage == "EMBEDDING_PENDING":
        from app.workers.tasks.embedding_tasks import chunk_and_embed
        result = chunk_and_embed.apply_async(args=[video_id], queue="embedding")
        logger.info("Pipeline enqueued from embedding", extra={"video_id": video_id, "task_id": result.id})
        return result.id

    logger.warning("Unknown pipeline stage", extra={"video_id": video_id, "stage": stage})
    return ""
