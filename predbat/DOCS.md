#  Predbat Home Assistant App

This app can be used with Home Assistant to run Predbat without AppDaemon, or even outside Home Assistant

![image](https://github.com/springfall2008/predbat_addon/assets/48591903/50580da1-5110-4711-b740-1c14cc103835)

For Predbat documention see: https://springfall2008.github.io/batpred/

If you want to buy me a beer then please use Paypal - [tdlj@tdlj.net](mailto:tdlj@tdlj.net)
![image](https://github.com/springfall2008/batpred/assets/48591903/b3a533ef-0862-4e0b-b272-30e254f58467)

## Installation as an app in Home Assistant

[![Open your Home Assistant instance and show the add app repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkamien5%2Fpredbat_addon)

* Go to settings, apps, install app, custom repositories
* Add 'https://github.com/kamien5/predbat_addon' as a new repository

![image](https://github.com/springfall2008/predbat_addon/assets/48591903/7eb18076-888b-4ea5-844b-cfa93157b759)

* Click out of the repository list and refresh the page
* Scroll down and find "Predbat (kamien5 fork)", click on it and click 'Install'
* This fork ships Predbat v9.5.0 inside the image and never downloads or updates Predbat at runtime
* Optionally set the `notify_device` option (for example `mobile_app_my_phone`, lowercase letters, digits and `_` only).
  Leave it empty to disable Predbat notifications: an empty value renders `notify_devices: []`, which differs
  from upstream Predbat, where a missing setting means `['notify']`
* Start the app. On every start it verifies the pinned code, installs it into `/addon_configs/fc83ef65_predbat`
  and writes `apps.yaml` from the image, filling in the Home Assistant location and the `notify_device` option
* `apps.yaml` in `/addon_configs/fc83ef65_predbat` is regenerated on every start, so manual edits there are
  overwritten; configuration changes go through this repository
* The `fc83ef65` prefix is not fixed: Home Assistant derives it from the repository URL as the first
  8 characters of the sha1 of the lowercased URL. For `https://github.com/kamien5/predbat_addon`:

  ```bash
  printf '%s' 'https://github.com/kamien5/predbat_addon' | tr 'A-Z' 'a-z' | sha1sum | cut -c1-8
  ```

  A fork published under another URL gets a different directory name.
* The hash is computed from the repository URL exactly as it is entered in Home Assistant (only
  lowercased). A trailing `.git` or `/`, or a `#branch` suffix, gives a different directory, so add
  the repository exactly as `https://github.com/kamien5/predbat_addon`
* Click restart on the app if need be

### EV charging energy (`car_charging_energy`)

The shipped `apps.yaml` keeps `num_cars: 0` (Predbat does not plan car charging) but sets
`car_charging_energy`, so energy used by the car can be removed from the house load history
(`car_charging_hold`). For this to work:

* `car_charging_energy` must point to an energy sensor in kWh with `state_class: total_increasing`
  (a cumulative counter, not power), and the recorder must store its history (not excluded in
  `recorder:`); Predbat reads it from history
* `switch.predbat_car_energy_reported_load` must be on (default on). When it is off, Predbat treats car
  energy as not part of the measured load and disables `car_charging_hold`, so nothing is subtracted
* if the sensor has no history, Predbat logs a warning and falls back to the `car_charging_threshold`
  heuristic

Please note the predbat.log will be in this addon_configs directory also.

Do not run this at the same time as the appdaemon-predbat or Predbat within AppDaemon (stop them first and remember to only have one on auto-start)

## Installation outside Home Assistant / standalone Docker

Not supported by this fork: `run.csh` and `Dockerfile.standalone` were removed, and the add-on
expects the Home Assistant Supervisor. Use upstream
[springfall2008/predbat_addon](https://github.com/springfall2008/predbat_addon) for those setups.

## Upgrading from AppDaemon to Predbat app

Step-by-step instructions to upgrade from running Predbat within AppDaemon or the AppDaemon-predbat add-on to using this Predbat app are included in the [Predbat installation instructions](https://springfall2008.github.io/batpred/install/#upgrading-from-appdaemon-to-predbat-app)

## Copyright

```text
Copyright (c) Trefor Southwell 2024 - All rights reserved
This software maybe used at no cost for personal use only.
No warranty is given, either expressed or implied.
```
