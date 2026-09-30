# Speaker script — Apnea screening on-device (11 slides)

Spoken narration, ~20–40 s per slide. First person. Numbers match the deck and
FINAL_RESULTS.md. Say the honest caveats as written — they make us credible.

---

## Slide 1 — Title
"Good [morning/afternoon]. Our project is an apnea screening system that runs
entirely on a small medical device — and, unusually, adapts itself to each
patient without ever sending their data anywhere. In one line: we take a sleep
apnea detector, shrink it onto a microcontroller, and show it can get measurably
better on the device itself. Three numbers to remember today — a plus three-and-a-half
point accuracy gain from on-device adaptation, seventy-seven microseconds and two
kilobytes of memory per run, and a live dashboard running on the real board.
I'll be clear throughout about what we proved and what is still ahead — this is a
research prototype, not a clinical device."

## Slide 2 — Problem
"Sleep apnea is one of the most under-diagnosed conditions there is — a large
share of people who have it are never tested. The reason is the test itself: the
gold standard is an overnight sleep study in a lab, wired to many sensors, scored
by a specialist. It's expensive, it's slow, and it simply does not scale to
everyone who needs screening — especially outside big cities. What's needed is
cheap, private, low-power screening that can run at home or at a small clinic, on
hardware that costs a few dollars, not a sleep lab."

## Slide 3 — Solution
"Our answer has three parts. First, the detector runs on the device itself — a
tiny neural network, ten inputs, about nine hundred parameters, small enough for
a microcontroller. Second, it calibrates itself to each patient's session without
needing any labelled data — no doctor has to annotate anything. Third, devices
improve together through federation: they share what they learn about calibration,
never the patient's raw data. Cheap, private, and self-improving."

## Slide 4 — How it works
"Here's the flow. A pulse-oximetry signal is turned into features every sixty
seconds; those go into the INT8 neural network running on the Cortex-M85 core;
out comes an apnea-or-normal verdict per window. Around that sit two loops. The
inner loop re-centres the decision threshold to each session — that's the on-device
adaptation. The outer loop is federation: many devices pool their calibration
statistics into a shared reference, so a new device benefits from the whole fleet.
Crucially, only statistics move between devices — never patient signals."

## Slide 5 — Result 1: on-device self-calibration
"This is our headline result, and it's measured on a sealed set of patients the
model had never seen. On its own, the shipped model scores seventy-nine point one
percent balanced accuracy. With label-free on-device recalibration, that rises to
eighty-two point six — a gain of three-and-a-half points, with a confidence
interval that excludes zero. And it costs nothing in labels: the label-free version
matches the version that uses ground-truth labels. So the device genuinely gets
better on unseen patients, without anyone annotating their data."

## Slide 6 — Result 2: federation
"Federation adds to that. As we pool calibration from one device up to seventy,
balanced accuracy climbs by about four-and-a-half to five points, and it saturates
around twenty to forty devices — so you don't need a huge fleet to get the benefit.
Pooling everyone into one shared reference beats splitting by site every time we
tested it. And this is privacy by design: no raw patient data ever leaves the
device — only calibration statistics. It's pooled calibration, not model averaging."

## Slide 7 — Performance
"On cost, the numbers are strong. One full calibrated session runs in about
seventy-seven thousand cycles — roughly seventy-seven microseconds — and a single
inference is under seven microseconds. Memory is about two kilobytes. And the board
is bit-exact against our host reference: the same inputs give identical outputs,
so we know the device isn't quietly drifting from the model we validated. One
honest note — we report cycles and memory, not energy, because we don't yet have a
current probe on the board; a power measurement is on the roadmap."

## Slide 8 — Live demo  (say the sensor point here)
"And this actually runs — this is a live dashboard on the real board. It shows the
verdict flipping between apnea and normal, the model's probability, the live input
features, and the measured accuracy, updating in real time. Now, one honest point.
We were not able to attach live sensors to a patient. We're building this from a
remote area in India, and the clinical-grade sensor hardware and setup would have
been very expensive for us to obtain. So instead of live capture, we stream real
recorded overnight recordings from a clinical dataset into the board, one window at
a time — and the board runs exactly the same inference it would on a live signal.
The device doesn't know the difference; the front-end sensor is the one piece we
haven't wired yet, and adding it is on our roadmap. Everything you see computed
here — the verdict, the probability, the timing — is the real thing running on real
silicon."

## Slide 9 — Impact
"So what have we actually delivered? A working path to apnea screening at the edge:
cheap, because it's a microcontroller; private, because data never leaves the
device; adaptive, because it tunes to each patient; and honest, because every
number here is measured, not hoped for. Our contribution isn't a new machine
learning algorithm — it's the engineering that makes this deployable on real
embedded hardware, with real-time performance we can stand behind."

## Slide 10 — Scope & roadmap
"We're deliberately clear about what's next. We validated on twenty-five sealed
patients; we want to widen that to one to two hundred to firm up the effect — right
now the lower bound of our confidence interval is just short of our pre-registered
target. We'd move from a proxy apnea index to proper clinical event scoring. We'd
add the current probe for a real energy figure, and bring in the on-chip NPU, which
is present in silicon but unused today — we run purely on the CPU. And we'd take the
federation to a real multi-device field trial. These are the roadmap, not failures —
each one builds on something we've already shown works."

## Slide 11 — Takeaway
"To close: four things we proved on real hardware this project. On-device adaptation
gives plus three-and-a-half points of accuracy on unseen patients, label-free.
Federation adds another four-and-a-half, privately. It runs in seventy-seven
microseconds and two kilobytes. And it's live on the board. It's a modest, honest
gain with a clear path forward — a screening tool that could reach the people the
sleep lab never will. Thank you — we're happy to take questions."

---

### Delivery notes
- Total ~5–7 minutes at a natural pace; trim slide 4 or 9 if you need it shorter.
- Say the two honest lines (slide 7 energy, slide 8 sensors) plainly and move on —
  they build trust, don't apologise for them.
- If asked "is it live sensor data?": "No — recorded clinical recordings streamed
  into the board; the inference is live, the sensor front-end is future work."
- If asked about accuracy: it's *balanced* accuracy (rare-class safe), not raw
  accuracy; ranking/AUROC is unchanged — the gain is at the decision threshold.
