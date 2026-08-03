class CredentialModel {
  final String id;
  final String type;
  final String name;
  final String? poblacion;
  final String? eventName;
  final String? companyName;
  final String addedOn;
  final Map<String, dynamic> raw;

  CredentialModel({
    required this.id,
    required this.type,
    required this.name,
    this.poblacion,
    this.eventName,
    this.companyName,
    required this.addedOn,
    required this.raw,
  });

  factory CredentialModel.fromJson(Map<String, dynamic> json) {
    // Traverse the nested document structure of walt.id credentials
    final Map<String, dynamic> doc = Map<String, dynamic>.from(
      json['parsedDocument'] ?? json,
    );
    final Map<String, dynamic> subject = Map<String, dynamic>.from(
      doc['credentialSubject'] ?? {},
    );

    String typeDisplay = "Credencial Comerç";
    final types = doc['type'] ?? doc['credentialData']?['type'];
    if (types is List && types.isNotEmpty) {
      typeDisplay = types.last.toString();
    }
    if (typeDisplay == "ComercioCredencial") {
      typeDisplay = "Credencial Comerç";
    }

    final String nameDisplay =
        (subject['name'] ??
                subject['fullName'] ??
                subject['firstName'] ??
                "Usuari Comerç")
            .toString();

    final String? poblacionDisplay = subject['poblacion']?.toString();
    final String? eventNameDisplay =
        (subject['eventName'] ?? subject['event_name'])?.toString();
    final String? companyNameDisplay =
        (subject['companyName'] ?? subject['company_name'])?.toString();

    final String idDisplay = (doc['id'] ?? json['id'] ?? "No ID").toString();
    final String addedOnDisplay = (json['addedOn'] ?? "").toString();

    return CredentialModel(
      id: idDisplay,
      type: typeDisplay,
      name: nameDisplay,
      poblacion: poblacionDisplay,
      eventName: eventNameDisplay,
      companyName: companyNameDisplay,
      addedOn: addedOnDisplay,
      raw: json,
    );
  }
}
