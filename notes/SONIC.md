2025 Dec 4 [cs.RO] arXiv:2511.07820v2

![NVIDIA logo](page_1_image_1_v2.jpg)

2025-12-8

# SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

Zhengyi Luo<sup>†</sup>, Ye Yuan<sup>†</sup>, Tingwu Wang<sup>†</sup>, Chenran Li<sup>†</sup>, Sirui Chen<sup>*</sup>, Fernando Castañeda<sup>*</sup>, Zi-Ang Cao<sup>*</sup>, Jiefeng Li<sup>*</sup>, David Minor<sup>*</sup>, Qingwei Ben<sup>*</sup>, Xingye Da<sup>*</sup>, Runyu Ding, Cyrus Hogg, Lina Song, Edy Lim, Eugene Jeong, Tairan He, Haoru Xue, Wenli Xiao, Zi Wang, Simon Yuen, Jan Kautz, Yan Chang, Umar Iqbal, Linxi "Jim" Fan<sup>‡</sup>, Yuke Zhu<sup>‡</sup>

Nvidia

<sup>†</sup> Co-First Authors

<sup>*</sup> Core Contributors

<sup>‡</sup> Project Leads

https://nvlabs.github.io/SONIC/

### Abstract

Despite the rise of billion-parameter foundation models trained across thousands of GPUs, similar scaling gains have not been shown for humanoid control. Current neural controllers for humanoids remain modest in size, target a limited set of behaviors, and are trained on a handful of GPUs over several days. We show that scaling up model capacity, data, and compute yields a generalist humanoid controller capable of creating natural and robust whole-body movements. Specifically, we posit motion tracking as a natural and scalable task for humanoid control, leveraging dense supervision from diverse motion-capture data to acquire human motion priors without manual reward engineering. We build a foundation model for motion tracking by scaling along three axes: network size (from 1.2M to 42M parameters), dataset volume (over 100M frames, 700 hours of high-quality motion data), and compute (9k GPU hours). Beyond demonstrating the benefits of scale, we show the practical utility of our model through two mechanisms: (1) a real-time universal kinematic planner that bridges motion tracking to downstream task execution, enabling natural and interactive control, and (2) a unified token space that supports various motion input interfaces, such as VR teleoperation devices, human videos, and vision-language-action (VLA) models, all using the same policy. Scaling motion tracking exhibits favorable properties: performance improves steadily with increased compute and data diversity, and learned representations generalize to unseen motions, establishing motion tracking at scale as a practical foundation for humanoid control.

### 1. Introduction

The past decade has witnessed a remarkable journey in artificial intelligence: the GPT (Achiam et al., 2023) family of models are trained on 25,000+ GPUs with trillions of tokens; video and image-generation models (Blattmann et al., 2023; Brooks et al., 2024; Ho et al., 2022; Ramesh et al., 2022; Rombach et al., 2022) leverage thousands of GPUs processing billions of images. These foundation models have shown a consistent pattern: scale unlocks emergent capabilities, generalization, and robustness that smaller models cannot achieve (Bommasani et al., 2021; Hoffmann et al., 2022; Kaplan et al., 2020; Wei et al., 2022). Yet for sim-to-real humanoid control, similar scaling gains have not been achieved. State-of-the-art humanoid control policies are typically small neural networks – often three-layer MLPs with a few million parameters – trained on a single GPU over a few days for a single task. Even more so, due to the manually engineered reward terms for each task, training a policy for too long may even lead to worse performance (Peng et al., 2018, 2021; Sutton, 2019).

Why hasn’t humanoid control scaled? The fundamental issue is the task selection. Tasks like locomotion require

© 2025 NVIDIA. All rights reserved.

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![A collage of images showing a humanoid robot performing various tasks such as human video teleoperation, VR teleoperation with whole body, kinematic planning, VR teleoperation with keypoints, text control, music control, and VLA integration.](page_2_image_1_v2.jpg)

Figure 1: SONIC enables diverse humanoid tasks through a universal control policy that handles diverse input modalities and control interfaces.

extensive reward engineering for each scenario – walking naturally forward provides little signal for dancing (He et al., 2025), getting up from the ground (He et al., 2025; Huang et al., 2025), or teleoperation (Ben et al., 2025; Li et al., 2025; Ze et al., 2025). Each new capability demands redesigned rewards and objectives, making scaling up difficult. Even if we identify a scalable objective that can learn diverse behaviors, a second challenge emerges: how do we support the diverse range of real-world applications? A desired humanoid controller should handle teleoperation, goal-directed tasks, navigation, and even vision-language commands (Ahn et al., 2022; Brohan et al., 2022, 2023; Ma et al., 2024; Open X-Embodiment Collaboration, 2023). Building a system that scales while remaining flexible for different task specifications is non-trivial.

In this work, we address both challenges by identifying motion tracking as the scalable foundational task for humanoid control. Motion tracking leverages human motion capture data, which provides dense, frame-by-frame supervision without reward engineering. Critically, humanoids benefit from decades of motion capture research – datasets covering walking, running, dancing, sports, and object interactions already exist at scale (Li et al., 2021; Mahmood et al., 2019; Punnakkal et al., 2021). While there exists prior art in motion tracking (Chen et al., 2025; He et al., 2024, 2025; Liao et al., 2025; Luo et al., 2023; Wang et al., 2020; Yin et al., 2025; Zeng et al., 2025; Zhang et al., 2025), they are mostly limited to showing whole-body motion tracking results on **training data** and have not demonstrated many downstream tasks beyond motion tracking or navigation. We supersize physics-based motion tracking to unprecedented 100 million frames (at 50 fps) and 128 GPUs training, achieving universal tracking capabilities across diverse human behaviors while maintaining real-time performance. In addition, we show how such a motion tracker can be applied to meaningful downstream

2

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

tasks, and introduce two key contributions. First, we develop a universal kinematic motion generation system for interactive control, enabling goal-directed tasks such as interactive locomotion and game-like character control through kinematic planning in motion space. Second, we design a universal token space that supports multimodal control – accepting inputs from teleoperation, human videos, music, text, and vision-language-action models through a unified interface (<mark>Kocabas et al., 2020</mark>; <mark>Li et al., 2021</mark>; <mark>Tevet et al., 2022</mark>; <mark>Zhang et al., 2023</mark>). This unified framework allows our motion tracker to directly interface with vision-language-action (VLA) models (<mark>Bjorck et al., 2025</mark>) and diverse control modalities.

We propose *<mark>S</mark>upersizing m<mark>O</mark>tion tracking for <mark>N</mark>atural humano<mark>I</mark>d <mark>C</mark>ontrol* (SONIC), a framework that enables natural humanoid control across a wide range of applications. We achieve high-precision teleoperation and interactive control capabilities, including running, jumping, and crawling with natural human-like movement. Leveraging our universal token space, our controller can support cross-embodiment motion tracking where estimated whole-body human motion can be directly mapped to humanoid control signals, bypassing the need for retargeting. We demonstrate seamless integration with multi-modal human motion generation models, supporting video, text, and music control through our universal token space. Furthermore, we show that teleoperation data collected through our system can be used to train vision-language-action foundation models, establishing a complete pipeline from motion tracking at scale to foundation model-based humanoid control. These results validate that massive-scale motion tracking serves as a practical and versatile foundational task for diverse real-world humanoid applications.

Our contributions are:

* We identify motion tracking as a scalable foundational task for humanoid control, demonstrating that it exhibits favorable scaling properties with both compute and data diversity. We scale up humanoid control to 9,000 GPU hours and 100 million frames of motion sequences, achieving universal tracking capabilities across diverse human behaviors.

* We introduce a kinematic motion generation system for interactive control and a universal token space supporting multimodal inputs, including teleoperation, human videos, motion commands, and VLA foundation models through a single-stage training process without distillation.

* We provide a comprehensive evaluation demonstrating empirical humanoid scaling trend, zero-shot transfer to unseen motions, robust sim-to-real deployment on physical humanoid robots, and successful integration with foundation models.

# 2. Results

We use the Unitree G1 humanoid (<mark>Unitree, 2024</mark>) to demonstrate our supersizing humanoid motion tracking framework, SONIC. Video results can be seen at <mark>our website</mark>. We demonstrate SONIC’s ability for motion tracking (<mark>Sec. 2.1</mark>), teleoperation (<mark>Sec. 2.4</mark>), multi-modal control (<mark>Sec. 2.3</mark>), and interactive kinematic motion planning (<mark>Sec. 2.2</mark>), as seen in <mark>Fig. 1</mark>.

## 2.1. Motion Tracking

SONIC, trained on 100 million frames of motion over 32,000 GPU hours (128 GPUs over 3 days), exhibits remarkable generalization to **unseen** motions. In this section, we evaluate the generalization capabilities of our tracker on large-scale, previously unseen motion datasets in simulation and the real world.

**Metrics.** We employ a comprehensive set of pose-based and physics-based metrics to measure motion imitation performance. The primary measure is the success rate (Succ), where an imitation attempt is deemed unsuccessful if the humanoid deviates too far from the reference motion trajectory. We further report the root-relative mean per-joint euclidean position error (MPJPE) $E_{\text{mpjpe}}$ (in mm), quantifying the local accuracy of the imitation. To assess physical fidelity, we also calculate differences in acceleration ($E_{\text{acc}}$, mm/frame<sup>2</sup>) and velocity ($E_{\text{vel}}$, mm/frame) between the simulated humanoid and the reference human motion.

3

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![Scatter plot showing the effect of scaling data size on success rate and MPJPE. Larger datasets (100m frames) show higher success rates and lower MPJPE.](page_4_image_1_v2.jpg)

![Scatter plot showing the effect of scaling model size on success rate and MPJPE. Larger models (42m parameters) show higher success rates and lower MPJPE.](page_4_image_2_v2.jpg)

![Scatter plot showing the effect of scaling GPU hours on success rate and MPJPE. More compute (9K GPU hours) leads to higher success rates and lower MPJPE.](page_4_image_3_v2.jpg)


<table>
  <tbody>
    <tr>
        <td>Method</td>
        <td>Success Rate (%)</td>
        <td>MPJPE</td>
        <td>Velocity Distance</td>
        <td>Acceleration Distance</td>
    </tr>
    <tr>
        <td>Any2Track</td>
        <td>58.3</td>
        <td>202.3</td>
        <td>14.9</td>
        <td>6.1</td>
    </tr>
    <tr>
        <td>BeyondMimic</td>
        <td>94.3</td>
        <td>57.4</td>
        <td>9.1</td>
        <td>2.5</td>
    </tr>
    <tr>
        <td>GMT</td>
        <td>84.2</td>
        <td>65.0</td>
        <td>12.7</td>
        <td>4.9</td>
    </tr>
    <tr>
        <td>Ours</td>
        <td>99.6</td>
        <td>42.7</td>
        <td>4.1</td>
        <td>1.2</td>
    </tr>
    <tr>
        <td>Ours (real)</td>
        <td> </td>
        <td>40.9</td>
        <td> </td>
        <td> </td>
    </tr>
  </tbody>
</table>

Figure 2: (a-c) Effect of scaling to different sizes of dataset, model, and compute. Mean per joint position error (MPJPE) indicates motion imitation error; lower is better. For (a), we measure the dataset size in millions of frames. (d-g) Comparing our method with baselines on tracking out-of-distribution motion sequences. (d) Success rate of tracking. (e-g) Different tracking accuracy metrics are evaluated on trajectories that are successfully tracked.

Our evaluation is conducted on a uniformly random subset of retargeted AMASS (<mark>Mahmood et al., 2019</mark>) data (9 hours, 1,602 trajectories), as used in TWIST (<mark>Ze et al., 2025</mark>). Notably, our test set is orders of magnitude larger than those in prior work (<mark>Zeng et al., 2025</mark>) and comparable in scale to some existing training sets. Importantly, SONIC is not trained on the AMASS dataset, underscoring the robustness of its generalization.

**Scaling Up Motion Tracking.** In <mark>Fig. 2</mark>, we analyze the impact of supersizing our humanoid motion tracking system along three key dimensions in simulation and real-world: GPU hours, model size, and motion dataset size. All evaluations are conducted in Isaac Lab (<mark>NVIDIA et al., 2025</mark>), with models trained to convergence over 3 to 7 days. For dataset size, we compare with training on LaFAN (0.4M frames), a subset of our in-house dataset (7.4M frames), and our full dataset (100M frames). For GPUs hours comparison, we train all models to convergence using 8, 32, and 128 GPUs. Across the board, scaling along any of these three axes leads to consistent improvements in motion imitation performance. Notably, increasing the size of the motion dataset yields the most substantial gains, while increased model size and compute (GPU hours) further enhance results. Notice that, for GPUs hours, parallelizing across more GPUs (e.g., 8 vs 128) is essential, as training on a smaller number of GPUs yields worse asymptotic performance than on a larger number of GPUs. For evaluation, motion imitation is considered unsuccessful if, at any point during tracking, the humanoid’s body height deviates by more than 0.25m from the reference motion or if the root orientation differs by more than 1 radian.

**Comparison with Baselines.** We demonstrate that our approach yields a universal motion tracker capable of accurately tracking a wide range of unseen motions. In <mark>Fig. 2</mark>, we compare our method to state-of-the-art trackers — Any2Track (<mark>Zhang et al., 2025</mark>), BeyondMimic (<mark>Liao et al., 2025</mark>), and GMT (<mark>Chen et al., 2025</mark>). The baselines are trained on different datasets (Any2Track and BeyondMimic on LaFAN; GMT on AMASS) but are all evaluated on the same unseen dataset for consistency. We use the officially released models when available (GMT) and use the publicly released code to train the respective models (Any2Track and BeyondMimic) when

4

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

not. To ensure a fair comparison, all evaluations are performed in MuJoCo (<mark>Todorov et al., 2012</mark>), which is supported by all baseline implementations. For these experiments, we adopt a more relaxed termination criterion to better reflect real-world deployment scenarios: imitation is only considered unsuccessful if the humanoid falls, defined as its root height deviating by more than 0.25m from the reference. Across all evaluation metrics, our method significantly outperforms the baselines, achieving higher success rates and improved tracking accuracy on unseen motion sequences.

**Real-World Evaluation.** We assess the real-world performance of SONIC by deploying it on 50 diverse motion trajectories, including dance, jumps, and loco-manipulation motions. As presented in <mark>Fig. 2</mark>, our policy achieves motion imitation in the real world that closely matches its simulation results, operating in a true zero-shot manner. Remarkably, it succeeds on all sequences without a single failure (100% success rate), underscoring the robustness and reliability of our tracker in challenging real-world scenarios.

## 2.2. Interactive Motion Control

In this section, we showcase the scalability and robustness of SONIC in whole-body, real-time interactive control tasks. We present a kinematic runtime generative motion planner that guides the robot's policy through user interaction. Our approach employs an autoregressive framework that continually regenerates future kinematic motions conditioned on the previous states and incoming user commands. For each planning step, the model generates motion segments lasting between 0.8s and 2.4s, where the duration is automatically determined by the neural planner to maximize flexibility and robustness. The planner achieves inference times under 5 ms on a standard laptop and 12 ms on a Jetson Orin GPU. Replanning is triggered as frequently as every 100 ms, or immediately when user commands are updated, ensuring highly responsive control.

SONIC supports a variety of applications, including but not limited to: (1) navigation control with arbitrary velocity, direction, and style commands; (2) interactive entertainment tasks such as boxing; (3) locomotion skills such as squatting, crawling, kneeling, etc., which are useful for downstream applications like teleoperation. Because both our kinematic planner and tracking policy are trained on the same large-scale dataset. Utilizing the scalable nature of SONIC, we note that all the applications above were designed afterwards without retraining the planner or the tracking policy. People with minimal animation or programming backgrounds can easily design and specify new desired behaviors.

For navigation control, SONIC supports velocity commands ranging from 0.0m/s to 6.0m/s, as well as arbitrary direction commands spanning 0 to 360 degrees. We employ a critically damped spring model to smooth impractical commands that cannot be achieved by the robot within one motion segment. SONIC achieves scalable, responsive, and robust navigation control, as shown in the first two rows of <mark>Fig. 3</mark>. SONIC also supports different styles such as drunken walking, injured walking, happy walking, stealth walking, etc., as shown in the third row of <mark>Fig. 3</mark>. The capacity of the model to generate robust inbetweening motions showcases the flexibility of SONIC, and the potential of more natural human-robot interaction.

SONIC further extends its versatility to interactive entertainment tasks such as boxing, as illustrated in the last two rows of <mark>Fig. 3</mark>. Existing academic solutions (<mark>Starke et al., 2021</mark>; <mark>Won et al., 2021</mark>) and industrial approaches (<mark>Unitree, 2025</mark>) often utilize a limited collection of boxing clips, requiring a switch between multiple expert models or action labels. This approach leads to discontinuous, unnatural transitions and even pauses. SONIC, on the other hand, enables much more fluid, responsive, and natural motion generation while retaining the robot's full freedom of movement throughout the task.

To enable downstream manipulation or navigation in confined environments, skills such as squatting, kneeling, and crawling are essential. As illustrated in <mark>Fig. 4</mark>, SONIC supports including squatting, kneeling, and crawling. For squatting and kneeling, we slow the pelvis height to be smoothly controlled from 0.3m to 0.8m. For navigation in especially tight spaces, SONIC also enables crawling. The robot can move omnidirectionally using its elbows and knees at velocities from 0.0m/s to 0.5m/s.

5

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![A composite image showing a humanoid robot performing various motions. The top section shows a sequence of movements labeled forward, backward, sideway, and running on a grid. The middle section shows snapshots of walking, sideway, and running styles, as well as emotional/physical states like happy, stealth, and injured. The bottom section shows a sequence of boxing moves including idle, left jab, block, right jab, left hook, right hook, and stance, followed by individual snapshots of these boxing stances.](page_6_image_1_v2.jpg)

Figure 3: Top three rows: interactive navigation switching between different velocities, directions, and styles. Bottom two rows: SONIC produces high-quality and responsive boxing motions while preserving the robot’s complete freedom of movement throughout the task.

## 2.3. Video Teleoperation and Multi-Modal Cross-Embodiment Control

As shown in <mark>Fig. 5</mark> (top), SONIC also demonstrates a real-time, multimodal, cross-embodiment control framework, enabled by our universal control policy. A unified motion generation system based on GENMO (<mark>Li et al., 2025</mark>) is designed to generate human motions from three input modalities: human demonstration video, natural-

6

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![Composite image showing a humanoid robot performing various motions: a sequence of kneeling, crawling, and getting up on a grid background; and real-world environment photos of the robot kneeling on one leg, squatting, kneeling on two legs, hand crawling, elbow crawling, and crawling forward under an obstacle.](page_7_image_1_v2.jpg)

Figure 4: Interactive squatting, kneeling, and crawling. With SONIC, the robot can squat, kneel, and crawl at arbitrary heights, enabling seamless application in real-world downstream scenarios such as teleoperation and navigation in complex environments.

language commands, and music audio. Transitions among modalities are coordinated through the multimodal motion generation system, enabling smooth handoffs without reinitialization.

**Video Teleoperation.** For video control, the system supports both pre-recorded clips and live monocular webcam streams. Human motion is estimated at $\ge 60$ frames per second (fps), enabling interactive teleoperation without specialized motion-capture hardware. Video control provides a higher-fidelity specification of pose and timing, yielding a precise imitation of demonstrated movements.

**Music and Text Control.** For text control, the system accepts natural-language prompts and synthesizes target motions at $\ge 60$ fps. Trained on a large-scale dataset, the policy executes previously unseen instructions in a zero-shot manner. An interactive graphical interface supports free-form prompting at any time with immediate on-robot responses (for example, “walk forward”, “kick left foot”, or “dance like a monkey”).

For music control, GENMO generates dance motions (which our tracking policy imitates) conditioned on melodic and rhythmic structure, tracking tempo, and adapting style to musical characteristics.

Our system supports seamless transitions between modalities. For example, users can initiate fine-grained control via video, switch to text for general control, and finally hand off to music for performance.

7

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![A composite image showing three control regimes for a humanoid robot: Video Teleoperation (top timeline), Text and Music Control (middle timeline with text prompts "Acts like a monkey" and "Punches with his left arm"), and VR Whole-Body Teleoperation (bottom grid showing various actions like side reach, front reach, one-leg kneel, deliver, open door, crawl, 360-spin landing, Kung-fu, two-leg kneel, floor roll, side step, and walk).](page_8_image_1_v2.jpg)

Figure 5: Video teleoperation, multi-modal control, and VR whole-body teleoperation.

## 2.4. VR-Based Teleoperation and Connecting to Foundation Models

We present three additional control regimes built on our universal motion tracker and token space: (1) Virtual Reality (VR)-based whole-body teleoperation for full-pose control, (2) VR-based 3-point teleoperation for efficient data collection, and (3) foundation-model-driven mobile manipulation, where a VLA autonomously controls the humanoid. While the teleoperation solutions presented in this section focus on VR-based interfaces, the same universal token-space supports video-based teleoperation; see Sec. 2.3.

### 2.4.1. VR-Based Whole-Body Teleoperation

We develop a full-body VR teleoperation system using the PICO whole-body motion-tracking interface Zhao et al. (2025). This requires wearing the PICO headset, two ankle trackers, and the handheld VR controllers. The PICO interface then provides human motion as full-body human pose estimates in SMPL (Loper et al., 2015) format. The tracked human motion is streamed in real time to our universal control policy, which will be introduced in Sec. 3.2. The human motion will be encoded via its respective encoder into the universal token space, and then decoded by the robot control decoder to yield low-latency, stable, human-like control, as can be seen in Fig. 5 (bottom).

8

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![Sequence of screenshots showing a Unitree G1 humanoid robot performing an apple-to-plate mobile manipulation task over time.](page_9_image_1_v2.jpg)

Figure 6: Apple-to-plate mobile bimanual manipulation on the Unitree G1 humanoid robot controlled by a fine-tuned GR00T N1.5 vision-language-action (VLA) model. The VLA emits teleoperation-format commands—poses of head and wrists, base height, and a navigation command—which are executed by SONIC. The model is fine-tuned on 300 VR-teleoperated trajectories and attains 95% success over 20 trials on this proof-of-concept task, demonstrating compatibility between foundation-model planning and our universal control policy.

### 2.4.2. VR-Based 3-Point Teleoperation

To enable scalable and portable data collection for tasks that do not require precise foot placement, we also introduce a lightweight mobile bimanual VR teleoperation interface that operates with the PICO headset and two handheld controllers (no ankle trackers are needed for this mode). The teleoperation interface outputs a compact command consisting of three upper-body SE(3) poses (head and both wrists), finger joint angles, waist height, a locomotion mode (slow walk or fast walk), and a navigation command specifying the desired root velocity and heading. These signals are fed into the kinematic motion planner (of <mark>Sec. 3.3</mark>) and hybrid encoder (introduced in <mark>Sec. 3.2</mark>), and then executed by the universal tracking policy.

We use this interface to collect 300 teleoperated demonstrations of a mobile pick-and-place task: the robot walks to a randomly placed apple on a table, grasps it with the right hand, and places it on a randomly positioned plate. This dataset serves as supervision for autonomous control with a vision-language-action (VLA) model in <mark>Sec. 2.4.3</mark>.

For this mobile manipulation task, teleoperation real-time tracking performance is reported for the right wrist only, since the left wrist remains largely stationary. Over 300 teleoperated trajectories, we measure the latency and tracking error from the right wrist target pose command to the realized wrist pose on the robot, with both quantities expressed in the waist frame. The pipeline exhibits a mean latency of 121.9 ms. The mean right-wrist position error is 6 cm with a 95th percentile of 13.3 cm, and the mean orientation error is 0.145 rad (8.32°) with a 95th percentile of 0.267 rad (15.31°). Position error is the Euclidean norm and orientation error is the geodesic angle on SO(3).

### 2.4.3. Foundation-Model-Driven Mobile Bimanual Manipulation

To demonstrate autonomous control through the same universal token interface, we connect a VLA foundation model to the pipeline used for teleoperation. Using the 300 trajectories collected with the 3-point teleoperation interface, we fine-tune a GR00T N1.5 model (<mark>Bjorck et al., 2025,</mark>) and evaluate it on the apple-to-plate mobile pick-and-place task described above (<mark>Fig. 6</mark>). The VLA outputs the same teleoperation-format control signals—three upper-body poses (head and both wrists), base (waist) height, and a navigation command (root linear and angular velocity)—which are then fed into the kinematic planner and hybrid encoder, and then executed via the universal control policy. On this proof-of-concept task, the system attains a 95% success rate over 20 trials, indicating that the universal motion tracker serves as a robust System 1 controller (fast, reactive whole-body skills) that complements the VLA’s System 2 capabilities (slower, deliberative reasoning) (<mark>Kahneman, 2011</mark>). This experiment is intended only to establish compatibility between foundation-model planning and our motion-tracking controller, not to claim broad generalization; scaling to richer task distributions is left for

9

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

future work. Looking ahead, interfacing the VLA with the universal token space offers a path toward high-level, whole-body reasoning layered atop the responsiveness, robustness, and human-motion inductive biases of the universal tracker, which is able to operate at substantially higher control rates. Exploring this integration at scale is an important direction for future work.

## 2.5. Discussion

We cast motion tracking as the core scalable task for learning a single, versatile humanoid controller. By training SONIC on 100 million+ motion frames with up to 128 GPUs, we obtain a single policy that produces natural, robust whole-body behaviors across diverse conditions. Equally important, we build the practical system that makes tracking usable in real deployments: a real-time kinematic motion planner that converts intent into short-horizon reference motions, and a universal token space that unifies heterogeneous interfaces (teleoperation, video, text, and music) within one policy.

We observe consistent improvements as data, model capacity, and compute increase, with generalization to unseen motions in simulation and real-world deployments. These findings support motion tracking as a practical route to acquire broad, transferable whole-body priors without per-task reward engineering.

Relative to prior trackers such as Any2Track (<mark>Zhang et al., 2025</mark>), BeyondMimic (<mark>Liao et al., 2025</mark>), and GMT (<mark>Chen et al., 2025</mark>), our system advances the state of the art along three dimensions: (i) we train on motion data that is orders of magnitude larger than existing systems and evaluate on substantially broader, previously unseen datasets; (ii) via a shared latent command space that unifies hybrid input commands to enable multi-modal control using a unified tracking policy; and (iii) our universal kinematic planner that bridges the gap between real-world user-demands and our tracking policies. These components collectively move motion tracking from demonstration-specific imitation toward a general foundation for humanoid control.

Limitations include the formal treatment of safety, compliance, and energy efficiency for extended deployments on the humanoid, as well as handling noisy input during deployments. Future work will study scaling laws across more diverse dataset, enable VLA instructed whole-body locomanipulation tasks, and explore joint training of planner, tokenizer, and policy to reduce modality gaps.

In summary, scaling motion tracking yields reliable, general whole-body control; pairing it with a planner, a universal token space, and an efficient onboard stack makes it usable as a system. We expect SONIC to serve as a practical foundation upon which higher-level perception and reasoning can be built to advance general-purpose humanoid autonomy.

# 3. Materials and Methods

## 3.1. Humanoid Motion Dataset

Our motion dataset is built from a large-scale motion-capture corpus comprising recordings from 170 human subjects. The participants include a balanced mix of male and female actors, with body heights ranging from 145 cm to 199 cm (mean = 174.3 cm, std = 10.9 cm), approximately following a normal distribution. The dataset spans a broad spectrum of everyday human behaviors, including locomotion, daily activities, gesturing, and a diverse set of combat motions with varied stylistic expressions. Clip durations range from 1 to 180 seconds. In total, the collection covers thousands of unique motion behaviors, with most actions performed by multiple subjects across multiple takes, providing rich intra- and inter-subject variation, as can be seen in <mark>Fig. 7</mark>. Our in-house dataset contains 700 hours of human motion, resulting in 100+ million frames at 50Hz. The human motion retargeted is adapted from GMR (<mark>Araujo et al., 2025</mark>) and PyRoki (<mark>Kim* et al., 2025</mark>).

## 3.2. Universal Humanoid Motion Tracking

<mark>Fig. 8</mark> provides an overview of our approach, SONIC, a universal humanoid motion tracking framework that employs a unified control policy to track diverse motion commands across different embodiments. A key

10

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![A grid of 11x10 small images showing a humanoid robot in various poses and motions, such as standing, walking, crouching, and falling.](page_11_image_1_v2.jpg)

Figure 7: Random samples from our motion dataset.

innovation is its ability to seamlessly handle robot motion, human motion, and hybrid motion (combining upper-body keypoints with lower-body robot motions) through a shared latent representation. This cross-embodiment capability enables the robot to learn from motion captured and raw video data, bridging the morphological gap between human and robot embodiments. We use various motion generators – kinematic motion planner, VR motion generator, human motion generator (GENMO) – to generate motion commands, which enable diverse applications including interactive gamepad control, VR 3-point teleoperation, whole-body teleoperation, video-based teleoperation, and multi-modal control from text and music.

11

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

![Diagram showing the SONIC universal control policy architecture, mapping various tasks and motion generators through specialized encoders to a universal token that drives robot control and motion decoders.](page_12_image_1_v2.jpg)

Figure 8: **SONIC enables universal humanoid motion tracking through a universal control policy that handles diverse motion commands and modalities.** Specialized encoders process robot, human, and hybrid motion commands into a universal token that drives robot control and motion decoders. This cross-embodiment design supports diverse applications including gamepad control, VR teleoperation, whole-body teleoperation, video teleoperation, and multi-modal control from text and music.

**Motion Tracking Formulation.** We formulate humanoid motion tracking as a Markov Decision Process $\mathcal{M} = \langle \mathcal{S}, \mathcal{A}, \mathcal{T}, \mathcal{R}, \gamma \rangle$, comprising state space, action space, transition function, reward function, and discount factor $\gamma$. We train the policy using proximal policy optimization (PPO) (Schulman et al., 2017) to maximize the expected cumulative discounted return $\mathbb{E} \left[ \sum_{t=1}^{T} \gamma^{t-1} r_t \right]$. Our environment design follows the general motion tracking formulation (Chen et al., 2025; He et al., 2024; Liao et al., 2025; Luo et al., 2023; Zhang et al., 2025), and we adapt the well-tuned environmental settings from (Liao et al., 2025) as the basis for scaling up humanoid motion tracking.

*States.* The state representation $s_t$ comprises two components: proprioceptive sensing $s_t^p$ and motion command $s_t^g$. Proprioceptive information $s_t^p \triangleq (q_t, \dot{q}_t, \omega_t, \psi_t, a_{t-1})$ includes joint pose $q_t$, joint velocity $\dot{q}_t$, root angular velocity $\omega_t$, gravity vector $g_t$ in the root frame, and previous action $a_{t-1}$. The motion command $s_t^g$ has three types: robot motion $g_r$, human motion $g_h$, or hybrid motion $g_m$ (combining upper-body keypoints with lower-body robot motions), where we drop the subscript $t$ for brevity. All state quantities are expressed in the robot's local heading frame to ensure rotation invariance. We use the 6D rotations representation (Zhou et al., 2019) throughout.

*Actions.* The policy $\pi$ outputs target joint positions $a_t$ as actions, which are tracked by proportional-derivative (PD) controllers at each joint. For PD gains setting, we follow prior art Liao et al. (2025); Raibert and Farshidian (2025) that proves effective in training high-quality tracking policy.

*Rewards.* We define the reward as $r_t = \mathcal{R}(s_t^p, s_t^g) + \mathcal{P}(s_t^p, a_t)$, combining tracking reward and penalty terms. The tracking term $\mathcal{R}$ minimizes errors in root position, root orientation, body link positions (relative to the root), body link orientations (relative to the root), body link linear velocities, and body link angular velocities between the robot state $s_t^p$ and the target $s_t^g$. The penalty term $\mathcal{P}$ discourages abrupt action changes, joint limit violations, and undesired contacts. Detailed reward design is presented in Table 3.

*Domain Randomization.* To enhance robustness and generalization across diverse scenarios, we apply systematic domain randomization during training. We randomize physical parameters, which include friction coefficients $(\mu_s, \mu_d)$, the restitution coefficient $(e)$, default joint positions $(q_0)$, and the base center-of-mass position. We also periodically apply random perturbations to the robot's root linear and angular velocities to simulate external pushes. Additionally, we apply motion perturbation to the target motion commands $s_t^g$ during training to improve robustness. All domain randomization parameters are detailed in Table 4.

12

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

**Universal Control Policy.** A distinguishing characteristic of our tracking framework is its ability to accommodate multiple motion command types from different embodiments through a unified encoder-decoder architecture. We accomplish cross-embodiment learning via specialized encoders that process heterogeneous inputs from both human and robot embodiments into a shared latent representation. This representation undergoes quantization to yield a *universal token*, which subsequently drives a common robot control decoder to generate motor commands. This design enables the policy to leverage motion data from diverse sources — both robot demonstrations and human motion — allowing the robot to imitate human movements despite morphological differences. An auxiliary robot motion decoder is also used to facilitate feature learning and serve as an implicit retargeting module from human to robot embodiment.

*Encoders.* Three specialized encoders process distinct motion command types: (1) robot motion encoder $\mathcal{E}_r$ encodes robot joint positions and velocities over $F_r$ future frames with a frame interval $\Delta t_r$, (2) human motion encoder $\mathcal{E}_h$ encodes 3D human joint positions (Loper et al., 2015) over $F_h$ future frames with a frame interval $\Delta t_h$, and (3) hybrid motion encoder $\mathcal{E}_m$ encodes sparse upper-body keypoints (head and hands) of the current frame (for real-time upper-body tracking), combined with lower-body robot motion over $F_m$ future frames with a frame interval $\Delta t_m$. Multi-frame inputs enable anticipatory behavior and improve the robustness of the policy. All encoders are implemented as multi-layer perceptrons (MLPs; architecture details in Table 1) that map commands $g_r, g_h, g_m$ into a shared latent space, enabling cross-embodiment representation alignment.

*Quantizer.* The encoded latent representation is quantized into a *universal token* $z$ using a vector quantizer. Specifically, we use FSQ (Mentzer et al., 2023) as our vector quantizer. The universal token is a $D_z$-dimensional vector with $L_z$ quantization levels per dimension.

*Decoders.* The *universal token* $z$ is decoded through two separate decoders. First, a robot control decoder $\mathcal{D}_c$ transforms the *universal token* into motor commands that control the robot’s joints. Second, a robot motion decoder $\mathcal{D}_r$ reconstructs the robot motion command, providing auxiliary supervision to improve the latent space and enhance feature learning. Both decoders are implemented as MLPs (Table 1).

**Training.** We prepare synchronized motion data across all three command types. Each command type $g_r, g_h, g_m$ is encoded via its respective encoder and quantized to produce universal tokens $z_r, z_h, z_m$. For each token, the control decoder $\mathcal{D}_c$ generates motor commands, while the motion decoder $\mathcal{D}_r$ reconstructs the robot motion command. The total loss comprises:

$$\mathcal{L} = \mathcal{L}_{\text{ppo}} + \mathcal{L}_{\text{recon}} + \mathcal{L}_{\text{token}} + \mathcal{L}_{\text{cycle}} \tag{1}$$

$$\mathcal{L}_{\text{recon}} = \|\mathcal{D}_r(z_r) - g_r\|^2 + \|\mathcal{D}_r(z_h) - g_r\|^2 + \|\mathcal{D}_r(z_m) - g_r\|^2 \tag{2}$$

$$\mathcal{L}_{\text{token}} = \|z_r - z_h\|^2 \tag{3}$$

$$\mathcal{L}_{\text{cycle}} = \|\mathcal{E}_r(\mathcal{D}_r(z_h)) - z_r\|^2 \tag{4}$$

where $\mathcal{L}_{\text{ppo}}$ denotes the standard PPO loss. $\mathcal{L}_{\text{recon}}$ represents the reconstruction loss for the robot motion command across different input modalities. Notably, when the input command is human motion $g_h$, the encoder-decoder acts as a retargeting pipeline from human to robot motion, and $\mathcal{L}_{\text{recon}}$ serves as a retargeting loss that enables cross-embodiment transfer. $\mathcal{L}_{\text{token}}$ measures the discrepancy between the robot token $z_r$ and the human motion token $z_h$, explicitly encouraging the encoder networks to produce aligned representations across embodiments. This loss is crucial for achieving cross-embodiment learning, as it ensures that motions from different embodiments (human vs. robot) are mapped to similar representations in the shared latent space. $\mathcal{L}_{\text{cycle}}$ is a cycle consistency loss between the original robot token $z_r$ and the token produced by re-encoding the reconstructed robot motion from the human token, i.e., $\mathcal{E}_r(\mathcal{D}_r(z_h))$. This loss further reinforces the alignment of the latent space and supports consistent cross-embodiment representation learning, ensuring that the translation from human to robot motion and back preserves the essential motion characteristics.

We employ bin-based adaptive motion sampling when selecting the initial frame for each episode. Specifically,

13

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

the entire motion dataset is partitioned into fixed-duration bins. For each bin, we calculate the corresponding failure rate $f_i$ of the policy. To prevent excessive sampling from bins with exceptionally high failure rates, the failure rate in each bin is capped at $\beta \bar{f}$, where $\beta$ is a hyperparameter and $\bar{f}$ is the average failure rate across all bins. The normalized, capped failure rates are then used to derive preliminary sampling weights $\hat{p}_i$ for each bin. The final sampling probability is defined as $p_i = \alpha \hat{p}_i + (1 - \alpha) \frac{1}{N}$, where $\alpha$ is a blending hyperparameter and $N$ is the total number of bins. This formulation balances targeted sampling of challenging bins with uniform coverage. A bin is selected according to $p_i$, and the initial frame is then sampled uniformly from within the chosen bin. We train our motion tracker using distributed training powered by <mark>Gugger et al. (2022)</mark> and <mark>von Werra et al. (2020)</mark> across multiple compute nodes. All models are trained using Isaac Lab (<mark>NVIDIA et al., 2025</mark>) as the simulation platform. Training hyperparameters are provided in Table 2.

**Tasks and Applications.** The universal motion tracking framework enables a wide range of applications:

1. *Interactive Gamepad Control*: Users intuitively control the humanoid via gamepad inputs. A generative kinematic motion planner, introduced in Section <mark>3.3</mark>, transforms user commands such as velocities, styles into diverse robot motions. The universal control policy tracks these motions through the robot motion encoder $\mathcal{E}_r$.
2. *VR 3-Point Teleoperation*: Users operate the humanoid using a PICO VR headset <mark>Zhao et al. (2025)</mark> and handheld controllers, which provide head and wrist SE(3) pose data. We also use the joysticks of the controllers to set a desired navigation command (linear and angular root velocity) and root height. The kinematic motion planner generates the lower-body motions, resulting in a hybrid command (upper-body keypoints, lower-body robot motion) tracked by the universal policy with the hybrid motion encoder $\mathcal{E}_m$.
3. *VLA Integration*: We post-train a GR00T N1.5 model on data collected with the VR 3-Point Teleoperation stack. The action of the VLA model is fed into the kinematic motion planner to generate the lower-body motions, resulting in a hybrid command (upper-body direct VLA action, lower-body robot motion) tracked by the universal policy with the hybrid motion encoder $\mathcal{E}_m$.
4. *VR Whole-body Teleoperation*: Users control the humanoid using VR headsets (PICO), handheld controllers, and IMU sensors on the ankles, which allows us to use off-the-shelf toolkits to stream full-body human motion. The universal control policy tracks this motion using the human motion encoder $\mathcal{E}_h$.
5. *Video Teleoperation & Multi-Modal Control*: We employ the multi-modal motion generation model GENMO (<mark>Li et al., 2025</mark>) to estimate and generate human motions from multi-modal inputs (e.g., video, text, audio). The universal control policy subsequently tracks the generated motions using the human motion encoder $\mathcal{E}_h$. Further details are presented in Section <mark>3.4</mark>.

## 3.3. Generative Kinematic Motion Planner

Our generative kinematic motion planner is a large-scale latent generative model, trained on the same natural whole-body motion data as the motion tracking policy. At a high level, the planning process is formulated as an autoregressive motion in-betweening generation task. The context keyframes capture historical robot states, such as joint positions and root positions, while target keyframes are either navigation guidance keyframes generated from user commands such as velocity, direction, and style, or skill-specific targets for actions such as squatting, crawling, boxing, etc.

**Motion Representation.** During training, we sample motion segments of length between 0.8s and 2.4s, extracting the keyframes at both endpoints to serve as the context and target keyframes. Our motion representation is mathematically equivalent to the humanoid pose configuration $q_t$ as introduced in <mark>Sec. 3.2</mark>. Specifically, we represent kinematic motion using the pelvis-relative joint positions and global joint rotations. During training, we randomly rotate the training samples to enable planning in all initial orientations. Incorporating global rotation instead of local, canonicalized rotation is essential for generating motions such as squatting and crawling, where the notion of heading is ill-defined and greatly affects the quality of motion planning. We refer readers to <mark>Meng et al. (2024)</mark> and <mark>Meng et al. (2025)</mark> for similar insights and additional discussion.

14

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

**Generative Neural Backbone in Latent Space.** Planning is conducted in the latent space, where continuous motions are first encoded as a sequence of latent tokens as follows:

$$ \{z_t\}_{t=1}^{T/4} = \text{enc} \left( \{p_t, r_t\}_{t=1}^T \right), \tag{5} $$

where $p_t$ and $r_t$ denote the pose configuration and root position at frame $t$, respectively. In practice, the encoder operates with a downsampling rate of 4. The latent token sequence is encoded by models such as Transformers or Conv1D networks to capture temporal consistency.

The inbetweening process in the token space is guided by two constraints: the starting and target keyframes, denoted as $\{p_t, r_t\}_{t=1}^4$ and $\{p_t, r_t\}_{t=T-4}^T$ respectively. Rather than training the network to predict the entire sequence of tokens from these sparse constraints in a single pass, we adopt a masked token prediction approach (<mark>Guo et al., 2024; Luo et al., 2024; Pinyoanuntapong et al., 2024; Yu et al., 2023</mark>). In this framework, the neural backbone iteratively predicts and finalizes the subset of tokens for which it has the highest confidence, progressively refining the prediction.

$$ h = \mathcal{F} \left( \{p_t, r_t\}_{t=1}^4, \{p_t, r_t\}_{t=T-4}^T, \{z_t\}_{t=1}^{T/4} \right), \tag{6} $$

$$ \text{Prob}(z_t) = \sigma(h). \tag{7} $$

This process is iterative, where $\mathcal{F}(\cdot)$ denotes the neural backbone, and $h$ represents the logits for each token position. Token probabilities are computed by applying a softmax function $\sigma(\cdot)$ to the logits. At the first iteration, all latent tokens are unknown, and we initialize the latent embedding with a learnable mask embedding, $z_{\text{masked}}$. During training, the proportion of masked tokens is uniformly sampled from the range $[100\%, 0\%]$. During inference, a cosine schedule determines the proportion of tokens to finalize at each iteration, specifically $1.0 - \cos \left( \frac{\pi}{2} \cdot \frac{L}{L_{\text{max}}} \right)$, where $L$ is the current iteration and $L_{\text{max}}$ is the maximum number of iterations. After finalization of all tokens, the predicted tokens are used to reconstruct the kinematic motions and generate the robot control signals.

**Root trajectory spring model.** We propose to use an intuitive critical damped spring model to generate the root position and heading of the keyframes from user commands as follows:

$$ x(t) = \left( x_T - x_0 + \left( v_0 + \frac{c}{2} (x_T - x_0) \right) t \right) e^{-\frac{c}{2}t}, \tag{8} $$

where $x_T$ denotes the target value, $x_0$ the initial value, $v_0$ the initial velocity, and $c$ the damping coefficient. We apply this critically damped spring model to three quantities: 1) the pelvis position along the x-axis, 2) the pelvis position along the y-axis, and 3) the projected heading angle of the pelvis. Damping coefficients of $5 \ln(2)$ and $20 \ln(2)$ are used for position and heading respectively. The target values may be obtained directly from the controllers. Alternatively, if the controller only specifies a desired velocity we can compute the expected target positions after 1.0s using the desired velocity. The target keyframes are then placed at the position and heading with $x(1.0)$, as computed by the spring model in <mark>Eq. (8)</mark>. In practice, we find that our generative kinematic motion planner is highly robust to the choice of damping coefficients. In fact, the spring model could often be omitted entirely, as the planner's ability to generate motions of variable length (ranging from 0.8s to 2.4s) and its strong inbetweening capability makes it adaptable to a wide range of root trajectory commands. Nevertheless, incorporating the spring model improves behavioral predictability and helps safeguard against unrealistic commands, such as abruptly reversing direction from 6.0m/s to $-6.0$m/s.

**Keyframe Module and Application Integration.** Traditional motion planning methods often rely on complex target keyframe generation, such as detailed footstep planning. In contrast, our system provides keyframes in a

15

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

far more intuitive manner, requiring minimal effort or expertise for keyframe specification.

For navigation control, target keyframes are generated by placing a randomly selected segment from the navigation clips of the desired style at the target root trajectory. Despite this simplicity, our model consistently produces natural and smooth motions that align well with the specified style. We attribute this to the model’s flexible, variable-length motion generation and its robust inbetweening capabilities. Additionally, the autoregressive replanning ensures that the generated motion is continually refreshed before reaching the end of any given clip, thus minimizing dependence on the specific spatial details of the chosen target keyframes. This approach generalizes to other motion styles such as walking, running, and crawling.

For entertainment tasks such as boxing, target keyframes are determined by selecting the most expressive segment (e.g., the frames with maximal arm extension for a punch) from motion clips that match the desired style. We also support motion layering, where the upper body is specified and the lower body is generated accordingly by the planner, enabling the introduction of predefined behaviors.

For interactive modes needed in manipulation tasks, such as squatting or kneeling, keyframes are retrieved online from the motion clip library according to the desired height. Unlike traditional approaches that require an extensive motion library, our system needs only a single clip to generate the full distribution of transitional motions for a given skill.

## 3.4. Multi-modal Motion Generation Model

We adopt GENMO (Li et al., 2025) to support multi-modal conditioning within one framework. The core idea is to treat estimation from videos as constrained generation: the model synthesizes a complete motion trajectory that must satisfy observed evidence (e.g., video keypoints), while the same network can also generate diverse motions from abstract conditions (e.g., text or audio). This unification lets generative priors regularize estimation under occlusion or noise, and conversely lets abundant in-the-wild video data improve generative diversity.

**Conditioning modalities and temporal layout.** The model accepts mixed, time-varying conditions, including text prompts, audio features, and visual observations. Conditions may appear over different temporal intervals (e.g., text at the start, audio segments mid-trajectory, intermittent video spans). We represent these inputs as temporally indexed condition streams. Each stream is encoded by a modality-specific encoder into a sequence of features aligned to a common motion frame rate. Missing intervals are handled natively (no special-case branching) by simply providing empty or masked tokens; downstream fusion treats these as regular positions with null content.

**Architecture.** Condition streams are fused using a temporal transformer with cross-attention from the motion tokens to the multi-modal condition tokens. A diffusion-based motion prior then operates over the human motion sequence, denoising from Gaussian noise to a kinematically plausible trajectory. The prior is trained to model human motion dynamics and is agnostic to the specific conditioning type; all modality-specific structure lives in the encoders and the fusion layers. We encode the denoised human motion into the universal token space, enabling a single decoder to serve multiple downstream embodiments.

**Training objective.** Training mixes two complementary objectives. (1) *Generative learning* uses the standard diffusion loss over human motions, conditioned on available modalities (text/audio/video) to learn a broad motion prior. (2) *Estimation-guided learning* adds reconstruction terms when observations are present (e.g., 2D/3D keypoints, trajectory constraints), encouraging the generated motion to match measurements exactly where they exist while relying on the prior elsewhere. Because estimation is realized as generation with hard/soft constraints, the same network parameters serve both tasks. Mixed batches with variable-length sequences and randomly dropped modalities teach the model to seamlessly handle partial and asynchronous evidence without special logic.

16

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

**Inference modes.** At test time, the model supports: (1) *Pure generation* from abstract prompts (text-only or text+audio) to diverse, realistic motions; (2) *Constrained generation* given video frames to produce accurate, temporally coherent reconstructions; and (3) *Hybrid control* where modalities switch over time (e.g., text sets intent, audio refines timing, brief video spans anchor pose). All modes share the same sampler and differ only in which condition streams are non-empty. The model is converted to TensorRT for fast inference.

**Integration with our system.** Although GENMO supports arbitrary-length motion generation, we use sliding windows with overlap to ensure low-latency motion generation. We modify the diffusion denoising process with inpainting to handle the transitions between windows. More specifically, our diffusion is formulated as the variance-preserving diffusion, where the denoiser predicts the clean human motion at each denosing step. The overlapped part of the denoised human motion is overwritten by the previous window’s motions during denoising.

## 3.5. Deployment

Experiments are conducted on a Unitree G1 platform using the built-in joint-level PD controller. The learned policy outputs desired joint angles are passed directly to the PD interface. All components of the inference and management stack execute *onboard*, leveraging the on-device CPU/GPU to minimize feedback latency and improve timing determinism.

The policy loop runs at 50 Hz. At each cycle, we assemble observations from the recent robot state and operator intent, evaluate a learned policy, and synthesize joint-space targets. To ensure crisp, compliant actuation, these targets are streamed by a separate high-rate process at 500 Hz through the Unitree low-level API, continuously publishing the latest user inputs (target motion command) without blocking the policy loop.

Due to the encoder-decoder design, our system can *seamlessly switch between different input interfaces* (e.g., keyboard, gamepad, or networked streams) by changing the input encoder, enabling seamless transitions between various tasks: interactive gamepad control, VR 3-point teleoperation, whole-body teleoperation, video-based teleoperation, and multi-modal control from text and music. The user input is captured independently at 100 Hz.

When needed, the kinematic motion planner is employed at 10 Hz which proposes short-horizon sequences based on the command from the input interface. These plans are temporally aligned with the 50 Hz policy loop and smoothly blended into the control objectives, providing a motion reference without sacrificing responsiveness. Each periodic process operates on consistent snapshots of the robot state, and we adopt a “latest-data-wins” convention to mitigate jitter, ensuring transient delays do not stall the system.

Both the interactive kinematic motion planner and the policy inference execute *onboard* the Jetson Orin GPU using TensorRT with *CUDA Graph* acceleration. This configuration yields reliable, low-variance execution with 1–2 ms per forward pass for policy and 12 ms per forward pass for motion generation. The resulting architecture emphasizes timing robustness and smoothness. It produces a stable motion, while decoupled loops isolate sensing and planning from control, stabilizing end-to-end latency. Unless otherwise noted, all reported experiments use this onboard configuration (50/10/500/100 Hz) with timing logs enabled for diagnostics.

## 4. Acknowledgments

We thank Scott Reed, Wei Liu, You Liang Tan, Avnish Narayan, Fengyuan Hu, Yuqi Xie, Letian (Max) Fu, Mengda Xu, Davis Rempe, Xue Bin (Jason) Peng, Haotian Zhang, Yifeng Jiang, Anna Minx, John Malaska, Chen Tessler, Soha Pouya, Kaushil Prakashbhai Kundalia, Huihua Zhao, Xiaowei Jiang, Olivier Dionne, Michael De Ruyter, Michael Buttner, Qi Wang, Yeongho Seol, Mathis Petrovich, Sanja Fidler, Kaifeng Zhao, Spencer Huang, Gavriel State, Yurong "Kelly" Guo for their thoughtful discussions and help. We thank Leilee Naderi and Amanpreet Singh for supporting with data collection and providing feedback on teleoperation user experience.

17

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

We thank Jeremy Chimienti and Tri Cao for their work ensuring robot readiness and conducting the necessary repairs. We also thank Tri Cao, Jazmin Sanchez, Demetria Quijada, and Jesse Yang for their help in filming and editing.

# 5. Contributors

ZL, YY, TW, CL contributed equally as co-first authors. They trained the polices, developed planners, and designed the deployment piplines.

SC, FC, ZC, JL, DM, QB, XD are core contributors towards the whole systems including system ID, VLA training, model speed up, teleoperation, etc.

SY, CH, LS, EL, EJ, TH focused on retargeting and filtering our large-scale humanoid motion data.

RD, TH, HX, WX, ZW helped with brainstorming and codebase setup.

SY, JK, YC, UI, LF, YZ are our leadership team providing guidance.

18

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

# References

[1] Josh Achiam, Steven Adler, Sandhini Agarwal, Lama Ahmad, Ilge Akkaya, Florencia Leoni Aleman, Diogo Almeida, Janko Altenschmidt, Sam Altman, Shyamal Anadkat, et al. Gpt-4 technical report. *arXiv preprint arXiv:2303.08774*, 2023. <mark>1</mark>

[2] Michael Ahn, Anthony Brohan, Noah Brown, and et al. Do as i can, not as i say: Grounding language in robotic affordances. *arXiv preprint arXiv:2204.01691*, 2022. URL <mark>https://arxiv.org/abs/2204.01691</mark>. <mark>2</mark>

[3] Joao Pedro Araujo, Yanjie Ze, Pei Xu, Jiajun Wu, and C. Karen Liu. Retargeting matters: General motion retargeting for humanoid motion tracking. *arXiv preprint arXiv:2510.02252*, 2025. <mark>10</mark>

[4] Qingwei Ben, Feiyu Jia, Jia Zeng, Junting Dong, Dahua Lin, and Jiangmiao Pang. Homie: Humanoid loco-manipulation with isomorphic exoskeleton cockpit. *arXiv preprint arXiv:2502.13013*, 2025. <mark>2</mark>

[5] Johan Bjorck, Valts Blukis, Fernando Castañeda, Nikita Cherniadev, Xingye Da, Runyu Ding, Linxi “Jim” Fan, Yu Fang, Dieter Fox, Fengyuan Hu, Spencer Huang, Joel Jang, Xiaowei Jiang, Kaushil Kundalia, Jan Kautz, Zhiqi Li, Kevin Lin, Zongyu Lin, ... hyeon Ye, Zhiding Yu, Yizhou Zhao, Zhe Zhang, Ruijie Zheng, and Yuke Zhu. Gr00t n1.5: An improved open foundation model for generalist humanoid robots. <mark>https://research.nvidia.com/labs/gear/gr00t-n1_5/</mark>, June 2025. Blog post; accessed 2025-10-30. <mark>9</mark>

[6] Johan Bjorck, Fernando Castañeda, Nikita Cherniadev, Xingye Da, Runyu Ding, Linxi “Jim” Fan, Yu Fang, Dieter Fox, Fengyuan Hu, Spencer Huang, Joel Jang, Zhenyu Jiang, Jan Kautz, Kaushil Kundalia, Lawrence Lao, Zhiqi Li, Zongyu Lin, Kevin Lin, ... Yu, Ao Zhang, Hao Zhang, Yizhou Zhao, Ruijie Zheng, and Yuke Zhu. Gr00t n1: An open foundation model for generalist humanoid robots. *arXiv preprint arXiv:2503.14734*, 2025. doi: 10.48550/arXiv.2503.14734. URL <mark>https://arxiv.org/abs/2503.14734</mark>. <mark>3, 9</mark>

[7] Andreas Blattmann, Tim Dockhorn, Robin Rombach, and Patrick Esser. Stable video diffusion: Scaling latent video diffusion models. *arXiv preprint arXiv:2311.15127*, 2023. URL <mark>https://arxiv.org/abs/2311.15127</mark>. <mark>1</mark>

[8] Rishi Bommasani, Drew A. Hudson, Ehsan Adeli, and et al. On the opportunities and risks of foundation models. *arXiv preprint arXiv:2108.07258*, 2021. URL <mark>https://arxiv.org/abs/2108.07258</mark>. <mark>1</mark>

[9] Anthony Brohan, Noah Brown, Carlos Carbajal, and et al. Rt-1: Robotics transformer for real-world control at scale. *arXiv preprint arXiv:2212.06817*, 2022. URL <mark>https://arxiv.org/abs/2212.06817</mark>. <mark>2</mark>

[10] Anthony Brohan, Noah Brown, Ilya Chelombiev, and et al. Rt-2: Vision-language-action models transfer web knowledge to robotic control. *Nature*, 2023. doi: 10.1038/s41586-023-06475-7. <mark>2</mark>

[11] Tim Brooks, Bill Peebles, Connor Holmes, Will DePue, Yufei Guo, Li Jing, David Schnurr, Joe Taylor, Troy Luhman, Eric Luhman, et al. Video generation models as world simulators. *OpenAI*, 2024. <mark>1</mark>

[12] Zixuan Chen, Mazeyu Ji, Xuxin Cheng, Xuanbin Peng, Xue Bin Peng, and Xiaolong Wang. Gmt: General motion tracking for humanoid whole-body control. *arXiv preprint arXiv:2506.14770*, 2025. <mark>2, 4, 10, 12</mark>

19

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

[13] Sylvain Gugger, Lysandre Debut, Thomas Wolf, Philipp Schmid, Zachary Mueller, Sourab Mangrulkar, Marc Sun, and Benjamin Bossan. Accelerate: Training and inference at scale made simple, efficient and adaptable. https://github.com/huggingface/accelerate, 2022. <mark>14</mark>

[14] Chuan Guo, Yuxuan Mu, Muhammad Gohar Javed, Sen Wang, and Li Cheng. Momask: Generative masked modeling of 3d human motions. In *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, pages 1900–1910, 2024. <mark>15</mark>

[15] Tairan He, Zhengyi Luo, Xialin He, Wenli Xiao, Chong Zhang, Weinan Zhang, Kris Kitani, Changliu Liu, and Guanya Shi. Omnih2o: Universal and dexterous human-to-humanoid whole-body teleoperation and learning. *arXiv preprint arXiv:2406.08858*, 2024. <mark>2, 12</mark>

[16] Tairan He, Jiawei Gao, Wenli Xiao, Yuanhang Zhang, Zi Wang, Jiashun Wang, Zhengyi Luo, Guanqi He, Nikhil Sobanbab, Chaoyi Pan, et al. Asap: Aligning simulation and real-world physics for learning agile humanoid whole-body skills. *arXiv preprint arXiv:2502.01143*, 2025. <mark>2</mark>

[17] Tairan He, Wenli Xiao, Toru Lin, Zhengyi Luo, Zhenjia Xu, Zhenyu Jiang, Jan Kautz, Changliu Liu, Guanya Shi, Xiaolong Wang, et al. Hover: Versatile neural whole-body controller for humanoid robots. In *2025 IEEE International Conference on Robotics and Automation (ICRA)*, pages 9989–9996. IEEE, 2025. <mark>2</mark>

[18] Xialin He, Runpei Dong, Zixuan Chen, and Saurabh Gupta. Learning getting-up policies for real-world humanoid robots. *arXiv preprint arXiv:2502.12152*, 2025. <mark>2</mark>

[19] Jonathan Ho, William Chan, Chitwan Saharia, Jay Whang, Ruiqi Gao, Alexey Gritsenko, Diederik P Kingma, Ben Poole, Mohammad Norouzi, David J Fleet, et al. Imagen video: High definition video generation with diffusion models. *arXiv preprint arXiv:2210.02303*, 2022. <mark>1</mark>

[20] Jordan Hoffmann, Sebastian Borgeaud, Arthur Mensch, and et al. Training compute-optimal large language models. *arXiv preprint arXiv:2203.15556*, 2022. URL https://arxiv.org/abs/2203.15556. <mark>1</mark>

[21] Tao Huang, Junli Ren, Huayi Wang, Zirui Wang, Qingwei Ben, Muning Wen, Xiao Chen, Jianan Li, and Jiangmiao Pang. Learning humanoid standing-up control across diverse postures. *arXiv preprint arXiv:2502.08378*, 2025. <mark>2</mark>

[22] Daniel Kahneman. *Thinking, Fast and Slow*. Farrar, Straus and Giroux, 2011. ISBN 9780374275631. <mark>9</mark>

[23] Jared Kaplan, Sam McCandlish, Tom Henighan, and et al. Scaling laws for neural language models. *arXiv preprint arXiv:2001.08361*, 2020. URL https://arxiv.org/abs/2001.08361. <mark>1</mark>

[24] Chung Min Kim\*, Brent Yi\*, Hongsuk Choi, Yi Ma, Ken Goldberg, and Angjoo Kanazawa. Pyroki: A modular toolkit for robot kinematic optimization. In *2025 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)*, 2025. URL https://arxiv.org/abs/2505.03728. <mark>10</mark>

[25] Muhammed Kocabas, Nikos Athanasiou, and Michael J. Black. Vibe: Video inference for human body pose and shape estimation. In *CVPR*, 2020. doi: 10.1109/CVPR42600.2020.01265. <mark>3</mark>

[26] Jialong Li, Xuxin Cheng, Tianshu Huang, Shiqi Yang, Ri-Zhao Qiu, and Xiaolong Wang. Amo: Adaptive motion optimization for hyper-dexterous humanoid whole-body control. *arXiv preprint arXiv:2505.03738*, 2025. <mark>2</mark>

[27] Jiefeng Li, Jinkun Cao, Haotian Zhang, Davis Rempe, Jan Kautz, Umar Iqbal, and Ye Yuan. Genmo: A generalist model for human motion. In *Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)*, 2025. <mark>6, 14, 16, 24</mark>

20

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

[28] Ruilong Li, Shan Li, Angjoo Huang, and et al. Bailando: 3d dance generation via actor-critic gpt with choreographic memory. In *SIGGRAPH Asia 2021*, 2021. doi: 10.1145/3478513.3480495. 3

[29] Ruilong Li, Shan Yang, David A. Ross, and Angjoo Kanazawa. AI Choreographer: Music conditioned 3d dance generation with aist++. In *IEEE/CVF International Conference on Computer Vision (ICCV)*, October 2021. 2

[30] Qiayuan Liao, Takara E Truong, Xiaoyu Huang, Guy Tevet, Koushil Sreenath, and C Karen Liu. Beyondmimic: From motion tracking to versatile humanoid control via guided diffusion. *arXiv preprint arXiv:2508.08241*, 2025. 2, 4, 10, 12

[31] Matthew Loper, Naureen Mahmood, Javier Romero, Gerard Pons-Moll, and Michael J. Black. Smpl: A skinned multi-person linear model. *ACM Transactions on Graphics (Proc. SIGGRAPH Asia)*, 34(6): 248:1–248:16, 2015. doi: 10.1145/2816795.2818013. URL <u>http://smpl.is.tue.mpg.de</u>. 8, 13

[32] Zhengyi Luo, Jinkun Cao, Alexander W. Winkler, Kris Kitani, and Weipeng Xu. Perpetual humanoid control for real-time simulated avatars. In *International Conference on Computer Vision (ICCV)*, 2023. 2, 12

[33] Zhuoyan Luo, Fengyuan Shi, Yixiao Ge, Yujiu Yang, Limin Wang, and Ying Shan. Open-magvit2: An open-source project toward democratizing auto-regressive visual generation. *arXiv preprint arXiv:2409.04410*, 2024. 15

[34] Yi Ma, Zahid Hazara, Brian Ichter, and et al. Droid: A large-scale in-the-wild robot manipulation dataset. *arXiv preprint arXiv:2403.12945*, 2024. URL <u>https://arxiv.org/abs/2403.12945</u>. 2

[35] Naureen Mahmood, Nima Ghorbani, Nikolaus F. Troje, Gerard Pons-Moll, and Michael J. Black. Amass: Archive of motion capture as surface shapes. In *Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)*, October 2019. 2, 4

[36] Zichong Meng, Yiming Xie, Xiaogang Peng, Zeyu Han, and Huaizu Jiang. Rethinking diffusion for text-driven human motion generation. *arXiv preprint arXiv:2411.16575*, 2024. 14

[37] Zichong Meng, Zeyu Han, Xiaogang Peng, Yiming Xie, and Huaizu Jiang. Absolute coordinates make motion generation easy. *arXiv preprint arXiv:2505.19377*, 2025. 14

[38] Fabian Mentzer, David Minnen, Eirikur Agustsson, and Michael Tschannen. Finite scalar quantization: Vq-vae made simple. *arXiv preprint arXiv:2309.15505*, 2023. 13

[39] NVIDIA, :, Mayank Mittal, Pascal Roth, James Tigue, Antoine Richard, Octi Zhang, Peter Du, Antonio Serrano-Muñoz, Xinjie Yao, René Zurbrügg, Nikita Rudin, Lukasz Wawrzyniak, Milad Rakhsha, Alain Denzler, Eric Heiden, Ales Borovicka, Ossama Ahmed, Iretiayo Akinola, Abrar Anwar, Mark T. Carlson, Ji Yuan Feng, Animesh Garg, Renato Gasoto, Lionel Gulich, Yijie Guo, M. Gussert, Alex Hansen, Mihir Kulkarni, Chenran Li, Wei Liu, Viktor Makoviychuk, Grzegorz Malczyk, Hammad Mazhar, Masoud Moghani, Adithyavairavan Murali, Michael Noseworthy, Alexander Poddubny, Nathan Ratliff, Welf Rehberg, Clemens Schwarke, Ritvik Singh, James Latham Smith, Bingjie Tang, Ruchik Thaker, Matthew Trepte, Karl Van Wyk, Fangzhou Yu, Alex Millane, Vikram Ramasamy, Remo Steiner, Sangeeta Subramanian, Clemens Volk, CY Chen, Neel Jawale, Ashwin Varghese Kuruttukulam, Michael A. Lin, Ajay Mandlekar, Karsten Patzwaldt, John Welsh, Huihua Zhao, Fatima Anes, Jean-Francois Lafleche, Nicolas Moënne-Loccoz, Soowan Park, Rob Stepinski, Dirk Van Gelder, Chris Amevor, Jan Carius, Jumyung Chang, Anka He Chen, Pablo de Heras Ciechomski, Gilles Daviet, Mohammad Mohajerani, Julia von Muralt, Viktor Reutskyy, Michael Sauter, Simon Schirm, Eric L. Shi, Pierre Terdiman, Kenny Vilella, Tobias Widmer, Gordon Yeoman, Tiffany Chen, Sergey Grizan, Cathy Li, Lotus Li, Connor Smith, Rafael Wiltz, Kostas Alexis, Yan Chang, David Chu, Linxi "Jim" Fan, Farbod Farshidian, Ankur Handa, Spencer Huang, Marco

21

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

Hutter, Yashraj Narang, Soha Pouya, Shiwei Sheng, Yuke Zhu, Miles Macklin, Adam Moravanszky, Philipp Reist, Yunrong Guo, David Hoeller, and Gavriel State. Isaac lab: A gpu-accelerated simulation framework for multi-modal robot learning, 2025. URL https://arxiv.org/abs/2511.04831. 4, 14

[40] Open X-Embodiment Collaboration. Open x-embodiment: Robotic learning datasets and rt-x models. *arXiv preprint arXiv:2310.08864*, 2023. URL https://arxiv.org/abs/2310.08864. 2

[41] Xue Bin Peng, Pieter Abbeel, Sergey Levine, and Michiel van de Panne. Deepmimic: Example-guided deep reinforcement learning of physics-based character skills. In *ACM SIGGRAPH 2018 Papers*, 2018. doi: 10.1145/3197517.3201311. 1

[42] Xue Bin Peng, Zhaoyu Zhou, Stephen Luo, and Michiel van de Panne. Amp: Adversarial motion priors for stylized physics-based character control. *ACM Transactions on Graphics*, 40(4), 2021. doi: 10.1145/3450626.3459670. 1

[43] Ekkasit Pinyoanuntapong, Pu Wang, Minwoo Lee, and Chen Chen. Mmm: Generative masked motion model. In *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, pages 1546–1555, 2024. 15

[44] Abhinanda Punnakkal, Michael J. Black, Tushar Kapadi, and Gerard Pons-Moll. Babel: Bodies, action and behavior with english labels. In *CVPR*, 2021. doi: 10.1109/CVPR46437.2021.00756. 2

[45] Marc Raibert and Farbod Farshidian. In *Workshop on Whole-body Control and Bimanual Manipulation: Applications in Humanoids and Beyond, Robotics: Science and Systems (RSS)*, June 2025. 12

[46] Aditya Ramesh, Prafulla Dhariwal, Alex Nichol, Casey Chu, and Mark Chen. Hierarchical text-conditional image generation with clip latents. *arXiv preprint arXiv:2204.06125*, 2022. 1

[47] Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, and Björn Ommer. High-resolution image synthesis with latent diffusion models. In *Proceedings of the IEEE/CVF conference on computer vision and pattern recognition*, pages 10684–10695, 2022. 1

[48] John Schulman, Filip Wolski, Prafulla Dhariwal, Alec Radford, and Oleg Klimov. Proximal policy optimization algorithms. *arXiv preprint arXiv:1707.06347*, 2017. 12

[49] Sebastian Starke, Yiwei Zhao, Fabio Zinno, and Taku Komura. Neural animation layering for synthesizing martial arts movements. *ACM Transactions on Graphics (TOG)*, 40(4):1–16, 2021. 5

[50] Richard S. Sutton. The bitter lesson. http://www.incompleteideas.net/IncIdeas/BitterLesson.html, 2019. 1

[51] Guy Tevet, Sigal Raab, Yuval Shafir, and et al. Human motion diffusion model. *arXiv preprint arXiv:2209.14916*, 2022. URL https://arxiv.org/abs/2209.14916. 3

[52] Emanuel Todorov, Tom Erez, and Yuval Tassa. Mujoco: A physics engine for model-based control. In *2012 IEEE/RSJ International Conference on Intelligent Robots and Systems*, pages 5026–5033. IEEE, 2012. doi: 10.1109/IROS.2012.6386109. 5

[53] Unitree. Humanoid robot G1_Humanoid Robot Functions_Humanoid Robot Price | Unitree Robotics — unitree.com. https://www.unitree.com/g1, 2024. [Accessed 31-10-2025]. 3

[54] Unitree. Unitree boxing. https://www.unitree.com/boxing, 2025. Accessed: 2024-06-30. 5

[55] Leandro von Werra, Younes Belkada, Lewis Tunstall, Edward Beeching, Tristan Thrush, Nathan Lambert, Shengyi Huang, Kashif Rasul, and Quentin Gallouédec. Trl: Transformer reinforcement learning. https://github.com/huggingface/trl, 2020. 14

22

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

[56] Tingwu Wang, Yunrong Guo, Maria Shugrina, and Sanja Fidler. Unicon: Universal neural controller for physics-based character motion. *arXiv preprint arXiv:2011.15119*, 2020. <mark>2</mark>

[57] Jason Wei, Yi Tay, Rishi Bommasani, and et al. Emergent abilities of large language models. *arXiv preprint arXiv:2206.07682*, 2022. URL https://arxiv.org/abs/2206.07682. <mark>1</mark>

[58] Jungdam Won, Deepak Gopinath, and Jessica Hodgins. Control strategies for physically simulated characters performing two-player competitive sports. *ACM Transactions on Graphics (TOG)*, 40(4):1–11, 2021. <mark>5</mark>

[59] Kangning Yin, Weishuai Zeng, Ke Fan, Minyue Dai, Zirui Wang, Qiang Zhang, Zheng Tian, Jingbo Wang, Jiangmiao Pang, and Weinan Zhang. Unitracker: Learning universal whole-body motion tracker for humanoid robots, 2025. URL https://arxiv.org/abs/2507.07356. <mark>2</mark>

[60] Lijun Yu, Yong Cheng, Kihyuk Sohn, José Lezama, Han Zhang, Huiwen Chang, Alexander G Hauptmann, Ming-Hsuan Yang, Yuan Hao, Irfan Essa, et al. Magvit: Masked generative video transformer. In *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, pages 10459–10469, 2023. <mark>15</mark>

[61] Yanjie Ze, Zixuan Chen, João Pedro Araújo, Zi-ang Cao, Xue Bin Peng, Jiajun Wu, and C Karen Liu. Twist: Teleoperated whole-body imitation system. *arXiv preprint arXiv:2505.02833*, 2025. <mark>2, 4</mark>

[62] Weishuai Zeng, Shunlin Lu, Kangning Yin, Xiaojie Niu, Minyue Dai, Jingbo Wang, and Jiangmiao Pang. Behavior foundation model for humanoid robots. *arXiv preprint arXiv:2509.13780*, 2025. <mark>2, 4</mark>

[63] Ye Zhang, Tong He, Qingxuan Zhang, and et al. T2m-gpt: Generating human motion from textual descriptions with discrete representations. In *CVPR*, 2023. doi: 10.1109/CVPR52729.2023.00877. <mark>3</mark>

[64] Zhikai Zhang, Jun Guo, Chao Chen, Jilong Wang, Chenghuai Lin, Yunrui Lian, Han Xue, Zhenrong Wang, Maoqi Liu, Huaping Liu, et al. Track any motions under any disturbances. *arXiv preprint arXiv:2509.13833*, 2025. <mark>2, 4, 10, 12</mark>

[65] Zhigen Zhao, Liuchuan Yu, Ke Jing, and Ning Yang. Xrobotoolkit: A cross-platform framework for robot teleoperation. *arXiv preprint arXiv:2508.00097*, 2025. <mark>8, 14</mark>

[66] Yi Zhou, Connelly Barnes, Jingwan Lu, Jimei Yang, and Hao Li. On the continuity of rotation representations in neural networks. In *Proceedings of the IEEE/CVF conference on computer vision and pattern recognition*, pages 5745–5753, 2019. <mark>12</mark>

23

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

# A. Supplementary Materials

## S1. Supplementary Video Descriptions

The <mark>project site</mark> hosts a collection of high-resolution videos that complement the results presented in the main paper. Each video demonstrates SONIC ’s large-scale motion tracking, interactive control, multi-modal interfaces, and VLA integrations on a Unitree G1. Below we provide detailed descriptions of each video category.

### S1.1 Teleoperation

**Video Teleoperation.** These clips visualize SONIC ’s ability to track diverse human motions—including walking, running, turning, jumping, dancing, floor motions for teleoperation. The videos emphasize our robust zero-shot imitation of out-of-distribution motion sequences

**Full-Body VR Control.** Using a PICO headset, ankle trackers, and controllers, full-body pose streams drive SONIC via the human-motion encoder. The robot performs walking, sidestepping, crouching, and loco-manipulations with low latency.

**3-Point VR Teleoperation.** A lightweight teleoperation mode uses only the headset and handheld controllers. The user provides upper body commands via the controllers and the navigation command for the planner to generate natural lower body movements. Videos show SONIC performing mobile manipulation, navigation, reaching, and fast upper-body control. Hybrid upper-body commands with lower-body motion planning provide stable teleoperation interface.

### S1.2 Interactive Motion Control

These videos demonstrate the real-time kinematic motion planner coupled with the universal tracking policy.

**Interactive Locomotion.** Users control the humanoid through continuous velocity and heading commands. SONIC replans every $\sim$100 ms and produces highly responsive and natural movements.

**Walking Style.** Clips illustrate smooth transitions between motion styles such as *drunken walk*, *injured walk*, *happy walk*, *stealth walk*, and sprinting. Our planner’s inbetweening capabilities enable seamless blends among styles.

**Interactive Boxing.** SONIC executes jabs, hooks, stance shifts, and reactive upper-body movements with fluidity. Unlike clip-switching methods, SONIC produces continuous, unbroken sequences with minimal artifacts.

**Squatting, Kneeling, and Crawling.** Videos show arbitrary pelvis-height control (0.3–0.8 m), kneeling variations, elbow crawling, hand–knee crawling, and transitions. These skills enable locomotion in confined spaces and downstream teleoperation behaviors.

### S1.3 Multi-Modal Motion Generation

These videos highlight SONIC ’s universal token space by accepting diverse motion interfaces—text and music.

**Text-Driven Motion..** SONIC responds to natural-language commands such as “walk forward”, “punch with your left hand”, or “act like a monkey” and can track the generated motion from GENMO <mark>(27)</mark>.

**Music-Conditioned Motion..** SONIC performs dance motions synchronized to tempo and musical phrasing, adapting to rhythmic and stylistic cues.

These videos demonstrate seamless transitions among modalities without training a new controller.

### S1.5 Foundation-Model-Driven Loco-Manipulation

These clips show a GR00T N1.5 vision–language–action (VLA) model driving SONIC via the same teleoperation interface.

24

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

<table>
  <thead>
    <tr>
        <th>Module</th>
        <th>Architecture</th>
        <th>Dims</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td colspan="3">*Network configuration*</td>
    </tr>
    <tr>
        <td>Quantizer</td>
        <td>FSQ</td>
        <td>token dimensions = $D_z$; quantization levels = $L_z$</td>
    </tr>
    <tr>
        <td>Encoder (g1)</td>
        <td>MLP</td>
        <td>hidden= $[2048, 1024, 512, 512]$</td>
    </tr>
    <tr>
        <td>Encoder (teleop)</td>
        <td>MLP</td>
        <td>hidden = $[2048, 1024, 512, 512]$</td>
    </tr>
    <tr>
        <td>Encoder (smpl)</td>
        <td>MLP</td>
        <td>hidden = $[2048, 1024, 512, 512]$</td>
    </tr>
    <tr>
        <td>Decoder (actions)</td>
        <td>MLP</td>
        <td>hidden = $[4096, 4096, 2048, 2048, 1024, 1024, 512, 512]$</td>
    </tr>
    <tr>
        <td>Decoder (refs)</td>
        <td>MLP</td>
        <td>hidden = $[2048, 1024, 512, 512]$</td>
    </tr>
    <tr>
        <td>Action dimension</td>
        <td>Diagonal Gaussian</td>
        <td>29</td>
    </tr>
    <tr>
        <td>Critic</td>
        <td>MLP</td>
        <td>hidden = $[4096, 4096, 2048, 2048, 1024, 1024, 512, 512]$</td>
    </tr>
    <tr>
        <td colspan="3">*Motion command*</td>
    </tr>
    <tr>
        <td>Future frames</td>
        <td>$F_r = F_h = F_m = 10$ frames</td>
        <td> </td>
    </tr>
    <tr>
        <td>Frame interval</td>
        <td>$\Delta t_r = t_m = 0.1s, \Delta t_h = 0.02s$</td>
        <td> </td>
    </tr>
  </tbody>
</table>

Table 1: Universal control policy hyperparameters.

* The VLA predicts head and wrist poses, base height, and navigation commands.

* SONIC executes these signals through its kinematic planner and universal control decoder.

* Videos show autonomous apple-to-plate mobile pick-and-place achieving 95% success.

This integration demonstrates SONIC as a fast, reactive System 1 whole-body controller under a system 2 VLA planner.

## S2. Supplementary Tables

This section includes four tables that provide implementation details of SONIC. These tables provide complete specifications for the network architecture, training hyperparameters, reward definitions, and domain randomization settings used to obtain the large-scale motion tracking results presented in the main paper.

**Table S2.1: Network Architecture.** Table <mark>1</mark> reports the full configuration of the encoder–decoder architecture used by SONIC, including:

* robot-motion encoder, human-motion encoder, and hybrid encoder;

* universal token quantizer parameters (FSQ levels, token dimension);

* robot-control decoder and auxiliary robot-motion decoder;

* layer dimensions, MLP depth, activation functions, and latent sizes.

**Table S2.2: Training Hyperparameters.** Table <mark>1</mark> lists all training configurations, including PPO hyperparameters, rollout length, discount factors, etc.

**Table S2.3: Reward Function.** Table <mark>3</mark> provides a complete breakdown of the reward terms used for large-scale motion tracking, including:

* root position/orientation matching,

* joint position and velocity tracking,

* body-link pose and velocity terms,

* action regularization and smoothness,

* penalty terms for joint limits and undesired contacts.

**Table S2.4: Domain Randomization.** Table <mark>4</mark> reports the ranges and distributions for all physical and kinematic randomization parameters used during training. These settings are applied during RL to ensure SONIC transfers robustly to the real Unitree G1.

Together, these four tables fully specify SONIC ’s training and implementation details to support reproducibility and further research.

25

SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control

<table>
  <thead>
    <tr>
        <th>Training hyperparameter</th>
        <th>Value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>Num parallel envs per GPU</td>
        <td>4096</td>
    </tr>
    <tr>
        <td>Num steps per env</td>
        <td>24</td>
    </tr>
    <tr>
        <td>Learning epochs</td>
        <td>5</td>
    </tr>
    <tr>
        <td>Num mini-batches</td>
        <td>4</td>
    </tr>
    <tr>
        <td>Discount $\gamma$</td>
        <td>0.99</td>
    </tr>
    <tr>
        <td>GAE $\lambda$</td>
        <td>0.95</td>
    </tr>
    <tr>
        <td>Clip parameter</td>
        <td>0.2</td>
    </tr>
    <tr>
        <td>Entropy coefficient</td>
        <td>0.013</td>
    </tr>
    <tr>
        <td>Value loss coefficient</td>
        <td>1.0</td>
    </tr>
    <tr>
        <td>Actor learning rate</td>
        <td>$2 \times 10^{-5}$</td>
    </tr>
    <tr>
        <td>Critic learning rate</td>
        <td>$1 \times 10^{-3}$</td>
    </tr>
    <tr>
        <td>Max gradient norm</td>
        <td>0.1</td>
    </tr>
    <tr>
        <td>Desired KL</td>
        <td>0.01</td>
    </tr>
    <tr>
        <td>Adaptive LR min/max</td>
        <td>$[1 \times 10^{-5}, 2 \times 10^{-4}]$</td>
    </tr>
    <tr>
        <td>Init noise std</td>
        <td>0.05</td>
    </tr>
    <tr>
        <td>Actor std clamp min/max</td>
        <td>$[0.001, 0.5]$</td>
    </tr>
    <tr>
        <td>Adaptive sampling bin size</td>
        <td>1s</td>
    </tr>
    <tr>
        <td>Adaptive sampling failure rate cap</td>
        <td>$\beta = 200$</td>
    </tr>
    <tr>
        <td>Adaptive sampling blending hyperparameter</td>
        <td>$\alpha = 0.1$</td>
    </tr>
  </tbody>
</table>

Table 2: Training hyperparameters.


<table>
  <thead>
    <tr>
        <th>Reward term</th>
        <th>Equation</th>
        <th>Weight</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td colspan="3">*Tracking rewards* $\mathcal{R}(\boldsymbol{s}_t^p, \boldsymbol{s}_t^g)$</td>
    </tr>
    <tr>
        <td>Root orientation</td>
        <td>$r_{\text{ori}}^{\text{root}}(t) = \exp(-\|\boldsymbol{o}_{t,r}^p - \boldsymbol{o}_{t,r}^g\|_2^2 / 0.4^2)$</td>
        <td>0.5</td>
    </tr>
    <tr>
        <td>Body link pos (rel.)</td>
        <td>$r_{\text{pos}}^{\text{body}}(t) = \exp(-\frac{1}{|\mathcal{B}|} \sum_{b \in \mathcal{B}} \|\boldsymbol{p}_{t,b}^{p,\text{rel}} - \boldsymbol{p}_{t,b}^{g,\text{rel}}\|_2^2 / 0.3^2)$</td>
        <td>1.0</td>
    </tr>
    <tr>
        <td>Body link ori (rel.)</td>
        <td>$r_{\text{ori}}^{\text{body}}(t) = \exp(-\frac{1}{|\mathcal{B}|} \sum_{b \in \mathcal{B}} \|\boldsymbol{o}_{t,b}^{p,\text{rel}} - \boldsymbol{o}_{t,b}^{g,\text{rel}}\|_2^2 / 0.4^2)$</td>
        <td>1.0</td>
    </tr>
    <tr>
        <td>Body link lin. vel</td>
        <td>$r_{\text{lin}}^{\text{body}}(t) = \exp(-\frac{1}{|\mathcal{B}|} \sum_{b \in \mathcal{B}} \|\boldsymbol{v}_{t,b}^p - \boldsymbol{v}_{t,b}^g\|_2^2 / 1.0^2)$</td>
        <td>1.0</td>
    </tr>
    <tr>
        <td>Body link ang. vel</td>
        <td>$r_{\text{ang}}^{\text{body}}(t) = \exp(-\frac{1}{|\mathcal{B}|} \sum_{b \in \mathcal{B}} \|\boldsymbol{\omega}_{t,b}^p - \boldsymbol{\omega}_{t,b}^g\|_2^2 / 3.14^2)$</td>
        <td>1.0</td>
    </tr>
    <tr>
        <td colspan="3">*Penalty terms* $\mathcal{P}(\boldsymbol{s}_t^p, \boldsymbol{a}_t)$</td>
    </tr>
    <tr>
        <td>Action rate</td>
        <td>$r_{\text{act}}(t) = \|\boldsymbol{a}_t - \boldsymbol{a}_{t-1}\|_2^2$</td>
        <td>-0.1</td>
    </tr>
    <tr>
        <td>Joint limit</td>
        <td>$r_{\text{jlim}}(t) = \sum_j \mathbb{1}[\boldsymbol{q}_{t,j} \notin [\boldsymbol{q}_{t,j}^{\min}, \boldsymbol{q}_{t,j}^{\max}]]$</td>
        <td>-10.0</td>
    </tr>
    <tr>
        <td>Undesired contacts</td>
        <td>$r_{\text{contact}}(t) = \sum_{c \notin \{\text{ankles, wrists}\}} \mathbb{1}[\|\boldsymbol{F}_c\| &gt; 1.0\text{N}]$</td>
        <td>-0.1</td>
    </tr>
  </tbody>
</table>

Table 3: Reward design. Superscript $g$: goal/target state from $\boldsymbol{s}_t^g$; superscript $p$: proprioceptive/current state from $\boldsymbol{s}_t^p$; $\mathcal{B}$: set of tracked body links; superscript “rel”: quantities relative to root frame.


<table>
  <thead>
    <tr>
        <th>Domain Randomization</th>
        <th>Sampling Distribution</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td colspan="2">*Physical parameters*</td>
    </tr>
    <tr>
        <td>Static friction coefficients</td>
        <td>$\mu_s \sim \mathcal{U}[0.3, 1.6]$</td>
    </tr>
    <tr>
        <td>Dynamic friction coefficients</td>
        <td>$\mu_d \sim \mathcal{U}[0.3, 1.2]$</td>
    </tr>
    <tr>
        <td>Restitution coefficient</td>
        <td>$e \sim \mathcal{U}[0, 0.5]$</td>
    </tr>
    <tr>
        <td>Default joint positions</td>
        <td>$\boldsymbol{q}_0 \sim \boldsymbol{q}_0 + \mathcal{U}[-0.01, 0.01]$</td>
    </tr>
    <tr>
        <td>Base COM offset (x, y, z)</td>
        <td>$\Delta x \sim \mathcal{U}[-0.075, 0.075], \Delta y \sim \mathcal{U}[-0.1, 0.1], \Delta z \sim \mathcal{U}[-0.1, 0.1]$</td>
    </tr>
    <tr>
        <td colspan="2">*Root velocity perturbations (external pushes)*</td>
    </tr>
    <tr>
        <td>Root linear vel (x, y, z)</td>
        <td>$v_x \sim \mathcal{U}[-0.5, 0.5], v_y \sim \mathcal{U}[-0.5, 0.5], v_z \sim \mathcal{U}[-0.2, 0.2]$</td>
    </tr>
    <tr>
        <td>Push duration</td>
        <td>$\Delta t \sim \mathcal{U}[1, 3]\text{s}$</td>
    </tr>
    <tr>
        <td>Root angular vel</td>
        <td>$\omega_{\text{roll}} \sim \mathcal{U}[-0.52, 0.52], \omega_{\text{pitch}} \sim \mathcal{U}[-0.52, 0.52], \omega_{\text{yaw}} \sim \mathcal{U}[-0.78, 0.78]$</td>
    </tr>
    <tr>
        <td colspan="2">*Target motion perturbations ($\boldsymbol{s}_t^g$)*</td>
    </tr>
    <tr>
        <td>Target position jitter</td>
        <td>$\Delta \boldsymbol{p}^g \sim \mathcal{U}[-0.05, 0.05]^3$ (x,y: $\pm 0.05$, z: $\pm 0.01$)</td>
    </tr>
    <tr>
        <td>Target orientation jitter</td>
        <td>$\Delta \phi_{\text{roll}}, \Delta \phi_{\text{pitch}} \sim \mathcal{U}[-0.1, 0.1], \Delta \phi_{\text{yaw}} \sim \mathcal{U}[-0.2, 0.2]$</td>
    </tr>
    <tr>
        <td>Target linear vel jitter</td>
        <td>$\Delta \boldsymbol{v}^g \sim \mathcal{U}[-0.5, 0.5]^3$ (x,y: $\pm 0.5$, z: $\pm 0.2$)</td>
    </tr>
    <tr>
        <td>Target angular vel jitter</td>
        <td>$\Delta \omega_{\text{roll}}, \Delta \omega_{\text{pitch}} \sim \mathcal{U}[-0.52, 0.52], \Delta \omega_{\text{yaw}} \sim \mathcal{U}[-0.78, 0.78]$</td>
    </tr>
    <tr>
        <td>Target joint jitter</td>
        <td>$\Delta \boldsymbol{q}_t^g \sim \mathcal{U}[-0.1, 0.1]$</td>
    </tr>
  </tbody>
</table>

Table 4: Domain randomization parameters applied during training. $\mathcal{U}[\cdot]$: uniform distribution.

26