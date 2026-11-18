#!/usr/bin/env python3
"""Find GTA VI chat spikes across live Twitch channels and queue local clip drafts."""

import argparse
from collections import Counter
from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import re
import select
import socket
import ssl
import statistics
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from clip_finder import (
    BASELINE_BUCKETS, BUCKET_SECONDS, MIN_HISTORY_BUCKETS, is_media_url, marked_candidates,
    page_video_duration, render_clip, render_page_clip, video_duration, video_url,
)

GAME = "Grand Theft Auto VI"
CLIP_SECONDS = 30
BEFORE_SECONDS = 18
MIN_MESSAGES = 10
MIN_RATIO = 3
CHANNEL = re.compile(r"[a-z0-9_]{1,25}")
CHAT_MESSAGE = re.compile(r"^:[^ ]+ PRIVMSG #(\w+) :")


class ChatDisconnected(Exception):
    pass


class SpikeDetector:
    def __init__(self, before=BEFORE_SECONDS):
        self.before = before
        self.first_bucket = None
        self.counts = {}
        self.next_start = 0

    def observe(self, channel, bucket, messages):
        if self.first_bucket is None:
            self.first_bucket = bucket
        oldest = max(self.first_bucket, bucket - BASELINE_BUCKETS)
        self.counts = {key: value for key, value in self.counts.items() if key >= oldest}
        history = range(oldest, bucket)
        self.counts[bucket] = messages
        if len(history) < MIN_HISTORY_BUCKETS or messages < MIN_MESSAGES:
            return None
        baseline = max(1, statistics.median(self.counts.get(key, 0) for key in history))
        peak = (bucket + 1) * BUCKET_SECONDS
        start = peak - self.before
        if messages / baseline < MIN_RATIO or start < self.next_start:
            return None
        end = start + CLIP_SECONDS
        self.next_start = end
        return {
            "id": f"{channel}-{peak}",
            "channel": channel,
            "start_unix": start,
            "peak_unix": peak,
            "end_unix": end,
            "messages": messages,
            "baseline": baseline,
            "ratio": messages / baseline,
        }


def emit(candidate, queue, stream_id=None):
    if candidate is None:
        return
    if stream_id is not None:
        candidate["stream_id"] = stream_id
    print(json.dumps(candidate), file=queue, flush=True)


def channel_name(value):
    name = value.lower()
    if not CHANNEL.fullmatch(name):
        raise ValueError("Expected a Twitch channel login")
    return name


def replay(path, queue, before=BEFORE_SECONDS):
    detectors = {}
    last_buckets = {}
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, start=1):
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Expected an object on replay line {number}")
            channel, bucket, messages = (row.get(key) for key in ("channel", "bucket", "messages"))
            if (not isinstance(channel, str) or type(bucket) is not int
                    or type(messages) is not int or messages < 0):
                raise ValueError(f"Invalid replay observation on line {number}")
            channel = channel_name(channel)
            if bucket <= last_buckets.get(channel, -1):
                raise ValueError(f"Replay buckets must increase per channel on line {number}")
            last_buckets[channel] = bucket
            if row.get("reset") is True or channel not in detectors:
                detectors[channel] = SpikeDetector(before)
            emit(detectors[channel].observe(channel, bucket, messages), queue, row.get("stream_id"))


def observe_chat(channel, queue, bucket_log, before):
    """Count visible chat by keypress on a POSIX terminal."""
    import termios
    import tty

    terminal = sys.stdin.fileno()
    settings = termios.tcgetattr(terminal)
    detector = SpikeDetector(before)
    bucket = int(time.time()) // BUCKET_SECONDS
    first_full = bucket + 1
    count = 0
    reset = True
    print("Watch chat beside this terminal. Wait for Ready. Space adds one, "
          "digits add 1–9. Ctrl-C stops.", file=sys.stderr, flush=True)
    try:
        tty.setcbreak(terminal)
        while True:
            deadline = (bucket + 1) * BUCKET_SECONDS
            readable, _, _ = select.select([terminal], [], [], max(0, deadline - time.time()))
            key = os.read(terminal, 1) if readable else None
            if key == b"":
                return
            current = int(time.time()) // BUCKET_SECONDS
            if current != bucket:
                if current == bucket + 1 and bucket >= first_full:
                    print(json.dumps({"channel": channel, "bucket": bucket,
                                      "messages": count, "reset": reset}), file=bucket_log, flush=True)
                    candidate = detector.observe(channel, bucket, count)
                    emit(candidate, queue)
                    print(f"{deadline} · {count} messages", file=sys.stderr, flush=True)
                    if candidate:
                        print(f"Spike {candidate['id']} · {candidate['ratio']:.1f}× baseline",
                              file=sys.stderr, flush=True)
                    reset = False
                elif current != bucket + 1:
                    detector = SpikeDetector(before)
                    first_full = current + 1
                    reset = True
                    print("Clock gap. Waiting for the next full bucket.", file=sys.stderr, flush=True)
                if current == first_full:
                    print("Ready", file=sys.stderr, flush=True)
                bucket, count = current, 0
            if bucket >= first_full:
                if key == b" ":
                    count += 1
                elif key and b"1" <= key <= b"9":
                    count += int(key)
    finally:
        termios.tcsetattr(terminal, termios.TCSADRAIN, settings)


def live_streams(channels, token, client_id):
    query = urlencode([("user_login", channel) for channel in channels])
    request = Request("https://api.twitch.tv/helix/streams?" + query, headers={
        "Authorization": f"Bearer {token}",
        "Client-Id": client_id,
    })
    try:
        with urlopen(request, timeout=8) as response:
            return {
                stream["user_login"]: stream["id"]
                for stream in json.load(response)["data"]
                if stream["game_name"] == GAME
            }
    except HTTPError as error:
        if error.code == 429 or error.code >= 500:
            raise ChatDisconnected(f"Twitch stream lookup returned HTTP {error.code}") from None
        raise ValueError(f"Twitch stream lookup returned HTTP {error.code}") from None
    except OSError as error:
        raise ChatDisconnected("Twitch stream lookup was interrupted") from error


def watch_connection(channels, token, client_id, login, queue, bucket_log, before):
    if any(character.isspace() for character in token):
        raise ValueError("Invalid Twitch access token format")
    context = ssl.create_default_context()
    with socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=10) as tcp:
        with context.wrap_socket(tcp, server_hostname="irc.chat.twitch.tv") as chat:
            chat.settimeout(1)
            chat.sendall(f"PASS oauth:{token}\r\nNICK {login}\r\n".encode())
            authenticated = False
            auth_deadline = time.monotonic() + 10
            pending = b""
            streams = {}
            detectors = {}
            first_full_bucket = {}
            counts = Counter()
            current_bucket = int(time.time()) // BUCKET_SECONDS
            next_check = 0
            while True:
                now = time.monotonic()
                if not authenticated and now >= auth_deadline:
                    raise ValueError("Twitch IRC did not authenticate the chat connection")
                if authenticated and now >= next_check:
                    active = live_streams(channels, token, client_id)
                    for channel in streams.keys() | active.keys():
                        if streams.get(channel) != active.get(channel):
                            detectors.pop(channel, None)
                            counts.pop(channel, None)
                            first_full_bucket.pop(channel, None)
                            if channel in active:
                                first_full_bucket[channel] = int(time.time()) // BUCKET_SECONDS + 1
                    if next_check == 0 or active != streams:
                        print("Live GTA VI channels: " + (", ".join(sorted(active)) or "none"),
                              file=sys.stderr, flush=True)
                    streams = active
                    next_check = time.monotonic() + 30
                try:
                    block = chat.recv(65536)
                except TimeoutError:
                    block = None
                if block == b"":
                    raise ChatDisconnected("Twitch IRC disconnected")
                bucket = int(time.time()) // BUCKET_SECONDS
                if current_bucket + 1 == bucket:
                    for channel, stream_id in streams.items():
                        if current_bucket < first_full_bucket[channel]:
                            continue
                        reset = channel not in detectors
                        if reset:
                            detectors[channel] = SpikeDetector(before)
                        messages = counts[channel]
                        if bucket_log is not None:
                            print(json.dumps({
                                "channel": channel, "bucket": current_bucket,
                                "messages": messages, "stream_id": stream_id, "reset": reset,
                            }), file=bucket_log, flush=True)
                        emit(detectors[channel].observe(channel, current_bucket, messages),
                             queue, stream_id)
                if bucket != current_bucket:
                    if bucket != current_bucket + 1:
                        detectors.clear()
                    current_bucket = bucket
                    counts.clear()
                if block is None:
                    continue
                *lines, pending = (pending + block).split(b"\r\n")
                for line in lines:
                    message = line.decode(errors="replace")
                    if message.startswith("PING "):
                        chat.sendall(("PONG " + message[5:] + "\r\n").encode())
                    elif message == ":tmi.twitch.tv RECONNECT":
                        raise ChatDisconnected("Twitch requested reconnection")
                    elif not authenticated and message.startswith(":tmi.twitch.tv 001 "):
                        authenticated = True
                        rooms = ",".join(f"#{channel}" for channel in channels)
                        chat.sendall(f"JOIN {rooms}\r\n".encode())
                    elif not authenticated and " NOTICE * " in message:
                        raise ValueError("Twitch IRC rejected authentication. Check login and chat:read scope.")
                    else:
                        match = CHAT_MESSAGE.match(message)
                        if match and match[1] in streams:
                            counts[match[1]] += 1


def watch(channels, queue, bucket_log, before):
    try:
        token = os.environ["TWITCH_ACCESS_TOKEN"].removeprefix("oauth:")
        client_id = os.environ["TWITCH_CLIENT_ID"]
        login = channel_name(os.environ["TWITCH_LOGIN"])
    except KeyError as error:
        raise ValueError(f"Set {error.args[0]} before watching Twitch") from None
    while True:
        try:
            watch_connection(channels, token, client_id, login, queue, bucket_log, before)
        except (ChatDisconnected, ConnectionError, TimeoutError, socket.gaierror) as error:
            print(f"Twitch connection interrupted ({type(error).__name__}). Reconnecting.",
                  file=sys.stderr, flush=True)
            time.sleep(5)


def render(args):
    with args.queue.open(encoding="utf-8") as source:
        matches = [row for line in source if (row := json.loads(line))["id"] == args.id]
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching cue ID")
    row = matches[0]
    video = args.video_url if args.video_url is not None else args.video
    page_url = args.video_url is not None and not is_media_url(args.video_url)
    duration = page_video_duration(video) if page_url else video_duration(video)
    peak = row["peak_unix"] - args.recording_start
    before = row["peak_unix"] - row["start_unix"]
    after = row["end_unix"] - row["peak_unix"]
    if before <= 0 or after <= 0 or before + after != CLIP_SECONDS:
        raise ValueError("Cue must describe a 30-second window around the peak")
    if not math.isfinite(peak) or peak < before or peak + after > duration:
        raise ValueError("The aligned recording must cover the complete cue window")
    candidate, = marked_candidates([peak], duration, before, after)
    if args.out.exists():
        raise ValueError(f"Output already exists: {args.out}")
    with TemporaryDirectory(dir=args.out.parent) as staging:
        draft = Path(staging) / "draft.mp4"
        if page_url:
            render_page_clip(video, candidate, draft)
        else:
            render_clip(video, candidate, draft)
        os.link(draft, args.out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    live = modes.add_parser("watch", help="queue candidates from live Twitch chat")
    live.add_argument("channels", nargs="+")
    live.add_argument("--buckets-out", type=Path, help="write aggregate counts for later replay")
    fixture = modes.add_parser("replay", help="queue candidates from recorded bucket counts")
    fixture.add_argument("buckets", type=Path)
    manual = modes.add_parser("observe", help="count visible chat from any platform in a POSIX terminal")
    manual.add_argument("channel")
    manual.add_argument("--buckets-out", type=Path, required=True)
    for mode in (live, fixture, manual):
        mode.add_argument("--out", type=Path, required=True, help="new local JSONL queue")
        mode.add_argument("--before", type=int, default=BEFORE_SECONDS, metavar="SECONDS",
                          help="seconds before the cue within the 30-second clip (default 18)")
    cut = modes.add_parser("render", help="cut one cue from a synchronized recording or VOD")
    cut.add_argument("--queue", type=Path, required=True)
    cut.add_argument("--id", required=True)
    video = cut.add_mutually_exclusive_group(required=True)
    video.add_argument("--video", type=Path)
    video.add_argument("--video-url", type=video_url)
    cut.add_argument("--recording-start", type=float, required=True,
                     help="Unix timestamp at recording frame zero after aligning to chat")
    cut.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.mode != "render" and not 0 < args.before < CLIP_SECONDS:
        parser.error("--before must be between 1 and 29 seconds")
    try:
        if args.mode == "render":
            render(args)
        elif args.mode == "replay":
            with args.out.open("x", encoding="utf-8") as queue:
                replay(args.buckets, queue, args.before)
        elif args.mode == "observe":
            if os.name != "posix" or not sys.stdin.isatty():
                raise ValueError("Observe needs an interactive POSIX terminal")
            channel = channel_name(args.channel)
            if args.buckets_out.resolve() == args.out.resolve():
                raise ValueError("Cue and bucket outputs must be different files")
            with (args.out.open("x", encoding="utf-8") as queue,
                  args.buckets_out.open("x", encoding="utf-8") as bucket_log):
                observe_chat(channel, queue, bucket_log, args.before)
        else:
            channels = list(dict.fromkeys(map(channel_name, args.channels)))
            if len(channels) > 20:
                raise ValueError("Watch supports up to 20 channels per run")
            if not all(os.environ.get(key) for key in
                       ("TWITCH_ACCESS_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_LOGIN")):
                raise ValueError("Set TWITCH_ACCESS_TOKEN, TWITCH_CLIENT_ID and TWITCH_LOGIN")
            if args.buckets_out is not None and args.buckets_out.resolve() == args.out.resolve():
                raise ValueError("Cue and bucket outputs must be different files")
            with ExitStack() as files:
                queue = files.enter_context(args.out.open("x", encoding="utf-8"))
                bucket_log = None
                if args.buckets_out is not None:
                    bucket_log = files.enter_context(args.buckets_out.open("x", encoding="utf-8"))
                watch(channels, queue, bucket_log, args.before)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
