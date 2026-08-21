# Downfall — web

A static site. No API, no database, no server-side rendering at request time.

That is a decision rather than a limitation. The trip archive changes once a
month and the outage record is committed to this repository anyway, so a served
query would be a query against a file the build already has. See
`Downfall_SRS_v1.0.md` §8.1.

## Data

Generated from the marts by `pipeline/export_web.py`, which writes two files
split by who reads them:

| File | Read by | Size |
|---|---|---|
| `public/data/network.json` | the browser, for the map | ~0.3 MB |
| `data/profiles.json` | the build, to generate station pages | ~2.5 MB |

The second never reaches a browser, so its size is a build concern and not a
page one.

Regenerate with:

```bash
python pipeline/export_web.py
```

## Station pages

Generated for the **top-200 cohort only** — the population the kill criterion is
evaluated on, fixed from the twelve months preceding collection so that it
cannot be influenced by the outages being measured. Generating a page for all
2,391 stations would imply they are all part of the analysis. They are not.

## The map

Leaflet, with CARTO's basemap tiles — free, no account, no API key, so NFR-1 is
satisfied without giving up the map. Attribution is on the map itself.

**An earlier version had no basemap at all**, and the README argued that was
better: that 2,391 dots draw the city's own shape and streets would only
distract. That was a rationalisation of a constraint rather than a design
decision, and it did not survive being looked at. Without streets it read as a
dot cloud, there was nothing to zoom into, and clicking a station did nothing —
so the one interaction the whole page exists for was missing.

It was also unnecessary: the constraint never required it, because keyless tile
providers exist.

Two things that had to be got right and were not, first time:

- **Both axes in the same units.** The bare-SVG version put latitude through
  Mercator, which returns a dimensionless radian-scale number, while leaving
  longitude in degrees. The ranges differed by 36.8×, the shared scale took the
  smaller, and the whole city collapsed into an 18-pixel strip.
- **`fitBounds` after the container has its real size.** Leaflet computes zoom
  from the container's current dimensions, and on first paint those are not
  final. The first attempt framed New Jersey with every station off screen.
  `invalidateSize()` on the next frame, plus a `ResizeObserver` so the framing
  survives a window resize.

## Run it

```bash
npm install
npm run dev
```

## What the site may not say

Everything currently displayed is **observed departures** — trips that happened.
That is precisely the quantity this project argues is wrong, so no figure is
labelled "demand" without qualification, and no station is described as
under-served. Both await thresholds fixed in `PREREGISTRATION.md` before the
data existed.
