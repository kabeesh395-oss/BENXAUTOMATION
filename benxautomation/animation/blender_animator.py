"""Blender 3D/2D cartoon character animation generator and renderer."""

import json
import logging
import math
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from benxautomation.animation.models import AnimatedShortScript

log = logging.getLogger(__name__)

# Template for Blender Python execution script
BLENDER_SCRIPT_TEMPLATE = '''
import sys
import bpy
import math

argv = sys.argv
args_idx = argv.index("--") if "--" in argv else -1
if args_idx == -1 or args_idx + 2 >= len(argv):
    print("Usage: blender -b -P script.py -- <script_json_path> <output_frames_dir>")
    sys.exit(1)

script_json_path = argv[args_idx + 1]
output_frames_dir = argv[args_idx + 2]

import json
with open(script_json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 1. Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# 2. Configure Workbench Toon Renderer
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'SINGLE'
scene.display.shading.single_color = (0.95, 0.95, 0.95)
scene.display.shading.show_object_outline = True
scene.display.shading.object_outline_color = (0.05, 0.05, 0.05)

# 3. 1080x1920 9:16 vertical resolution at 12 fps (traditional cartoon on twos)
fps = 12
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.fps = fps

scenes_data = data.get("scenes", [])
total_duration = sum(s.get("duration_seconds", 8.0) for s in scenes_data)
total_frames = max(120, int(total_duration * fps))

scene.frame_start = 1
scene.frame_end = total_frames

# 4. Materials setup
mat_white = bpy.data.materials.new(name="Mat_White")
mat_white.diffuse_color = (1.0, 1.0, 1.0, 1.0)

mat_black = bpy.data.materials.new(name="Mat_Black")
mat_black.diffuse_color = (0.05, 0.05, 0.05, 1.0)

mat_accent = bpy.data.materials.new(name="Mat_Accent")
mat_accent.diffuse_color = (0.2, 0.2, 0.2, 1.0)

# 5. Create Camera
cam_data = bpy.data.cameras.new("MainCamera")
cam_obj = bpy.data.objects.new("MainCamera", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.location = (0, -4.5, 1.4)
cam_obj.rotation_euler = (math.radians(85), 0, 0)

# 6. Create Character Model ("Benny" Black & White Toon)
# Character Root Empty
char_root = bpy.data.objects.new("Character_Root", None)
scene.collection.objects.link(char_root)
char_root.location = (0, 0, 0)

# Head
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.55, location=(0, 0, 1.5))
head = bpy.context.active_object
head.name = "Head"
head.parent = char_root
head.data.materials.append(mat_white)

# Torso / Body
bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.8, location=(0, 0, 0.6))
body = bpy.context.active_object
body.name = "Body"
body.parent = char_root
body.data.materials.append(mat_white)

# Left Eye
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(-0.16, -0.45, 1.58))
eye_l = bpy.context.active_object
eye_l.name = "Eye_L"
eye_l.parent = head
eye_l.data.materials.append(mat_white)

# Right Eye
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(0.16, -0.45, 1.58))
eye_r = bpy.context.active_object
eye_r.name = "Eye_R"
eye_r.parent = head
eye_r.data.materials.append(mat_white)

# Left Pupil
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=(-0.16, -0.55, 1.58))
pupil_l = bpy.context.active_object
pupil_l.name = "Pupil_L"
pupil_l.parent = eye_l
pupil_l.data.materials.append(mat_black)

# Right Pupil
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=(0.16, -0.55, 1.58))
pupil_r = bpy.context.active_object
pupil_r.name = "Pupil_R"
pupil_r.parent = eye_r
pupil_r.data.materials.append(mat_black)

# Eyebrow Left
bpy.ops.mesh.primitive_cube_add(size=0.1, location=(-0.16, -0.48, 1.74))
brow_l = bpy.context.active_object
brow_l.scale = (1.4, 0.2, 0.3)
brow_l.name = "Brow_L"
brow_l.parent = head
brow_l.data.materials.append(mat_black)

# Eyebrow Right
bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.16, -0.48, 1.74))
brow_r = bpy.context.active_object
brow_r.scale = (1.4, 0.2, 0.3)
brow_r.name = "Brow_R"
brow_r.parent = head
brow_r.data.materials.append(mat_black)

# Cartoon Mouth
bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.06, location=(0, -0.50, 1.32))
mouth = bpy.context.active_object
mouth.rotation_euler = (math.radians(90), 0, 0)
mouth.name = "Mouth"
mouth.parent = head
mouth.data.materials.append(mat_black)

# Left Arm (Upper + Forearm)
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.6, location=(-0.55, 0, 0.75))
arm_l = bpy.context.active_object
arm_l.name = "Arm_L"
arm_l.parent = body
arm_l.data.materials.append(mat_white)

# Right Arm
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.6, location=(0.55, 0, 0.75))
arm_r = bpy.context.active_object
arm_r.name = "Arm_R"
arm_r.parent = body
arm_r.data.materials.append(mat_white)

# Stage Floor Disc
bpy.ops.mesh.primitive_circle_add(radius=2.5, location=(0, 0, 0), fill_type='NGON')
floor = bpy.context.active_object
floor.name = "Stage_Floor"
floor.data.materials.append(mat_white)

# Thematic Background Prop (Infographic Display)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 1.8, 1.6))
board = bpy.context.active_object
board.name = "Thematic_Board"
board.scale = (1.8, 0.05, 1.2)
board.data.materials.append(mat_black)

# Prop Icon / Object
bpy.ops.mesh.primitive_ico_sphere_add(radius=0.3, location=(0.8, 0, 1.8))
prop_sphere = bpy.context.active_object
prop_sphere.name = "Prop_Sphere"
prop_sphere.data.materials.append(mat_accent)

# 7. Animate Scenes Keyframing
current_frame = 1

for sc_idx, sc in enumerate(scenes_data):
    sc_dur = sc.get("duration_seconds", 8.0)
    sc_frames = max(24, int(sc_dur * fps))
    end_frame = current_frame + sc_frames

    pose = sc.get("pose", "TALKING_EXCITED")
    cam_motion = sc.get("camera_motion", "STATIC_MEDIUM")

    # Camera Motion Keyframing
    cam_obj.keyframe_insert(data_path="location", frame=current_frame)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=current_frame)

    if cam_motion == "DOLLY_IN_CLOSEUP":
        cam_obj.location = (0, -4.5, 1.4)
        cam_obj.keyframe_insert(data_path="location", frame=current_frame)
        cam_obj.location = (0, -3.2, 1.5)
        cam_obj.keyframe_insert(data_path="location", frame=end_frame)
    elif cam_motion == "PAN_LEFT_TO_RIGHT":
        cam_obj.location = (-0.8, -4.2, 1.4)
        cam_obj.keyframe_insert(data_path="location", frame=current_frame)
        cam_obj.location = (0.8, -4.2, 1.4)
        cam_obj.keyframe_insert(data_path="location", frame=end_frame)
    elif cam_motion == "SLOW_DUTCH_TILT":
        cam_obj.rotation_euler = (math.radians(85), math.radians(-5), 0)
        cam_obj.keyframe_insert(data_path="rotation_euler", frame=current_frame)
        cam_obj.rotation_euler = (math.radians(85), math.radians(5), 0)
        cam_obj.keyframe_insert(data_path="rotation_euler", frame=end_frame)
    else:
        cam_obj.location = (0, -4.2, 1.4)
        cam_obj.keyframe_insert(data_path="location", frame=current_frame)
        cam_obj.location = (0, -4.0, 1.4)
        cam_obj.keyframe_insert(data_path="location", frame=end_frame)

    # Prop Rotation
    prop_sphere.keyframe_insert(data_path="rotation_euler", frame=current_frame)
    prop_sphere.rotation_euler = (0, 0, math.radians(180 * (sc_idx + 1)))
    prop_sphere.keyframe_insert(data_path="rotation_euler", frame=end_frame)

    # Character Poses & Arm Gestures
    if "POINTING" in pose:
        # Right arm points up/right
        arm_r.rotation_euler = (math.radians(70), math.radians(-30), math.radians(60))
        arm_l.rotation_euler = (math.radians(-10), 0, 0)
        head.rotation_euler = (0, 0, math.radians(-10))
    elif "SHRUGGING" in pose:
        arm_r.rotation_euler = (math.radians(45), math.radians(-40), math.radians(45))
        arm_l.rotation_euler = (math.radians(45), math.radians(40), math.radians(-45))
        head.rotation_euler = (0, math.radians(12), 0)
    elif "THINKING" in pose:
        arm_r.rotation_euler = (math.radians(110), 0, math.radians(30))
        arm_l.rotation_euler = (math.radians(20), 0, 0)
        head.rotation_euler = (math.radians(-10), math.radians(-12), 0)
    elif "TRIUMPHANT" in pose:
        arm_r.rotation_euler = (math.radians(140), math.radians(-20), 0)
        arm_l.rotation_euler = (math.radians(140), math.radians(20), 0)
        head.rotation_euler = (math.radians(15), 0, 0)
    elif "SURPRISED" in pose:
        arm_r.rotation_euler = (math.radians(75), math.radians(-35), math.radians(20))
        arm_l.rotation_euler = (math.radians(75), math.radians(35), math.radians(-20))
        head.rotation_euler = (math.radians(-15), 0, 0)
    else:  # TALKING_EXCITED / NEUTRAL
        arm_r.rotation_euler = (math.radians(30), math.radians(-15), 0)
        arm_l.rotation_euler = (math.radians(20), math.radians(15), 0)
        head.rotation_euler = (0, 0, 0)

    arm_r.keyframe_insert(data_path="rotation_euler", frame=current_frame)
    arm_l.keyframe_insert(data_path="rotation_euler", frame=current_frame)
    head.keyframe_insert(data_path="rotation_euler", frame=current_frame)

    # Dynamic Talking Animation (Mouth opening and closing with phonemes)
    f = current_frame
    mouth_cycle = 0
    while f < end_frame:
        # Mouth open / close scale
        mouth_scale = 1.0 if (mouth_cycle % 2 == 0) else 0.25
        mouth.scale = (1.0, mouth_scale, mouth_scale)
        mouth.keyframe_insert(data_path="scale", frame=f)

        # Subtle head bobbing while talking
        bob = math.sin(f * 0.5) * 0.05
        head.location = (0, 0, 1.5 + bob)
        head.keyframe_insert(data_path="location", frame=f)

        # Subtle body sway
        body_rot = math.sin(f * 0.25) * math.radians(3)
        char_root.rotation_euler = (0, 0, body_rot)
        char_root.keyframe_insert(data_path="rotation_euler", frame=f)

        mouth_cycle += 1
        f += 3  # every 3 frames (~4 times per second at 12 fps)

    # Blinking Keyframes
    blink_f = current_frame + int(sc_frames / 2)
    eye_l.scale = (1.0, 1.0, 1.0)
    eye_r.scale = (1.0, 1.0, 1.0)
    eye_l.keyframe_insert(data_path="scale", frame=blink_f - 1)
    eye_r.keyframe_insert(data_path="scale", frame=blink_f - 1)
    eye_l.scale = (1.0, 1.0, 0.1)
    eye_r.scale = (1.0, 1.0, 0.1)
    eye_l.keyframe_insert(data_path="scale", frame=blink_f)
    eye_r.keyframe_insert(data_path="scale", frame=blink_f)
    eye_l.scale = (1.0, 1.0, 1.0)
    eye_r.scale = (1.0, 1.0, 1.0)
    eye_l.keyframe_insert(data_path="scale", frame=blink_f + 1)
    eye_r.keyframe_insert(data_path="scale", frame=blink_f + 1)

    current_frame = end_frame

# 8. Configure output and render PNG image sequence
import os
os.makedirs(output_frames_dir, exist_ok=True)
scene.render.filepath = os.path.join(output_frames_dir, "frame_")
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'

print("STARTING_BLENDER_RENDER total_frames=" + str(total_frames))
bpy.ops.render.render(animation=True)
print("COMPLETED_BLENDER_RENDER")
'''


class BlenderAnimator:
    """Invokes Blender in headless mode to render 1080x1920 cartoon character animation."""

    def __init__(self, blender_path: Path) -> None:
        self.blender_path = blender_path
        if not self.blender_path.is_file():
            raise FileNotFoundError(f"Blender binary not found at {self.blender_path}")

    def render_script_to_frames(
        self, script: AnimatedShortScript, output_frames_dir: Path, timeout_seconds: int = 600
    ) -> int:
        """Execute Blender script to render 1080x1920 PNG frames."""
        output_frames_dir.mkdir(parents=True, exist_ok=True)

        job_dir = output_frames_dir.parent / "job_spec"
        job_dir.mkdir(parents=True, exist_ok=True)
        script_spec_path = job_dir / f"{script.script_id}_spec.json"
        blender_runner_script = job_dir / "blender_render_runner.py"

        # Serialize script data
        with open(script_spec_path, "w", encoding="utf-8") as f:
            json.dump(asdict(script), f, indent=2, default=str)

        # Write runner script
        blender_runner_script.write_text(BLENDER_SCRIPT_TEMPLATE, encoding="utf-8")

        cmd = [
            str(self.blender_path.resolve()),
            "-b",
            "--python",
            str(blender_runner_script.resolve()),
            "--",
            str(script_spec_path.resolve()),
            str(output_frames_dir.resolve()),
        ]

        log.info("Running Blender render job for %s in background...", script.script_id)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)

        if "COMPLETED_BLENDER_RENDER" not in res.stdout:
            log.error("Blender render stderr:\n%s", res.stderr)
            raise RuntimeError(f"Blender render failed for {script.script_id}: {res.stderr[:500]}")

        rendered_pngs = list(output_frames_dir.glob("frame_*.png"))
        log.info("Blender rendered %d animation frames for %s", len(rendered_pngs), script.script_id)
        return len(rendered_pngs)
