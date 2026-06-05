import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:app_links/app_links.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/wallet_service.dart';

class WalletController with ChangeNotifier, WidgetsBindingObserver {
  final WalletService _walletService = WalletService();
  final _storage = const FlutterSecureStorage();
  late AppLinks _appLinks;

  // Estado
  bool _isLoading = false;
  List<dynamic> _credentials = [];
  bool _isAuthenticated = false;
  String _userToken = '';
  String _walletId = '';
  String _currentCallback = '';
  Uri? _pendingDeepLink;
  bool _startupDone = false;
  String _pendingOpenId4VP = '';
  String _poblacion = '';
  String _userName = '';
  String _userEmail = '';
  String _keycloakUserId = '';

  // Getters
  bool get isLoading => _isLoading;
  List<dynamic> get credentials => _credentials;
  bool get isAuthenticated => _isAuthenticated;
  String get userToken => _userToken;
  String get walletId => _walletId;
  String get currentCallback => _currentCallback;
  String get pendingOpenId4VP => _pendingOpenId4VP;
  String get poblacion => _poblacion;
  String get userName => _userName;
  String get userEmail => _userEmail;
  String get keycloakUserId => _keycloakUserId;

  WalletController() {
    WidgetsBinding.instance.addObserver(this);
    _initDeepLinks();
    _startup();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _pendingDeepLink != null) {
      Uri uri = _pendingDeepLink!;
      _pendingDeepLink = null;
      Future.delayed(const Duration(milliseconds: 600), () {
        processDeepLink(uri);
      });
    }
  }

  // ── Arranque ────────────────────────────────────────────────

  Future<void> _startup() async {
    String? token = await _storage.read(key: 'wallet_token');
    if (token != null) {
      String? wid = await _walletService.getDefaultWallet(token);
      if (wid != null) {
        _userToken = token;
        _isAuthenticated = true;
        _walletId = wid;

        // Read user info from local storage
        _userEmail = await _storage.read(key: 'wallet_user_email') ?? '';
        _userName = await _storage.read(key: 'wallet_user_name') ?? '';
        _keycloakUserId = await _storage.read(key: 'wallet_user_keycloak_id') ?? '';

        // If info is missing, fetch and save it
        if (_userEmail.isEmpty || _userName.isEmpty || _keycloakUserId.isEmpty) {
          await _fetchAndSaveUserInfo(token);
        }

        if (_userEmail.isNotEmpty) {
          await syncLocationSettings(_walletId, _userToken, _userEmail);
        }

        await loadCredentials();
      } else {
        await _storage.delete(key: 'wallet_token');
      }
    }

    _startupDone = true;

    // Procesar enlace pendiente si lo hay
    if (_pendingDeepLink != null) {
      processDeepLink(_pendingDeepLink!);
    }

    notifyListeners();
  }

  Future<void> _fetchAndSaveUserInfo(String token) async {
    try {
      final userInfo = await _walletService.getUserInfo(token);
      if (userInfo != null) {
        String? email = userInfo['email'];
        String? name = userInfo['name'] ?? userInfo['given_name'] ?? userInfo['preferred_username'];
        String? keycloakUid = userInfo['sub'];

        if (email != null) {
          await _storage.write(key: 'wallet_user_email', value: email);
          _userEmail = email;
        }
        if (name != null) {
          await _storage.write(key: 'wallet_user_name', value: name);
          _userName = name;
        }
        if (keycloakUid != null) {
          await _storage.write(key: 'wallet_user_keycloak_id', value: keycloakUid);
          _keycloakUserId = keycloakUid;
        }
        notifyListeners();
      }
    } catch (e) {
      print("Error fetching/saving user info: $e");
    }
  }

  // ── Deep Links ──────────────────────────────────────────────

  void _initDeepLinks() {
    _appLinks = AppLinks();

    _appLinks.getInitialLink().then((uri) {
      if (uri != null) {
        print("COLD START LINK: $uri");
        _pendingDeepLink = uri;
        if (_startupDone) processDeepLink(uri);
      }
    });

    _appLinks.uriLinkStream.listen((uri) {
      print("STREAM LINK: $uri");
      if (uri.scheme == 'wallet' &&
          (uri.host == 'verify' || uri.host == 'presentation')) {
        if (_startupDone) {
          processDeepLink(uri);
        } else {
          _pendingDeepLink = uri;
        }
      }
    });
  }

  void processDeepLink(Uri uri) {
    print("PROCESANDO DEEP LINK: $uri");
    String? callback = uri.queryParameters['callback'];
    if (callback != null) {
      _currentCallback = callback;
    }

    _pendingOpenId4VP = uri.queryParameters['uri'] ?? uri.toString();
    _pendingDeepLink = null;
    notifyListeners();
  }

  void clearPendingOpenId4VP() {
    _pendingOpenId4VP = '';
    notifyListeners();
  }

  // ── Acciones ────────────────────────────────────────────────

  Future<void> syncLocationSettings(String walletId, String token, String email) async {
    try {
      final key = 'temp_poblacion_${email.trim().toLowerCase()}';
      final tempPoblacion = await _storage.read(key: key);

      if (tempPoblacion != null && tempPoblacion.isNotEmpty) {
        bool success = await _walletService.updateWalletSettings(walletId, token, {
          'poblacion': tempPoblacion,
        });
        if (success) {
          _poblacion = tempPoblacion;
          await _storage.delete(key: key);
        }
      } else {
        final settingsResponse = await _walletService.getWalletSettings(walletId, token);
        if (settingsResponse != null && settingsResponse['settings'] != null) {
          final settingsMap = settingsResponse['settings'];
          if (settingsMap is Map && settingsMap['poblacion'] != null) {
            _poblacion = settingsMap['poblacion'].toString();
          }
        }
      }
    } catch (e) {
      print("Error syncing location settings: $e");
    }
  }

  Future<bool> login(String email, String password) async {
    _isLoading = true;
    notifyListeners();

    String? token = await _walletService.login(email, password);
    if (token != null) {
      await _storage.write(key: 'wallet_token', value: token);
      await _storage.write(key: 'wallet_user_email', value: email);
      _userToken = token;
      _userEmail = email;
      _isAuthenticated = true;

      // Fetch and save full user info (name, Keycloak ID)
      await _fetchAndSaveUserInfo(token);

      String? wid = await _walletService.getDefaultWallet(token);
      if (wid != null) {
        _walletId = wid;
        await syncLocationSettings(wid, token, email);
        await loadCredentials();
      }
      _isLoading = false;
      notifyListeners();
      return true;
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  Future<bool> register(String name, String email, String password, {String poblacion = ''}) async {
    _isLoading = true;
    notifyListeners();
    bool success = await _walletService.register(name, email, password, poblacion: poblacion);
    if (success && poblacion.isNotEmpty) {
      await _storage.write(key: 'temp_poblacion_${email.trim().toLowerCase()}', value: poblacion);
    }
    _isLoading = false;
    notifyListeners();
    return success;
  }

  Future<void> loadCredentials() async {
    if (_userToken.isEmpty || _walletId.isEmpty) return;
    _isLoading = true;
    notifyListeners();

    try {
      final List<dynamic> creds = await _walletService.getCredentials(
        _walletId,
        _userToken,
      );
      creds.sort((a, b) => (b['addedOn'] ?? "").compareTo(a['addedOn'] ?? ""));
      _credentials = creds;
    } catch (e) {
      print("Error loading credentials: $e");
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> handlePresentation(String openid4vp) async {
    try {
      _isLoading = true;
      notifyListeners();

      List<String> credentialIds = _credentials
          .map<String>((c) => c['id']?.toString() ?? '')
          .where((id) => id.isNotEmpty)
          .toList();

      bool success = await _walletService.presentCredential(
        _walletId,
        openid4vp,
        _userToken,
        credentialIds,
      );

      if (success && _currentCallback.isNotEmpty) {
        final Uri callbackUri = Uri.parse(_currentCallback);
        if (await canLaunchUrl(callbackUri)) {
          await launchUrl(
            callbackUri,
            mode: LaunchMode.externalNonBrowserApplication,
          );
          _currentCallback = '';
        }
      }

      _isLoading = false;
      notifyListeners();
      return success;
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> requestNewCredential() async {
    if (_walletId.isEmpty || _userToken.isEmpty) return false;
    _isLoading = true;
    notifyListeners();

    if (_poblacion.isEmpty) {
      String? email = await _storage.read(key: 'wallet_user_email');
      if (email != null) {
        await syncLocationSettings(_walletId, _userToken, email);
      }
    }

    bool success = await _walletService.requestCredential(
      _walletId,
      _userToken,
      poblacion: _poblacion,
    );
    if (success) await loadCredentials();
    _isLoading = false;
    notifyListeners();
    return success;
  }

  Future<void> logout() async {
    await _storage.delete(key: 'wallet_token');
    await _storage.delete(key: 'wallet_user_email');
    await _storage.delete(key: 'wallet_user_name');
    await _storage.delete(key: 'wallet_user_keycloak_id');
    _isAuthenticated = false;
    _userToken = '';
    _credentials = [];
    _walletId = '';
    _poblacion = '';
    _userName = '';
    _userEmail = '';
    _keycloakUserId = '';
    notifyListeners();
  }
}
