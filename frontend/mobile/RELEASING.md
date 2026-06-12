# Releasing MediSense AI to Google Play

## Build a release bundle

```bash
cd frontend/mobile
./scripts/bump_version.sh build      # bump versionCode (required for every upload)
flutter build appbundle --release    # -> build/app/outputs/bundle/release/app-release.aab
```

Upload the `.aab` to Play Console (Internal testing track first, then promote to Production).

## Versioning

Play rejects any upload whose `versionCode` is not strictly greater than the last.
`scripts/bump_version.sh` always bumps the build number; pass a part to also bump the name:

| Command | 1.0.0+1 becomes | When |
|---|---|---|
| `bump_version.sh build` | `1.0.0+2` | re-upload, no user-facing change |
| `bump_version.sh patch` | `1.0.1+2` | bug-fix release |
| `bump_version.sh minor` | `1.1.0+2` | new features |
| `bump_version.sh major` | `2.0.0+2` | breaking redesign |

## Signing (already configured)

- Upload keystore lives **outside the repo**: `~/keystores/medisense-upload-keystore.jks`
- `android/key.properties` (git-ignored) holds the path + passwords; alias `upload`.
- `android/app/build.gradle.kts` reads `key.properties` and signs `release` builds with it,
  falling back to debug keys only when `key.properties` is absent.
- **Back up the `.jks` file and its password.** Losing them means you can never update the app.

## Code shrinking

R8 minify + resource shrinking are on for `release`. Keep rules are in
`android/app/proguard-rules.pro` (Flutter, Firebase, Health Connect, speech_to_text).
If a release build crashes with `ClassNotFoundException`, add a `-keep` rule there.

## ⚠️ Backend must be live before launch

The app's production config (`.env.production`) points to the live backend on
DigitalOcean App Platform:

    API_BASE_URL=https://medisense-ai-7li7x.ondigitalocean.app/api/v1

This host is reachable (`/api/v1/health` returns 200). See
`docs/deploy/digitalocean.md` for the backend deploy. If you later put the API
behind a custom domain (e.g. `api.medisense.ai`), update `.env.production` to
that URL, add it to the backend's `CORS_ORIGINS`, and rebuild.

Otherwise the app is non-functional on first launch and risks a Play policy rejection
("broken functionality").

## Dependency status

Safe within-constraint upgrades have been applied. The following have **major**
versions available — defer until after the first launch, upgrade one at a time with
testing (each has breaking changes):

- `flutter_riverpod` / `riverpod_annotation` 2.x → 3.x
- `go_router` 14 → 17
- `firebase_core` / `firebase_messaging` 3/15 → 4/16
- `fl_chart` 0.70 → 1.x
- `flutter_local_notifications` 18 → 21
- `flutter_secure_storage` 9 → 10
- `google_fonts` 6 → 8, `flutter_dotenv` 5 → 6, `intl` 0.19 → 0.20, `flutter_lints` 4 → 6
