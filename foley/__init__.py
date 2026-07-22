"""foley — a retrieval-first façade for sound effects.

foley finds (or generates) the right sound effect for a moment of narration and
weaves it in. It is the SFX sibling of ``arioso`` (a unified façade over AI
music-generation backends): one simple surface over many sound *sources* (a
bring-your-own library, service APIs like Freesound, and generative-AI models),
a searchable *index* of every sound (by keyword *and* meaning, via CLAP
embeddings + hybrid search), an *agent* that selects the right sound for a
narrative context, and a *compositor* that places it under the voice.

Four stages::

    SOURCE  ->  INDEX  ->  SELECT  ->  WEAVE
    (get)      (find)      (choose)    (compose)

Intended façade (design-stage — see ``misc/docs/design.md`` and
``misc/docs/roadmap.md`` for what is implemented)::

    import foley

    foley.find("She pushed open the heavy oak door; rain hammered outside.")
    foley.search("distant thunder rumble", k=10)
    foley.generate("a single wooden door creak", backend="stable_audio_open")
    foley.ingest("~/my_sounds/")

The design is grounded in the research reports under ``misc/docs/research/``.
"""
