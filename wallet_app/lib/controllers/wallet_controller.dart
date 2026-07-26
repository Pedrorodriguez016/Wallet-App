import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:app_links/app_links.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/wallet_service.dart';
import '../models/user.dart';
import '../models/credential.dart';

class WalletController with ChangeNotifier, WidgetsBindingObserver {
  final WalletService _walletService = WalletService();
  final _storage = const FlutterSecureStorage();
  late AppLinks _appLinks;

  // Estado
  bool _isLoading = false;
  List<CredentialModel> _credentials = [];
  bool _isAuthenticated = false;
  String _userToken = '';
  String _walletId = '';
  String _currentCallback = '';
  Uri? _pendingDeepLink;
  bool _startupDone = false;
  String _pendingOpenId4VP = '';
  UserModel? _user;
  String _userDid = '';

  // Getters
  bool get isLoading => _isLoading;
  List<CredentialModel> get credentials => _credentials;
  bool get isAuthenticated => _isAuthenticated;
  String get userToken => _userToken;
  String get walletId => _walletId;
  String get currentCallback => _currentCallback;
  String get pendingOpenId4VP => _pendingOpenId4VP;
  UserModel? get user => _user;
  String get userDid => _userDid;
  String get poblacion => _user?.poblacion ?? '';
  String get userName => _user?.name ?? '';
  String get userEmail => _user?.email ?? '';
  String get keycloakUserId => _user?.keycloakUserId ?? '';

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
        String email = await _storage.read(key: 'wallet_user_email') ?? '';
        String name = await _storage.read(key: 'wallet_user_name') ?? '';
        String keycloakUid = await _storage.read(key: 'wallet_user_keycloak_id') ?? '';
        String? p = await _storage.read(key: 'wallet_user_poblacion');

        if (email.isNotEmpty || name.isNotEmpty || keycloakUid.isNotEmpty) {
          _user = UserModel(
            email: email,
            name: name,
            keycloakUserId: keycloakUid,
            poblacion: p,
          );
        }

        // If info is missing, fetch and save it
        if (_user == null || _user!.email.isEmpty || _user!.name.isEmpty || _user!.keycloakUserId.isEmpty) {
          await _fetchAndSaveUserInfo(token);
        }

        if (_user != null && _user!.email.isNotEmpty) {
          await syncLocationSettings(_walletId, _userToken, _user!.email);
        }

        await loadUserDid();
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
        await _storage.write(key: 'wallet_user_email', value: userInfo.email);
        await _storage.write(key: 'wallet_user_name', value: userInfo.name);
        await _storage.write(key: 'wallet_user_keycloak_id', value: userInfo.keycloakUserId);
        if (userInfo.poblacion != null) {
          await _storage.write(key: 'wallet_user_poblacion', value: userInfo.poblacion!);
        }

        _user = userInfo;
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
          if (_user != null) {
            _user = _user!.copyWith(poblacion: tempPoblacion);
            await _storage.write(key: 'wallet_user_poblacion', value: tempPoblacion);
          }
          await _storage.delete(key: key);
        }
      } else {
        final settingsResponse = await _walletService.getWalletSettings(walletId, token);
        if (settingsResponse != null && settingsResponse['settings'] != null) {
          final settingsMap = settingsResponse['settings'];
          if (settingsMap is Map && settingsMap['poblacion'] != null) {
            final String p = settingsMap['poblacion'].toString();
            if (_user != null) {
              _user = _user!.copyWith(poblacion: p);
              await _storage.write(key: 'wallet_user_poblacion', value: p);
            }
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
      _isAuthenticated = true;

      // Fetch and save full user info (name, Keycloak ID)
      await _fetchAndSaveUserInfo(token);

      String? wid = await _walletService.getDefaultWallet(token);
      if (wid != null) {
        _walletId = wid;
        if (_user != null) {
          await syncLocationSettings(wid, token, _user!.email);
        }
        await loadUserDid();
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
      final List<CredentialModel> creds = await _walletService.getCredentials(
        _walletId,
        _userToken,
      );
      creds.sort((a, b) => b.addedOn.compareTo(a.addedOn));
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
          .map<String>((c) => c.id)
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

    if (_user?.poblacion == null || _user!.poblacion!.isEmpty) {
      String? email = await _storage.read(key: 'wallet_user_email');
      if (email != null) {
        await syncLocationSettings(_walletId, _userToken, email);
      }
    }

    bool success = await _walletService.requestCredential(
      _walletId,
      _userToken,
      poblacion: poblacion,
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
    await _storage.delete(key: 'wallet_user_poblacion');
    _isAuthenticated = false;
    _userToken = '';
    _credentials = [];
    _walletId = '';
    _user = null;
    _userDid = '';
    notifyListeners();
  }

  Future<void> loadUserDid() async {
    if (_walletId.isEmpty || _userToken.isEmpty) return;
    try {
      final did = await _walletService.getUserDid(_walletId, _userToken);
      if (did != null) {
        _userDid = did;
        notifyListeners();
      }
    } catch (e) {
      print("Error loading user DID: $e");
    }
  }

  Future<bool> updatePoblacion(String nuevaPoblacion) async {
    if (_walletId.isEmpty || _userToken.isEmpty) return false;
    _isLoading = true;
    notifyListeners();

    try {
      bool success = await _walletService.updateWalletSettings(_walletId, _userToken, {
        'poblacion': nuevaPoblacion,
      });
      if (success) {
        if (_user != null) {
          _user = _user!.copyWith(poblacion: nuevaPoblacion);
          await _storage.write(key: 'wallet_user_poblacion', value: nuevaPoblacion);
        }
        await loadCredentials();
        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e) {
      print("Error updating location: $e");
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }
}
