---
term: Information State
definition: The string OpenSpiel keys on for one seat at one position (`information_state_string`): the seat's [[seat-view]] rendered by `render_information_state` — its zones through their declared [[projection]]s, the public [[state-variable]]s, and its [[observation-log]], each event by the `repr` of its spelling. Perfect recall, per player. Not "information set", the equivalence class of histories it induces (→ F-14), and not the Observation Log, which is the event sequence it embeds.
layer: interop
status: canonical
reserved: false
home: `infostate.py`
see: [seat-view, observation-log]
retired_spellings: []
findings: [F-14]
---

**Interop.** OpenSpiel's information state string (perfect recall, per
player): one seat's [[seat-view]] rendered by `render_information_state`, its
[[observation-log]] embedded verbatim, each event by the `repr` of its
spelling. "Information state" is the per-player artifact; "information set" is
the equivalence class it induces — don't interchange them (→ F-14). Not the
Observation Log, which is the event sequence the string embeds.
