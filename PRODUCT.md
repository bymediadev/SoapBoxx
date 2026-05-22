# SoapBoxx — Product Definition

**V1 build (7 days):** [`SOAPBOXX_V1_7DAY_EXECUTION.md`](SOAPBOXX_V1_7DAY_EXECUTION.md)  
**V1 spec:** [`SOAPBOXX_EXECUTION_PLAN_V1.md`](SOAPBOXX_EXECUTION_PLAN_V1.md)  
**Foundation:** [`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](SOAPBOXX_MASTER_PLAN_FOUNDATION.md) — primary asset is **structured measurements and patterns**; podcasts are **source material**.

## What SoapBoxx is

SoapBoxx is a **structured podcast measurement and pattern discovery system**. It ingests episodes that **already exist** on hosting platforms (YouTube, RSS, files), extracts **facts** (hook length, talk ratios, question counts, …), organizes them in a **knowledge + source** library, and optionally adds producer coaching on demand.

It is **not** a host, player, analytics clone, or AI critic. It is **not** a recorder by default.



## Two libraries (hosting vs insights)



**Hosting platforms** (Spotify, Apple Podcasts, YouTube, RSS, etc.) are the **catalog** — where shows are published, discovered, and listened to. SoapBoxx does **not** replace them.



**SoapBoxx** builds a **separate insights library** on your machine: measured structure, category benchmarks, and optional coach notes, organized like a real library (category → author → show → episodes). We **import from** those platforms (URLs, feeds, files); we **store insights**, not another copy of the listening experience.



```text
Spotify / Apple / YouTube / RSS  →  ingest (weekly batch)  →  SoapBoxx insights shelf
```



Over time, each show on a host platform can map to one shelf row in SoapBoxx with growing episode-level measurements — your private producer archive, not a new podcast host.



## Core value proposition



Most tools help you record or publish.



SoapBoxx helps you:



> **Import → Extract transcript → Coach + Intelligence → Improve next episode**



## Core loop



1. **Import** — YouTube URL, paste transcript, transcript file, or audio file

2. **Extract** — Pull/clean words (captions, ASR, or paste)

3. **Coach** — Episode Coach Report (sections A–F)

4. **Intelligence** — Metrics, category comparison, tier A/B/C, actions

5. **Improve** — Apply changes on the next recording (wherever you record)



## Episode Coach Report (canonical output)



| Section | Purpose |

|--------|---------|

| A. Episode Summary | 2–3 lines max |

| B. Strong Moments | What worked and **why** |

| C. Weak Moments | Where engagement dropped and **why** |

| D. Missed Opportunities | Follow-ups and deeper angles skipped |

| E. Host Behavior Patterns | Observable habits |

| F. Next Episode Improvements | 3–7 specific, repeatable behaviors (**most important**) |



## Intelligence snapshot (second output)



Structured metrics (hook timing, talk balance, questions, follow-ups, etc.), compared to **show category** benchmarks, rule-based **A/B/C tier**, and action bullets. Stored locally in SQLite for trend comparison.



## Target user



- Independent podcasters and small teams

- Interview, commentary, and analysis shows

- Creators who already publish on YouTube or elsewhere



## What SoapBoxx is NOT



- Not a DAW or in-app recorder (Studio tab hidden unless `SOAPBOXX_SHOW_STUDIO=1`)

- Not a hosting or distribution platform (Spotify et al. stay the catalog; SoapBoxx is the insights layer on top)

- Not guest matching or booking

- Not a generic chatbot



## Success metric



A user reads the outputs in **2–3 minutes** and knows what to change on the **next** episode.



## Technical pillars



1. **Episode ingest** — `backend/episode_ingest/` (YouTube, files, paste)

2. **Episode Coach Report** — `backend/episode_coach_report.py`

3. **Intelligence v1** — `backend/intelligence_v1/` (metrics, DB, benchmarks, tier)

4. **Insights library** — `backend/library/` (shelf + weekly batch from hosted episodes)



See [`docs/EPISODE_INGEST_FRAMEWORK.md`](docs/EPISODE_INGEST_FRAMEWORK.md), [`docs/INTELLIGENCE_V1.md`](docs/INTELLIGENCE_V1.md), and [`docs/LIBRARY_AND_BATCH.md`](docs/LIBRARY_AND_BATCH.md).

