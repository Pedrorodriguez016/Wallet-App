class UserModel {
  final String email;
  final String name;
  final String keycloakUserId;
  final String? poblacion;

  UserModel({
    required this.email,
    required this.name,
    required this.keycloakUserId,
    this.poblacion,
  });

  factory UserModel.fromJson(Map<String, dynamic> json, {String? poblacion}) {
    return UserModel(
      email: (json['email'] ?? '').toString().trim(),
      name: (json['name'] ?? json['given_name'] ?? json['preferred_username'] ?? '').toString().trim(),
      keycloakUserId: (json['sub'] ?? '').toString().trim(),
      poblacion: poblacion?.trim(),
    );
  }

  UserModel copyWith({
    String? email,
    String? name,
    String? keycloakUserId,
    String? poblacion,
  }) {
    return UserModel(
      email: email ?? this.email,
      name: name ?? this.name,
      keycloakUserId: keycloakUserId ?? this.keycloakUserId,
      poblacion: poblacion ?? this.poblacion,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'email': email,
      'name': name,
      'sub': keycloakUserId,
      if (poblacion != null) 'poblacion': poblacion,
    };
  }
}
