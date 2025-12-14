# AMD_Robotics_Hackathon_2025_SantaBot_Gift_Dispatcher

## Team Information

**Team:** versag  
**Members:** Sagar Verma  

**Summary:**  
We built a festive, kid-friendly tabletop game where children “command Santa’s robot” to pick the right colored gift from a central pile and drop it into the correct destination zone. Under the hood, we collected a compact but diverse imitation-learning dataset and trained **two policies (ACT and smolVLA2)**. The focus is robust pick-and-place under clutter and lighting variation (day/night + warm/white/blue LED sweeps) in a real hackathon environment.

**Project media (add these to `assets/`):**
- Setup / arena:  
  - `assets/IMG_8989.jpg` (full table view)  
  - `assets/IMG_8987.jpg` (ideal layout)
- Harder cluttered configurations:  
  - `assets/IMG_8981.jpg`, `assets/IMG_8984.jpg`, `assets/IMG_8985.jpg`, `assets/IMG_8988.jpg`
- *Optional:* add a short demo video: `assets/demo.mp4` or `assets/demo.gif`

Example embeds:

```md
![SantaBot arena](assets/IMG_8989.jpg)

![Ideal setup](assets/IMG_8987.jpg)

![Hard configuration](assets/IMG_8985.jpg)
```

---

## Submission Details

### 1. Mission Description

**Mission:** *Elf-Rescue Gift Delivery*

It's December, Santa needs help delivering gifts, and the elves had too much mulled wine. Kids act as dispatchers: they choose which gift color must be delivered next, and SantaBot executes the pick-and-drop.

**Real-world application:**

This maps directly to real pick-and-place logistics: **sorting items into bins/zones based on an instruction**. The "kid game" framing makes it fun and approachable, while the underlying behavior is the same primitive needed for warehouse kitting, tabletop sorting, and bin packing.

**Arena (v1 – what I built and tested):**

* A static grid board with many white squares and a distributed set of colored squares (red, orange, yellow, green, dark-blue).

* A central "gift pile" region where LEGO-like blocks start in random poses and clutter.

* Target zones are colored squares on the board.

**Instruction / prompt mapping used in the dataset (consumed by smolVLA2):**

* `pick red cube and put in red square`

* `pick orange cube and put in orange square`

* `pick brown cube and put in yellow square`

* `pick light-blue cube and put in green square`

* `pick dark-blue cube and put in dark-blue square`

(We intentionally include a few "non-identical" mappings like brown→yellow and light-blue→green to verify instruction-following behavior rather than only color matching.)

---

### 2. Creativity

**What is novel or unique in the approach?**

* A **Christmas-themed "Santa logistics" game** that makes robotics approachable for kids while still being a real-world manipulation problem.

* A deliberately "hackathon-realistic" setup: clutter, imperfect placements, varied object orientations, and major lighting variation.

* Training and comparing **two imitation learning approaches (ACT vs smolVLA2)** on the same task.

**Innovation in design / methodology / application**

* Dataset intentionally includes:

  * easy/ideal layouts

  * difficult layouts (tight packing, occlusions, long side up)

  * both night + day domains to reduce illumination bias

---

### 3. Technical implementations

#### Teleoperation / Dataset capture

* **305 episodes**, each **~10–12 seconds**

* **145 night-time** episodes with overhead LED lighting cycled across:

  * warm

  * white

  * blue

    (collection-level augmentation)

* **160 daytime** episodes to avoid day/night bias

* Objects: LEGO-like blocks with varied shapes/orientations:

  * red, orange, brown, light-blue, dark-blue

* Scenarios include both:

  * "ideal" configurations

  * "hard" configurations (tight clustering, occlusions, long side up)

*<Image/video of teleoperation or dataset capture>*

```md
![Arena + objects](assets/IMG_8987.jpg)

![Hard clutter](assets/IMG_8984.jpg)
```

#### Training

* Trained **two policies**:

  * **ACT** (behavior cloning baseline)

  * **smolVLA2** (instruction-conditioned policy using the prompts above)

* Trained separate variants:

  * **night-only**

  * **day-only**

* Next step (planned): **combined day+night** training.

#### Inference

* At runtime, the user provides an instruction corresponding to the next "gift" to deliver (via deterministic UI like keyboard/buttons — not voice due to hackathon noise).

* The policy executes: approach → grasp → move → drop → reset.

*<Image/video of inference eval>*

```md
![Inference scene](assets/IMG_8981.jpg)
```

---

### 4. Ease of use

**How generalizable is the implementation across tasks or environments?**

* The command format is minimal and human-friendly:

  **"pick `<object>` and put in `<target>`"**

* The same pipeline extends to:

  * new object colors/shapes

  * new target zones (bins, squares, "chimneys")

  * new board layouts (as long as reachable and visible)

**Flexibility and adaptability**

* Adding new "gift types" is straightforward: collect additional demos for the new instruction and fine-tune.

* Dataset already includes substantial variation (pose, clutter, illumination), which supports better real-world robustness.

**Types of commands or interfaces needed**

* Avoid voice (noisy hackathon). Use:

  * keyboard shortcuts

  * on-screen color buttons

  * optional physical colored buttons (best for public demos)

---

## Results / Observations

### Policy performance (ACT vs smolVLA2)

* **ACT worked well out-of-the-box** for this tabletop pick-and-place setting.

  * It reliably picks objects and moves toward the intended target region.

* **smolVLA2 did not work reliably in the current setup**.

  * In evaluation, it often fails early and is **not able to consistently reach the correct colored LEGO block**, suggesting additional tuning is needed (prompt formatting, dataset balance, training hyperparameters, or model/config alignment).

### Current limitation (placement accuracy)

* With **ACT**, the main remaining issue is **final placement precision**:

  * The policy often drops the object **near the correct destination square**, but occasionally in a **neighboring square** (off by ~1 cell).

* Likely next improvements:

  * **more demonstrations** emphasizing the final approach and precise placement

  * **tuning** (e.g., action scaling, control smoothing, curriculum focusing on placement)

---

## Why this matters (real-world relevance)

Even though the demo is framed as a Christmas/kids game, the underlying task is a realistic version of **sorting and placement under real-world complexity**:

* cluttered scenes (tight packing)

* varied object orientations (long side up)

* strong lighting shifts (day vs night; warm/white/blue LED)

* instruction-conditioned sorting (object-to-target mapping)

This closely relates to:

* warehouse kitting and sorting

* tabletop logistics

* bin packing / routing

* general human-in-the-loop manipulation primitives

---

## Motivation

My original motivation was to introduce **bin packing and color sorting** as a fun, interactive game for kids using **LeRobot**:

* kids issue simple dispatch commands (which gift to deliver next)

* the robot performs the pick-and-place

* the game naturally teaches the idea of sorting + routing (logistics) through play

---

## Scope of this hackathon demo

This submission is intentionally scoped to the **core engineering challenge**:

* dataset capture (teleop episodes under diverse conditions)

* training and comparing policies (ACT vs smolVLA2)

* analyzing failure modes and what it takes to close the gap for a robust public-facing game

In other words: this is a credible step toward a kid-friendly sorting game, and it highlights the practical gap between "works in controlled conditions" and "works reliably in the wild."

## Additional Links
*For example, you can provide links to:*

- *Link to a video of your robot performing the task*
- *URL of your dataset in Hugging Face*
- *URL of your model in Hugging Face*
- *Link to a blog post describing your work*

## Code submission

This is the directory tree of this repo, you need to fill in the `mission` directory with your submission details.

```terminal
AMD_Robotics_Hackathon_2025_ProjectTemplate-main/
├── README.md
└── mission
    ├── code
    │   └── <code and script>
    └── wandb
        └── <latest run directory copied from wandb of your training job>
```


The `latest-run` is generated by wandb for your training job. Please copy it into the wandb sub directory of you Hackathon Repo.

The whole dir of `latest-run` will look like below:

```terminal
$ tree outputs/train/smolvla_so101_2cube_30k_steps/wandb/
outputs/train/smolvla_so101_2cube_30k_steps/wandb/
├── debug-internal.log -> run-20251029_063411-tz1cpo59/logs/debug-internal.log
├── debug.log -> run-20251029_063411-tz1cpo59/logs/debug.log
├── latest-run -> run-20251029_063411-tz1cpo59
└── run-20251029_063411-tz1cpo59
    ├── files
    │   ├── config.yaml
    │   ├── output.log
    │   ├── requirements.txt
    │   ├── wandb-metadata.json
    │   └── wandb-summary.json
    ├── logs
    │   ├── debug-core.log -> /dataset/.cache/wandb/logs/core-debug-20251029_063411.log
    │   ├── debug-internal.log
    │   └── debug.log
    ├── run-tz1cpo59.wandb
    └── tmp
        └── code
```

**NOTES**

1. The `latest-run` is the soft link, please make sure to copy the real target directory it linked with all sub dirs and files.
2. Only provide (upload) the wandb of your last success pre-trained model for the Mission.
# AMD_Hackthon_2025_team22
