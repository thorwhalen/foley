"""``generate`` — the live generation-source façade (SOURCE → INDEX in one call).

The generate sibling of :func:`foley.sources.pull.add_from`: resolve a registered
:class:`~foley.sources.base.GenerateAdapter`, synthesize a sound from a prompt, and
run the resulting bytes through the SAME :func:`foley.index.ingest.ingest_one`
pipeline the local, bulk, and retrieve paths use — so decode / QC / embed / tag /
store are **not forked**. The division of labor mirrors ``add_from`` exactly: the
ADAPTER owns audio synthesis + license construction (it holds the model, seed, and
resolved native params), the FAÇADE owns the ``ingest_one`` call + the
:class:`~foley.index.ingest.IngestReport`.

Two differences from the retrieve path, both load-bearing:

* **By-value storage — the generation flywheel.** Both generator licenses
  (``Stability-Community``, ``ElevenLabs-SFX``) carry ``cache_bytes_ok=True``, so
  the bytes are stored by-value (the opposite of Freesound's by-reference); every
  generation becomes a first-class, re-searchable, locally-served library entry —
  a future free retrieval. The id is the decoded-PCM content hash
  (``sound_id=None``), so a byte-identical regeneration content-dedups
  (``skipped_dup``) and is never stored twice.
* **Operator-consented AI-training gate.** Both generator licenses carry
  ``ai_training_ok=False``, which ``ingest_one``'s universal fail-closed gate would
  reject. The user calling :func:`foley.generate` and keeping the result IS the
  explicit consent (they asked to create + persist THIS sound), so the façade calls
  ``ingest_one(..., allow_ai_training_forbidden=True)`` — the SAME lever
  :func:`foley.bootstrap.bootstrap` uses for Sonniss / BBC RemArc. The consent is to
  *embed + persist only*: ``ai_training_ok`` stays ``False`` on the record, so
  :func:`foley.keep` still refuses the sound for any ``IntendedUse(will_train=True)``
  downstream.

The public :func:`foley.generate` (a thin wrapper in :mod:`foley`) returns the
single stored :class:`~foley.base.Candidate` (report 10 §4.2); this workhorse
returns the full :class:`~foley.index.ingest.IngestReport` for ``add_from``-symmetric
resilience — a backend failure becomes a recorded ``error`` entry, never an
unhandled exception.
"""

from __future__ import annotations

from typing import Optional

from ..base import Candidate, CandidateOrigin
from ..index.ingest import IngestReport, IngestResult, ingest_one
from .registry import get_source

#: The consent note stamped on a stored generation whose license forbids AI
#: training (mirrors :func:`foley.bootstrap.bootstrap`'s Ring-2 acknowledgement).
_CONSENT_NOTE = "AI-training restriction acknowledged by operator (consent recorded)"


class GenerationError(RuntimeError):
    """Raised by :func:`foley.generate` when a backend yields no stored sound.

    Carries the full :class:`~foley.index.ingest.IngestReport` and the terminal
    :attr:`status` so a caller can react distinctly to ``quarantined`` (QC-rejected —
    e.g. regenerate), ``rights_blocked``, or ``error``. The lower-level
    :func:`generate` workhorse never raises this — it always returns an inspectable
    report; only the public :func:`foley.generate` promise raises.

    Attributes:
        report: The :class:`~foley.index.ingest.IngestReport` from the run.
        status: The terminal :class:`~foley.index.ingest.IngestResult` status
            (``'quarantined'`` | ``'rights_blocked'`` | ``'error'`` | …).
    """

    def __init__(self, message: str, *, report: IngestReport, status: Optional[str]):
        super().__init__(message)
        self.report = report
        self.status = status


class SafetyRefusal(GenerationError):
    """Raised (fail-closed) when a generation prompt trips a #9b safety gate.

    A pre-synthesis hard stop: nothing is generated or stored. Distinct from a
    resilience ``error`` result (a backend/ingest failure the workhorse records
    without raising) — a safety refusal is a deliberate refusal of an unsafe
    request. Its ``report`` is an empty pre-generation report and ``status`` is
    ``'refused'``. Carries :attr:`hits` (the matched marks/patterns). Subclass of
    :class:`GenerationError` so the public :func:`foley.generate` ``Raises`` clause
    already covers it. See :func:`foley.provenance.disclosure.scan_prompt`.
    """

    def __init__(self, message: str, *, hits: "list[str]", report: IngestReport):
        super().__init__(message, report=report, status="refused")
        self.hits = hits


class TrademarkRefusal(SafetyRefusal):
    """A :class:`SafetyRefusal` for a prompt naming a trademarked audio logo (report 07 §7.2)."""


class RecognizableVoiceRefusal(SafetyRefusal):
    """A :class:`SafetyRefusal` for a prompt requesting a recognizable / cloned voice (report 07 §7.1)."""


def candidate_of(result: IngestResult) -> Candidate:
    """Wrap a stored :class:`~foley.index.ingest.IngestResult` as a generated candidate.

    The report-10 §4.2 shape: retrieval and generation return the same
    :class:`~foley.base.Candidate`, differing only in ``origin``. Use on a
    ``pass`` / ``warn`` result (its ``record`` is the canonical, stored
    :class:`~foley.base.SoundRecord`).

    Args:
        result: A stored ingest result (``result.record`` is not ``None``).

    Returns:
        A :class:`~foley.base.Candidate` with ``origin=CandidateOrigin.generated``.
    """
    return Candidate(sound=result.record, origin=CandidateOrigin.generated)


def generate(
    prompt: str,
    *,
    backend: str = "stable_audio",
    library=None,
    store: bool = True,
    adapter=None,
    watermark: Optional[bool] = None,
    on_flagged: str = "refuse",
    watermarker=None,
    provenance_store=None,
    **affordances,
) -> IngestReport:
    """Generate a sound via ``backend`` and ingest it (by-value) into ``library``.

    Progressive disclosure: ``generate("a single wooden door creak")`` works out of
    the box (the local Stable Audio Open backend, into the process-wide default
    library); every other knob is an optional keyword. The generated bytes are
    routed through the shared :func:`~foley.index.ingest.ingest_one` pipeline
    (decode → QC → embed → tag → store), stored by-value with a content-hash id.

    Disclosure/safety (#9b), all optional and degrading gracefully:

    * **Safety gate** — the prompt is scanned for trademarked audio logos + cloned
      voices *before* any synthesis spend (:func:`foley.provenance.disclosure.scan_prompt`).
      Fail-closed by default (``on_flagged='refuse'`` raises :class:`SafetyRefusal`);
      ``on_flagged='warn'`` proceeds but stamps ``potential_trademark`` /
      ``contains_recognizable_voice`` on the record so :func:`foley.keep` drops it
      downstream.
    * **Watermark** — with ``foley[provenance]`` installed, the generated bytes are
      AudioSeal-watermarked *before* ingest (the stored bytes carry the mark),
      setting ``license.watermark``. Without the extra, generation proceeds
      unmarked (a note is recorded).
    * **Content credential** — a portable C2PA-shaped JSON sidecar recording the
      AI origin + license is written for every stored generation and referenced by
      ``license.c2pa_manifest_ref`` (stdlib; always on).

    Args:
        prompt: The natural-language sound description.
        backend: A registered generate-source name (``'stable_audio'`` (default,
            local) | ``'elevenlabs'`` (hosted)).
        library: Target :class:`~foley.index.library.SoundLibrary` (default: the
            process-wide default library).
        store: If ``False``, synthesize + enrich but do not add to the library
            (probe/QC/embed only — a preview; no content-credential sidecar).
        adapter: An optional pre-built adapter (the dependency-injection seam — a
            test passes a fake-transport / fake-pipeline adapter; production omits
            it and the registry lazily builds one).
        watermark: ``True`` require an AudioSeal watermark (error if
            ``foley[provenance]`` absent), ``False`` never watermark, ``None``
            (default, auto) watermark iff AudioSeal is installed.
        on_flagged: ``'refuse'`` (default, fail-closed) raise on a safety-flagged
            prompt; ``'warn'`` proceed and flag the record.
        watermarker: An injected :class:`~foley.provenance.disclosure.Watermarker`
            (the DI seam; wins over auto-detect — tests pass a fake).
        provenance_store: A ``MutableMapping[str, dict]`` for content-credential
            sidecars (default: :func:`foley.stores.make_provenance_store`).
        **affordances: Unified generation affordances forwarded to the adapter's
            ``generate`` (``duration``, ``prompt_influence``, ``negative_prompt``,
            ``steps``, ``seed``, ``loop``, ``output_format`` — see
            :data:`foley.base.GENERATION_AFFORDANCES`); unsupported ones are
            warn-and-dropped per the source's ``on_unsupported_param``.

    Returns:
        An :class:`~foley.index.ingest.IngestReport` — inspect ``.ingested`` for the
        stored record (``storage_mode == by_value``) and ``.summary()`` for counts.
        A backend or ingest failure is recorded as a single ``error`` result, never
        raised (``add_from``-symmetric resilience).

    Raises:
        SafetyRefusal: If the prompt trips a safety gate and ``on_flagged='refuse'``.
        WatermarkUnavailable: If ``watermark=True`` but ``foley[provenance]`` is absent.
    """
    from ..index.library import default_library
    from ..provenance import disclosure  # stdlib top-level; heavy deps lazy inside

    if on_flagged not in ("refuse", "warn"):
        raise ValueError(f"on_flagged must be 'refuse' or 'warn', got {on_flagged!r}")

    # -- Safety gate (fail-closed) — BEFORE any GPU/HTTP spend ------------------
    scan = disclosure.scan_prompt(prompt)
    if scan.flagged and on_flagged == "refuse":
        empty = IngestReport(root=f"{backend}:{prompt}")
        if scan.trademark_hits:
            raise TrademarkRefusal(
                f"prompt matches trademarked audio logo(s): {list(scan.trademark_hits)}. "
                "Pass on_flagged='warn' to override (the clip is then flagged and keep() drops it).",
                hits=list(scan.trademark_hits),
                report=empty,
            )
        raise RecognizableVoiceRefusal(
            f"prompt requests a recognizable / cloned voice: {list(scan.voice_hits)}. "
            "Pass on_flagged='warn' to override (the clip is then flagged and keep() drops it).",
            hits=list(scan.voice_hits),
            report=empty,
        )

    # Resolve the watermarker fail-fast: watermark=True without foley[provenance]
    # errors BEFORE spending on generation.
    wm = disclosure.resolve_watermarker(watermark, watermarker)

    lib = library if library is not None else default_library()
    gen = adapter if adapter is not None else get_source(backend)["adapter"]

    report = IngestReport(root=f"{backend}:{prompt}")
    # A synthesis failure (auth / rate-limit / model load / bad response) yields an
    # inspectable report with one error entry, never an unhandled exception.
    try:
        clip = gen.generate(prompt, **affordances)
    except Exception as exc:
        report.record(
            IngestResult(id=f"{backend}:generate", status="error", error=repr(exc))
        )
        return report

    lic = clip.candidate.sound.license

    # Warn-mode: reaching here with a flagged scan means on_flagged='warn'. Stamp the
    # safety flags on the record so the fail-closed keep() gate drops it downstream.
    if scan.flagged:
        if scan.potential_trademark:
            lic.potential_trademark = True
        if scan.contains_recognizable_voice:
            lic.contains_recognizable_voice = True
        clip.notes.append(
            f"safety: proceeded in warn mode; flagged {list(scan.trademark_hits + scan.voice_hits)}"
        )

    # Watermark BEFORE ingest so the stored bytes carry the mark AND the content-hash
    # id hashes the watermarked PCM. Graceful degrade: a watermark failure never
    # fails the generation (the mark is descriptive provenance, not a license gate).
    audio_bytes = clip.audio_bytes
    if wm is not None:
        try:
            wres = wm.embed(clip.audio_bytes)
            audio_bytes = wres.audio_bytes
            lic.watermark = wres.meta
        except Exception as exc:  # noqa: BLE001 - any embed failure degrades gracefully
            clip.notes.append(f"watermarking skipped: {exc!r}")
    elif watermark is None:
        clip.notes.append("watermarking skipped: foley[provenance] not installed")

    # One try guards BOTH the content-credential sidecar (which decodes the bytes to
    # pre-compute the id) AND the ingest — so an undecodable response (a hosted API
    # returning HTTP 200 with a non-audio body) is recorded as an error, not a crash.
    sound_id = None
    try:
        # Content-credential sidecar (stdlib; every STORED generated clip). Single-pass:
        # pre-compute the content-hash id from the (watermarked) bytes so the sidecar
        # key and license.c2pa_manifest_ref match the id ingest_one re-mints — no
        # meta re-store.
        if store:
            from ..index.ingest import content_id
            from ..stores import content_key, make_provenance_store

            sound_id = content_id(audio_bytes)
            pstore = (
                provenance_store
                if provenance_store is not None
                else make_provenance_store()
            )
            credential = disclosure.build_content_credential(
                clip.candidate.sound,
                asset_id=sound_id,
                asset_hash={"alg": "sha256", "value": content_key(audio_bytes)},
            )
            disclosure.write_content_credential(pstore, sound_id, credential)
            lic.c2pa_manifest_ref = sound_id

        res = ingest_one(
            audio_bytes,
            library=lib,
            sound_id=sound_id,  # == content_id(audio_bytes); ingest re-mints the same id
            license=lic,  # watermark + c2pa_manifest_ref + provenance, flags derived
            captioner=_metadata_captioner(prompt),
            seed_tags=(clip.candidate.sound.tags or None),
            store=store,
            allow_ai_training_forbidden=True,  # operator consent (embed+persist only)
        )
    except Exception as exc:
        report.record(
            IngestResult(id=f"{backend}:ingest", status="error", error=repr(exc))
        )
        return report

    # Surface the adapter's + disclosure notes (unsupported affordances, warn-mode
    # flag, watermark-skip) in the run report.
    if clip.notes:
        res.notes.extend(clip.notes)
    # Record the operator-consent acknowledgement on a stored generation whose
    # license forbids AI training (mirrors bootstrap's Ring-2 note). ai_training_ok
    # stays False on the record — keep() still rejects it for will_train uses.
    if res.status in ("pass", "warn") and not lic.ai_training_ok:
        res.notes.append(_CONSENT_NOTE)
    report.record(res)
    return report


def _metadata_captioner(prompt: str):
    """The prompt as the sound's caption (feeds the BM25 keyword index).

    Imported from :mod:`foley.bootstrap` locally to avoid a
    ``sources`` ↔ ``bootstrap`` import cycle (same seam :func:`add_from` uses).
    """
    from ..bootstrap import MetadataCaptioner

    return MetadataCaptioner(prompt) if prompt else None
