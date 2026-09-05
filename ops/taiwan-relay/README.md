# taiwan-relay

A fetch relay for the one class of source that refuses every egress available
to automation: `ins-info.ib.gov.tw`, the Insurance Bureau's statutory
disclosure portal. Measured 2026-09-05 (decisions 4.13), it refuses this
project's sandbox and a GitHub-hosted runner identically — the TCP connect
never completes — while the same URLs succeed from a Taiwanese connection.
Every other source the project needs is reachable from one of the two, so this
exists solely to give continuous integration a Taiwanese address.

## What it is not

Not a general proxy. It forwards only to hosts in `ALLOWED_HOSTS` (currently
one), only over https, and only when the caller presents `X-Relay-Token`
matching the `RELAY_TOKEN` environment variable. Widen `ALLOWED_HOSTS`
deliberately, never as a convenience. Behaviour verified locally: missing and
wrong tokens are refused, a foreign host is refused, a plain-http target is
refused, and only the allowlisted https target is forwarded.

## Deploy

Use **Google Cloud Shell**: `gcloud` is installed and already authenticated
there, so nothing is needed on your own machine.

- **Desktop or iPad:** open <https://console.cloud.google.com> and tap the
  `>_` icon. On iPad, Safari serves the desktop console by default and the
  terminal behaves normally.
- **iPhone:** the browser terminal is cramped; the Google Cloud iOS app has a
  built-in Cloud Shell with a control-key row, which is easier on a small
  screen.

The build takes a few minutes. Keep the tab or app in the foreground while it
runs — a backgrounded mobile session can drop the connection. If it does, the
build continues server-side and re-running the command is safe either way.

One line, so it can be pasted on a phone or tablet as easily as a laptop.
Cloud Shell usually opens with a project already selected and `deploy.sh`
uses whatever is set, so try this first:

```
rm -rf ~/tlfx && git clone -q https://github.com/WillBtK/Taiwan-Lifers.git ~/tlfx && bash ~/tlfx/ops/taiwan-relay/deploy.sh
```

If it stops because no project is set, find yours — the Cloud Shell prompt
shows it in brackets, or run `gcloud config get-value project`, or
`gcloud projects list` for all of them. It is the lowercase hyphenated id,
not the display name and not the numeric project number. Then prefix the
line above with `gcloud config set project YOUR_PROJECT_ID &&`. An empty
`projects list` means there is no project yet, and creating one with billing
attached is the only genuinely fiddly step on a phone.

It re-clones into `~/tlfx` each time so a repeat run always deploys current
code, and Cloud Shell's home directory persists between sessions.

`deploy.sh` enables the two required APIs, deploys from source to Cloud Run in
`asia-east1`, and prints the service URL and a generated token. It is safe to
re-run.

`asia-east1` is the whole point: it is physically in Changhua, Taiwan. No
other mainstream provider currently offers a Taiwanese region, which is why
this targets Google rather than being provider-neutral.

## Then verify, before trusting it

```
RELAY_URL=... RELAY_TOKEN=... bash ops/taiwan-relay/verify.sh
```

This matters more than it looks. Cloud Run egress uses shared Google-owned
addresses that are **not always geolocated to the region running the
service**, and the origin filters on geography. So whether this works cannot
be established from the architecture; it has to be measured. `verify.sh`
fetches a real payload and tells you which case you are in.

- **PASS** — add the secrets below and the weekly workflow takes over.
- **FAIL with 502** — the relay reached the origin and the origin refused.
  Cloud Run's egress is not being read as Taiwanese. The fallback is a Compute
  Engine `e2-micro` in `asia-east1` with its own external address, running
  this same app; a dedicated regional address geolocates reliably where shared
  Google ranges may not. Roughly USD 7–10/month at current list prices, which
  you should confirm rather than take from this file. Google's always-free
  `e2-micro` allowance does not cover `asia-east1`.

## Wire it to CI

Add two repository secrets under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `TAIWAN_RELAY_URL` | the service URL `deploy.sh` prints |
| `TAIWAN_RELAY_TOKEN` | the token `deploy.sh` prints |

`.github/workflows/fetch-sources.yml` picks them up with no code change. Until
they exist, that workflow still runs and still collects every other source;
the relay-bound ones are recorded unavailable rather than failing the run.

## Cost and exposure

Cloud Run scales to zero and this is called a handful of times a month, so it
sits inside the free tier in normal use. Confirm against current pricing
rather than taking that on trust.

`--allow-unauthenticated` puts authentication in the relay's own token rather
than in Google IAM, which is what lets a GitHub runner call it with a single
header and no service-account key. The token is therefore the only thing
standing between the relay and anyone who finds the URL — but the blast radius
is bounded by design, since the worst an attacker gains is the ability to
fetch a public Taiwanese government page. Rotate by re-running `deploy.sh`
with a new `RELAY_TOKEN` and updating the secret. Some organisations forbid
unauthenticated Cloud Run services by policy; if the deploy is rejected on
those grounds, switch to IAM authentication and give the workflow a service
account, which is more setup for the same result.
