# Flutter wrapper
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }
-dontwarn io.flutter.embedding.**

# Firebase / messaging
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# Health Connect / androidx.health
-keep class androidx.health.** { *; }
-dontwarn androidx.health.**

# speech_to_text
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**

# Keep annotations used by reflection
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes Exceptions
