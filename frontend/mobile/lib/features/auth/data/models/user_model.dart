class UserModel {
  final String uuid;
  final String email;
  final String role;
  final String? firstName;
  final String? lastName;
  final bool? consentIot;
  final bool? consentNlp;
  final bool? consentSharing;

  const UserModel({
    required this.uuid,
    required this.email,
    required this.role,
    this.firstName,
    this.lastName,
    this.consentIot,
    this.consentNlp,
    this.consentSharing,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) => UserModel(
        uuid: (json['user_uuid'] ?? json['uuid']) as String,
        email: json['email'] as String,
        role: json['role'] as String,
        firstName: json['first_name'] as String?,
        lastName: json['last_name'] as String?,
        consentIot: json['consent_iot'] as bool?,
        consentNlp: json['consent_nlp'] as bool?,
        consentSharing: json['consent_sharing'] as bool?,
      );
}
