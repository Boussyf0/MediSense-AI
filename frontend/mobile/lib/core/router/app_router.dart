import 'package:go_router/go_router.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../api/dio_client.dart';
import '../../features/auth/presentation/pages/splash_page.dart';
import '../../features/auth/presentation/pages/onboarding_page.dart';
import '../../features/auth/presentation/pages/login_page.dart';
import '../../features/auth/presentation/pages/consent_page.dart';
import '../../features/chat/presentation/pages/chat_page.dart';
import '../../features/chat/presentation/pages/history_page.dart';
import '../../features/appointments/presentation/pages/appointments_page.dart';
import '../../features/appointments/presentation/pages/booking_page.dart';
import '../../features/appointments/presentation/pages/doctors_directory_page.dart';
import '../../features/appointments/data/models/doctor_model.dart';
import '../../features/iot/presentation/pages/iot_dashboard_page.dart';
import '../../features/profile/presentation/pages/profile_page.dart';
import '../../features/profile/presentation/pages/medication_reminders_page.dart';
import '../widgets/main_shell.dart';

const _storage = FlutterSecureStorage();

final appRouter = GoRouter(
  initialLocation: '/splash',
  refreshListenable: sessionExpiredNotifier,
  redirect: (context, state) async {
    final token = await _storage.read(key: 'access_token');
    final onboarded = await _storage.read(key: 'onboarded');
    final loc = state.matchedLocation;

    final isAuth = loc.startsWith('/splash') ||
        loc.startsWith('/onboarding') ||
        loc.startsWith('/login') ||
        loc.startsWith('/consent');

    if (token != null && isAuth && loc != '/consent') return '/home';
    if (token == null && !isAuth) {
      return onboarded != null ? '/login' : '/onboarding';
    }
    return null;
  },
  routes: [
    GoRoute(path: '/splash', builder: (_, __) => const SplashPage()),
    GoRoute(
        path: '/onboarding', builder: (_, __) => const OnboardingPage()),
    GoRoute(path: '/login', builder: (_, __) => const LoginPage()),
    GoRoute(path: '/consent', builder: (_, __) => const ConsentPage()),
    ShellRoute(
      builder: (context, state, child) => MainShell(child: child),
      routes: [
        GoRoute(
          path: '/home',
          builder: (_, __) => const ChatPage(),
          routes: [
            GoRoute(
              path: 'history',
              builder: (_, __) => const HistoryPage(),
            ),
          ],
        ),
        GoRoute(
          path: '/appointments',
          builder: (_, __) => const AppointmentsPage(),
          routes: [
            GoRoute(
              path: 'new',
              builder: (_, state) => BookingPage(
                preselectedDoctor: state.extra is DoctorModel
                    ? state.extra as DoctorModel
                    : null,
              ),
            ),
            GoRoute(
              path: 'doctors',
              builder: (_, __) => const DoctorsDirectoryPage(),
            ),
          ],
        ),
        GoRoute(path: '/iot', builder: (_, __) => const IotDashboardPage()),
        GoRoute(
          path: '/profile',
          builder: (_, __) => const ProfilePage(),
          routes: [
            GoRoute(
              path: 'reminders',
              builder: (_, __) => const MedicationRemindersPage(),
            ),
          ],
        ),
      ],
    ),
  ],
);
