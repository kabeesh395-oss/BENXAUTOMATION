import pytest

from autoclip_app.live_clipper import identify_platform


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.twitch.tv/example_channel", "twitch"),
        ("https://twitch.tv/example_channel", "twitch"),
        ("https://www.youtube.com/watch?v=example", "youtube"),
        ("https://youtu.be/example", "youtube"),
    ],
)
def test_identify_supported_live_platforms(url, expected):
    assert identify_platform(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://www.twitch.tv/example_channel",
        "https://example.com/live",
        "not-a-url",
        "https://youtube.com.evil.example/watch?v=123",
    ],
)
def test_reject_unsupported_or_unsafe_live_urls(url):
    with pytest.raises(ValueError):
        identify_platform(url)
