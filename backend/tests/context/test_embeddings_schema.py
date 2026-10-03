from app.context.embeddings import EMBEDDING_DIMENSIONS, EmbedTask
from app.context.models import DuplicateCandidate, KbChunk
from app.modules.activities.models import Activity


def test_embed_tasks_are_the_gemini_task_types() -> None:
    assert EmbedTask.DOCUMENT == "RETRIEVAL_DOCUMENT"
    assert EmbedTask.QUERY == "RETRIEVAL_QUERY"


def test_vector_columns_are_bound_to_the_dimension_constant() -> None:
    assert Activity.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS
    assert KbChunk.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS


def test_hnsw_indexes_use_cosine_ops() -> None:
    indexes = {
        ix.name: ix
        for ix in [*Activity.__table__.indexes, *KbChunk.__table__.indexes]
        if ix.name and ix.name.endswith("_embedding_hnsw")
    }
    assert set(indexes) == {"ix_activities_embedding_hnsw", "ix_kb_chunks_embedding_hnsw"}
    for ix in indexes.values():
        options = ix.dialect_options["postgresql"]
        assert options["using"] == "hnsw"
        assert options["ops"] == {"embedding": "vector_cosine_ops"}


def test_kb_has_no_owner_columns() -> None:
    # KB documents are company-wide reference material, not user-owned rows (CLAUDE §2.4).
    assert "owner_id" not in KbChunk.__table__.c
    assert "team_id" not in KbChunk.__table__.c


def test_duplicate_candidates_are_owner_scoped() -> None:
    assert "owner_id" in DuplicateCandidate.__table__.c
    assert "team_id" in DuplicateCandidate.__table__.c
