from handwave.config.profile import Profile
from handwave.services.app_matcher import select_profile


def test_no_profiles_falls_back_to_global():
    match = select_profile([], executable="spotify.exe")
    assert match.profile is None
    assert match.reason == "global_fallback"


def test_exact_executable_match():
    spotify = Profile(name="Spotify", app_executable="spotify.exe")
    match = select_profile([spotify], executable="C:\\Apps\\Spotify.exe")
    assert match.profile == spotify
    assert match.reason == "executable_match"


def test_unmatched_executable_falls_back_to_global():
    spotify = Profile(name="Spotify", app_executable="spotify.exe")
    match = select_profile([spotify], executable="notepad.exe")
    assert match.profile is None
    assert match.reason == "global_fallback"


def test_disabled_profile_is_never_selected():
    spotify = Profile(name="Spotify", app_executable="spotify.exe", enabled=False)
    match = select_profile([spotify], executable="spotify.exe")
    assert match.profile is None
    assert match.reason == "global_fallback"


def test_window_title_match_is_more_specific_than_executable_only():
    generic = Profile(name="Chrome", app_executable="chrome.exe")
    youtube = Profile(name="Chrome YouTube", app_executable="chrome.exe", app_window_title_pattern="YouTube")
    match = select_profile([generic, youtube], executable="chrome.exe", window_title="YouTube - Google Chrome")
    assert match.profile == youtube
    assert match.reason == "window_title_match"


def test_falls_back_to_executable_only_when_title_does_not_match_pattern():
    youtube = Profile(name="Chrome YouTube", app_executable="chrome.exe", app_window_title_pattern="YouTube")
    match = select_profile([youtube], executable="chrome.exe", window_title="Gmail - Google Chrome")
    assert match.profile == youtube
    assert match.reason == "executable_match"


def test_conflicting_matches_are_resolved_deterministically():
    first = Profile(name="A", app_executable="chrome.exe")
    second = Profile(name="B", app_executable="chrome.exe")
    profiles = [first, second]
    expected = min(profiles, key=lambda p: p.profile_id)

    assert select_profile(profiles, executable="chrome.exe").profile == expected
    assert select_profile(list(reversed(profiles)), executable="chrome.exe").profile == expected
