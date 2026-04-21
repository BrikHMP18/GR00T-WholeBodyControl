# Logistic Picking

Home
Overview
Competition
Schedule
Awards
Sponsors
Organizers
WBCD 2025
WBCD 2026 Competition Track

Full task specs, bills of materials, and CAD files are open-source on GitHub

Track 1#: LOGISTICS PICKING
Track 2#: LOGISTICS PACKING
Track 3#: LAB EXPERIMENTS
Track 4#: DEFORMABLE MANIPULATION

## Track 1: Logistics Picking

Robot from Unitree

Robot Demonstration
Teleop real robot video from Unitree -- bring your best and do even better!

This task focuses on whole-body teleoperated control and end-effector coordination utilizing the Unitree G1 humanoid robot. The objective is to bridge the gap between research and practical application by simulating a logistics scenario. Participants must use remote operation methods (VR, motion capture) to transfer items from shelves of varying heights to a transport vehicle. The system relies solely on the robot's own perception capabilities to execute complex maneuvers including upright, bent, and crouched postures.

### Robot Configuration: Unitree G1

Unitree G1

End effectors: A pair of end effectors (clamps, three-finger or five-finger dexterous hands)

Control method: VR headset or inertial motion capture suit

## Task Rules

The competition time limit is 10 minutes. The goal is to complete as many item transfer tasks as possible within this window.

- **Control Method:** Remote operation via VR headset or inertial motion capture suit.
- **Perception:** Participants must acquire external information solely through the robot's onboard perception system.
- **Capacity:** There is no limit on the number of items transferred per single operation cycle, provided they are not dropped.

### Step 1: Shelf Picking

Navigate the robot to the shelving unit and extract items. The difficulty varies by shelf height, requiring specific body postures.

| Action | Description | Posture |
|--------|-------------|---------|
| 1a | Pick item from Top Shelf | Upright Position |
| 1b | Pick item from Middle Shelf | Bent Position |
| 1c | Pick item from Bottom Shelf | Crouched Position |

**Success Criteria:** Item securely grasped from the shelf without knocking over other items.

### Step 2: Transportation

Transport the grasped items from the shelving area to the designated unloading area.

| Action | Description |
|--------|-------------|
| 2a | Stabilize item(s) during locomotion |
| 2b | Navigate to the transport vehicle/table |

**Success Criteria:** Maintain grasp on items throughout the movement. Drops result in penalties.

### Step 3: Placement

Place the items onto the transport vehicle or unloading table.

| Action | Description |
|--------|-------------|
| 3a | Position item over target area |
| 3b | Release item securely |

**Success Criteria:** Item rests stably on the unloading surface.

## Scoring

Scoring is weighted based on the difficulty of the whole-body motion required (posture).

| Source | Posture | Points | Criteria |
|--------|---------|--------|----------|
| Top Shelf | Upright | +5 | Successful transfer from high shelf |
| Middle Shelf | Bent | +8 | Successful transfer from middle shelf |
| Bottom Shelf | Crouched | +10 | Successful transfer from bottom shelf |
| Item Drop | — | -3 | Per item dropped during transportation |

## Items Used in This Task

- Coke
- Poker Cards
- Speed Cube
- Tennis Ball
- Cling Wrap
- Soft Toy
- Bowl
- Toilet Paper
- Bar Soap
- Potato Chips

## Human Demonstration

Sample task execution by a human operator for demonstration purposes.
