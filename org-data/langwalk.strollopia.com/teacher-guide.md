# Teacher Guide — LangWalk

Welcome to LangWalk. This guide walks you through creating and running a language challenge from scratch.

---

## What you need before you start

- A LangWalk teacher account (your administrator sets `is_producer = true` on your user record)
- A city map or area you want to use for the challenge
- Activity content: questions, audio clips, prompts

---

## Concepts

| Term | What it means |
|------|---------------|
| **Challenge** | The top-level thing you create — a named route with a language and level |
| **Stop** | A physical location students walk to (pinned on the map) |
| **Activity** | A task at a stop — quiz, listen, speak, write, photo, or check-in |
| **Join code** | A short code students use to enrol in your published challenge |
| **Linear progression** | Students must complete all activities at a stop before the next one unlocks |

---

## Step 1 — Log in and go to the Dashboard

Go to **langwalk.strollopia.com** and log in.

You land on **My Challenges** (`/teach`). This lists every challenge you own.

---

## Step 2 — Create a challenge

1. Click **New challenge** (top right).
2. A new draft challenge appears in the list, titled "New Challenge".
3. Click **Edit →** to open the builder.

---

## Step 3 — Build the route in the builder

The builder has three panels:

```
[ Stop list ] | [ Map ] | [ Activity editor ]
```

**Add stops:**

- Click anywhere on the map to drop a stop pin at that location.
- Or click **Add stop manually** in the left sidebar to place a pin at the default centre and drag it into position.
- Drag pins on the map to adjust their exact position.
- Drag stops in the sidebar list to reorder them — students walk them in list order.
- Click the trash icon on a stop to delete it.

**Rename stops:**

Stop names default to "Stop 1", "Stop 2", etc. — currently rename by editing via the API or wait for the rename field (coming soon).

---

## Step 4 — Add activities to each stop

1. Click a stop in the sidebar to select it. The activity editor opens on the right.
2. Choose an **activity type** from the grid:

| Type | Use it for |
|------|-----------|
| **Quiz** | Multiple-choice comprehension question |
| **Listen** | Audio clip + comprehension question |
| **Speak** | Spoken prompt the student reads aloud (teacher reviews manually) |
| **Write** | Written prompt with a model answer shown after submission |
| **Photo** | Instruction to photograph something at the location |
| **Check-in** | Simple tap to confirm the student reached the spot |

3. Fill in the form fields for the chosen type.
4. Click **Add activity**. It appears in the stop's activity list.
5. Repeat for each activity at this stop, then move to the next stop.

**Quiz tips:**
- Mark exactly one option as correct using the radio button.
- Add an explanation — it shows after the student submits.

**Audio tip (Listen):**
- Paste a direct audio URL (mp3 or ogg) into the Audio URL field.
- Follow it with a comprehension quiz as normal.

---

## Step 5 — Publish the challenge

When your stops and activities are ready:

1. Click **Publish** at the bottom of the stop sidebar.
2. The button is disabled until you have at least one stop.
3. Once published, a **Join code** appears (e.g. `XK7R2M`). This is what students use to enrol.

A published challenge cannot be un-published. You can still edit stops and activities after publishing.

---

## Step 6 — Share the join code with students

Share the join code in one of two ways:

- **URL link:** `https://langwalk.strollopia.com/join/XK7R2M`  
  Students tap the link and hit **Join Challenge** — no typing needed.

- **Code only:** Tell students to go to `langwalk.strollopia.com/join` and type the code.

---

## Step 7 — Monitor student progress

Back on the Dashboard (`/teach`), published challenges show a **Progress** link.

The progress table shows:
- One row per enrolled student
- One column per stop
- A green tick when all activities at a stop are complete, a fraction (e.g. `2/3`) when partial, and an empty circle when not started
- A total column (`completed / total activities`)

---

## Activity types — content reference

### Quiz

```
Question:   "Wie komme ich zum Bahnhof?"
Option A:   "Geradeaus und dann links"    ← mark correct
Option B:   "Immer geradeaus"
Option C:   "Rechts, dann rechts"
Explanation: "'Geradeaus' means straight ahead; 'links' means left."
```

### Listen

```
Audio URL:  https://cdn.example.com/clips/bahnhof-dialog.mp3
Question:   "What does the speaker ask for?"
Options:    [as above]
```

### Speak / Write

```
Prompt:       "Ask for directions to the market in German."
Model answer: "Entschuldigung, wo ist der Marktplatz bitte?"
```
The model answer is shown to the student after they submit so they can self-assess.

### Check-in

```
Instruction: "You're standing in front of the Goldenes Dachl.
              Take a moment to read the information plaque, then tap Check in."
```

---

## Tips for a good challenge

- **Keep stops to 3–7** for a 60–90 minute walk.
- **Lead with a Check-in** at each stop so students confirm location before attempting language tasks.
- **Mix activity types** — a Listen followed by a Quiz followed by a Speak keeps the experience varied.
- **Use B1/B2 language** for activities if your students are intermediate — the real-world context does the scaffolding.
- **Walk the route yourself** before publishing — check GPS accuracy and walking time between stops.
