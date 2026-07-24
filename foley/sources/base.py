"""The bulk-corpus source contract — a downloaded corpus as an ingestable stream.

foley's SOURCE stage has two shapes. This module defines the **bulk-corpus**
shape used by :func:`foley.bootstrap.bootstrap` to seed the library from corpora
the user has already downloaded to local disk (FSD50K, Clotho, FoleySet, …). It
is deliberately narrower than the live/HTTP ``SourceAdapter`` (search / get /
download / generate) that subtask #5 introduces: a bulk corpus only has to
*enumerate its clips* and *say what each clip's license is*. Everything else —
decode, QC, tag, embed, dedup, the by-value/by-reference storage gate — is reused
verbatim from :func:`foley.index.ingest.ingest_one`; adapters never touch the
library.

The two responsibilities of an adapter:

    * :meth:`CorpusAdapter.iter_clips` — yield a :class:`ClipSpec` per audio file,
    * :meth:`CorpusAdapter.resolve_license` — map a clip's corpus metadata to a
      fully-derived :class:`~foley.base.LicenseRecord` (via the licensing SSOT,
      never hand-set flags), setting ``rights_verified`` True **only** for an
      authoritatively-recognized license (fail-closed otherwise).

Concrete adapters register themselves in :data:`CORPUS_REGISTRY` via
:func:`register_corpus`; :func:`corpora_in_rings` / :func:`select_corpora` drive
the ring policy in the bootstrap orchestrator. The registry is a plain dict — no
auto-discovery / ``SOURCE_CONFIG`` (that is #5's concern).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator, Optional, Protocol, runtime_checkable

from ..base import AcquisitionMethod, LicenseRecord
from ..licensing import apply_license_flags

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..base import Candidate, SoundRecord


@dataclass
class ClipSpec:
    """One clip inside a local bulk corpus, described but not yet ingested.

    Attributes:
        path: Absolute path to the audio file on disk.
        source_id: The corpus-native id (e.g. an FSD50K ``fname``); used only for
            reporting/provenance — the stored ``SoundRecord.id`` is still the
            content hash minted by the ingest pipeline.
        meta: Free-form per-clip metadata the adapter carries to
            :meth:`CorpusAdapter.resolve_license` and (optionally) to caption/tag
            hints — e.g. ``{"license_id", "creator_name", "source_url",
            "caption", "tag_hints"}``.
    """

    path: str
    source_id: str
    meta: dict = field(default_factory=dict)


@runtime_checkable
class CorpusAdapter(Protocol):
    """A downloaded bulk corpus presented as an ingestable stream of clips.

    Implementations are plain objects (usually a small ``@dataclass``) carrying
    three class-level facts (``name`` / ``ring`` / ``default_license_id``) and the
    two methods below. They perform **no** embedding, storage, or library access.
    """

    #: Registry key / CLI name — ``'fsd50k'`` | ``'clotho'`` | ``'foleyset'`` | …
    name: str
    #: Bootstrap ring: ``0`` ship-in-repo, ``1`` fetch, ``2`` opt-in/quarantined.
    ring: int
    #: The corpus compilation license id (a per-clip license may still override).
    default_license_id: str

    def corpus_dir(self, data_dir: str) -> str:
        """The on-disk root for this corpus under ``data_dir`` (``data_dir/name``)."""
        ...

    def iter_clips(self, root: str) -> Iterator[ClipSpec]:
        """Yield a :class:`ClipSpec` for every ingestable clip under ``root``."""
        ...

    def resolve_license(self, spec: ClipSpec) -> LicenseRecord:
        """Return the fully-derived rights record for ``spec`` (licensing SSOT)."""
        ...


@runtime_checkable
class SourceAdapter(Protocol):
    """The live/HTTP source contract (report 10 §4.2): ``search`` + ``get`` + ``download``.

    A **retrieve** adapter (Freesound, #5) fetches existing sounds from a service:
    ``search`` returns ranked :class:`~foley.base.Candidate`\\ s, ``get`` resolves
    one id to a :class:`~foley.base.SoundRecord`, and ``download`` returns the
    (transient, TOS-permitting) bytes to embed. It returns the SAME
    ``Candidate`` / ``SoundRecord`` shapes as the retrieval index, so callers see
    one uniform interface whether audio is remote, cached, or local.

    Distinct from (and complementary to) the narrow bulk-corpus
    :class:`CorpusAdapter`: a live adapter does NOT re-implement enrichment or
    storage — it converges on the same :func:`foley.index.ingest.ingest_one`
    pipeline via :func:`foley.sources.pull.add_from` (it *wraps* the corpus
    machinery, it does not fork it). **Generation** adapters (#6: Stable Audio
    Open, ElevenLabs) will add a sibling ``generate`` surface; it is intentionally
    out of scope here so this Protocol stays runtime-checkable for retrieve
    adapters.
    """

    def search(self, query: str, **kw) -> "list[Candidate]":
        """Return ranked candidates for ``query`` (license filter pushed native)."""
        ...

    def get(self, source_id: str) -> "SoundRecord":
        """Resolve one source id to a metadata :class:`~foley.base.SoundRecord`."""
        ...

    def download(self, source_id: str) -> bytes:
        """Return a sound's bytes (honoring ``cache_bytes_ok`` at the storage gate)."""
        ...


def _build_license(
    *,
    source: str,
    license_id: str,
    rights_verified: bool,
    acquisition_method: AcquisitionMethod,
    overrides: Optional[dict] = None,
    source_id: Optional[str] = None,
    source_url: Optional[str] = None,
    license_url: Optional[str] = None,
    creator_name: Optional[str] = None,
    attribution_text: Optional[str] = None,
) -> LicenseRecord:
    """Construct a :class:`~foley.base.LicenseRecord` and derive its flags (SSOT).

    The shared core of :func:`bulk_license` (``acquisition_method=bulk``) and
    :func:`api_license` (``acquisition_method=api``): it builds the record and
    routes it through :func:`~foley.licensing.apply_license_flags` so the eight
    permission flags are DERIVED from ``license_id`` (+ optional per-source
    ``overrides``) — never hand-set. ``rights_verified`` is passed through
    unchanged (it is not a derived flag): ``True`` only for an
    authoritatively-recognized license, so an unknown id stays fail-closed and
    :func:`foley.keep` drops it while its provenance is still recorded.
    """
    record = LicenseRecord(
        source=source,
        source_id=source_id,
        source_url=source_url,
        license_url=license_url,
        license_id=license_id,
        acquisition_method=acquisition_method,
        creator_name=creator_name,
        attribution_text=attribution_text,
        rights_verified=rights_verified,
    )
    # The eight permission flags are DERIVED from license_id (+ overrides) by
    # apply_license_flags — never hand-set here.
    return apply_license_flags(record, overrides=overrides)


def bulk_license(
    *,
    source: str,
    license_id: str,
    rights_verified: bool,
    source_id: Optional[str] = None,
    source_url: Optional[str] = None,
    creator_name: Optional[str] = None,
    attribution_text: Optional[str] = None,
) -> LicenseRecord:
    """Build a bulk-acquisition :class:`~foley.base.LicenseRecord`, flags derived.

    The SSOT license builder every **bulk-corpus** adapter routes through
    (``acquisition_method=bulk``); a thin wrapper over :func:`_build_license`. Its
    signature is unchanged from #4 — no ``overrides`` (a downloaded corpus is
    cacheable by-value), so every existing corpus adapter keeps working verbatim.

    Args:
        source: Provenance source tag (e.g. ``'fsd50k'``, ``'foleyset'``).
        license_id: The normalized license id (a key of ``LICENSE_FLAGS``, else it
            falls back to the all-False ``unknown`` flags).
        rights_verified: Whether the license is authoritatively known (fail-closed
            gate input — pass ``False`` for unrecognized/ambiguous licenses).
        source_id: The corpus-native clip id, for provenance.
        source_url: A human-resolvable URL for the clip (attribution/credits).
        creator_name: The uploader/creator (required for CC-BY attribution).
        attribution_text: A ready-made attribution string, if the corpus supplies one.

    Returns:
        A populated ``LicenseRecord`` with its derived flags applied.
    """
    return _build_license(
        source=source,
        license_id=license_id,
        rights_verified=rights_verified,
        acquisition_method=AcquisitionMethod.bulk,
        source_id=source_id,
        source_url=source_url,
        creator_name=creator_name,
        attribution_text=attribution_text,
    )


def api_license(
    *,
    source: str,
    license_id: str,
    rights_verified: bool,
    overrides: Optional[dict] = None,
    source_id: Optional[str] = None,
    source_url: Optional[str] = None,
    license_url: Optional[str] = None,
    creator_name: Optional[str] = None,
    attribution_text: Optional[str] = None,
) -> LicenseRecord:
    """Build an API-acquisition :class:`~foley.base.LicenseRecord`, flags derived.

    The live-source sibling of :func:`bulk_license` (``acquisition_method=api``),
    used by HTTP :class:`SourceAdapter`\\ s (Freesound, …). It exposes the
    ``overrides`` seam so an adapter can flip an operational flag on top of the
    per-item copyright license **without** minting a new ``license_id`` — the
    Freesound case: keep the sound's own CC id (``CC0-1.0`` / ``CC-BY-4.0`` / …)
    but pass ``overrides={'cache_bytes_ok': False}`` because the API TOS forbids
    caching the bytes even for CC0. ``redistribute_standalone_ok`` (copyright) and
    ``cache_bytes_ok`` (TOS) are distinct; only the latter is flipped.

    Args:
        source: Provenance source tag (e.g. ``'freesound'``).
        license_id: The per-item normalized license id (a key of ``LICENSE_FLAGS``).
        rights_verified: ``True`` only for an authoritatively-recognized license
            (fail-closed gate input); MUST be ``True`` for :func:`foley.keep` to
            admit the sound.
        overrides: Per-source flag overrides applied on top of ``license_id``'s row
            (e.g. ``{'cache_bytes_ok': False}``). Keys must be ``LicenseFlags``
            fields (validated by :func:`~foley.licensing.derive_license_flags`).
        source_id: The source-native id (e.g. a Freesound numeric id), for provenance.
        source_url: A human-resolvable URL for the item (attribution + the stable
            by-reference re-fetch handle).
        license_url: The license URL/label exactly as the source served it.
        creator_name: The uploader/creator (required for CC-BY attribution).
        attribution_text: A ready-made attribution string, if supplied.

    Returns:
        A populated ``LicenseRecord`` with its derived flags (+ overrides) applied.
    """
    return _build_license(
        source=source,
        license_id=license_id,
        rights_verified=rights_verified,
        acquisition_method=AcquisitionMethod.api,
        overrides=overrides,
        source_id=source_id,
        source_url=source_url,
        license_url=license_url,
        creator_name=creator_name,
        attribution_text=attribution_text,
    )


@dataclass
class UniformCorpus:
    """A bulk corpus where **every** clip carries the same license.

    Covers FoleySet (CC-BY), Sonniss (Sonniss-GDC), BBC RemArc (RemArc) and any
    other single-license drop: it walks the audio tree and stamps one license.
    ``rights_verified`` is a constructor field so a corpus whose blanket license
    is authoritatively known passes the gate, while a merely-assumed one can stay
    fail-closed. Subclass to enrich per-clip ``meta`` (see
    :class:`~foley.sources.clotho.ClothoEvalCorpus`).
    """

    name: str
    ring: int
    default_license_id: str
    source: str
    rights_verified: bool = True
    tag_hints_from_path: bool = False

    def corpus_dir(self, data_dir: str) -> str:
        """``data_dir/<name>`` — the conventional on-disk root for this corpus."""
        from pathlib import Path

        return str(Path(data_dir) / self.name)

    def iter_clips(self, root: str) -> Iterator[ClipSpec]:
        """Yield one :class:`ClipSpec` per audio file under ``root``.

        When :attr:`tag_hints_from_path` is set, the clip's parent folder names
        (relative to ``root``) are carried in ``meta['tag_hints']`` — corpora like
        FoleySet encode a Foley taxonomy in their directory structure.
        """
        from pathlib import Path

        from ..index.ingest import iter_audio_files

        # iter_audio_files expands '~'; match that so relative_to lines up.
        root_path = Path(root).expanduser()
        for fp in iter_audio_files(root):
            meta: dict = {}
            if self.tag_hints_from_path:
                rel = fp.relative_to(root_path) if fp.is_relative_to(root_path) else fp
                meta["tag_hints"] = list(rel.parts[:-1])
            yield ClipSpec(path=str(fp), source_id=fp.stem, meta=meta)

    def resolve_license(self, spec: ClipSpec) -> LicenseRecord:
        """Stamp the corpus's uniform license (derived via the licensing SSOT)."""
        return bulk_license(
            source=self.source,
            license_id=self.default_license_id,
            rights_verified=self.rights_verified,
            source_id=spec.source_id,
        )


#: Registry of concrete bulk-corpus adapters, keyed by ``adapter.name``.
CORPUS_REGISTRY: "dict[str, CorpusAdapter]" = {}


def register_corpus(adapter: "CorpusAdapter") -> "CorpusAdapter":
    """Register ``adapter`` in :data:`CORPUS_REGISTRY` (idempotent) and return it.

    Raises:
        ValueError: If a *different* adapter is already registered under the name.
    """
    existing = CORPUS_REGISTRY.get(adapter.name)
    if existing is not None and type(existing) is not type(adapter):
        raise ValueError(f"corpus name {adapter.name!r} already registered")
    CORPUS_REGISTRY[adapter.name] = adapter
    return adapter


def ring_of(name: str) -> int:
    """Return the ring of the registered corpus ``name`` (raises ``KeyError``)."""
    return CORPUS_REGISTRY[name].ring


def corpora_in_rings(rings: "tuple[int, ...]") -> "list[CorpusAdapter]":
    """Registered adapters whose ring is in ``rings`` (sorted by name)."""
    return [a for _, a in sorted(CORPUS_REGISTRY.items()) if a.ring in rings]


def select_corpora(
    *, rings: "tuple[int, ...]" = (0, 1), corpora: "Optional[list[str]]" = None
) -> "list[CorpusAdapter]":
    """Resolve the adapters a bootstrap run should touch.

    An explicit ``corpora`` allowlist (by name) wins over ``rings``; otherwise
    every registered adapter in the given rings is selected. Ring 2 is never in
    the default ``rings`` — it is opt-in only.

    Raises:
        KeyError: If a name in ``corpora`` is not registered.
    """
    if corpora is not None:
        return [CORPUS_REGISTRY[name] for name in corpora]
    return corpora_in_rings(rings)
