import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'screens/splash_screen.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/verify_identity_screen.dart';
import 'theme/app_theme.dart';
import 'controllers/wallet_controller.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: ".env");
  
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => WalletController()),
      ],
      child: const WalletApp(),
    ),
  );
}

class WalletApp extends StatelessWidget {
  const WalletApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'El meu Wallet Digital',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: const RootWrapper(),
      routes: {
        '/login': (context) => LoginScreen(),
        '/home': (context) => HomeScreen(),
        '/register': (context) => RegisterScreen(),
        '/verify': (context) => const VerifyIdentityScreen(),
      },
    );
  }
}

class RootWrapper extends StatefulWidget {
  const RootWrapper({super.key});

  @override
  State<RootWrapper> createState() => _RootWrapperState();
}

class _RootWrapperState extends State<RootWrapper> {
  @override
  void initState() {
    super.didChangeDependencies();
  }

  @override
  Widget build(BuildContext context) {
    final wallet = context.watch<WalletController>();
    print("ROOT_WRAPPER: Auth=${wallet.isAuthenticated}, Loading=${wallet.isLoading}, Pending=${wallet.pendingOpenId4VP.isNotEmpty}");

    // 1. Si está cargando y no tenemos token, mostramos Splash
    if (!wallet.isAuthenticated && wallet.isLoading) {
      return const SplashScreen();
    }

    // 2. Si no está autenticado, mostramos Login
    if (!wallet.isAuthenticated) {
      return LoginScreen();
    }

    // 3. Si hay un deep link pendiente (SSI), navegamos a Verify
    if (wallet.pendingOpenId4VP.isNotEmpty) {
      print("ROOT_WRAPPER: Detectado enlace SSI, preparando navegación...");
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (wallet.pendingOpenId4VP.isNotEmpty) {
          String uri = wallet.pendingOpenId4VP;
          print("ROOT_WRAPPER: Navegando a /verify con URI: $uri");
          wallet.clearPendingOpenId4VP();
          Navigator.of(context).pushNamed('/verify', arguments: {'openid4vp': uri});
        }
      });
    }

    // 4. Por defecto, si está autenticado, mostramos Home
    return HomeScreen();
  }
}
