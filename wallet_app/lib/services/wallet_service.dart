import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../models/user.dart';
import '../models/credential.dart';

class WalletService {
  final Dio _dio = Dio(
    BaseOptions(
      baseUrl: (dotenv.env['API_URL'] ?? 'http://localhost:7001/wallet-api')
          .trim(),
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );

  // --- AUTENTICACIÓN (vía Keycloak) ---

  /// Obtiene un token de admin de Keycloak a través de walt.id
  Future<String?> _getKeycloakAdminToken() async {
    try {
      final response = await _dio.get('/auth/keycloak/token');
      // El endpoint devuelve directamente el token como string
      if (response.data is String) {
        return response.data;
      }
      return response.data['access_token'];
    } catch (e) {
      print('Error obteniendo admin token de Keycloak: $e');
      return null;
    }
  }

  /// Login vía Keycloak: walt.id valida contra Keycloak y
  /// crea/vincula la cuenta en la tabla 'accounts' automáticamente
  Future<String?> login(String email, String password) async {
    try {
      final response = await _dio.post(
        '/auth/keycloak/login',
        data: {
          'type': 'keycloak',
          'username': email.trim(),
          'password': password.trim(),
        },
      );
      return response.data['token'];
    } catch (e) {
      print('Error en login service (keycloak): $e');
      return null;
    }
  }

  /// Registro: crea el usuario y emite/guarda la credencial ComercioCredencial en el backend
  Future<bool> register(String name, String email, String password, {String poblacion = 'Barcelona'}) async {
    try {
      final response = await _dio.post(
        '/auth/register',
        data: {
          'name': name.trim(),
          'email': email.trim(),
          'password': password.trim(),
          'poblacion': poblacion.trim().isNotEmpty ? poblacion.trim() : 'Barcelona',
        },
      );
      return response.statusCode == 201 || response.statusCode == 200;
    } catch (e) {
      print('Error en registro service (backend): $e');
      return false;
    }
  }

  Future<UserModel?> getUserInfo(String token) async {
    try {
      final response = await _dio.get(
        '/auth/user-info',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      if (response.data != null) {
        return UserModel.fromJson(Map<String, dynamic>.from(response.data));
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  Future<String?> getDefaultWallet(String token) async {
    try {
      final response = await _dio.get(
        '/wallet/accounts/wallets',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      if (response.data is List && response.data.isNotEmpty) {
        return response.data[0]['id'];
      } else if (response.data is Map && response.data['wallets'] != null) {
        final wallets = response.data['wallets'] as List;
        if (wallets.isNotEmpty) {
          return wallets[0]['id'];
        }
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  Future<List<CredentialModel>> getCredentials(String walletId, String token) async {
    try {
      final response = await _dio.get(
        '/wallet/$walletId/credentials',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      if (response.data is List) {
        return (response.data as List)
            .map((c) => CredentialModel.fromJson(Map<String, dynamic>.from(c)))
            .toList();
      }
      return [];
    } catch (e) {
      return [];
    }
  }

  Future<bool> requestCredential(String walletId, String token, {String poblacion = ''}) async {
    try {
      // 1. DID
      final didsResponse = await _dio.get(
        '/wallet/$walletId/dids',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      String userDid;
      if (didsResponse.data is List && didsResponse.data.isNotEmpty) {
        userDid = didsResponse.data[0]['did'];
      } else {
        final newDid = await _dio.post(
          '/wallet/$walletId/dids/create/key',
          options: Options(headers: {'Authorization': 'Bearer $token'}),
        );
        userDid = newDid.data;
      }

      // 2. User Info
      final userInfo = await getUserInfo(token);
      final String userEmail = userInfo?.email ?? "usuari@comercio.local";
      final String userName = userInfo?.name ?? "Usuari Comerç";

      // 3. Issue Offer via our new Backend
      final offerResponse = await _dio.post(
        '/credentials/offer',
        data: {
          "credential_type": "ComercioCredencial",
          "user_claims": {
            "id": userDid,
            "name": userName,
            "email": userEmail,
            "poblacion": poblacion.isNotEmpty ? poblacion : "Barcelona",
          }
        },
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      final String offerUri = offerResponse.data['offer_url'];

      // 4. Use Offer
      final claimResponse = await _dio.post(
        '/wallet/$walletId/exchange/useOfferRequest',
        data: offerUri,
        options: Options(
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'text/plain',
          },
        ),
      );

      return claimResponse.statusCode == 200 || claimResponse.statusCode == 201;
    } catch (e) {
      print('Error en requestCredential service: $e');
      return false;
    }
  }

  Future<bool> presentCredential(
    String walletId,
    String openid4vpUri,
    String token,
    List<String> credentialIds,
  ) async {
    try {
      final response = await _dio.post(
        '/wallet/$walletId/exchange/usePresentationRequest',
        data: {
          "presentationRequest": openid4vpUri,
          "selectedCredentials": credentialIds,
        },
        options: Options(
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'application/json',
          },
        ),
      );
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<Map<String, dynamic>?> getWalletSettings(String walletId, String token) async {
    try {
      final response = await _dio.get(
        '/wallet/$walletId/settings',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return response.data;
    } catch (e) {
      print('Error en getWalletSettings: $e');
      return null;
    }
  }

  Future<bool> updateWalletSettings(String walletId, String token, Map<String, dynamic> settings) async {
    try {
      final response = await _dio.post(
        '/wallet/$walletId/settings',
        data: settings,
        options: Options(
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'application/json',
          },
        ),
      );
      return response.statusCode == 200 || response.statusCode == 201 || response.statusCode == 202;
    } catch (e) {
      print('Error en updateWalletSettings: $e');
      return false;
    }
  }
}
