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

## The map has no basemap, deliberately

Every tile provider wants an API key, and NFR-1 puts the project on free tiers
with no account anywhere. It is also the better picture: 2,391 dots draw the
network's own shape, and streets underneath would invite reading the streets
instead of the data.

Web Mercator rather than plain lat/lon — at this latitude the naive projection
stretches Manhattan noticeably north–south, and it looks subtly wrong to anyone
who knows the city.

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
