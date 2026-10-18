"""Unit tests for the 2D Puppet & Body Language Rigging Engine."""

import pytest
from PIL import Image

from benxautomation.animation.puppet_engine import (
    PuppetCharacter,
    PuppetPose,
    PuppetState,
)


def test_puppet_all_poses_render_cleanly():
    puppet = PuppetCharacter("ben")
    poses = [
        PuppetPose.IDLE,
        PuppetPose.POINTING,
        PuppetPose.SHRUGGING,
        PuppetPose.PANIC_JUMP,
        PuppetPose.HOLDING_PHONE,
        PuppetPose.THUMBS_UP,
    ]

    for p in poses:
        state = PuppetState(
            character="ben",
            pose=p,
            is_speaking=True,
            is_blinking=False,
            frame_idx=10,
        )
        frame = puppet.render_puppet_frame(state, canvas_size=(360, 640))
        assert isinstance(frame, Image.Image)
        assert frame.size == (360, 640)


def test_speech_bounce_and_panic_jump():
    puppet = PuppetCharacter("ben")
    # Idle silent
    state_idle = PuppetState(
        character="ben",
        pose=PuppetPose.IDLE,
        is_speaking=False,
        frame_idx=10,
    )
    frame_idle = puppet.render_puppet_frame(state_idle, canvas_size=(360, 640))

    # Speaking with rhythmic bounce
    state_speaking = PuppetState(
        character="ben",
        pose=PuppetPose.IDLE,
        is_speaking=True,
        frame_idx=10,
    )
    frame_speaking = puppet.render_puppet_frame(state_speaking, canvas_size=(360, 640))

    assert frame_idle.size == frame_speaking.size


def test_character_universe_all_roster():
    characters = ["ben", "max", "mr_cash", "the_king", "dr_quantum"]
    poses = [PuppetPose.IDLE, PuppetPose.POINTING, PuppetPose.SHRUGGING, PuppetPose.PANIC_JUMP, PuppetPose.HOLDING_PROP]

    for char in characters:
        puppet = PuppetCharacter(char)
        for p in poses:
            # Test speaking frame
            state_speak = PuppetState(
                character=char,
                pose=p,
                is_speaking=True,
                is_blinking=False,
                frame_idx=5,
            )
            frame_speak = puppet.render_puppet_frame(state_speak, canvas_size=(360, 640))
            assert frame_speak.size == (360, 640)

            # Test blinking frame
            state_blink = PuppetState(
                character=char,
                pose=p,
                is_speaking=False,
                is_blinking=True,
                frame_idx=80,
            )
            frame_blink = puppet.render_puppet_frame(state_blink, canvas_size=(360, 640))
            assert frame_blink.size == (360, 640)


def test_all_character_expressions():
    characters = ["ben", "max", "mr_cash", "the_king", "dr_quantum"]
    expressions = ["shocked", "panic", "smirk", "warning", "skeptical", "triumph", "explaining"]

    for char in characters:
        puppet = PuppetCharacter(char)
        for expr in expressions:
            state = PuppetState(
                character=char,
                pose=PuppetPose.IDLE,
                is_speaking=True,
                expression=expr,
                frame_idx=15,
            )
            frame = puppet.render_puppet_frame(state, canvas_size=(360, 640))
            assert frame.size == (360, 640)


def test_background_engine_all_themes():
    from benxautomation.animation.background_engine import BackgroundEngine

    engine = BackgroundEngine()
    themes = [
        "bank_vault", "tech_blueprint", "cyber_matrix", "quantum_lab",
        "wall_street", "command_center", "airport_station", "throne_room",
        "retro_mainframe", "ben_studio", "street_day", "street_night",
    ]

    for theme in themes:
        # Test 9:16 Portrait (Shorts)
        bg_shorts = engine.render_background(theme, canvas_size=(360, 640), frame_idx=5)
        assert bg_shorts.size == (360, 640)

        # Test 16:9 Landscape (Longform)
        bg_longform = engine.render_background(theme, canvas_size=(640, 360), frame_idx=5)
        assert bg_longform.size == (640, 360)


def test_render_puppet_with_background():
    from benxautomation.animation.background_engine import BackgroundEngine

    bg_engine = BackgroundEngine()
    bg = bg_engine.render_background("bank_vault", canvas_size=(360, 640), frame_idx=10)

    puppet = PuppetCharacter("mr_cash")
    state = PuppetState(
        character="mr_cash",
        pose=PuppetPose.HOLDING_PROP,
        expression="smirk",
        is_speaking=True,
        frame_idx=10,
    )
    frame = puppet.render_puppet_frame(state, canvas_size=(360, 640), background=bg)
    assert frame.size == (360, 640)

