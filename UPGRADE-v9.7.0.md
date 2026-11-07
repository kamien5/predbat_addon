# Upgrade Predbat v9.6.5 → v9.7.0 (kamien5 fork addon 1.7.1-kamien5.4)

## Podsumowanie

Aktualizacja silnika Predbat z v9.6.5 do v9.7.0 (25 commitów upstream), zachowując wszystkie zabezpieczenia i konfigurację kamien5 fork.

## Zmiany w vendorowanym kodzie

### Nowe pliki
- `billing.py` — moduł rozliczeń Octopus/Kraken API (nieaktywny w tej instalacji, używamy polskich dostawców)

### Kluczowe upstream commity (v9.6.5..v9.7.0)

1. **fix(mcp): stop /oauth/register handing out mcp_secret** (#5847, #5992)
   - Naprawa ujawniania sekretu MCP przez niezabezpieczony endpoint
   - **NIE DOTYCZY tej instalacji** — MCP wyłączony, endpoint nie jest dostępny
   - Upstream naprawił: client credentials grant, signing key derivation, scope enforcement
   - Zabezpieczenie forka: endpoint jest już zablokowany przez `launch.py` web hardening

2. **fix(execute): treat Control SOC only charge as running charge** (#6001)
   - Dotyczy Sunsynk/SolaX w trybie Control SOC only
   - **NIE DOTYCZY FoxESS** w tej instalacji

3. **fix(sunsynk): estimate battery size from BMS** (#6007)
   - Sunsynk: estymacja pojemności z BMS zamiast ustawienia invertera
   - **NIE DOTYCZY FoxESS**

4. **feat(gecloud): cut GE Cloud API calls ~95%** (#6005)
   - Optymalizacja GE Cloud
   - **NIE DOTYCZY** — nie używamy GE Cloud

5. **Show billing in History view** (#6009, #5926)
   - Wyświetlanie rzeczywistych rachunków Octopus/Kraken w widoku History
   - **NIEAKTYWNE** — billing.py nie jest konfigurowany, brak kluczy API

6. **fix(plan): export must earn its keep on nominal metric** (#5977)
   - Lepsza walidacja okien eksportu
   - **POZYTYWNE** — ogólna poprawa jakości planowania

7. **fix(solcast): scale P10/P90 with calibrated P50** (#5974)
   - Kalibracja scenariuszy pesymistycznych/optymistycznych
   - **POZYTYWNE** — używamy Forecast.Solar, ale może mieć wpływ na plany

## Zgodność z zabezpieczeniami kamien5

### ✅ Wszystkie zabezpieczenia zachowane

1. **Samoaktualizacja wyłączona** — `launch.py` stubs działają
2. **Vendor integrity** — MANIFEST.sha256 zaktualizowany (115 plików)
3. **Web hardening** — testy passed, wszystkie blocked endpoints nadal zablokowane
4. **apps.yaml pinning** — zachowany SHA256 (niezmieniony)
5. **Supervisor token** — nigdy nie logowany
6. **MCP endpoints** — zablokowane (dodatkowo upstream naprawił lukę)

### Testy regresji

```bash
pytest tests/ -v
# Result: 40 passed, 5 skipped
```

Wszystkie testy bezpieczeństwa i vendor integrity przeszły.

## Zachowane zachowania konfiguracyjne

### apps.yaml — BEZ ZMIAN

Konfiguracja niezmieniona:
- `battery_min_soc: [input_number.battery_min_soc]` — min SoC 11% przez guardian HA
- `inverter_limit_charge: [5100]` — limit ładowania 5.1 kW
- `battery_rate_max: [5300]` — max baterii 5.3 kW
- `charge_start_service: script.bateria_force_charge` — guardian FC+PV 0.5kW
- Wszystkie discharge services → "Self Use" (eksport zablokowany)

**UWAGA DEPLOYMENT:** Obecna konfiguracja ma `inverter_limit_charge: [5100]` (5.1 kW).
Według komentarza w apps.yaml, to "foxess_modbus: Predbat nie czyta limitu z falownika".
Jeśli chcesz zwiększyć ten limit, zmień apps.yaml PRZED deploymentem i przelicz SHA256.

Guardian HA nadal egzekwuje limity przyłącza (15kW/25A per faza).

## Ocena ryzyka

### 🟢 Niskie ryzyko

- Upstream naprawił lukę MCP, która **nie dotyczy** tej instalacji (MCP wyłączony + blocked)
- Nowy moduł `billing.py` **nieaktywny** (brak konfiguracji Octopus/Kraken)
- Zmiany w execute.py, sunsynk.py, gecloud.py **nie dotyczą FoxESS**
- Usprawnienia plan.py i solcast.py **ogólne** — poprawa jakości planów

### 🟡 Do obserwacji

1. **Zmienione zachowanie eksportów** — `export_gate_metric` (#5977)
   - Monitoruj: czy Predbat nadal nie próbuje eksportować (wszystkie discharge services = Self Use)
   
2. **Calibrated P10/P90** — Solcast/Forecast.Solar (#5974)
   - Monitoruj: scenariusze pesymistyczne/optymistyczne w pierwszych 24h

3. **Billing entity** — nowa encja `sensor.predbat_billing`
   - Powinna pozostać nieaktywna (brak upstream API)

## Weryfikacja po deployment

### Sprawdzenia obowiązkowe (pierwsze 30 min)

1. **Wersja**: `sensor.predbat_status` = **9.7.0** (nie 9.6.5)
2. **Vendor integrity**: log nie zawiera "MANIFEST mismatch"
3. **Web endpoints**: UI dostępny przez ingress, admin endpoints blocked
4. **Work mode**: dozwolone tylko Self Use, Back-up, Force Charge
5. **Min SoC**: `number.min_soc_on_grid` ≈ 11%
6. **Guardian FC+PV**: przy PV > 0.5 kW i koszcie ≥ 0 → Self Use
7. **Eksport**: Predbat NIE wywołuje Force Discharge / Feed-in First
8. **Plan**: nowy plan wygenerowany w ciągu 30 min

### Obserwacja (2-4h)

1. Przejścia `work_mode` zgodne z planem + guardian
2. SoC nie spada < 11% on-grid bez uzasadnienia
3. FC nie utrzymuje się podczas PV > 0.5 kW z kosztem ≥ 0
4. Import z sieci podczas tanich okien G13 zgodny z planem
5. Brak flood w logu (Fox warnings, download attempts)
6. `sensor.predbat_billing` nieaktywny (brak danych)

## Rollback procedure

### Warunki rollbacku

- `work_mode` utknął poza allowlist
- SoC < 11% on-grid bez uzasadnienia
- FC utrzymuje się podczas PV > 0.5 kW z kosztem ≥ 0
- Brak nowego planu > 1 cykl planowania
- Krytyczne błędy automatyzacji

### Kroki rollbacku

1. **Settings → System → Backups**
2. Wybierz backup sprzed update
3. **Restore** add-on Predbat
4. Po restarcie: verify `sensor.predbat_status` = 9.6.5
5. Verify checklist (jak po deployment)

**Backup OBOWIĄZKOWY przed update.**

## Wdrożenie

### Pre-deployment checklist

✅ **OBOWIĄZKOWO przed update:**

1. Full HA backup (Settings → System → Backups)
2. Record:
   - `sensor.predbat_status` version
   - `select.work_mode`
   - `number.min_soc_on_grid`
   - Screenshot obecnego planu Predbat
3. Backup `/addon_configs/.../` (optional)

### Timing

Wdróż:
- Dzień, operator obecny
- Poza oknami ładowania G13
- 2-4h observation window

### Path: kamien5 Fork (standard)

1. Nowy image `1.7.1-kamien5.4` (Predbat v9.7.0) published do repo
2. HA: **Settings → Add-ons → Predbat (kamien5 fork)** → refresh repo
3. Gdy Supervisor pokaże update dla `update.predbat_kamien5_fork_update`:
   - **Update**
4. Po instalacji: **Restart** add-on Predbat
5. Verify (patrz wyżej)
6. Observe 2-4h

**NIE używaj** `select.predbat_update` — self-update disabled w kamien5.

## Limitacje znane

1. **MCP server** — zablokowany w forku (upstream naprawił lukę, ale endpoint i tak niedostępny)
2. **Billing / History koszty Octopus** — nieaktywne (brak Kraken API)
3. **Sunsynk BMS battery size** — nie dotyczy FoxESS
4. **GE Cloud optimizations** — nie dotyczy tej instalacji

## Commit SHA i tagi

- Upstream tag: `v9.7.0` = commit `4cbf633355525ea62ddf8e47e647ee215b38f1ca`
- Addon version: `1.7.1-kamien5.4`
- PR branch: `cursor/vendor-predbat-v9.7.0-2ba3`
- Vendor files: 115 (was 114, +billing.py)

## Dokumenty powiązane

- `SECURITY-REVIEW.md` — przegląd bezpieczeństwa v9.5.0 (fork kamien5-v1)
- `DEPLOY.md` — ogólna procedura deployment/rollback
- Upstream release notes: https://github.com/springfall2008/batpred/releases/tag/v9.7.0

---

**Przygotował:** Cursor Agent  
**Data:** 2026-11-07  
**Status:** READY FOR REVIEW — nie deploy do koordynacji z Piotrem
