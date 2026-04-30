# Resumen

La misión general es poder computar exactamente estas variables:
    * 
- **`smpl_joints` (72D)**: 24 joints × xyz (en el mismo frame/convención que espera el deployment)
- **`smpl_anchor_orientation` (6D)**: orientación del anchor/pelvis en 6D (misma convención que `GatherMotionAnchorOrientationMutiFrame`)
- **`motion_joint_positions_wrists` (6D)**: 6 joints de muñeca del robot (wrist roll/pitch/yaw por lado)
- **`encoder_mode_4` (4D)**: one-hot del modo (para SMPL típicamente “smpl”)


El problema principal es que estas variables se encuentran en C++