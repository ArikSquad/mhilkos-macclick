# MacClik

MacClik is a small, native autoclicker written in Rust. It supports Linux,
macOS (Intel and Apple Silicon), and Windows.

## Features

- Global, rebindable start/stop hotkey
- Left, right, and middle clicks
- Single or double click
- Millisecond-to-hour intervals
- Current pointer or fixed coordinates
- Run until stopped or for a fixed count

## Install

Download the archive for your platform from
[Releases](https://github.com/Mhilkos/MacClik/releases).

On macOS, move `MacClik.app` to Applications, open it, and allow it under
**System Settings → Privacy & Security → Accessibility**. The Intel and Apple
Silicon downloads are native builds for their respective processors.

On Linux, extract the archive and run `./macclik`. MacClik currently requires
an X11 session; native Wayland input injection is not broadly supported by
desktop compositors.

## Build

Install [Rust](https://rustup.rs/), then run:

```sh
cargo run --release
```

Linux builds need the X11 development libraries. On Debian or Ubuntu:

```sh
sudo apt install libx11-dev libxi-dev libxtst-dev libxcb1-dev \
  libxkbcommon-dev libwayland-dev
```

## Release

Push a version tag to build and publish all platform archives:

```sh
git tag v0.2.0
git push origin v0.2.0
```

The GitHub Actions workflow creates native Intel and Apple Silicon macOS app
bundles, plus Linux and Windows binaries. Builds are currently unsigned, so
macOS may require right-clicking the app and choosing **Open** on first launch.

## License

[MIT](LICENSE)
