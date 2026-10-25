# kamien5 hardened fork

This is a hardened fork of springfall2008/predbat_addon (base 587e1a7a, add-on 1.7.1):
Predbat v9.5.0 is vendored and verified against `predbat/MANIFEST.sha256` on every start,
self-update is disabled, the Supervisor token is never logged or passed in argv, permissions
are minimal (no Supervisor API, no ports, only `addon_config`), and dependencies are pinned
with hashes. See `SECURITY-REVIEW.md` and `tests/README.md`.

#  Predbat Home Assistant App
Predbat Home Assistant App

This app can be used with Home Assistant to run Predbat without AppDaemon

The code here can also be used to run Predbat outside Home Assistant (but still talking to Home Assistant)

See the documentation https://github.com/springfall2008/predbat_addon/blob/main/predbat/DOCS.md

![image](https://github.com/springfall2008/predbat_addon/assets/48591903/9151bcae-897c-49cf-b1b4-ee29501bd208)

If you want to buy me a beer then please use Paypal - [tdlj@tdlj.net](mailto:tdlj@tdlj.net)
![image](https://github.com/springfall2008/batpred/assets/48591903/b3a533ef-0862-4e0b-b272-30e254f58467)


