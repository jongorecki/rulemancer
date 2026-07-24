# Tests for content-derived ruling_id() (docs/DECISIONS.md 2026-07-24
# "Positional ruling cache corrupted by the Scryfall merge; purged").
#
# ruling_id() used to be positional (oracle_id#index): a position in a list
# owned by an external data source. When the Scryfall local-bulk merge
# reordered a card's rulings, cached embeddings stayed bolted to indices
# whose text had moved -- 92% of the ruling_emb cache went stale silently.
# This file locks in the durable fix: ruling_id() is now a hash of the
# ruling TEXT, so reordering the rulings list can't move an id, and cached
# embeddings can never point at the wrong text.

import hashlib

import numpy as np

from rulesagent.cache import KVCache
from rulesagent.contracts import Card
from rulesagent.tools import ruling_retrieval
from rulesagent.tools.ruling_retrieval import ruling_id


def make_card(oracle_id: str = "card-oracle-id", rulings: list[str] | None = None) -> Card:
    return Card(
        name="Test Card",
        oracle_text="Test oracle text.",
        type_line="Instant",
        mana_cost="{U}",
        oracle_id=oracle_id,
        rulings=rulings or [],
    )


def _fake_vec(text: str) -> np.ndarray:
    """Deterministic, text-keyed stand-in for a real embedding -- same text
    always yields the same vector, different text yields a different one, no
    network call."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = np.frombuffer(digest, dtype=np.uint8).astype(np.float32)
    return vec / np.linalg.norm(vec)


def fake_embed_documents(texts: list[str], model: str) -> np.ndarray:
    return np.stack([_fake_vec(t) for t in texts])


def test_ruling_id_survives_reordering():
    """The regression that defines the fix: the same set of rulings in a
    different order must produce the same set of ids, each still mapped to
    its own text. Under the old oracle_id#index scheme this fails, because
    the id at a given position changes meaning when the list is reordered."""
    rulings_forward = [
        "This ability triggers only once per turn.",
        "You may respond to this trigger with an instant.",
        "The token created is not legendary.",
    ]
    card_forward = make_card(oracle_id="abc-123", rulings=rulings_forward)
    ids_forward = {ruling_id(card_forward, i): text for i, text in enumerate(rulings_forward)}

    rulings_shuffled = [rulings_forward[2], rulings_forward[0], rulings_forward[1]]
    card_shuffled = make_card(oracle_id="abc-123", rulings=rulings_shuffled)
    ids_shuffled = {ruling_id(card_shuffled, i): text for i, text in enumerate(rulings_shuffled)}

    assert set(ids_forward) == set(ids_shuffled)
    for rid, text in ids_forward.items():
        assert ids_shuffled[rid] == text


def test_ruling_id_changes_when_ruling_text_changes():
    card_original = make_card(rulings=["The trigger happens on upkeep."])
    card_edited = make_card(rulings=["The trigger happens on upkeep, not end step."])

    assert ruling_id(card_original, 0) != ruling_id(card_edited, 0)


def test_ruling_id_strips_leading_and_trailing_whitespace_only():
    card_padded = make_card(rulings=["  Some ruling text.  "])
    card_clean = make_card(rulings=["Some ruling text."])

    assert ruling_id(card_padded, 0) == ruling_id(card_clean, 0)


def test_ruling_id_is_case_sensitive():
    """Two rulings differing only in case ARE different text and must get
    different ids -- no lowercasing normalization."""
    card_lower = make_card(rulings=["some ruling text."])
    card_upper = make_card(rulings=["Some Ruling Text."])

    assert ruling_id(card_lower, 0) != ruling_id(card_upper, 0)


def test_ruling_id_format_is_oracle_id_hash_prefix_plus_12_hex_chars():
    card = make_card(oracle_id="abc-123", rulings=["Some ruling text."])

    rid = ruling_id(card, 0)
    prefix, sep, suffix = rid.partition("#")

    assert prefix == "abc-123"
    assert sep == "#"
    assert len(suffix) == 12
    assert all(c in "0123456789abcdef" for c in suffix)
    expected = hashlib.sha256("Some ruling text.".encode("utf-8")).hexdigest()[:12]
    assert suffix == expected


def test_card_ruling_embeddings_correspond_to_own_text_after_reorder(tmp_path, monkeypatch):
    """Cache integrity across a reorder: _card_ruling_embeddings() on a card,
    then on the same card with rulings reordered, must return embeddings
    where row i always matches card.rulings[i] -- never a stale vector from
    the old index. Uses a deterministic fake embedder (no network)."""
    monkeypatch.setattr(ruling_retrieval, "_cache", KVCache("ruling_emb", db_path=tmp_path / "cache.db"))
    monkeypatch.setattr(ruling_retrieval, "embed_documents", fake_embed_documents)

    rulings = [
        "Alpha: this happens first.",
        "Beta: this happens second.",
        "Gamma: this happens third.",
    ]
    card = make_card(oracle_id="xyz-789", rulings=rulings)
    embs = ruling_retrieval._card_ruling_embeddings(card)
    for i, text in enumerate(rulings):
        assert np.allclose(embs[i], _fake_vec(text))

    rulings_reordered = [rulings[2], rulings[0], rulings[1]]
    card_reordered = make_card(oracle_id="xyz-789", rulings=rulings_reordered)
    embs_reordered = ruling_retrieval._card_ruling_embeddings(card_reordered)
    for i, text in enumerate(rulings_reordered):
        assert np.allclose(embs_reordered[i], _fake_vec(text))
