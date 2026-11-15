# GTA V field tests

November 15, 2026. Source intervals use the Twitch replay clock. Local labels use seconds from the beginning of each downloaded excerpt. Viewer clips provide independently chosen reference intervals. They are examples of clips viewers made, not an exhaustive list of good moments. Source video and chat stayed local.

| Source and excerpt | Reference | Default ranking | Follow-up |
|---|---|---|---|
| [Burn](https://www.twitch.tv/videos/2925128680), 00:56:00–01:04:00 | Two editorial marks chosen from frames and audio before ranking | Three picks. One touched a labeled interval. Neither reached a marked anchor. | Lowering the minimum from ten to four messages returned the same picks. |
| [Diables](https://www.twitch.tv/videos/2929472756), 03:41:00–03:49:30 | [Viewer clip](https://www.twitch.tv/diables/clip/GenerousColdbloodedFerretResidentSleeper-D6QHqXFJ8CsQEkdZ) at 03:47:49–03:48:19, with the game exit marked as the anchor | The first pick reached the anchor. Its cut started one second after the reference interval. | `--before 25 --limit 1` rendered one verified 45-second draft that covered the reference. |
| [Buddha](https://www.twitch.tv/videos/2901578792), 01:07:00–01:22:00 | [Clip A](https://clips.twitch.tv/BenevolentBovineBatteryOneHand-pug4WlwAl7kVf0h6) at 01:10:40–01:11:02, [clip B](https://clips.twitch.tv/RacyRealMochaBCouch-FsBbdBF2iHm5lzr9) at 01:10:58–01:11:28, and [clip C](https://clips.twitch.tv/PoliteFragileBeaverLitty-d6YA_II7uaJSbgkO) at 01:18:36–01:19:06 | Five picks. Three partial intervals, zero full intervals. The first two references overlap and describe one cluster. | `--after 50` kept the same five peak times and covered all three intervals. Five 70-second portrait drafts decoded with audio, adding 150 seconds to total review time. |

A [separate pre-existing Burn clip](https://www.twitch.tv/burn/clip/AmusedCarelessCurlewTheTarFu-h_VtfI85cu8616PO) served as a manual-mode input. The 32–52 second cut decoded at 1080 × 1920 with audio.

For the Diables and Buddha comparisons, the longer windows were chosen after reviewing the baseline. They demonstrate the effect of adding context to these examples. The global defaults were unchanged.
