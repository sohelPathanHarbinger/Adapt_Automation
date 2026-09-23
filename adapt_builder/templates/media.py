"""adapt-contrib-media, for the Key Concepts videos.

The storyboard describes these videos as a ``Narration | On Screen Text``
table rather than shipping one, so the automation cannot produce the asset. It
emits the component wired to the filename the video should be delivered under,
and puts the narration script and on-screen text in the build report so
whoever produces the video has the spec in one place.
"""

from __future__ import annotations

from .. import config
from ..model import Component
from .base import Ctx, base_component

PLAYER_OPTIONS = {
    "poster": "",
    "showPosterWhenEnded": True,
    "defaultVideoWidth": 480,
    "defaultVideoHeight": 270,
    "videoWidth": -1,
    "videoHeight": -1,
    "defaultAudioWidth": 400,
    "defaultAudioHeight": 30,
    "defaultSeekBackwardInterval": "(media.duration * 0.05)",
    "defaultSeekForwardInterval": "(media.duration * 0.05)",
    "audioWidth": -1,
    "audioHeight": -1,
    "startVolume": 0.8,
    "loop": False,
    "autoRewind": True,
    "enableAutosize": True,
    "alwaysShowHours": False,
    "showTimecodeFrameCount": False,
    "framesPerSecond": 25,
    "autosizeProgress": True,
    "alwaysShowControls": False,
    "hideVideoControlsOnLoad": False,
    "clickToPlayPause": True,
    "iPadUseNativeControls": False,
    "iPhoneUseNativeControls": False,
    "AndroidUseNativeControls": False,
    "features": [
        "playpause",
        "current",
        "progress",
        "duration",
        "tracks",
        "volume",
        "fullscreen",
    ],
    "isVideo": True,
    "enableKeyboard": True,
    "pauseOtherPlayers": True,
    "tracksText": "mejs.i18n.t('Captions/Subtitles')",
    "hideCaptionsButtonWhenEmpty": True,
    "toggleCaptionsButtonWhenOnlyOne": False,
    "slidesSelector": "",
}


def build(component: Component, ctx: Ctx) -> dict:
    src = component.extra.get("src", "")

    data = base_component(component, ctx, "media")
    data["body"] = ""
    data["_setCompletionOn"] = "ended"
    data["_useClosedCaptions"] = True
    data["_allowFullScreen"] = True
    data["_pauseWhenOffScreen"] = False
    data["_playsinline"] = False
    data["_preventForwardScrubbing"] = False
    data["_startLanguage"] = "en"
    data["_showVolumeControl"] = True
    data["_startVolume"] = "80%"
    data["_aspectRatio"] = "landscape"
    data["_offsetMediaControls"] = False
    data["_media"] = {
        "mp4": src,
        "ogv": src,
        "poster": config.MEDIA_POSTER,
        "cc": [{"srclang": "en", "src": ""}],
    }
    data["_transcript"] = {
        "_setCompletionOnView": False,
        "_inlineTranscript": False,
        "_externalTranscript": False,
        "inlineTranscriptButton": "Transcript",
        "inlineTranscriptCloseButton": "Close Transcript",
        "inlineTranscriptBody": component.extra.get("narration", ""),
        "transcriptLinkButton": "",
        "transcriptLink": "",
    }
    data["_playerOptions"] = PLAYER_OPTIONS
    data["_pageLevelProgress"] = {"_isEnabled": True}

    ctx.report.note(
        f"{ctx.id}: video '{src}' is referenced but not produced by this build - "
        "see the Key Concepts scripts section of this report"
    )
    return data
