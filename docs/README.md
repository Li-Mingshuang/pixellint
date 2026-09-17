# pixellint docs

The main [README](../README.md) is the argument: what this is, why it works, and
what it got wrong. These documents go deeper on specific machinery.

| doc | what it covers | read it when |
|---|---|---|
| [rules.md](rules.md) | the separation rule in full, and the four times calibration was wrong | you are changing a threshold, or a check is failing by a hair |
| [palettes.md](palettes.md) | how to design a palette that will not fight you | you are starting a new palette |
| [scenes.md](scenes.md) | the scene spec, depth bands, the layout solver, the composition rule | you are adding objects to a scene |
| [authoring.md](authoring.md) | adding a layer from scratch; the discipline for parallel authoring agents | you are writing a new asset, or briefing an agent |
| [decisions.md](decisions.md) | a dated log of what changed, why, and what was reversed | you are wondering why something is the way it is |

## The one-paragraph version

Pixel art is a deterministic medium: a 16×32 sprite is 512 cells, each an index
into a locked palette. That makes it small enough to author as text and precise
enough to verify by assertion instead of by eye — which is what lets a model with
no image input generate it. Every script here serves one of two jobs: **render
grids into images**, or **assert something about them**. The second job is the
interesting one, and the hardest part of it is not writing checks but keeping
them honest: a check that fires on differences nobody can perceive teaches people
to work around the checker instead of with it.
