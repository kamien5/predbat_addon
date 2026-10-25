# Przegląd bezpieczeństwa: fork kamien5/predbat_addon (hardening/kamien5-v1)

Baza: `springfall2008/predbat_addon` @ `587e1a7a32cdf2b1d9e427b37411bfe102c713b1` (add-on 1.7.1).
Kod Predbata: `springfall2008/batpred` tag `v9.5.0` = commit `0cfceaaa719b9ce3de1d10185578feffb008908b`
(zweryfikowane `git ls-remote` i `git rev-parse v9.5.0^{commit}`), zwendorowany w `predbat/vendor/`
(114 plików, `predbat/MANIFEST.sha256`, opis w `predbat/VENDOR.txt`).
Data przeglądu: 2026-10-25.

## 1. Token Supervisora i nagłówek Authorization w batpred v9.5.0

Zakres: wszystkie pliki `predbat/vendor/*.py`. Przejrzane wystąpienia `SUPERVISOR_TOKEN`, `ha_key`,
`Authorization`, `Bearer` oraz wywołania `log()`/`print()` zawierające `token`/`key`:

```
cd predbat/vendor
grep -n -i -w -e SUPERVISOR_TOKEN -e ha_key -e Authorization -e Bearer *.py
grep -n -i -E "(self\.log|print)\(.*\b(ha_key|SUPERVISOR_TOKEN|Authorization|Bearer|token|key)\b" *.py
```

Wynik:
- Token Supervisora jest czytany ze zmiennej środowiskowej i używany wyłącznie w nagłówku żądań HTTP
  i w wiadomości uwierzytelniającej websocketu; żadne z tych miejsc nie jest logowane.
- Komunikaty błędów połączenia z HA zawierają tylko URL, nazwę ustawienia lub obiekt odpowiedzi,
  nigdy wartości tokenu ani nagłówków.
- `print` kluczy API występuje tylko w narzędziach wiersza poleceń (`__main__`), nie w działaniu add-onu.
- Logi stanu tokenów innych integracji (pobrany/odświeżony/odrzucony) nie zawierają wartości.
- Predbat ma własną redakcję wartości z `secrets.yaml` i kluczy-poświadczeń w apps.yaml.

Wniosek: Predbat v9.5.0 nie wypisuje tokenu Supervisora ani nagłówka Authorization do logu.

## 2. Utwardzenie UI/API WWW (defensywne)

Serwer WWW Predbata (port 5052) nie ma własnego uwierzytelniania. Fork dodaje w `launch.py`
(kod zwendorowany bez zmian):
- maskowanie pól sekretnych i lokalizacji w odpowiedziach UI/API (`***configured***`): pola oznaczone
  w rejestrze jako sekretne, rozpoznawane przez `utils.is_secret_key`, nazwy z `_key`, `token`,
  `password`, `secret`, `api_key` oraz `latitude`/`longitude`; przy błędzie przetwarzania odpowiedź
  jest odrzucana (fail closed);
- `latitude`/`longitude` dopisane do nazw traktowanych przez Predbata jak poświadczenia (maskowanie
  w UI, eksporcie diagnostycznym i redakcji logów);
- dostęp do UI tylko z proxy ingress Supervisora (172.30.32.2) i loopback, inne adresy dostają 403;
- wyłączone surowe edytory/eksport apps.yaml (apps.yaml i tak jest generowany od nowa przy każdym starcie).

Testy: `tests/test_web_hardening.py`.

## 3. Ścieżki samoaktualizacji i wykonania obcego kodu

| Ścieżka | Neutralizacja w forku |
|---|---|
| `select.predbat_update`, `update.predbat_version`, `auto_update` | funkcje pobierania/instalacji z `download.py` zastąpione zaślepkami w `launch.py` przed importem `predbat` |
| naprawa instalacji przy starcie (pobranie z GitHuba) | `startup.py` zapisuje `/config/manifest.yaml` z przypiętych plików, sprawdzenie przechodzi offline |
| wtyczki `*_plugin.py`, pakiety przesłaniające moduły, `__pycache__`, nieprzypięte `.py/.pyc/.so` (w tym `prediction_kernel_lib.so`) | usuwane z `/config` przy każdym starcie; Predbat uruchamiany `python3 -I -B` |
| zmienne środowiskowe `PREDBAT_*` (m.in. `PREDBAT_KERNEL_SO`, przełączniki testowe) | `run.sh` usuwa wszystkie `PREDBAT_*` przed startem; nie ma ich w opcjach add-onu |
| hot-reload po zmianie `.py` | restart add-onu -> `startup.py` przywraca przypięty kod |

Test (`tests/test_startup.py`): podmiana `/config/predbat.py` -> restart -> `restored: predbat.py`,
sha256 = MANIFEST. Na kodzie v9.5.0: żądanie aktualizacji do `v9.6.0` i `main` -> komunikat
"Predbat self-update is disabled in the kamien5 fork", zero zapytań sieciowych.

## 4. Prekompilowane biblioteki `prediction_kernel_lib_*.so`

Sumy w `MANIFEST.sha256` porównane z plikami w tagu v9.5.0 (`git show 0cfceaaa:apps/predbat/<plik> | sha256sum`):

| plik | sha256 | zgodność z tagiem |
|---|---|---|
| prediction_kernel_lib_aarch64.so | f690fb4242a49582b0aa21c18825d0a9e89ee9428496d7761e4b72944f22c4e9 | tak |
| prediction_kernel_lib_armv7l.so | b3065e914eb9618e4545a37726d72e1545fe8e02ce993167113efadf811fdfd8 | tak |
| prediction_kernel_lib_darwin_arm64.so | 96c77873d39829d4478d11a02eea69d57984a7bb5e7511d80c83a94028ce5df1 | tak |
| prediction_kernel_lib_darwin_x86_64.so | 2f98732a51f405eb55fb1d8c5bd9d1f404f09f9a1ee0f4cedd19f6a039a22ac5 | tak |
| prediction_kernel_lib_i686.so | 4790f8b27a63dde301064f642e30802566e11d0241ff59df1743634324707075 | tak |
| prediction_kernel_lib_x86_64.so | 36e3efb7ff5129017da87b382a343db99c5024b7f4ee1edc79d30ec67dcc12b0 | tak |

Binaria zbudowane upstream (commit "update prediction kernel binaries for all platforms", 2026-09-30);
źródło `prediction_kernel.cpp` jest w vendor, binariów nie odtwarzaliśmy. Fallback w czystym Pythonie
istnieje: `prediction_kernel.py` ładuje bibliotekę przez ctypes, a gdy jej brak, jest nieaktualna lub
się nie ładuje, Predbat używa silnika Pythona (`prediction.py`). Kernel można też wyłączyć opcją
apps.yaml `prediction_kernel_enable`.

## 5. apps.yaml i dane w repo

`predbat/rootfs/apps.yaml` = pakiet v5 + prio2 (sha256 `bc4b790e3a8f63230f6ce3e4b680a9cab51d4f6212cc6072dae3f2862da3f1ee`; jedyna zmiana względem v5: `car_charging_energy` + komentarz):
tylko nazwy encji i parametry; placeholdery `__HA_LATITUDE__`, `__HA_LONGITUDE__`, `__HA_NOTIFY_DEVICE__`.
Przy każdym starcie `startup.py`: weryfikuje sha256, pobiera współrzędne z HA `GET /api/config`
(token z env, bez proxy i przekierowań), bierze `notify_device` z opcji add-onu (`^[a-z0-9_]+$`,
puste = `[]`, brak powiadomień), zapisuje `/config/apps.yaml` (0600) i kończy z kodem 1, jeśli
został jakikolwiek placeholder `__HA_*__`. Wartości nie trafiają do logu, repo ani odpowiedzi UI.

## 6. Skan sekretów i historia

- `gitleaks git --redact .` (cała historia) i `gitleaks dir --redact .`: 0 znalezisk. Jedyne
  znalezisko surowe (publiczny klucz klienta aplikacji Ohme w upstreamowym `predbat/vendor/ohme.py`)
  jest wyłączone w `.gitleaksignore` dokładnym fingerprintem.
- `git log -p --all -S` dla starej nazwy usługi powiadomień z poprzedniej wersji apps.yaml: pusto
  (żaden commit nie zawiera poprzedniego apps.yaml ani danych osobowych).
