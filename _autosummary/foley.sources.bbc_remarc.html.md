# foley.sources.bbc_remarc

BBC RemArc (Rewind Archive) — a Ring-2, quarantined corpus.

The BBC Rewind sound-effects archive (report 11 §1.4) is released under the
**RemArc** license: personal / educational / research use only — `commercial_ok
= False` **and** `ai_training_ok = False` (two hard flags). It is a Ring-2
corpus: web-only (no bulk API), so the user must have downloaded the WAVs
themselves, and it is refused by the fail-closed ingest gate unless the operator
passes explicit consent (`accept_ai_restricted=True`).

### Module Attributes

| [`BBC_REMARC`](#foley.sources.bbc_remarc.BBC_REMARC)   | The BBC RemArc Ring-2 adapter (non-commercial AND ai_training_ok=False).   |
|---------------------------------------------------------------|----------------------------------------------------------------------------|

### foley.sources.bbc_remarc.BBC_REMARC *= UniformCorpus(name='bbc_remarc', ring=2, default_license_id='RemArc', source='bbc_remarc', rights_verified=True, tag_hints_from_path=False)*

The BBC RemArc Ring-2 adapter (non-commercial AND ai_training_ok=False).
