# Current work

Milestone: `fix/bounded-scene-preparation`, based on live Server main
`34b7984415b496bd8da3143acf9ad6aeee2825fe`. The local restored base
`9cb4ec696a468a32278fbed67ed3cf02ef4af419` has tree
`3cf41ed0cb679c110ec24e3e1e2f827d7187163d`; publish with actual remote ancestry.
Fetch main remains `0d6aa28a4a0c6944c053e3d63e150908b44b9175`; no open PR
in either repository at start. Owner approval continues for implementation, bounded
checks, independent review and merging passing development changes, not release.

## Delivered and current change

Server PR35/36 and Fetch PR22 are merged: Gemini3.8 for new jobs, foreign SRT/VTT
import and explicit saved-text translation, shared Qwen/scene runtime compatibility,
and exact verified Server item entry retaining viewing state. Prior evidence remains
applicable; these steps are not pending implementation.

Preview generation and scene preparation could keep posting when successful responses
repeated the same completed count. A focused DOM regression reproduced a fourth POST
after two unchanged responses. Both preparation entry points now stop on two successive
responses without a new high-water completed count, invalid counters, a request/body
wait over150s, or10minutes/256requests per explicit action. Preview and analysis stages
track progress separately. There are no automatic request retries. Existing completed
tiles remain; a new explicit action reuses server checkpoints. Closing/switching the
player cannot begin a later preparation stage. An aborted client wait does not claim
to cancel server work; the UI says the current server batch may still finish.

This changes only browser-side preparation control and its tests. Server APIs,
checkpoint formats, models, captions, original files, ranking and query egress are
unchanged. Fresh independent fixed-HEAD review and existing model-free CI gate merge.

## Verification

- New preparation DOM regression: original code failed (4POSTs instead of3); corrected
  code passes. Checks cover both preview entry points, analysis-stage no-progress,
  explicit resume, HTTP-header/body stalls, late timeout responses, elapsed limit,
  malformed progress and closed-player isolation. HTTP/media are mocked.
- All9DOM entry scripts pass, including existing caption, audio, recommendation,
  preview and scene flows. Existing Python preview8 and scene8 tests pass
  (7.611s and5.670s respectively); no new model inference.
- A45-minute,160x90,1fps generated H.264 fixture ran through actual FFmpeg/SQLite and
  production ASGI endpoints:120previews,0failed frames; restart after16 preserved
  those results and made104remaining previews. All120JPEG endpoints succeeded.
  Position1357.25s, selected caption/+500ms and original SHA remained unchanged.
  The full probe took11.22s on Linux CPU; tiny synthetic input is not a speed forecast.
  No real browser, model inference, natural footage or target-device acceptance.

## Blocked acceptance and next work

Fresh natural long-speech Qwen→aligner→Gemini3.8 acceptance is stopped. The prior
`test/bounded-long-speech@f038f85` branch preserves the complete handoff: model
setup failed before any weight download; socksio installation hit network approval
cancellation twice. This session rechecked missing socksio/weights without repeating
that installation or changing route. Two already-held public dialogue recordings
(706.24s and762.048s) and their reference annotations passed offline hash/time checks.
Some reference text was used in translation comparisons; these are not pristine
holdouts. No new ASR/alignment/Gemini calls. Renewed general approval alone is not
new evidence that the execution limit changed.

Finish this bounded preparation review/CI/development merge. Then, only when an
allowed environment has the dependencies and pinned model assets, run the fresh
continuous-speech product path with saved span/batch reuse and finite limits.
Natural long-caption viewing, actual Chrome Fetch discovery/save/item navigation,
Windows11/RTX installation/VRAM/playback, useful enhancement and subjective search/
recommendation acceptance remain open. SwinIR and the earlier filter experiment
have no adopted enhancement preset; no new enhancement-quality claim is made.

Stop on elapsed/no-progress limits or repeated same-cause failures, terminate owned
processes and preserve originals/complete evidence. Existing browser/CDP/profile/proxy
and model-inference CI workaround prohibitions remain. Do not convert missing target
hardware or human viewing acceptance into synthetic completion claims.
