from __future__ import annotations


TOPICS_BY_CATEGORY: dict[str, frozenset[str]] = {
    "control_system": frozenset(
        {
            "control_architecture",
            "cryogenics",
            "epics",
            "interlock",
            "ioc",
            "opi",
            "pv",
            "timing",
        }
    ),
    "high_level_application": frozenset({"hla"}),
    "beam_diagnostics": frozenset(
        {
            "bpm",
            "data_acquisition",
            "electron_beam_diagnostics",
            "orbit",
            "photon_diagnostics",
            "waveform",
        }
    ),
    "accelerator_physics": frozenset(
        {
            "accelerator_design",
            "beam_transport",
            "lattice",
            "light_source",
            "mba",
            "undulator",
        }
    ),
}


VALID_CATEGORIES = frozenset(TOPICS_BY_CATEGORY)
