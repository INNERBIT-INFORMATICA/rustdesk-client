#!/usr/bin/env python3
"""
Generate a custom Windows RustDesk client by dispatching
generator-windows.yml directly via the GitHub CLI (`gh`) -- no rdgen
server required.

Builds the same "custom.txt" settings payload that the rdgen web form
produces (see rdgenerator/views.py:generate_custom_client), base64-encodes
it together with the connection settings, and triggers the workflow with
`gh workflow run`. Icon/logo files (if given) are embedded as base64
inputs instead of being fetched over HTTP.

Requires: `gh` authenticated with `repo` + `workflow` scope for the target
fork (gh auth status).

Example:
    python3 rdgen_cli.py \\
        --repo Welington98/rdgen \\
        --server rustdesk.innerbit.com.br \\
        --key "ZMLOYLzSTnPmfaWMds0RMWHtXApkfLY+wSk5K5QuKIo=" \\
        --filename innerbit-rustdesk \\
        --version 1.5.0
"""
import argparse
import base64
import json
import re
import subprocess
import sys

UNSAFE_NAME_CHARS = re.compile(r'[&\\|\'"$`\r\n]')


def reject_unsafe(value, field):
    if value and UNSAFE_NAME_CHARS.search(value):
        print(f"error: --{field} contains unsupported characters (& \\ | ' \" $ `, newlines)", file=sys.stderr)
        sys.exit(1)
    return value


def validate_png(path):
    try:
        from PIL import Image
    except ImportError:
        print("warning: Pillow not installed, skipping icon/logo validation", file=sys.stderr)
        return
    with Image.open(path) as img:
        if img.format != 'PNG':
            print(f"error: {path} is not a PNG file", file=sys.stderr)
            sys.exit(1)
        w, h = img.size
        if w != h:
            print(f"error: {path} must be square (got {w}x{h})", file=sys.stderr)
            sys.exit(1)


def b64_file(path):
    if not path:
        return ""
    validate_png(path)
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def build_custom(args):
    """Mirrors the decodedCustom construction in rdgenerator/views.py."""
    custom = {}
    if args.direction != 'both':
        custom['conn-type'] = args.direction
    if args.disable_installation:
        custom['disable-installation'] = 'Y'
    if args.disable_settings:
        custom['disable-settings'] = 'Y'
    if args.appname and args.appname.lower() != 'rustdesk':
        custom['app-name'] = args.appname
    custom['override-settings'] = {}
    custom['default-settings'] = {}
    if args.permanent_password:
        custom['password'] = args.permanent_password
    if args.theme != 'system':
        target = custom['override-settings'] if args.theme_override else custom['default-settings']
        target['theme'] = args.theme
    custom['enable-lan-discovery'] = 'N' if args.deny_lan else 'Y'
    custom['allow-auto-disconnect'] = 'Y' if args.auto_close else 'N'

    target = custom['override-settings'] if args.permissions_override else custom['default-settings']
    target['access-mode'] = args.permissions_type
    target['enable-keyboard'] = 'N' if args.disable_keyboard else 'Y'
    target['enable-clipboard'] = 'N' if args.disable_clipboard else 'Y'
    target['enable-file-transfer'] = 'N' if args.disable_file_transfer else 'Y'
    target['enable-audio'] = 'N' if args.disable_audio else 'Y'
    target['enable-tunnel'] = 'N' if args.disable_tcp else 'Y'
    target['enable-remote-restart'] = 'N' if args.disable_remote_restart else 'Y'
    target['enable-record-session'] = 'N' if args.disable_recording else 'Y'
    target['enable-block-input'] = 'N' if args.disable_blocking_input else 'Y'
    target['allow-remote-config-modification'] = 'Y' if args.enable_remote_modi else 'N'
    target['direct-server'] = 'Y' if args.enable_direct_ip else 'N'
    target['verification-method'] = 'use-permanent-password' if args.hide_connection_window else 'use-both-passwords'
    target['approve-mode'] = args.pass_approve_mode
    target['allow-hide-cm'] = 'Y' if args.hide_connection_window else 'N'
    target['allow-remove-wallpaper'] = 'N' if args.keep_wallpaper else 'Y'
    target['enable-remote-printer'] = 'N' if args.disable_printer else 'Y'
    target['enable-camera'] = 'N' if args.disable_camera else 'Y'
    target['enable-terminal'] = 'N' if args.disable_terminal else 'Y'
    if args.permissions_override and args.direction == 'incoming':
        target['custom-rendezvous-server'] = args.server
        target['api-server'] = args.api_server

    for line in (args.default_manual or '').splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            custom['default-settings'][k.strip()] = v.strip()
    for line in (args.override_manual or '').splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            custom['override-settings'][k.strip()] = v.strip()

    return custom


def build_config(args):
    server = args.server or 'rs-ny.rustdesk.com'
    server_port = args.server_port or '21116'
    key = args.key or 'OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw='
    api_server = args.api_server or f"{server}:21114"
    url_link = args.url_link or 'https://rustdesk.com'
    download_link = args.download_link or 'https://rustdesk.com/download'
    appname = reject_unsafe(args.appname, 'appname') or 'rustdesk'
    compname = (reject_unsafe(args.compname, 'compname') or 'Purslane Ltd').replace('&', r'\&')
    androidappid = args.android_app_id or 'com.carriez.flutter_hbb'

    filename = re.sub(r'[^\w\s-]', '_', args.filename).strip().replace(' ', '_')
    if not filename or not all(ch.isascii() for ch in args.filename):
        print("error: --filename must be non-empty ASCII", file=sys.stderr)
        sys.exit(1)

    custom_json = json.dumps(build_custom(args))
    custom_b64 = base64.b64encode(custom_json.encode('ascii')).decode('ascii')

    config = {
        "server": server,
        "serverPort": server_port,
        "key": key,
        "apiServer": api_server,
        "custom": custom_b64,
        "appname": appname,
        "urlLink": url_link,
        "downloadLink": download_link,
        "delayFix": 'true' if args.delay_fix else 'false',
        "xOffline": 'true' if args.x_offline else 'false',
        "removeNewVersionNotif": 'true' if args.remove_new_version_notif else 'false',
        "compname": compname,
        "androidappid": androidappid,
        "filename": filename,
    }
    return config


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--repo', required=True, help='GitHub repo to dispatch against, e.g. Welington98/rdgen')
    p.add_argument('--ref', default='master', help='branch to run the workflow from')
    p.add_argument('--version', default='1.5.0', help='RustDesk version to build')
    p.add_argument('--filename', required=True, help='output exe/msi name (no spaces/special chars)')
    p.add_argument('--server', help='custom rendezvous server host (default: rs-ny.rustdesk.com)')
    p.add_argument('--server-port', default='', help='rendezvous port (default: 21116)')
    p.add_argument('--key', help='server public key')
    p.add_argument('--api-server', default='', help='API server (default: <server>:21114)')
    p.add_argument('--url-link', default='', help='custom URL replacing https://rustdesk.com')
    p.add_argument('--download-link', default='', help='custom download URL')
    p.add_argument('--appname', default='', help='custom app name')
    p.add_argument('--compname', default='', help='company name for copyright')
    p.add_argument('--android-app-id', default='', help='custom android app id')
    p.add_argument('--icon', default='', help='path to a square PNG icon')
    p.add_argument('--logo', default='', help='path to a square PNG logo')
    p.add_argument('--direction', choices=['incoming', 'outgoing', 'both'], default='both')
    p.add_argument('--disable-installation', action='store_true')
    p.add_argument('--disable-settings', action='store_true')
    p.add_argument('--theme', choices=['light', 'dark', 'system'], default='system')
    p.add_argument('--theme-override', action='store_true', help='make theme non-changeable by the user')
    p.add_argument('--permanent-password', default='')
    p.add_argument('--pass-approve-mode', choices=['password', 'click', 'password-click'], default='password-click')
    p.add_argument('--deny-lan', action='store_true')
    p.add_argument('--enable-direct-ip', action='store_true')
    p.add_argument('--auto-close', action='store_true')
    p.add_argument('--hide-connection-window', action='store_true')
    p.add_argument('--permissions-override', action='store_true', help='make permissions non-changeable by the user')
    p.add_argument('--permissions-type', choices=['custom', 'full', 'view'], default='custom')
    p.add_argument('--enable-remote-modi', action='store_true')
    p.add_argument('--keep-wallpaper', action='store_true')
    for flag in ('keyboard', 'clipboard', 'file-transfer', 'audio', 'tcp',
                 'remote-restart', 'recording', 'blocking-input', 'printer',
                 'camera', 'terminal'):
        p.add_argument(f'--disable-{flag}', action='store_true')
    p.add_argument('--delay-fix', dest='delay_fix', action='store_true', default=True)
    p.add_argument('--no-delay-fix', dest='delay_fix', action='store_false')
    p.add_argument('--x-offline', action='store_true')
    p.add_argument('--remove-new-version-notif', action='store_true')
    p.add_argument('--default-manual', default='')
    p.add_argument('--override-manual', default='')
    p.add_argument('--platform', choices=['windows', 'linux', 'macos', 'android'], default='windows',
                    help='windows-x86 is not wired up to this CLI-only path yet')
    p.add_argument('--dry-run', action='store_true', help='print the gh command instead of running it')
    args = p.parse_args()

    workflow = {
        'windows': 'generator-windows.yml',
        'linux': 'generator-linux.yml',
        'macos': 'generator-macos.yml',
        'android': 'generator-android.yml',
    }[args.platform]

    config = build_config(args)
    config_b64 = base64.b64encode(json.dumps(config).encode('utf-8')).decode('ascii')
    icon_b64 = b64_file(args.icon)
    logo_b64 = b64_file(args.logo)

    cmd = [
        'gh', 'workflow', 'run', workflow,
        '--repo', args.repo,
        '--ref', args.ref,
        '-f', f'version={args.version}',
        '-f', f'config_b64={config_b64}',
        '-f', f'icon_b64={icon_b64}',
        '-f', f'logo_b64={logo_b64}',
    ]

    if args.dry_run:
        print(' '.join(cmd[:6] + ['-f', 'version=...', '-f', 'config_b64=<%d chars>' % len(config_b64),
                                   '-f', 'icon_b64=<%d chars>' % len(icon_b64),
                                   '-f', 'logo_b64=<%d chars>' % len(logo_b64)]))
        print("\nDecoded config:")
        print(json.dumps(config, indent=2))
        return

    subprocess.run(cmd, check=True)
    print(f"\nDispatched. Watch it with:\n  gh run list --repo {args.repo} --workflow {workflow} --limit 1")
    artifact_hints = {
        'windows': config['filename'],
        'linux': f"{config['filename']}-<arch>-packages (e.g. {config['filename']}-x86_64-packages), "
                 f"plus {config['filename']}-<arch>.AppImage / .flatpak",
        'macos': f"{config['filename']}-<arch>.dmg (arch: x86_64 or aarch64)",
        'android': f"{config['filename']}-<arch>.apk (arch: aarch64, armv7 or x86_64)",
    }
    print("Once it succeeds, a 'publish-release' job attaches the built files to a "
          "GitHub Release (tag {filename}-{version}-<run-id>), downloadable with a stable "
          "URL, e.g.:\n"
          f"  https://github.com/{args.repo}/releases\n"
          "\nOr, to list/download via gh instead:\n"
          f"  gh release list --repo {args.repo}\n"
          f"  gh release download <tag> --repo {args.repo}\n"
          "\nArtifacts (90-day expiry) are still produced too, if you need those instead:\n"
          f"  gh run view <run-id> --repo {args.repo}\n"
          f"  gh run download <run-id> --repo {args.repo} -n <artifact-name>\n"
          f"(artifact name pattern: {artifact_hints[args.platform]})")


if __name__ == '__main__':
    main()
