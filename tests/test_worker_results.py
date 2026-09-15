import pytest
from pydantic import ValidationError

from research_agent.schemas import WorkerResult


def result_data() -> dict[str, object]:
    return {
        "worker_id": "worker-1",
        "assignment": {
            "worker_id": "worker-1",
            "focused_task": "Assess adoption",
            "investigation_focus": "Investigate current adoption evidence",
            "evidence_to_find": ["Recent surveys"],
        },
        "claims": [
            {
                "claim": "Adoption increased.",
                "evidence": [{"source_id": "source-1", "evidence": "Survey reported growth."}],
            }
        ],
        "sources": [
            {
                "source_id": "source-1",
                "title": "Survey",
                "url": "https://example.com/survey",
                "snippet": "Survey reported growth.",
                "publisher": "Example Research",
            }
        ],
        "uncertainties": ["The survey sample may not represent every industry."],
    }


def test_grounded_worker_result_is_valid() -> None:
    assert WorkerResult.model_validate(result_data()).worker_id == "worker-1"


@pytest.mark.parametrize(
    ("quoted", "expected"),
    [
        ('"Survey reported growth."', "Survey reported growth."),
        ("'Survey reported growth.'", "Survey reported growth."),
        ("“Survey reported growth.”", "Survey reported growth."),
        ("‘Survey reported growth.’", "Survey reported growth."),
    ],
)
def test_matching_outer_quotes_are_removed_before_validation(
    quoted: str,
    expected: str,
) -> None:
    data = result_data()
    data["claims"] = [
        {
            "claim": "Adoption increased.",
            "evidence": [{"source_id": "source-1", "evidence": quoted}],
        }
    ]

    result = WorkerResult.model_validate(data)

    assert result.claims[0].evidence[0].evidence == expected


def test_internal_quotation_marks_are_preserved() -> None:
    data = result_data()
    excerpt = 'Survey reported "strong" growth.'
    data["sources"][0]["snippet"] = excerpt
    data["claims"] = [
        {
            "claim": "Adoption increased.",
            "evidence": [{"source_id": "source-1", "evidence": f'"{excerpt}"'}],
        }
    ]

    result = WorkerResult.model_validate(data)

    assert result.claims[0].evidence[0].evidence == excerpt


def test_claim_without_evidence_is_rejected() -> None:
    data = result_data()
    data["claims"] = [{"claim": "Unsupported claim", "evidence": []}]

    with pytest.raises(ValidationError):
        WorkerResult.model_validate(data)


def test_unknown_evidence_source_is_rejected() -> None:
    data = result_data()
    data["claims"] = [
        {
            "claim": "Claim",
            "evidence": [{"source_id": "source-unknown", "evidence": "Unsupported evidence"}],
        }
    ]

    with pytest.raises(ValidationError, match="unknown sources"):
        WorkerResult.model_validate(data)


def test_evidence_not_present_in_source_is_rejected() -> None:
    data = result_data()
    data["claims"] = [
        {
            "claim": "Claim",
            "evidence": [{"source_id": "source-1", "evidence": "A fact absent from the source"}],
        }
    ]

    with pytest.raises(ValidationError, match="excerpt from the referenced source"):
        WorkerResult.model_validate(data)


def test_quoted_paraphrased_evidence_is_rejected() -> None:
    data = result_data()
    data["claims"] = [
        {
            "claim": "Claim",
            "evidence": [{"source_id": "source-1", "evidence": '"The survey showed gains."'}],
        }
    ]

    with pytest.raises(ValidationError, match="excerpt from the referenced source"):
        WorkerResult.model_validate(data)


def test_unmatched_outer_quote_is_not_removed() -> None:
    data = result_data()
    data["claims"] = [
        {
            "claim": "Claim",
            "evidence": [{"source_id": "source-1", "evidence": '"Survey reported growth.'}],
        }
    ]

    with pytest.raises(ValidationError, match="excerpt from the referenced source"):
        WorkerResult.model_validate(data)


def test_duplicate_source_ids_remain_rejected() -> None:
    data = result_data()
    duplicate = dict(data["sources"][0])
    duplicate["url"] = "https://example.com/another-survey"
    data["sources"] = [data["sources"][0], duplicate]

    with pytest.raises(ValidationError, match="source IDs must be unique"):
        WorkerResult.model_validate(data)


def test_duplicate_source_urls_remain_rejected() -> None:
    data = result_data()
    duplicate = dict(data["sources"][0])
    duplicate["source_id"] = "source-2"
    data["sources"] = [data["sources"][0], duplicate]

    with pytest.raises(ValidationError, match="source URLs must be unique"):
        WorkerResult.model_validate(data)


def test_worker_id_must_match_assignment() -> None:
    data = result_data()
    data["worker_id"] = "worker-changed"

    with pytest.raises(ValidationError, match="worker_id must match"):
        WorkerResult.model_validate(data)
