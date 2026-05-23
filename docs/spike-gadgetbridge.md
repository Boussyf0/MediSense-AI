# Spike — MediSense Band (Gadgetbridge-wrapped HRV companion)

**Status:** planned
**Owner:** Abderrahim Boussyf
**Target:** 3–5 working days for spike; +2 weeks hardening if green
**Created:** 2026-05-20

## 1. Problem statement

The mobile sync (`frontend/mobile/lib/features/iot/domain/health_sync_service.dart`) reads HR / SpO₂ / HRV from Health Connect. Mi Fitness — Xiaomi's official bridge from the Mi Band 7 Pro to Health Connect — **does not publish HRV at all**. Confirmed on 2026-05-20 by inspecting the Mi Fitness data-authorization screen on the user's phone: HRV is not in the list of writable types. SpO₂ comes through (4 points in 24h), HR comes through when the user forces a Mi Fitness sync; HRV is structurally absent.

The Mi Band 7 Pro **does** measure HRV internally — it powers the in-app stress score and sleep recovery. Xiaomi just keeps the raw value locked inside Mi Fitness. To get HRV into MediSense we must bypass Mi Fitness and read the band over BLE ourselves.

## 2. Goal

Prove that a separate Android companion app, forked from **Gadgetbridge** (GPLv3), can:

1. Pair with the Mi Band 7 Pro (reusing Gadgetbridge's existing Xiaomi auth handshake).
2. Stream HR samples + RR intervals over BLE.
3. Compute **RMSSD** locally over a 60-second sliding window.
4. `POST /iot/ingest` to the MediSense backend on the same `(device_id, ts)` contract `health_sync_service.dart` already uses.

Spike succeeds if ≥1 hour of continuous HR samples + ≥10 plausible RMSSD readings flow end-to-end from the real band into the dashboard.

## 3. Architecture

```
[Mi Band 7 Pro]
      |  BLE  (Xiaomi proprietary auth — handled by Gadgetbridge core, untouched)
      v
[MediSense Band companion APK]                              <- GPLv3, Android-only
      |  - reuses Gadgetbridge's BLE manager + device support
      |  - new HrvComputer: RMSSD over 60s sliding RR buffer
      |  - new HttpIngestSink: Retrofit + WorkManager, exp. backoff, idempotent
      |  - reads JWT from main app via ContentProvider (no token duplication)
      v
  POST /iot/ingest   { device_id, samples: [{ts, hr, spo2, hrv}], battery }
      |
      v
[MediSense backend]   <- unchanged contract; new vendor='xiaomi' source='gadgetbridge'
      |
      v
[MediSense main app]  <- unchanged; sees a new device_id and renders vitals
```

### Why two APKs

The companion is a **derivative of Gadgetbridge (GPLv3)**. The main MediSense app is proprietary. Communicating over Android Intents / ContentProvider is the standard IPC boundary the FSF considers *not* linking — same pattern K-9 Mail uses to talk to OpenKeychain. Keeping the GPL code in its own process keeps the main app's licensing untouched.

### Why Gadgetbridge specifically

It already solves the hardest problem: the **Xiaomi auth handshake** for Mi Band 5/6/7/7 Pro/8. Reimplementing that from scratch is ~2–4 weeks of reverse-engineering and breaks on every firmware update. Forking buys us that work; the maintenance cost gets shared with upstream.

### Mi Fitness coexistence

The band only trusts **one BLE client at a time** for the auth slot. Pairing with the companion means unpairing from Mi Fitness. This is a documented user-flow cost — the companion app's onboarding must spell it out. Users who insist on keeping Mi Fitness must stay on the option-1 path (HR + SpO₂ via Health Connect, no HRV).

## 4. Phases

### Phase 0 — Legal scoping (½ day)

- Confirm GPLv3 is acceptable for the companion APK.
- Add `LEGAL.md` documenting the IPC-as-boundary stance with citations (FSF FAQ).
- Decide companion license: **GPLv3 only**, no dual licensing.

### Phase 1 — Fork & strip (1 day)

- Fork `Freeyourgadget/Gadgetbridge` at the latest tagged release.
- Gut everything except: Mi Band 7 Pro device support, BLE manager, internal DB, settings shell.
- Rebrand:
  - package `ma.nsynergy.medisense.band`
  - icon + name "MediSense Band"
  - splash screen referencing MediSense AI
- **Exit:** APK builds, installs, pairs with the band, shows live HR — same UX as upstream.

### Phase 2 — Auth handoff (½ day)

- The user goes through the companion's in-app Mi Band pairing flow once.
- The auth key lives inside the companion's app-private storage. No manual extraction tools, no copy-paste keys.
- Document the **mandatory Mi Fitness unpair step** in the companion's onboarding screen.

### Phase 3 — HRV computation (1 day)

- Locate where Gadgetbridge surfaces **RR intervals** for the Mi Band 7 Pro:
  - `service/devices/huami/MiBand7PSupport.java` and the realtime activity-sample handler are the suspected entry points; the exact symbol may have moved upstream.
- Add `HrvComputer`:
  - Maintains a 60-second sliding buffer of RR intervals (ms).
  - Emits `RMSSD = sqrt(mean(diff(RR)^2))` once per minute.
  - Drops the window if fewer than 20 RR samples accumulated (avoids garbage values from intermittent BLE).
- Sanity check: cross-correlate against Mi Fitness's own stress score over the same window — they should trend together, not match exactly.

### Phase 4 — HTTP sink + JWT handoff (1 day)

- New `HttpIngestSink`:
  - Retrofit client targeting `${API_BASE_URL}/iot/ingest`.
  - WorkManager job, 5-min batch window, exponential backoff on 5xx, idempotent on the `(patient_uuid, ts)` unique constraint the backend already enforces.
- JWT delivery via ContentProvider:
  - Main MediSense app exposes `content://ma.nsynergy.medisense.ai.provider/token` returning the current access token.
  - Companion queries this provider on each batch. No token duplication; refreshes ride along with the main app.
- Configurable via the same `.env.development` URL the mobile app uses.

### Phase 5 — Backend prerequisite (½ day) — **independent, ship first**

- Make `BiometricReading.hrv` nullable. Migration on Alembic.
- `POST /iot/ingest`: drop a sample only if **hr OR spo2** is null; accept hrv-null samples.
- Accept `vendor='xiaomi'`, `source='gadgetbridge'` enum values on the (future) IotDevice columns.
- This is strictly broader behavior — also unblocks Apple Watch and generic BLE HRP bands. Ships independently of the spike outcome.

## 5. Exit criteria

Spike **succeeds** if all hold on the user's actual Mi Band 7 Pro:

| Criterion | Threshold |
|---|---|
| Continuous HR ingestion | ≥1 hour of samples, gaps < 60 s |
| RMSSD output | ≥10 plausible samples in that hour, values 15–80 ms at rest |
| Reconnect survival | Band power-cycle → companion reconnects ≤ 60 s |
| Main app regression | Dashboard renders the new `device_id` with vendor/source badge |

## 6. Kill criteria

Stop the spike and revert to **option 1 only** if any of:

- Gadgetbridge upstream auth no longer works against the current Mi Band 7 Pro firmware revision (means joining upstream's protocol-reverse effort — out of PFE scope).
- RR intervals turn out to not be exposed by the band's current firmware (HRV becomes unreachable via any direct-BLE approach; option 1 already covers HR + SpO₂).
- Mi Fitness coexistence becomes a hard requirement (users won't unpair) — Gadgetbridge can't share the auth slot, period.

## 7. Out of scope

- **iOS.** Apple blocks background BLE for non-MFi devices; the companion approach is Android-only by design.
- **Sleep / steps / temperature.** Schema is extensible but `BiometricReading` only stores HR/SpO₂/HRV today. Adding metrics is a separate sprint.
- **Play Store distribution.** Gadgetbridge isn't on Play (anti-modding policies). Companion ships via direct APK + F-Droid.
- **Multi-band fan-out.** One band per phone for v1.
- **Closed-source commercial distribution.** GPL companion is fine for the PFE / research scope; productizing under a commercial license needs separate legal work.

## 8. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Xiaomi firmware update breaks auth | Medium | High | Pin to a known-working firmware in docs; fast-follow upstream Gadgetbridge fixes |
| GPL contamination of main app | Low | Critical | IPC-only boundary, no shared modules, no shared build graph; documented in `LEGAL.md` |
| User refuses to unpair Mi Fitness | Medium | High | Fallback path = option 1 (HR + SpO₂ via Health Connect, no HRV) — already implemented |
| RMSSD values diverge from clinical HRV | Medium | Medium | Recommend Polar H10 in docs for clinically meaningful HRV; Mi Band HRV is wellness-grade only |
| iOS users left behind | High | Medium | Document upfront; recommend Apple Watch + HealthKit for those users |

## 9. Recommended sequence

1. **Today (Phase 5):** ship HRV-optional backend + mobile. Real Mi Band HR + SpO₂ flowing this afternoon. Unblocks demos and PFE evaluation independently of the spike.
2. **After PFE defense:** take this spike if the supervisor/jury values the HRV signal. 3-day spike, 2-week hardening if green.

## 10. Critical files (when the spike runs)

| Layer | Path | Change |
|---|---|---|
| Backend model | `backend/app/db/models/biometric_reading.py` | `hrv` nullable |
| Migration | `backend/alembic/versions/<new>.py` | Single nullable column change |
| Backend route | `backend/app/api/v1/endpoints/iot.py` | Drop sample only if `hr is None or spo2 is None` |
| Backend schema | `backend/app/schemas/iot.py` | `VitalSample.hrv` already optional — no change |
| Backend tests | `backend/tests/test_iot.py` | Add: hrv-null sample accepted (201); hr-null still dropped |
| Mobile sync | `frontend/mobile/lib/features/iot/domain/health_sync_service.dart` | Remove `lastHrv == null` gate; drop the 14-day HRV seed query (Mi Fitness never writes it) |
| Mobile UI | `frontend/mobile/lib/features/iot/presentation/pages/iot_dashboard_page.dart` | "—" / "indisponible" when HRV null |
| Companion (new) | `frontend/companion-band/` | Forked Gadgetbridge; Android Studio project (separate from `frontend/mobile/`) |
| Legal | `frontend/companion-band/LEGAL.md` | GPL boundary documentation |
